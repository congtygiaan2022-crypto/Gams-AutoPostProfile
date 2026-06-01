from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import os
import re
import random

class FacebookAutomator:
    def __init__(self, debugger_address, driver_path=None, strategies=None):
        import requests
        import socket
        self.strategies = strategies or {}
        self.driver = None
        
        host, port = debugger_address.split(':')
        
        # 1. Ultimate Initialization (Hardened for Proxy US & Slow GPM)
        print(f"[Automator] Waiting for browser at {debugger_address}...")
        
        # Phase A: Wait for port to be open at socket level
        port_num = int(port)
        for attempt in range(15):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex((host, port_num)) == 0:
                    print(f"[Automator] Port {port} is listening.")
                    break
            time.sleep(1)
            
        # Phase B: Wait for 'page' target via CDP
        page_found = False
        for attempt in range(60):
            try:
                # Use longer timeout for slow systems
                resp = requests.get(f"http://{host}:{port}/json", timeout=10)
                if resp.status_code == 200:
                    targets = resp.json()
                    # Check if any target is a physical 'page'
                    if any(t.get('type') == 'page' for t in targets):
                        print(f"[Automator] Found active page target after {attempt + 1} attempts.")
                        page_found = True
                        break
                
                # Force-Tab Protocol: if still no page after 5 attempts, try to force one
                if attempt >= 5 and attempt % 10 == 0:
                    print(f"[Automator] Forcing a new tab via /json/new (PUT)...")
                    try:
                        requests.put(f"http://{host}:{port}/json/new", timeout=5)
                    except: pass
            except Exception as e:
                if attempt % 10 == 0:
                    print(f"[Automator] CDP Heartbeat {attempt}/60... ({e})")
            
            time.sleep(1)
            
        if not page_found:
            # Last ditch effort: try to connect anyway, maybe Selenium is smarter
            print("[Automator] Final attempt to connect blindly...")
            
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", debugger_address)
        
        last_err = None
        for attempt in range(5):
            try:
                if driver_path and os.path.exists(driver_path):
                    service = Service(executable_path=driver_path)
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                else:
                    self.driver = webdriver.Chrome(options=chrome_options)
                
                self.driver.set_page_load_timeout(300) 
                self.driver.set_script_timeout(120)
                self.driver.implicitly_wait(10) # 10s wait for slow proxies
                
                print(f"[Automator] Connected to browser on {debugger_address}")
                return
            except Exception as e:
                last_err = e
                print(f"[Automator] Connection attempt {attempt + 1}/5 failed: {e}")
                if "discovering" in str(e).lower() and attempt < 4:
                    print("[Automator] Retrying after forcing new tab...")
                    try: requests.get(f"http://{host}:{port}/json/new", timeout=5)
                    except: pass
                time.sleep(5)
        
        if not self.driver:
            raise last_err

    def _switch_to_best_tab(self):
        """Chuyển sang tab tốt nhất: ưu tiên facebook.com, fallback bất kỳ tab không phải extension."""
        try:
            handles = self.driver.window_handles
            if len(handles) <= 1:
                return  # Only one tab, nothing to switch
            
            # Priority 1: any facebook tab
            for h in handles:
                try:
                    self.driver.switch_to.window(h)
                    url = self.driver.current_url.lower()
                    if "facebook.com" in url:
                        print(f"[Automator] Switched to facebook tab: {url[:60]}")
                        return
                except: pass
            
            # Priority 2: any non-extension navigable tab (new-tab-page, blank, etc.)
            for h in handles:
                try:
                    self.driver.switch_to.window(h)
                    url = self.driver.current_url.lower()
                    if not url.startswith("chrome-extension://"):
                        print(f"[Automator] Switched to navigable tab: {url[:60]}")
                        return
                except: pass
            
            # Fallback: switch to first handle
            self.driver.switch_to.window(handles[0])
            print(f"[Automator] Switched to first tab: {self.driver.current_url[:60]}")
        except Exception as e:
            print(f"[Automator] Tab switch warning: {e}")

    def resolve_asset_id(self, nick_link):
        # Try to find asset_id in URL without navigation first
        asset_id = None
        if "asset_id=" in nick_link:
            asset_id = nick_link.split("asset_id=")[-1].split("&")[0]
        
        # If it's a direct page ID in URL
        if not asset_id:
            parts = nick_link.strip("/").split("/")
            if parts[-1].isdigit():
                asset_id = parts[-1]
            
        # Must navigate to resolve or confirm
        self.log(f"Navigating to resolve IDs: {nick_link}")
        self._safe_get(nick_link)
        time.sleep(3)
        
        if "asset_id=" in self.driver.current_url:
            asset_id = self.driver.current_url.split("asset_id=")[-1].split("&")[0]
            
        if not asset_id:
            # Look for actorID in page source - common for personal profiles in professional mode
            match = re.search(r'"actorID":"(\d+)"', self.driver.page_source)
            if match: 
                asset_id = match.group(1)
                self.log(f"Resolved asset_id from actorID: {asset_id}")
            
        if not asset_id:
            # Fallback to userID from cookies if nothing else works
            try:
                c = self.driver.get_cookie("c_user")
                if c: 
                    asset_id = c['value']
                    self.log(f"Resolved asset_id from c_user cookie: {asset_id}")
            except: pass

        if not asset_id:
            # Last ditch effort: any large digit in page source that looks like a Profile ID
            import re
            match = re.search(r'fb://profile/(\d+)', self.driver.page_source)
            if match: asset_id = match.group(1)
            
        # Also resolve business_id while we are here
        self.business_id = "" 
        if "business_id=" in self.driver.current_url:
            self.business_id = self.driver.current_url.split("business_id=")[-1].split("&")[0]
        else:
             match_biz = re.search(r'"businessID":"(\d+)"', self.driver.page_source)
             if match_biz: self.business_id = match_biz.group(1)

        return asset_id

    def upload_reel_by_link(self, nick_link, video_path, title, scrape_name=False, use_personal=False):
        """
        Router: chon flow upload phu hop.
        use_personal=True  -> facebook.com/reels/create (Nick ca nhan)
        use_personal=False -> business.facebook.com bulk composer (fanpage)
        """
        if use_personal:
            # Nick ca nhan: khong can asset_id, dang tung video 1
            if isinstance(video_path, list):
                results = []
                for vp, t in video_path:
                    results.append(self.upload_reel_personal(vp, t))
                return results
            else:
                return self.upload_reel_personal(video_path, title)

        # Fanpage flow (giu nguyen logic cu)
        asset_id = self.resolve_asset_id(nick_link)
        if not asset_id:
            raise Exception("Could not find Asset ID for this page link.")
        batch = video_path if isinstance(video_path, list) else [(video_path, title)]
        return self.upload_reels_bulk(asset_id, batch)


    def log(self, msg):
        print(f"[Automator] {msg}")

    def set_timeout(self):
        try:
            self.driver.set_page_load_timeout(300)
        except:
            pass

    def _wait_for_element(self, xpaths, timeout=30, interval=1.0):
        """Poll DOM until any of the given xpath selectors appears. Returns (True, element) or (False, None)."""
        if isinstance(xpaths, str):
            xpaths = [xpaths]
        start = time.time()
        self.driver.implicitly_wait(0)
        try:
            while time.time() - start < timeout:
                for xp in xpaths:
                    try:
                        els = self.driver.find_elements(By.XPATH, xp)
                        if els and els[0].is_displayed():
                            return True, els[0]
                    except: pass
                time.sleep(interval)
        finally:
            self.driver.implicitly_wait(2)
        return False, None

    def _wait_for_text_in_page(self, keywords, timeout=60, interval=1.0):
        """Poll page source until any keyword appears. Returns True immediately when found."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                src = self.driver.page_source.lower()
                if any(k.lower() in src for k in keywords):
                    return True
            except: pass
            time.sleep(interval)
        return False

    def upload_reels_bulk(self, asset_id, batch_list):
        """
        batch_list: List of (video_path, title)
        """
        self.set_timeout()
        upload_url = f"https://business.facebook.com/latest/bulk_upload_composer?asset_id={asset_id}"
        
        # 0. Skip redundant navigation if already there
        if upload_url.lower() not in self.driver.current_url.lower():
            self.log(f"[BULK] Navigating to: {upload_url}")
            self._safe_get(upload_url)
        else:
            self.log(f"[BULK] Already at composer URL: {upload_url}. Skipping reload.")

        # Handle "Select Page" or "Get Started" screen if needed
        self._dismiss_tooltips()
        
        # Event-driven: wait for page to show the upload UI (Add videos button or file input)
        # Increased timeout to 30s for slow profiles
        ready, _ = self._wait_for_element([
            "//div[@role='button'][contains(., 'Add videos') or contains(., 'Thêm video') or @aria-label='Add videos' or @aria-label='Thêm video']",
            "//div[@role='button'][contains(., 'Select Page') or contains(., 'Chá»n trang')]",
            "//input[@type='file']"
        ], timeout=30)
        
        if not ready:
            self.log("[BULK] Warning: Upload page did not load expected UI in 30s, proceeding anyway.")
        
        # 1. TÃ¬m input vÃ  táº£i video lÃªn
        paths = [os.path.abspath(v[0]) for v in batch_list]
        
        try:
            # 1. Báº¥m nÃºt "Add videos" Ä‘á»ƒ kÃ­ch hoáº¡t input file áº©n (Meta logic)
            self.log("[BULK] Clicking 'Add videos' button to trigger input injection...")
            add_btn_selectors = [
                "//div[@role='button'][contains(., 'Add videos') or contains(., 'Thêm video') or @aria-label='Add videos' or @aria-label='Thêm video']",
                "//div[@role='button']//span[contains(text(), 'Add videos') or contains(text(), 'Thêm video')]",
                "//div[@role='button'][@aria-label='Add videos' or @aria-label='Thêm video']",
                "//div[@role='button'][contains(., 'Select Page') or contains(., 'Chá»n trang')]" # Handle intermediary page selection
            ]
            
            btn_clicked = False
            for sel in add_btn_selectors:
                try:
                    btns = self.driver.find_elements(By.XPATH, sel)
                    for b in btns:
                        if b.is_displayed():
                            self.driver.execute_script("arguments[0].click();", b)
                            self.log(f"[BULK] Clicked button via selector: {sel}")
                            btn_clicked = True
                            break
                    if btn_clicked: break
                except: continue
            
            if not btn_clicked:
                self.log("[BULK] Warning: Could not find 'Add videos' button via selectors, will search for naked input.")
            
            time.sleep(5) # Äá»£i input xuáº¥t hiá»‡n hoáº·c chuyá»ƒn trang

            # 2. TÃ¬m input file
            input_file = None
            for _ in range(2): # Try twice, second time with frame search
                inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
                self.log(f"[BULK] Found {len(inputs)} file inputs in current context.")
                
                # Chá»n input phÃ¹ há»£p nháº¥t
                for inp in inputs:
                    mult = inp.get_attribute("multiple") or ""
                    acc = (inp.get_attribute("accept") or "").lower()
                    if mult == "true" or "video" in acc or acc == "" or acc == "*":
                        input_file = inp
                        break
                
                if input_file: break
                
                # If not found in current context, try searching in frames
                self.log("[BULK] Input not found in main context, searching in iframes...")
                if self._switch_to_composer_frame_recursive():
                    continue # Re-run find_elements in new context
                else:
                    self.driver.switch_to.default_content()
                    break

            if not input_file and inputs: input_file = inputs[0]
            if not input_file:
                # Capture a screenshot or log more DOM info here if needed
                self.log("[BULK] CRITICAL: No file input found after all attempts.")
                raise Exception("KhÃ´ng tÃ¬m tháº¥y input file ngay cáº£ sau khi báº¥m nÃºt.")

            # 3. Gá»­i file
            text_paths = "\n".join(paths)
            
            # Ã‰p hiá»‡n á»•n Ä‘á»‹nh trÆ°á»›c khi send_keys
            self.driver.execute_script("""
                arguments[0].style.display = 'block'; 
                arguments[0].style.visibility = 'visible'; 
                arguments[0].style.opacity = '1'; 
                arguments[0].style.position = 'absolute';
                arguments[0].style.top = '0';
                arguments[0].style.left = '0';
                arguments[0].style.width = '100px'; 
                arguments[0].style.height = '100px';
            """, input_file)
            time.sleep(2)
            
            # Reset input
            self.driver.execute_script("arguments[0].value = '';", input_file)
            
            input_file.send_keys(text_paths)
            self.log(f"[BULK] Sent {len(paths)} files to input.")
            
            # 4. KÃ­ch hoáº¡t React báº±ng chuá»—i sá»± kiá»‡n má»Ÿ rá»™ng
            js_script = """
            var input = arguments[0];
            var files = input.files;
            if (files.length > 0) {
                // Thá»© tá»± sá»± kiá»‡n quan trá»ng cho React
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                
                // Giáº£ láº­p thÃªm sá»± kiá»‡n drop vÃ o vÃ¹ng chá»©a cha
                var dropzone = input.parentElement;
                while (dropzone && !dropzone.innerText.includes('Add videos')) {
                    dropzone = dropzone.parentElement;
                }
                dropzone = dropzone || input.parentElement;

                var dataTransfer = new DataTransfer();
                for(var i=0; i<files.length; i++) { dataTransfer.items.add(files[i]); }
                
                var dropEvent = new DragEvent('drop', {
                    bubbles: true,
                    dataTransfer: dataTransfer
                });
                dropzone.dispatchEvent(dropEvent);
            }
            """
            self.driver.execute_script(js_script, input_file)

        except Exception as e:
            self.log(f"[BULK] Error in injection chain: {e}")
            raise e

        # 2. Äá»£i load xong máº» video (Event-driven: ngay khi Ã´ nháº­p liá»‡u hoáº·c row xuáº¥t hiá»‡n)
        self.log(f"[BULK] Waiting for processing (max 60s)...")
        start_t = time.time()
        upload_started = False
        while time.time() - start_t < 60:
            # Check xem cÃ²n chá»¯ "Upload up to 50 videos" khÃ´ng
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Upload up to 50 videos" not in body_text and "Thumbnail" in body_text:
                upload_started = True
                self.log("[BULK] Video list detected.")
                break  # Proceed immediately â€” no extra sleep
            
            # Check xem có Ã´ textbox nào hiá»‡n ra chÆ°a
            boxes = self.driver.find_elements(By.XPATH, "//div[@role='textbox'] | //textarea")
            if any(b.is_displayed() for b in boxes):
                upload_started = True
                self.log("[BULK] Metadata boxes appeared.")
                break  # Proceed immediately
            
            time.sleep(0.5)  # Poll every 0.5s instead of 3s

        
        if not upload_started:
            self.log("[BULK] Warning: Timeout waiting for video list. Proceeding anyway...")
        
        # 3. Äiá»n Title cho tá»«ng video
        self.log(f"[BULK] Filling titles for each video...")
        
        # Thá»­ tÃ¬m cÃ¡c Ã´ nháº­p liá»‡u báº±ng nhiá»u cÃ¡ch (localized placeholders/labels)
        for i, (video_path, title) in enumerate(batch_list):
            try:
                # Meta thÆ°á»ng dÃ¹ng "Description" hoáº·c "MÃ´ táº£"
                # Ta tÃ¬m textbox dá»±a trÃªn thá»© tá»± xuáº¥t hiá»‡n hoáº·c nhÃ£n
                selectors = [
                    f"(//div[@role='textbox' or @role='textarea' or @contenteditable='true'])[{i+1}]",
                    f"(//textarea)[{i+1}]",
                    f"//div[contains(@aria-label, 'Description') or contains(@aria-label, 'MÃ´ táº£')][{i+1}]",
                    f"//textarea[contains(@placeholder, 'Description') or contains(@placeholder, 'MÃ´ táº£')][{i+1}]"
                ]
                
                target_box = None
                for sel in selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, sel)
                        if elements and elements[0].is_displayed():
                            target_box = elements[0]
                            break
                    except: continue
                
                if target_box:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_box)
                    time.sleep(1)
                    target_box.click()
                    time.sleep(0.5)
                    # Sá»­ dá»¥ng thuáº­t toÃ¡n lÃ m sáº¡ch tiÃªu Ä‘á» (xÃ³a hashtag...)
                    clean_title = self._get_clean_title(title)
                    target_box.send_keys(clean_title)
                    self.log(f"[BULK] Filled title for video #{i+1}: {clean_title}")
                else:
                    self.log(f"[BULK] Warning: Could not find box for video #{i+1} using multiple selectors.")
                    try:
                        snipped_text = self.driver.find_element(By.TAG_NAME, "body").text[:200].replace('\n', ' ')
                        self.log(f"[BULK] Debug UI Text: {snipped_text}")
                    except: pass
            except Exception as e:
                self.log(f"[BULK] Error filling title for video #{i+1}: {e}")

        # 4. Sequence Next/Publish
        # Bulk upload thÆ°á»ng cáº§n 1-2 lần báº¥m Tiáº¿p vÃ  1 lần ÄÄƒng
        for step in range(4):
            self.log(f"[BULK] Next Sequence step {step+1}...")
            # Event-driven: wait for footer button to appear (no fixed sleep before search)
            self._wait_for_element([
                "//div[@role='button'][contains(., 'Next') or contains(., 'Tiáº¿p') or contains(., 'Publish') or contains(., 'ÄÄƒng') or contains(., 'Share')]"
            ], timeout=5)
            self._dismiss_tooltips()
            
            clicked = False
            # Láº¥y thÃ´ng tin viewport Ä‘á»ƒ lá»c nÃºt chÃ¢n trang (Footer)
            # Theo nghiÃªn cá»©u DOM, nÃºt Next/Publish tháº­t náº±m á»Ÿ 15% dÆ°á»›i cÃ¹ng vÃ  30% bÃªn pháº£i
            v_height = self.driver.execute_script("return window.innerHeight;")
            v_width = self.driver.execute_script("return window.innerWidth;")
            footer_y_threshold = v_height * 0.85 
            footer_x_threshold = v_width * 0.65
            
            buttons = self.driver.find_elements(By.XPATH, "//div[@role='button']")
            best_button = None
            priority_texts = ["tiáº¿p", "next", "Ä‘Äƒng", "publish", "share", "chia sáº»"]

            # 1. TÃ¬m theo text + tá»a Ä‘á»™ FOOTER (Ráº¥t quan trá»ng Ä‘á»ƒ trÃ¡nh decoy)
            for p_text in priority_texts:
                for b in buttons:
                    try:
                        if b.is_displayed() and b.is_enabled():
                            loc = b.location
                            # Chỉ xÃ©t cÃ¡c nÃºt náº±m á»Ÿ khu vá»±c Footer bÃªn pháº£i
                            if loc['y'] > footer_y_threshold and loc['x'] > footer_x_threshold:
                                t = b.text.lower()
                                if p_text in t and not any(w in t for w in ["há»§y", "cancel", "back", "quay láº¡i"]):
                                    best_button = b
                                    break
                    except: continue
                if best_button: break
            
            # 2. Fallback: Náº¿u khÃ´ng tÃ¬m tháº¥y theo text á»Ÿ footer, láº¥y nÃºt "náº±m xa nháº¥t vá» phÃ­a dÆ°á»›i bÃªn pháº£i"
            if not best_button:
                max_score = 0
                for b in buttons:
                    try:
                        if b.is_displayed():
                            loc = b.location
                            if loc['y'] > footer_y_threshold:
                                score = loc['x'] + loc['y']
                                if score > max_score:
                                    max_score = score
                                    best_button = b
                    except: continue

            if best_button:
                btn_text = best_button.text or "Unknown"
                self.log(f"[BULK] Clicking button: {btn_text}")
                self.driver.execute_script("arguments[0].click();", best_button)
                clicked = True
            
            if not clicked:
                self.log("[BULK] No clickable button found in sequence.")
                break
                
            # Check thành công báº±ng text hoáº·c URL hoáº·c biáº¿n máº¥t của composer
            page_text = self.driver.page_source.lower()
            current_url = self.driver.current_url.lower()
            
            # Náº¿u đã quay vá» trang home hoáº·c content, coi nhÆ° xong
            if "bulk_upload_composer" not in current_url:
                self.log("[BULK] Composer URL changed. Assuming success.")
                wait_time = random.randint(5, 15)
                self.log(f"[BULK] Waiting {wait_time}s for stability after publish...")
                time.sleep(wait_time)
                return "Uploaded Bulk"

            success_keywords = [
                "success", "creating your reels", "done", "đã Ä‘Äƒng", "hoàn tất", 
                "xong", " reels của báº¡n Ä‘ang Ä‘Æ°á»£c táº¡o", "quáº£n lÃ½ tất cả ná»™i dung"
            ]
            if any(k in page_text for k in success_keywords):
                self.log("[BULK] Success message detected. Entering aggressive search for 'Done' button...")
                
                # --- AGGRESSIVE DONE BUTTON SEARCH (5 RETRIES) ---
                done_selectors = [
                    "//div[@role='dialog']//div[@role='button']//span[text()='Done' or text()='Xong' or text()='HoÃ n táº¥t']",
                    "//div[@role='dialog']//div[@role='button'][contains(., 'Done') or contains(., 'Xong') or contains(., 'HoÃ n táº¥t')]",
                    "//div[@role='button']//span[text()='Done' or text()='Xong' or text()='HoÃ n táº¥t']",
                    "//button[contains(., 'Done') or contains(., 'Xong') or contains(., 'HoÃ n táº¥t')]",
                    "//div[@aria-label='Done' or @aria-label='Xong' or @aria-label='HoÃ n táº¥t']"
                ]
                
                done_clicked = False
                for attempt in range(1, 6):
                    self.log(f"[BULK] Done button search (Attempt {attempt}/5)...")
                    for sel in done_selectors:
                        btns = self.driver.find_elements(By.XPATH, sel)
                        for b in btns:
                            try:
                                if b.is_displayed():
                                    self.driver.execute_script("arguments[0].click();", b)
                                    self.log(f"[BULK] ✓ Clicked 'Done' button via selector: {sel}")
                                    done_clicked = True
                                    break
                            except: continue
                        if done_clicked: break
                    
                    if done_clicked: break
                    time.sleep(4) # Wait between retries
                
                if not done_clicked:
                    self.log("[BULK] Warning: Could not find 'Done' button after 5 attempts. Checking generic closure...")
                    self._close_popups_v2() # Fallback only if specific Done button fails
                
                # Event-driven final wait: poll for URL change or dialog disappearance (max 15s)
                self.log(f"[BULK] Waiting for upload to finalize...")
                deadline = time.time() + 15
                while time.time() < deadline:
                    cur_url = self.driver.current_url.lower()
                    if "bulk_upload_composer" not in cur_url:
                        break  # URL changed -> done
                    try:
                        # Check if publish dialog is gone
                        dialogs = self.driver.find_elements(By.XPATH, "//div[@role='dialog']")
                        if not any(d.is_displayed() for d in dialogs):
                            break  # Dialog closed -> done
                    except: pass
                    time.sleep(0.5)
                
                return "Uploaded Bulk"

        self.log("[BULK] Warning: Finished button sequence without confirmed success text.")
        return "Bulk Flow Finished"

    # upload_reel_v2 (Plan 1) đã bá»‹ gá»¡ bá» theo yÃªu cáº§u của User.


    # ═══════════════════════════════════════════════════════════════════════
    #  THUẬT TOÁN ĐĂNG REELS CHO Nick CÁ NHÂN (Personal Profile)
    #  URL: https://www.facebook.com/reels/create
    # ═══════════════════════════════════════════════════════════════════════
    def upload_reel_personal(self, video_path, title):
        """
        Đăng video lên Nick cá nhân qua giao diện Mobile Facebook (m.facebook.com).
        Thuật toán:
          1. Giả lập UA iPhone/Android
          2. Vào m.facebook.com
          3. Nhấn "What's on your mind?" → mở composer
          4. Nhấn Photo/Video → upload file
          5. Điền mô tả (title đã xóa hashtag)
          6. Nhấn Post
          7. Khôi phục UA mặc định
        """
        import random as _random
        self.set_timeout()
        abs_video = os.path.abspath(video_path)

        if not os.path.exists(abs_video):
            raise Exception(f"Video file không tồn tại: {abs_video}")

        # Lấy tên file video (không bao gồm đuôi) làm tiêu đề gốc
        video_name = os.path.basename(abs_video)
        raw_name_no_ext = os.path.splitext(video_name)[0]
        
        # Làm sạch hashtag: xóa mọi từ bắt đầu bằng # cho đến khoảng trắng
        import re
        clean_title = re.sub(r'#\S+', '', raw_name_no_ext)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        # Nếu title truyền vào từ DB có nội dung khác, có thể nối thêm hoặc ưu tiên tên file
        # Ở đây em ưu tiên hoàn toàn tên file video theo yêu cầu của anh.
        # clean_title = self._get_clean_title(title) # Bỏ dòng cũ này

        # Thử tìm link affiliate từ file .txt cùng tên video
        link_file = os.path.splitext(abs_video)[0] + ".txt"
        if os.path.exists(link_file):
            try:
                with open(link_file, 'r', encoding='utf-8') as f:
                    aff_link = f.read().strip()
                    if aff_link:
                        clean_title = f"{clean_title}\n\n{aff_link}"
                        self.log(f"[MOBILE] ✓ Link affiliate: {aff_link[:40]}")
            except: pass

        self.log(f"[MOBILE] ══ Bắt đầu đăng bài qua Mobile UI ══")
        self.log(f"[MOBILE] Video: {os.path.basename(abs_video)}")
        self.log(f"[MOBILE] Title: {clean_title[:80]}")

        # ── BƯỚC 1: Giả lập thiết bị iPhone ─────
        IPHONE_UA = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.4 Mobile/15E148 Safari/604.1"
        )
        try:
            # Chỉ cần set User Agent là đủ cho FB Mobile
            self.driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": IPHONE_UA,
                "platform": "iPhone",
                "userAgentMetadata": {
                    "architecture": "",
                    "bitness": "",
                    "brands": [{"brand": "Safari", "version": "17"}],
                    "fullVersionList": [{"brand": "Safari", "version": "17.4"}],
                    "mobile": True,
                    "model": "iPhone",
                    "platform": "iOS",
                    "platformVersion": "17.4"
                }
            })
            self.driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
                "width": 393,
                "height": 852,
                "deviceScaleFactor": 3,
                "mobile": True
            })
            self.driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {
                "enabled": True
            })
            self.log("[MOBILE] ✓ Đã đặt User Agent + Viewport iPhone 15 Pro")
        except Exception as e:
            self.log(f"[MOBILE] Warning UA emulation: {e}")

        try:
            # ── BƯỚC 2: Mở Facebook Mobile ─────────────────────────────────────
            self.log("[MOBILE] Bước 2: Xóa cookies Desktop & Mở m.facebook.com...")
            self._switch_to_best_tab()

            # Xóa cookie phân giải để Facebook không bắt ép về Desktop
            try:
                self.driver.get("https://facebook.com/robots.txt")
                self.driver.delete_cookie("wd")
                self.driver.delete_cookie("m_pixel_ratio")
                self.driver.delete_cookie("dp")
            except: pass

            # Navigate thẳng vào home để hạn chế redirect
            fb_urls = [
                "https://m.facebook.com/home.php",
                "https://m.facebook.com/"
            ]
            for fb_url in fb_urls:
                self._safe_get(fb_url)
                # Poll tối đa 15s chờ FB load, thoát ngay khi xong
                for _ in range(15):
                    current_url = self.driver.current_url.lower()
                    if "m.facebook.com" in current_url and "login" not in current_url:
                        break
                    time.sleep(1)
                current_url = self.driver.current_url.lower()
                self.log(f"[MOBILE] URL sau {fb_url}: {current_url[:80]}")
                if "m.facebook.com" in current_url:
                    break
            
            self._dismiss_tooltips()

            current_url = self.driver.current_url.lower()
            is_mobile = "m.facebook.com" in current_url
            self.log(f"[MOBILE] Chế độ: {'mobile' if is_mobile else 'desktop'}")

            # ── BƯỚC 3: Tìm và điền caption / Mở composer ─────────────────────
            is_desktop = "www.facebook.com" in self.driver.current_url.lower()
            mode_name = "DESKTOP" if is_desktop else "MOBILE"
            self.log(f"[{mode_name}] Bước 3: Tìm ô status/composer...")
            
            # Nếu đang ở Mobile, thử truy cập thẳng vào trang composer để bypass decoy
            if not is_desktop and "m.facebook.com" in self.driver.current_url:
                 current_url = self.driver.current_url.lower()
                 if "/composer/" not in current_url:
                     self.log("[MOBILE] Chuyển hướng trực tiếp tới m.facebook.com/composer/")
                     self._safe_get("https://m.facebook.com/composer/")
                     time.sleep(3)

            composer_selectors = []
            if is_desktop:
                composer_selectors = [
                    "//div[@role='button']//span[contains(text(), \"What's on your mind\") or contains(text(), 'nghĩ gì')]/ancestor::div[@role='button'][1]",
                    "//div[contains(@class,'x1i10hfl')]//span[contains(text(), 'mind') or contains(text(), 'nghĩ')]",
                    "//span[contains(text(), \"What's on your mind\") or contains(text(), 'nghĩ gì')]"
                ]
            else:
                composer_selectors = [
                    "//div[@data-sigil='m-composer-button']",
                    "//button[@id='m-composer-button']",
                    "//div[@role='button']//span[contains(text(), \"What's on your mind\")]/ancestor::div[@role='button'][1]",
                    "//div[@role='button']//span[contains(text(), 'nghĩ gì')]/ancestor::div[@role='button'][1]",
                    "//div[@aria-label=\"What's on your mind?\"]",
                    "//a[contains(@href, 'composer')]",
                    "//textarea[contains(@name,'message') or contains(@name,'status')]"
                ]

            composer_opened = False
            self.driver.implicitly_wait(0) # Tắt tạm thời để poll nhanh
            for sel in composer_selectors:
                try:
                    els = self.driver.find_elements(By.XPATH, sel)
                    for el in els:
                        if el.is_displayed():
                            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                            time.sleep(0.5)
                            from selenium.webdriver.common.action_chains import ActionChains
                            ActionChains(self.driver).move_to_element(el).click().perform()
                            self.log(f"[{mode_name}] ✓ Đã nhấn/focus composer: {sel[:60]}")
                            composer_opened = True
                            # Poll tối đa 5s chờ composer mở, thoát ngay
                            for _ in range(10):
                                # Kiểm tra xem đã vào trang composer chưa
                                if "/composer/" in self.driver.current_url.lower():
                                    break
                                # Hoặc tìm input file/dialog
                                if self.driver.find_elements(By.XPATH, "//input[@type='file'] | //div[@role='dialog']"):
                                    break
                                time.sleep(0.5)
                            break
                    if composer_opened: break
                except: continue
            self.driver.implicitly_wait(10) # Khôi phục

            if not composer_opened:
                self.log(f"[{mode_name}] ⚠ Không tìm thấy composer box. Có thể đã mở sẵn.")

            self._dismiss_tooltips()
            time.sleep(2)

            # ── BƯỚC 4: Tìm input file (Photo/Video) ─────────────────────────
            self.log(f"[{mode_name}] Bước 4: Tìm input[type=file] để upload video...")
            
            photo_selectors = []
            if is_desktop:
                photo_selectors = [
                    "//div[@aria-label='Photo/video' or @aria-label='Ảnh/video']",
                    "//div[@role='button'][.//span[contains(text(), 'Photo') or contains(text(), 'Ảnh')]]",
                    "//div[contains(@class,'x1i10hfl')]//div[contains(@aria-label,'Photo') or contains(@aria-label,'Ảnh')]"
                ]
            else:
                photo_selectors = [
                    "//div[@role='button' and (contains(.,'Video') or contains(.,'video'))]",
                    "//div[@aria-label='Video' or contains(text(),'Video')]",
                    "//div[@role='button'][contains(.,'Photos') or contains(.,'Ảnh')]",
                    "//div[@aria-label='Photo/video' or @aria-label='Ảnh/video' or contains(@aria-label,'Photo') or contains(@aria-label,'Ảnh')]"
                ]
                
            photo_btns = []
            self.driver.implicitly_wait(0)
            for p_sel in photo_selectors:
                try: photo_btns.extend(self.driver.find_elements(By.XPATH, p_sel))
                except: pass
                
            photo_clicked = False
            for pb in photo_btns:
                if pb.is_displayed():
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", pb)
                        time.sleep(0.5)
                        from selenium.webdriver.common.action_chains import ActionChains
                        ActionChains(self.driver).move_to_element(pb).click().perform()
                        self.log(f"[{mode_name}] ✓ Đã nhấn nút Photo/Video bằng ActionChains.")
                        photo_clicked = True
                        # Poll tối đa 5s chờ input file xuất hiện, thoát ngay
                        for _ in range(10):
                            if self.driver.find_elements(By.XPATH, "//input[@type='file']"):
                                break
                            time.sleep(0.5)
                        break
                    except: continue
            
            if not photo_clicked:
                self.log(f"[{mode_name}] ⚠ Cảnh báo: Không click được nút Photo/Video, thử tìm input trực tiếp...")

            file_input = None
            # 4a. Poll tìm input file (tối đa 8s, thoát ngay khi thấy)
            for attempt in range(16):
                all_inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
                if all_inputs:
                    file_input = all_inputs[-1]
                    self.log(f"[{mode_name}] ✓ Tìm thấy input file (attempt {attempt+1}).")
                    break
                time.sleep(0.5)
            self.driver.implicitly_wait(10)

            # 4b. Tìm bằng JS (kể cả hidden inputs)
            if not file_input:
                self.log("[MOBILE] Tìm input file bằng JS (kể cả hidden)...")
                try:
                    file_input = self.driver.execute_script(
                        "return document.querySelector('input[type=\"file\"]');"
                    )
                    if file_input:
                        self.log("[MOBILE] ✓ Tìm thấy input file bằng JS.")
                except: pass

            if not file_input:
                raise Exception("[MOBILE] Không tìm thấy input[type=file] sau tất cả nỗ lực.")

            # ── BƯỚC 5: Upload video ─────────────────────────────────────────
            self.log(f"[MOBILE] Bước 5: Upload video...")
            # Ép input file hiển thị
            self.driver.execute_script("""
                arguments[0].style.display = 'block';
                arguments[0].style.visibility = 'visible';
                arguments[0].style.opacity = '1';
                arguments[0].style.position = 'fixed';
                arguments[0].style.top = '0';
                arguments[0].style.left = '0';
                arguments[0].style.width = '50px';
                arguments[0].style.height = '50px';
                arguments[0].style.zIndex = '99999';
            """, file_input)
            time.sleep(0.3)
            file_input.send_keys(abs_video)
            self.log(f"[MOBILE] ✓ Đã gửi video vào input.")

            # Đóng hộp thoại File Picker nếu còn mở (native dialog)
            try:
                import pyautogui
                time.sleep(0.5)
                pyautogui.press('escape')
                self.log("[MOBILE] ✓ Đã nhấn Escape đóng File Picker.")
            except Exception as esc_e:
                self.log(f"[MOBILE] ⚠ Không đóng được File Picker: {esc_e}")

            # Trigger change events
            self.driver.execute_script("""
                var inp = arguments[0];
                inp.dispatchEvent(new Event('change', {bubbles: true}));
                inp.dispatchEvent(new Event('input', {bubbles: true}));
            """, file_input)

            # Đợi upload xử lý - poll mỗi 1s, thoát ngay khi có bất kỳ dấu hiệu nào
            self.log("[MOBILE] Đợi video upload/xử lý (max 120s)...")
            upload_done = False
            self.driver.implicitly_wait(0) # Quan trọng: tránh 10s wait mỗi selector trong loop
            for i in range(120):
                # Kiểm tra nhiều dấu hiệu "đã upload xong"
                try:
                    # 1. Nút POST/Đăng xuất hiện
                    post_btns = self.driver.find_elements(By.XPATH,
                        "//*[@type='submit' or (@role='button' and (contains(.,'POST') or contains(.,'Post') or contains(.,'Share') or contains(.,'Đăng')))]"
                    )
                    if any(b.is_displayed() for b in post_btns):
                        self.log(f"[MOBILE] ✓ Phát hiện nút POST sau {i+1}s.")
                        upload_done = True
                        break

                    # 2. Icon thùng rác (xóa video) xuất hiện = video đã đính kèm
                    trash = self.driver.find_elements(By.XPATH,
                        "//*[@aria-label='Remove' or @aria-label='Xóa' or @aria-label='Delete']"
                        " | //div[contains(@class,'delete') or contains(@class,'remove')][@role='button']"
                    )
                    if any(t.is_displayed() for t in trash):
                        self.log(f"[MOBILE] ✓ Phát hiện icon xóa video sau {i+1}s (video đã đính kèm).")
                        upload_done = True
                        break

                    # 3. Phần tử video/thumbnail xuất hiện trong DOM
                    videos = self.driver.find_elements(By.XPATH, "//video | //div[contains(@class,'video_preview')]")
                    if any(v.is_displayed() for v in videos):
                        self.log(f"[MOBILE] ✓ Phát hiện video preview sau {i+1}s.")
                        upload_done = True
                        break

                    # 4. Text kích thước file (vd: "7.8 MB") xuất hiện = đã xử lý
                    page_src = self.driver.page_source
                    if ' MB' in page_src or ' KB' in page_src:
                        import re as _re
                        if _re.search(r'\d+\.?\d*\s*(MB|KB)', page_src):
                            self.log(f"[MOBILE] ✓ Phát hiện thông tin kích thước file sau {i+1}s.")
                            upload_done = True
                            break
                except: pass
                time.sleep(1)
                if i > 0 and i % 20 == 0:
                    self.log(f"[MOBILE] Đang đợi... {i}s")
            self.driver.implicitly_wait(10) # Khôi phục

            if not upload_done:
                self.log("[MOBILE] ⚠ Timeout 120s, tiếp tục dù chưa thấy dấu hiệu upload.")


            # ── BƯỚC 6: Điền mô tả ─────────────────────────────────────────
            self.log(f"[{mode_name}] Bước 6: Điền mô tả: '{clean_title[:60]}'")
            desc_selectors = [
                # Mobile Facebook - ô soạn thảo chính
                "//textarea[@name='xc_message']",
                "//textarea[contains(@placeholder,\"What's on your mind\") or contains(@placeholder,'mind') or contains(@placeholder,'Write') or contains(@placeholder,'nghĩ gì')]",
                # Div contenteditable (React-based)
                "//div[@contenteditable='true' and @role='textbox']",
                "//div[@contenteditable='true']",
                "//div[@role='textbox']",
                # Fallback cuối cùng
                "(//textarea)[1]",
                "(//div[@contenteditable='true'])[1]",
            ]
            desc_filled = False
            for sel in desc_selectors:
                try:
                    els = self.driver.find_elements(By.XPATH, sel)
                    for el in els:
                        if not el.is_displayed():
                            continue
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                            time.sleep(0.3)
                            # Dùng ActionChains để click + send_keys cho tất cả loại element
                            # ActionChains kích hoạt React đúng cách
                            ActionChains(self.driver).click(el).perform()
                            time.sleep(0.3)
                            # Xóa nội dung cũ bằng Ctrl+A + Delete
                            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
                            time.sleep(0.2)
                            ActionChains(self.driver).send_keys(Keys.DELETE).perform()
                            time.sleep(0.2)
                            # Gõ text bằng send_keys (kích hoạt React đúng)
                            ActionChains(self.driver).send_keys(clean_title).perform()
                            time.sleep(0.3)
                            # Xác nhận đã có text
                            entered = el.get_attribute('value') or el.text or el.get_attribute('textContent') or ''
                            if clean_title[:10] in entered or len(entered) > 0:
                                self.log(f"[{mode_name}] ✓ Đã điền mô tả thành công.")
                            else:
                                self.log(f"[{mode_name}] ✓ Đã gõ mô tả (không xác nhận được text).")
                            desc_filled = True
                            break
                        except Exception as fill_e:
                            self.log(f"[{mode_name}] ⚠ Lỗi điền vào element: {fill_e}")
                            continue
                    if desc_filled:
                        break
                except:
                    continue

            if not desc_filled:
                self.log(f"[{mode_name}] ⚠ Không điền được mô tả, tiếp tục đăng không có caption.")
            else:
                time.sleep(0.5)  # Thời gian tối thiểu để React cập nhật state


            # ── BƯỚC 7: Nhấn Post ────────────────────────────────────────────
            self.log(f"[{mode_name}] Bước 7: Tìm và nhấn nút Post...")
            post_btn_selectors = [
                # Mobile XPATHs từ Antigravity Browser
                "//div[@role='button']//span[text()='POST' or text()='Post' or text()='Đăng']/ancestor::div[@role='button'][1]",
                "//div[@role='button' and contains(@class, 'bg-s7')]",
                "//div[@role='button'][contains(.,'POST') or contains(.,'Post') or contains(.,'Đăng')]",
                # Desktop & Fallbacks
                "//div[@aria-label='Post' or @aria-label='Đăng'][@role='button']",
                "//button[@type='submit']",
                "//*[@type='submit']",
                "//*[@role='button'][contains(.,'Post') or contains(.,'Đăng') or contains(.,'Share') or contains(.,'Publish')]",
                "//input[@type='submit']",
                "//button[contains(text(),'Post') or contains(text(),'Đăng') or contains(text(),'Share')]",
            ]
            posted = False
            for sel in post_btn_selectors:
                try:
                    btns = self.driver.find_elements(By.XPATH, sel)
                    for btn in btns:
                        if btn.is_displayed():
                            btn_txt = btn.text.strip() or btn.get_attribute("value") or "Submit"
                            self.log(f"[MOBILE] Nhấn nút: '{btn_txt}'")
                            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                            time.sleep(0.5)
                            from selenium.webdriver.common.action_chains import ActionChains
                            ActionChains(self.driver).move_to_element(btn).click().perform()
                            time.sleep(8)
                            posted = True
                            break
                    if posted: break
                except: continue

            if posted:
                self.log("[MOBILE] Đang xác minh bài đăng (max 20s)...")
                success_verified = False
                for i in range(20):
                    curr_url = self.driver.current_url.lower()
                    page_text = self.driver.page_source.lower()
                    
                    if "/composer/" not in curr_url and "reels/create" not in curr_url:
                        self.log(f"[MOBILE] ✓ Đã thoát khỏi trang soạn thảo (URL: {curr_url[:40]}).")
                        success_verified = True
                        break
                    
                    if any(k in page_text for k in ["đã đăng", "thành công", "success", "posted", "published", "hoàn tất"]):
                        self.log("[MOBILE] ✓ Thấy thông báo thành công trên màn hình.")
                        success_verified = True
                        break
                        
                    try:
                        still_there = False
                        self.driver.implicitly_wait(0)
                        for s in post_btn_selectors[:3]: 
                            if self.driver.find_elements(By.XPATH, s):
                                still_there = True
                                break
                        self.driver.implicitly_wait(10)
                        if not still_there:
                            self.log("[MOBILE] ✓ Nút Post đã biến mất. Coi như hoàn tất.")
                            success_verified = True
                            break
                    except: pass

                    time.sleep(1)
                    if i % 5 == 0 and i > 0: self.log(f"[MOBILE] Đang đợi xác nhận... {i}s")

                if success_verified:
                    self.log("[MOBILE] ✓✓ ĐÃ ĐĂNG BÀI THÀNH CÔNG!")
                    return "Uploaded Personal"
                else:
                    self.log("[MOBILE] ⚠ Không thể xác nhận đăng thành công (Timeout).")
                    return "Failed: Verification Timeout"
            else:
                self.log("[MOBILE] ⚠ Không tìm thấy nút Post để bấm.")
                return "Failed: Post Button Not Found"

        finally:
            # ── BƯỚC 8: Khôi phục browser về desktop mode ─────────────────
            try:
                self.driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": ""})
                self.driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
                self.driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {"enabled": False})
                self.log("[MOBILE] ✓ Đã khôi phục về Desktop mode (UA + Viewport + Touch).")
            except Exception as e:
                self.log(f"[MOBILE] Warning restore: {e}")


    # ── Helper methods cho upload_reel_personal ──────────────────────────

    def _personal_find_file_input(self):
        """Tìm input[type=file] phù hợp nhất trên trang Reels Create."""
        # 1. Selector from subagent investigation: actual modal input
        modal_inputs = self.driver.find_elements(By.XPATH, "//div[@role='dialog']//input[@type='file' and contains(@accept, 'video')]")
        if modal_inputs:
            self.log(f"[PERSONAL] Ưu tiên modal input file.")
            return modal_inputs[0]

        # 2. General precise input
        specific = self.driver.find_elements(By.XPATH, "//input[@type='file' and contains(@accept, 'video')]")
        if specific:
            return specific[-1] # Usually the latter one is active

        # 3. Fallback to generic
        inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
        # self.log(f"[PERSONAL] Tìm thấy {len(inputs)} input file (fallback).") # Avoid spamming the loop log

        for inp in inputs:
            acc = (inp.get_attribute("accept") or "").lower()
            if "video" in acc:
                self.log(f"[PERSONAL] Chọn input có accept='{acc}'")
                return inp

        if inputs:
            self.log("[PERSONAL] Dùng input file đầu tiên (không có accept=video).")
            return inputs[0]
            
        # Tìm trong iframe nếu không thấy
        self.log("[PERSONAL] Không thấy input ở main context, tìm trong iframe...")
        if self._switch_to_composer_frame_recursive():
            inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
            if inputs:
                return inputs[0]
        self.driver.switch_to.default_content()

        # Cuối cùng: Dùng Javascript querySelector (để vượt qua Shadow DOM hoặc XPath lỗi)
        try:
            self.log("[PERSONAL] Dùng Javascript querySelector để tìm input file...")
            js_el = self.driver.execute_script(
                "return document.querySelector('input[type=\"file\"][accept*=\"video\"]') || "
                "document.querySelector('input[type=\"file\"]');"
            )
            if js_el:
                self.log(f"[PERSONAL] Đã tìm thấy DOM Element bằng Javascript: {js_el}")
                return js_el
        except Exception as e:
            self.log(f"[PERSONAL] Lỗi khi chạy Javascript query: {e}")

        return None

    def _personal_wait_video_processing(self, timeout=120):
        """Đợi video được xử lý xong (preview/description box xuất hiện)."""
        start_t = time.time()
        while time.time() - start_t < timeout:
            try:
                # Dấu hiệu 1: Ô description xuất hiện
                desc_boxes = self.driver.find_elements(By.XPATH,
                    "//div[@role='textbox'] | //div[@contenteditable='true'] | //textarea")
                if any(b.is_displayed() for b in desc_boxes):
                    self.log("[PERSONAL] ✓ Ô description đã xuất hiện → video sẵn sàng.")
                    return True

                # Dấu hiệu 2: Nút Next/Share xuất hiện
                action_btns = self.driver.find_elements(By.XPATH,
                    "//div[@role='button'][contains(., 'Next') or contains(., 'Tiếp') or "
                    "contains(., 'Share') or contains(., 'Chia sẻ') or "
                    "contains(., 'Publish') or contains(., 'Đăng')]")
                if any(b.is_displayed() for b in action_btns):
                    self.log("[PERSONAL] ✓ Nút Next/Share đã xuất hiện → video sẵn sàng.")
                    return True

                # Dấu hiệu 3: Video preview (canvas/video element)
                previews = self.driver.find_elements(By.XPATH,
                    "//video | //canvas | //div[contains(@style, 'background-image')]")
                if len(previews) > 1:  # Thường sẽ có preview video
                    self.log("[PERSONAL] ✓ Video preview detected.")
                    return True

            except Exception as e:
                pass

            time.sleep(1)

        return False

    def _personal_find_description_box(self):
        """Tìm ô mô tả/caption bằng JavaScript cực mạnh (xuyên Iframe)."""
        js_func = """
        window.findReelDescriptionBox = function(doc) {
            // Broad search for any textbox-like element in a Reels context
            let selectors = [
                "div[role='textbox']",
                "div[contenteditable='true']",
                "textarea",
                "[aria-label*='reel' i]",
                "[aria-placeholder*='reel' i]",
                "[aria-label*='mô tả' i]"
            ];
            for (let sel of selectors) {
                let els = doc.querySelectorAll(sel);
                for (let el of els) {
                    // Check if displayed and not a search/chat box (heuristic)
                    if (el.offsetHeight > 20) {
                        // Tránh các nút hoặc thanh tìm kiếm nhỏ
                        let txt = (el.getAttribute('aria-label') || '').toLowerCase();
                        if (txt.includes('search') || txt.includes('tìm kiếm')) continue;
                        return el;
                    }
                }
            }
            return null;
        };
        """
        self.driver.execute_script(js_func)
        
        # 1. Search in main document
        found = self.driver.execute_script("return window.findReelDescriptionBox(document);")
        if found: return found

        # 2. Search in all IFrames
        frames = self.driver.find_elements(By.TAG_NAME, "iframe")
        for frame in frames:
            try:
                self.driver.switch_to.frame(frame)
                self.driver.execute_script(js_func) # Inject into frame too
                found = self.driver.execute_script("return window.findReelDescriptionBox(document);")
                self.driver.switch_to.default_content()
                if found: return found
            except:
                self.driver.switch_to.default_content()
                continue
        
        return None

    def _personal_fill_description(self, text):
        """Tìm và điền ô mô tả trên trang Reels Create."""
        try:
            # Đợi một chút để UI ổn định
            time.sleep(3)
            
            # Log thử xem có textbox nào không để debug
            boxes = self.driver.execute_script("""
                return Array.from(document.querySelectorAll('div[role="textbox"], textarea')).map(el => ({
                    label: el.getAttribute('aria-label') || '',
                    placeholder: el.getAttribute('aria-placeholder') || '',
                    visible: el.offsetHeight > 0
                }));
            """)
            if boxes:
                self.log(f"[PERSONAL] Debug: Tìm thấy {len(boxes)} textbox(es): {boxes}")

            target_box = self._personal_find_description_box()
            
            if not target_box:
                self.log("[PERSONAL] ⚠ Chưa thấy ô description (có thể ở bước sau).")
                return False

            # Scroll đến ô description
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_box)
            time.sleep(0.5)

            # Click để focus
            try:
                target_box.click()
            except:
                self.driver.execute_script("arguments[0].click();", target_box)
            time.sleep(0.5)

            # Clear nội dung cũ và nhập text
            self.driver.execute_script("""
                var el = arguments[0];
                el.focus();
                if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                    el.value = arguments[1];
                } else {
                    el.textContent = arguments[1];
                }
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, target_box, text)
            
            self.log(f"[PERSONAL] ✓ Đã điền mô tả: {text[:50]}...")
            return True
        except Exception as e:
            self.log(f"[PERSONAL] Lỗi điền mô tả: {e}")
            return False

    def _personal_click_next_and_share(self, text=""):
        """Bấm qua các bước Next → Share trên Reels Create. 
        KEY INSIGHT: Dialog có thể đang ở trạng thái skeleton loading, phải đợi nó finish load trước.
        """
        for attempt in range(12): 
            self.log(f"[PERSONAL] Click attempt {attempt + 1}/12...")
            self._dismiss_tooltips()

            if not self._personal_caption_filled and text:
                res = self._personal_fill_description(text)
                if res: self._personal_caption_filled = True

            # ─── BƯỚC QUAN TRỌNG: Đợi Dialog có nút thật (không còn skeleton) ────
            # Skeleton loading = các div animation không có role='button'
            # Real UI = xuất hiện các div[@role='button'] trong dialog
            self.log("[PERSONAL] Đợi dialog xuất hiện nút thật...")
            dialog_ready = False
            for wait_i in range(40):  # Đợi tối đa 40s
                try:
                    # Tìm nút Next/Share/Tiếp ở bất kỳ đâu trên trang (không giới hạn dialog)
                    real_btns = self.driver.find_elements(By.XPATH,
                        "//*[@role='button'][contains(., 'Next') or contains(., 'Tiếp') or "
                        "contains(., 'Share') or contains(., 'Chia sẻ') or "
                        "contains(., 'Publish') or contains(., 'Đăng') or contains(., 'Done') or contains(., 'Xong')]"
                    )
                    visible_btns = [b for b in real_btns if b.is_displayed()]
                    if visible_btns:
                        self.log(f"[PERSONAL] Tìm thấy {len(visible_btns)} nút thật sau {wait_i}s: '{visible_btns[0].text[:40]}'")
                        dialog_ready = True
                        break
                except: pass
                time.sleep(1)

            if not dialog_ready:
                self.log("[PERSONAL] Không thấy nút thật sau 40s.")
                time.sleep(3)
                # Không continue - vẫn thử tìm nút dù sao

            # ─── TÌM NÚT TRONG DIALOG ─────────────────────────────────────────
            context = self.driver
            try:
                dialogs = self.driver.find_elements(By.XPATH, "//div[@role='dialog']")
                if dialogs:
                    context = dialogs[-1]
            except: pass

            # DUMP all visible text in dialog for debugging
            try:
                all_text = context.text.replace("\n", " | ")
                self.log(f"[PERSONAL] Dialog content: '{all_text[:300]}'")
            except: pass

            # Tìm nút bằng selector cực rộng
            buttons = context.find_elements(By.XPATH, 
                ".//*[@role='button' or self::button]"
            )
            
            best_button = None
            strong_keywords = ["share", "chia sẻ", "đăng", "publish", "next", "tiếp", "done", "xong"]
            exclude_keywords = ["đóng", "close", "huỷ", "hủy", "cancel", "back", "discard", "like", "thích", "comment", "bình luận", "reply", "x"]

            for b in buttons:
                try:
                    if not b.is_displayed(): continue
                    
                    txt = (b.text or "").lower().strip()
                    aria = (b.get_attribute("aria-label") or "").lower().strip()
                    cls = (b.get_attribute("class") or "").lower()
                    full_info = f"{txt} {aria}"
                    
                    if any(ex == full_info.strip() or ex in full_info for ex in exclude_keywords): continue
                    
                    if any(k in full_info for k in strong_keywords):
                        # Prefer blue button (x1n2onr6 class = FB primary button)
                        if "x1n2onr6" in cls or not best_button:
                            best_button = b
                        if "x1n2onr6" in cls:
                            break  # Best possible match found
                except: continue

            if not best_button:
                self.log("[PERSONAL] Không thấy nút. Dump tất cả role='button' trong dialog:")
                try:
                    for b in buttons[:20]:
                        try:
                            if b.is_displayed():
                                self.log(f"  - text='{b.text.strip()[:40]}' aria='{(b.get_attribute('aria-label') or '')[:40]}'")
                        except: pass
                except: pass
                time.sleep(5)
                continue

            btn_txt = best_button.text.strip() or (best_button.get_attribute("aria-label") or "Unknown")
            self.log(f"[PERSONAL] Bấm nút: '{btn_txt}'")
            
            # Click với đầy đủ mouse events (React cần mousedown+mouseup+click)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", best_button)
            time.sleep(1)
            
            clicked = False
            for method in ["action_chains", "js_dispatch", "js_click"]:
                try:
                    if method == "action_chains":
                        from selenium.webdriver.common.action_chains import ActionChains
                        ActionChains(self.driver).move_to_element(best_button).click().perform()
                    elif method == "js_dispatch":
                        self.driver.execute_script("""
                            var el = arguments[0];
                            ['mousedown','mouseup','click'].forEach(n => {
                                el.dispatchEvent(new MouseEvent(n, {bubbles:true, cancelable:true, view:window}));
                            });
                        """, best_button)
                    elif method == "js_click":
                        self.driver.execute_script("arguments[0].click();", best_button)
                    
                    time.sleep(6)
                    try:
                        if not best_button.is_displayed():
                            clicked = True; break
                        if best_button.text.strip() != btn_txt:
                            clicked = True; break
                    except:
                        clicked = True; break
                except: pass

            status = "✓ OK" if clicked else "⚠ Vẫn hiện diện"
            self.log(f"[PERSONAL] {status} sau khi bấm '{btn_txt}'")

            time.sleep(3)
            new_url = self.driver.current_url.lower()
            if "/reels/create" not in new_url and "facebook.com" in new_url:
                self.log(f"[PERSONAL] ✓ Thành công: Đã rời trang Reels Create.")
                return "Uploaded Personal"

        return None

    def _personal_wait_publish_success(self, timeout=30):
        """Đợi xác nhận publish thành công."""
        start_t = time.time()
        while time.time() - start_t < timeout:
            try:
                # Check 1: URL thay đổi khỏi /reels/create
                current_url = self.driver.current_url.lower()
                if "reels/create" not in current_url and "facebook.com" in current_url:
                    self.log("[PERSONAL] ✓ URL đã chuyển khỏi /reels/create.")
                    return True

                # Check 2: Thông báo thành công trong page
                page_text = self.driver.page_source.lower()
                success_keywords = [
                    "your reel has been shared", "reel của bạn đã được chia sẻ",
                    "shared successfully", "đã chia sẻ thành công",
                    "reel published", "đã đăng reel",
                    "your reel is now", "reel is being",
                    "reel đang được", "đã chia sẻ reel"
                ]
                if any(k in page_text for k in success_keywords):
                    return True

                # Check 3: Dialog thành công xuất hiện
                dialogs = self.driver.find_elements(By.XPATH,
                    "//div[@role='dialog']//span[contains(., 'shared') or contains(., 'chia sẻ') or "
                    "contains(., 'published') or contains(., 'đăng')]")
                if any(d.is_displayed() for d in dialogs):
                    return True

            except:
                pass
            time.sleep(1)

        return False

    def _personal_close_popups(self):
        """Đóng các popup/overlay đặc thù của trang Reels Create cá nhân."""
        popup_selectors = [
            # Nút Dismiss/Bỏ qua
            "//div[@role='button'][contains(., 'Dismiss') or contains(., 'Bỏ qua') or contains(., 'Not now') or contains(., 'Không phải bây giờ')]",
            # Share to story popup - bỏ qua
            "//div[@role='button'][contains(., 'Skip') or contains(., 'Bỏ qua')]",
            # Got it button
            "//div[@role='button'][contains(., 'Got it') or contains(., 'Đã hiểu')]"
        ]
        try:
            for sel in popup_selectors:
                elements = self.driver.find_elements(By.XPATH, sel)
                for el in elements:
                    if el.is_displayed():
                        txt = el.text.lower()
                        # Không đóng nút Share/Next (tránh nhầm)
                        if any(w in txt for w in ["share", "chia sẻ", "next", "tiếp", "publish", "đăng"]):
                            continue
                        self.log(f"[PERSONAL] Đóng popup: {el.text.strip()[:30]}")
                        self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(1)
        except:
            pass

    def _dismiss_tooltips(self):
        """ Closes small tooltips/overlays that block logic """
        tooltips = [
            "//div[@role='dialog']//div[@role='button'][contains(., 'Got it') or contains(., 'Đã hiá»ƒu')]",
            "//div[contains(@class, 'x1i10hfl')]//div[contains(., 'Done') or contains(., 'Xong')]",
            "//div[contains(text(), 'You can now add a collaborator')]/following-sibling::div[@role='button']"
        ]
        for ts in tooltips:
            try:
                btns = self.driver.find_elements(By.XPATH, ts)
                for b in btns:
                    if b.is_displayed():
                        print(f"[Automator] [V2] Dismissing tooltip via {ts}")
                        self.driver.execute_script("arguments[0].click();", b)
                        time.sleep(1)
            except: continue

    def _switch_to_composer_frame_recursive(self):
        """ Recursive search for composer marker """
        self.driver.switch_to.default_content()
        return self._search_frames_for_marker()

    def _search_frames_for_marker(self):
        markers = [
            "//input[@type='file']",
            "//div[@role='button'][contains(translate(@aria-label, 'VIDEO', 'video'), 'video')]",
            "//*[contains(text(), 'Add Video') or contains(text(), 'Thêm video')]",
            "//div[@role='textbox']"
        ]
        # Check current
        for m in markers:
            try:
                if self.driver.find_elements(By.XPATH, m):
                    print(f"[Automator] [V2] Context found via {m}")
                    return True
            except: continue
        
        # Check kids
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        for i, frame in enumerate(iframes):
            try:
                self.driver.switch_to.frame(frame)
                if self._search_frames_for_marker(): return True
                self.driver.switch_to.parent_frame()
            except:
                try: self.driver.switch_to.parent_frame()
                except: self.driver.switch_to.default_content()
        return False

    def _close_popups_v2(self):
        """ Specialized popup closer for Business Suite Composer """
        try:
            popup_selectors = [
                 "//div[@role='button'][@aria-label='Close' or @aria-label='ÄÃ³ng' or @aria-label='Dismiss']",
                 "//div[@role='button'][descendant::span[text()='Dismiss' or text()='Bỏ qua' or text()='Maybe later' or text()='LÃºc khÃ¡c']]",
                 "//div[contains(@aria-label, 'Got it')]",
                 "//div[contains(@class, 'x1i10hfl')]//div[@role='button'][.//i]" 
            ]
            for sel in popup_selectors:
                elements = self.driver.find_elements(By.XPATH, sel)
                for el in elements:
                    if el.is_displayed():
                        print(f"[Automator] [V2] Closing popup: {sel}")
                        self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(1)
        except: pass

    def upload_reel_old(self, asset_id, video_path, title, scrape_name=False):
        """ The original bulk_upload_composer method, kept as Backup 2 """
        if scrape_name:
            page_name = None
            try:
                profile_url = f"https://www.facebook.com/{asset_id}"
                print(f"[Automator] Scrape requested. Navigating to profile: {profile_url}")
                self.driver.get(profile_url)
                time.sleep(5)
                
                # Method 1: Regex Search for "Switch into ... 's Page"
                try:
                    # Search for any element containing the key phrase
                    xpath_switch = "//*[contains(text(), 'Switch into') or contains(text(), 'Chuyá»ƒn sang')]"
                    elements = self.driver.find_elements(By.XPATH, xpath_switch)
                    
                    found_name = None
                    for el in elements:
                        txt = el.text.strip()
                        # Regex to capture content between "Switch into " and "'s"
                        # English: "Switch into [Tanglike.net 8092...] 's Page"
                        # Vietnamese: "Chuyá»ƒn sang trang [Tanglike.net 8092...]" ? Or "Chuyá»ƒn sang [Name]..."
                        # User matched: "Switch into Tanglike.net 809248679251752381748's Page"
                        
                        # English Pattern
                        match_en = re.search(r"Switch into (.*?)'s Page", txt)
                        if match_en:
                            found_name = match_en.group(1).strip()
                            print(f"[Automator] Regex Match (EN): {found_name}")
                            break
                            
                        # Vietnamese Pattern (Approximation based on standard FB translation)
                        # Usually "Chuyá»ƒn sang trang của [Name]" or "Chuyá»ƒn sang [Name]"
                        if "Chuyá»ƒn sang" in txt:
                             # Try to capture reasonable length text after Chuyá»ƒn sang
                             match_vi = re.search(r"Chuyá»ƒn sang (.*?)( trang|$)", txt)
                             if match_vi:
                                 found_name = match_vi.group(1).strip()
                                 print(f"[Automator] Regex Match (VI): {found_name}")
                                 break
                    
                    if found_name:
                        page_name = found_name
                        print(f"[Automator] Scraped Name from Regex: {page_name}")
                        
                except Exception as e:
                    print(f"[Automator] Regex search failed: {e}")

                # Method 2: H1 Tag (Visible name)
                if not page_name:
                    try:
                        h1_el = self.driver.find_element(By.TAG_NAME, "h1")
                        if h1_el:
                            page_name = h1_el.text.strip()
                            print(f"[Automator] Scraped Name from H1: {page_name}")
                    except: pass

                # Method 3: Meta Tag og:title
                if not page_name:
                    try:
                        meta_title = self.driver.find_element(By.XPATH, "//meta[@property='og:title']")
                        content = meta_title.get_attribute("content")
                        if content and "Facebook" not in content:
                            page_name = content.strip()
                            print(f"[Automator] Scraped Name from og:title: {page_name}")
                    except: pass
                
                # Method 4: Page Title (Last Resort)
                if not page_name:
                    page_title = self.driver.title
                    if page_title and "Facebook" in page_title:
                         clean = re.sub(r'\(\d+\)\s*', '', page_title)
                         clean = clean.replace("| Facebook", "").replace("Facebook", "").strip()
                         if clean: 
                            page_name = clean
                            print(f"[Automator] Scraped Name from Title: {page_name}")
                
                # Method 4: Page Title (Last Resort)
                if not page_name:
                    page_title = self.driver.title
                    if page_title and "Facebook" in page_title:
                         clean = re.sub(r'\(\d+\)\s*', '', page_title)
                         clean = clean.replace("| Facebook", "").replace("Facebook", "").strip()
                         if clean: 
                            page_name = clean
                            print(f"[Automator] Scraped Name from Title: {page_name}")

                if not page_name:
                    print("[Automator] Failed to scrape name from Profile.")
                
            except Exception as e:
                print(f"[Automator] Profile scraping failed: {e}")

        upload_url = f"https://business.facebook.com/latest/bulk_upload_composer?asset_id={asset_id}"
        print(f"[Automator] [Backup] Navigating to upload URL: {upload_url}")
        
        # Thêm vÃ²ng láº·p refresh trang náº¿u tráº¯ng do lá»—i pháº§n cá»©ng/máº¡ng
        max_wait_time = 180 # 3 phút
        start_wait = time.time()
        file_input = None
        reload_count = 0
        
        self._safe_get(upload_url)
        time.sleep(3)
        # Reverted: self._close_popups_v2() here was causing issues with the upload composer
        

        while time.time() - start_wait < max_wait_time:
            # Handle "Permission denied"
            if "Permission denied" in self.driver.page_source or "sufficient permissions" in self.driver.page_source:
                 print("[Automator] Permission denied detected. Reloading page...")
                 self.driver.refresh()
                 time.sleep(4)
            
            try:
                # 1. Clean title: Remove all hashtags and non-BMP characters
                import re
                # Remove hashtags (words starting with #)
                clean_title = re.sub(r'#\w+', '', title)
                # Remove emojis/non-BMP
                clean_title = "".join(c for c in clean_title if ord(c) <= 0xFFFF)
                # Clean up double spaces
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                
                # Chá» nÃºt upload
                file_input = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
                )
                break # TÃ¬m tháº¥y nÃºt -> thoát vÃ²ng láº·p chá»
            except Exception as e:
                reload_count += 1
                if reload_count >= 3:
                     print("[Automator] Đã táº£i láº¡i 3 lần nhÆ°ng váº«n tráº¯ng trang. Bỏ qua page nÃ y.")
                     raise Exception("SKIP_PAGE: Lỗi tráº¯ng trang liÃªn tá»¥c khÃ´ng tÃ¬m tháº¥y nÃºt upload")
                print(f"[Automator] KhÃ´ng tÃ¬m tháº¥y input upload, tráº¯ng trang hoáº·c lá»—i máº¡ng. F5 láº¡i trang... ({reload_count}/3)")
                try:
                    self.driver.refresh()
                    time.sleep(3)
                except:
                    pass

        if not file_input:
            raise Exception("QuÃ¡ 3 phút khÃ´ng load Ä‘Æ°á»£c trang upload (tráº¯ng trang liÃªn tá»¥c).")

        try:
            file_input.send_keys(os.path.abspath(video_path))
            print("[Automator] Video file sent.")
            
            # Wait for fields to appear
            print("[Automator] Waiting for title/description fields...")
            time.sleep(3) # Heavy wait for Meta Business Suite
            
            # Find all text areas (usually Title, Description, etc.)
            fields = self.driver.find_elements(By.XPATH, "//textarea | //div[@role='textbox']")
            print(f"[Automator] Found {len(fields)} text fields.")
            
            for field in fields:
                try:
                    # Clear and fill every visible text field with the clean title
                    if field.is_displayed():
                        field.click()
                        time.sleep(1)
                        # Use Ctrl+A, Backspace to clear if clear() doesn't work well
                        from selenium.webdriver.common.keys import Keys
                        field.send_keys(Keys.CONTROL + "a")
                        field.send_keys(Keys.BACKSPACE)
                        field.send_keys(clean_title)
                        print(f"[Automator] Filled a field with: {clean_title}")
                except Exception as e:
                    print(f"[Automator] Error filling field: {e}")

            # Click 'Next' steps - usually 2-3 steps
            for i in range(3):
                print(f"[Automator] Attempting to click Next step {i+1}...")
                time.sleep(5) # Wait for processing/UI
                
                next_selectors = [
                    "//div[@role='button']//span[translate(text(), 'NEXTTIEPTUCPublishÄÄƒng', 'nexttieptucpublishdang')='next' or translate(text(), 'NEXTTIEPTUCPublishÄÄƒng', 'nexttieptucpublishdang')='tiáº¿p' or translate(text(), 'NEXTTIEPTUCPublishÄÄƒng', 'nexttieptucpublishdang')='tiáº¿p tá»¥c']",
                    "//div[contains(@aria-label, 'Next') or contains(@aria-label, 'Tiáº¿p') or contains(@aria-label, 'Tiáº¿p tá»¥c')][@role='button']",
                    "//div[@role='button'][descendant::span[contains(text(), 'Next') or contains(text(), 'Tiáº¿p')]]",
                    "//span[text()='Next' or text()='Tiáº¿p' or text()='Tiáº¿p tá»¥c']/ancestor::div[@role='button']"
                ]
                
                clicked = False
                for sel in next_selectors:
                    try:
                        btns = self.driver.find_elements(By.XPATH, sel)
                        for btn in btns:
                            if btn.is_displayed() and btn.is_enabled():
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                                time.sleep(1)
                                self.driver.execute_script("arguments[0].click();", btn)
                                print(f"[Automator] Success clicking Next via: {sel}")
                                clicked = True
                                break
                        if clicked: break
                    except: continue
                
                if not clicked:
                    print(f"[Automator] Could not find Next button for step {i+1} via selectors. Logging all buttons:")
                    all_btns = self.driver.find_elements(By.XPATH, "//div[@role='button']")
                    for b in all_btns:
                        try:
                            t = b.text.strip().replace("\n", " ")
                            a = b.get_attribute("aria-label") or ""
                            if t or a:
                                print(f"  - Button: text='{t}', aria='{a}'")
                                if any(word in t.lower() or word in a.lower() for word in ["next", "tiáº¿p", "tiáº¿p tá»¥c", "publish", "Ä‘Äƒng", "chia sáº»"]):
                                    self.driver.execute_script("arguments[0].click();", b)
                                    print(f"  -> Clicked based on heuristic: {t}/{a}")
                                    clicked = True
                                    break
                        except: continue
                
                if not clicked:
                    print(f"[Automator] Step {i+1} Next button really not found, maybe reached end or not ready.")
                    time.sleep(5)
                else:
                    time.sleep(7) # Wait for page transition
            
            # Final Publish
            print("[Automator] Waiting for final Publish button...")
            publish_selectors = [
                "//div[@role='button']//span[text()='Publish' or text()='ÄÄƒng' or text()='Chia sáº»' or text()='Share']",
                "//div[contains(@aria-label, 'Publish') or contains(@aria-label, 'ÄÄƒng') or contains(@aria-label, 'Chia sáº»') or contains(@aria-label, 'Share')][@role='button']",
                "//div[@role='button'][descendant::span[contains(text(), 'Publish') or contains(text(), 'ÄÄƒng') or contains(text(), 'Chia sáº»')]]",
                "//span[text()='Publish' or text()='ÄÄƒng' or text()='Chia sáº»' or text()='Share']/ancestor::div[@role='button']"
            ]
            
            publish_clicked = False
            for sel in publish_selectors:
                try:
                    btns = self.driver.find_elements(By.XPATH, sel)
                    for btn in btns:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                            time.sleep(1)
                            self.driver.execute_script("arguments[0].click();", btn)
                            print(f"[Automator] Success clicking Publish via: {sel}")
                            publish_clicked = True
                            break
                    if publish_clicked: break
                except: continue
            
            if not publish_clicked:
                print("[Automator] No Publish button found via selectors. Searching by text...")
                all_b = self.driver.find_elements(By.XPATH, "//div[@role='button']")
                for b in all_b:
                    try:
                        txt = b.text.lower()
                        if any(w in txt for w in ["publish", "Ä‘Äƒng", "chia sáº»", "share"]):
                            self.driver.execute_script("arguments[0].click();", b)
                            print(f"[Automator] Clicked Publish via text search: {txt}")
                            publish_clicked = True
                            break
                    except: continue

            if publish_clicked:
                # Reverted: long wait loop here. Now handled by gui.py refreshing after success.
                return "Uploaded successfully"
            else:
                raise Exception("Could not find or click Publish button.")
            
        except Exception as e:
            print(f"[Automator] Error during upload: {e}")
            raise e

    def find_and_open_post(self, asset_id, title_text):
        """
        Navigates to Published Posts, finds post by title, and opens its details panel.
        Returns True if panel opened successfully, False otherwise.
        NOTE: This method no longer extracts the post link - it just opens the panel for commenting.
        """
        try:
            clean_title = self._get_clean_title(title_text)
            
            # Navigate to Published Posts page
            published_url = f"https://business.facebook.com/latest/posts/published_posts/?asset_id={asset_id}"
            print(f"[Automator] [Backup] Navigating to: {published_url}")
            self._safe_get(published_url)
            time.sleep(3)
            self._close_popups_v2()
            
            # Try to find and click the post with 3 scrolls
            for scroll_attempt in range(1, 4):
                print(f"[Automator] [Backup] Searching for post (Attempt {scroll_attempt}/3): {clean_title[:80]}...")
                target_post = self._find_target_post_element(clean_title)
                
                if target_post:
                    print(f"[Automator] [Backup] Found post. Opening panel...")
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_post)
                        time.sleep(2)
                        self.driver.execute_script("arguments[0].click();", target_post)
                        time.sleep(3)  # Wait for panel to open
                        print(f"[Automator] [Backup] Panel opened successfully.")
                        return True
                    except Exception as click_err:
                        print(f"[Automator] [Backup] Error opening panel: {click_err}")
                
                if scroll_attempt < 3:
                    print(f"[Automator] [Backup] Post not found. Attempting robust JS scroll...")
                    self._robust_js_scroll()
                    time.sleep(4) # Chá» load thÃªm ná»™i dung
                    self._close_popups_v2()
            
            print("[Automator] [Backup] Failed to find/open post after 3 scrolls.")
            return False
            
        except Exception as e:
            print(f"[Automator] [Backup] Error in find_and_open_post: {e}")
            return False

    def _get_clean_title(self, title_text):
        import re
        clean = re.sub(r'#\S+', '', title_text)
        clean = "".join(c for c in clean if ord(c) <= 0xFFFF)
        clean = re.sub(r'\s+', ' ', clean).strip()
        clean = clean.replace("'", "").replace('"', "")
        return clean

    def _robust_js_scroll(self):
        """
        Facebook uses nested flex containers with overflow. Scrolling window.scrollTo does not work.
        This JS snippet finds all scrollable div containers and scrolls them to the bottom.
        """
        js_scroll_all = """
        document.querySelectorAll('div').forEach(el => {
            if (el.scrollHeight > el.clientHeight && el.clientHeight > 300) {
                el.scrollTop = el.scrollHeight;
            }
        });
        """
        self.driver.execute_script(js_scroll_all)

    def _find_target_post_element(self, clean_title):
        """
        Searches for a post by iteratively reducing title length to find the best match.
        Now integrated with more specific container matching to avoid picking wrong posts.
        """
        lengths = [len(clean_title), 80, 60, 40, 25]
        lengths = sorted(list(set([l for l in lengths if l <= len(clean_title)])), reverse=True)
        
        # Priority 1: Elements inside potential post containers or with heading roles
        # Priority 2: Generic text matches
        
        container_xpaths = [
            # Business Suite Grid/Feed containers
            "//div[contains(@id, 'feed')]//*[contains(text(), '{0}')]",
            "//div[contains(@class, 'card')]//*[contains(text(), '{0}')]",
            "//div[@role='article']//*[contains(text(), '{0}')]",
            # Direct text match as fallback
            "//*[contains(text(), '{0}')]"
        ]

        # Temporarily disable implicit wait for fast scanning
        self.driver.implicitly_wait(0)
        
        try:
            for l in lengths:
                search_str = clean_title[0:l]
                if not search_str.strip(): continue
                
                for cx in container_xpaths:
                    try:
                        xpath_post = cx.format(search_str)
                        matches = self.driver.find_elements(By.XPATH, xpath_post)
                        for m in matches:
                            try:
                                if m.is_displayed():
                                    # Verify it's actually looking like a title (not too long, not an input)
                                    tag = m.tag_name.lower()
                                    if tag not in ['input', 'textarea', 'script', 'style']:
                                        return m
                            except: continue
                    except: continue
            return None
        finally:
            # Restore implicit wait
            self.driver.implicitly_wait(2)

    def comment_in_feed_grid(self, asset_id, title_text, comment_template):
        """
        Primary Strategy: Comment directly on the Feed and Grid page.
        Enhanced with robust selectors and better scrolling.
        """
        try:
            url = f"https://business.facebook.com/latest/posts/feed_and_grid?asset_id={asset_id}"
            print(f"[Automator] [Primary] Navigating to: {url}")
            self._safe_get(url)
            # Event-driven: proceed when page content appears
            self._wait_for_element(["//div[@role='main']", "//div[@role='article']"], timeout=5)
            self._close_popups_v2()
            
            # --- STEP 1: FIND POST CONTAINER WITH 3 SCROLLS ---
            clean_title = self._get_clean_title(title_text)
            
            target_post = None
            for scroll_attempt in range(1, 4):
                print(f"[Automator] [Primary] Searching for post (Attempt {scroll_attempt}/3): {clean_title[:80]}...")
                target_post = self._find_target_post_element(clean_title)
                
                if target_post:
                    print(f"[Automator] [Primary] Found post on attempt {scroll_attempt}.")
                    break
                
                if scroll_attempt < 3:
                    print(f"[Automator] [Primary] Post not found. Attempting robust JS scroll...")
                    self._robust_js_scroll()
                    # Event-driven: wait for new content to load (max 3s)
                    self._wait_for_element(["//div[@role='article']|//div[contains(@class,'card')]"], timeout=3)
                    self._close_popups_v2()
            
            if not target_post:
                print(f"[Automator] [Primary] Post '{clean_title[:40]}' not found after 3 scrolls.")
                return False, None

            # Scroll post into middle of screen
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_post)
            # No fixed sleep, proceed immediately
            
            # --- STEP 2: FIND COMMENT BOX OR BUTTON ---
            # Strategy: Sometimes the textbox is hidden behind a "Comment" button, 
            # and sometimes it's already visible as "Comment as..."
            
            # Sub-Strategy A: Look for "Comment as..." or Vietnamese equivalent directly
            textbox_selectors = [
                "//div[@role='textbox'][contains(@aria-label, 'Comment as') or contains(@aria-label, 'BÃ¬nh luáº­n dÆ°á»›i tÃªn') or contains(@aria-label, 'BÃ¬nh luáº­n vá»›i tÆ° cÃ¡ch')]",
                "//div[@role='textbox'][@aria-label='Write a comment...' or @aria-label='Viáº¿t bÃ¬nh luáº­n...']",
                "//div[@contenteditable='true']"
            ]
            
            # Sub-Strategy B: Look for "Comment" button to reveal textbox
            btn_selectors = [
                "//div[@aria-label='Leave a comment' or @aria-label='Viáº¿t bÃ¬nh luáº­n' or @aria-label='BÃ¬nh luáº­n']",
                "//div[@role='button'][descendant::span[contains(text(), 'Comment') or contains(text(), 'BÃ¬nh luáº­n')]]",
                "//span[contains(text(), 'Comment') or contains(text(), 'BÃ¬nh luáº­n')]/ancestor::div[@role='button']"
            ]
            
            textbox = None
            title_y = target_post.location['y']
            
            # Try to find textbox directly first (it's faster)
            for sel in textbox_selectors:
                elements = self.driver.find_elements(By.XPATH, sel)
                for el in elements:
                    try:
                        if el.is_displayed() and abs(el.location['y'] - title_y) < 1200:
                            textbox = el
                            break
                    except: continue
                if textbox: break

            # If no textbox, try the Comment button
            if not textbox:
                print("[Automator] [Primary] Textbox not visible. Searching for Comment button...")
                comment_btn = None
                for sel in btn_selectors:
                    btns = self.driver.find_elements(By.XPATH, sel)
                    min_dist = 1200
                    for b in btns:
                        try:
                            if b.is_displayed():
                                dist = abs(b.location['y'] - title_y)
                                if dist < min_dist:
                                    min_dist = dist
                                    comment_btn = b
                        except: continue
                    if comment_btn: break
                
                if comment_btn:
                    print("[Automator] [Primary] Found Comment button. Clicking...")
                    self.driver.execute_script("arguments[0].click();", comment_btn)
                    print("[Automator] [Primary] Waiting 5s for textbox to appear...")
                    time.sleep(5)
                    
                    # Re-search for textbox after click with detailed logging
                    print("[Automator] [Primary] Searching for textbox after click...")
                    for sel in textbox_selectors:
                        elements = self.driver.find_elements(By.XPATH, sel)
                        print(f"[Automator] [Primary] Selector '{sel[:50]}...' found {len(elements)} elements")
                        for el in elements:
                            try:
                                is_displayed = el.is_displayed()
                                el_y = el.location['y']
                                dist = abs(el_y - title_y)
                                aria = el.get_attribute('aria-label') or ''
                                print(f"[Automator] [Primary]   - Element: displayed={is_displayed}, dist={dist}, aria='{aria[:50]}'")
                                if is_displayed and dist < 1200:
                                    textbox = el
                                    print(f"[Automator] [Primary]   - SELECTED this textbox!")
                                    break
                            except Exception as e:
                                print(f"[Automator] [Primary]   - Error checking element: {e}")
                                continue
                        if textbox: break
                else:
                    print("[Automator] [Primary] No Comment button found.")
            
            if not textbox:
                print("[Automator] [Primary] Failed to find comment interaction area.")
                return False, None
            
            # --- STEP 3: TYPE AND POST ---
            spun_comment = self._spin_text(comment_template)
            clean_comment = "".join(c for c in spun_comment if ord(c) <= 0xFFFF)
            
            print(f"[Automator] [Primary] Posting comment: {clean_comment[:30]}...")
            
            # Use JS click to avoid interception
            self.driver.execute_script("arguments[0].click();", textbox)
            time.sleep(1)
            
            from selenium.webdriver.common.keys import Keys
            textbox.send_keys(Keys.CONTROL + "a")
            textbox.send_keys(Keys.BACKSPACE)
            
            lines = clean_comment.split('\n')
            for i, line in enumerate(lines):
                textbox.send_keys(line)
                if i < len(lines) - 1:
                    textbox.send_keys(Keys.SHIFT + Keys.ENTER)
            
            time.sleep(1)
            textbox.send_keys(Keys.ENTER)
            print("[Automator] [Primary] Comment sent. Verifying submission...")
            
            # --- STEP 4: VERIFY COMMENT POSTED ---
            verified = self._verify_comment_posted()
            
            if not verified:
                print("[Automator] [Primary] Warning: Could not verify comment was posted.")
                return False, None
            
            print("[Automator] [Primary] Comment verified successfully!")
            
            # --- STEP 5: FETCH LINK ---
            post_link = None
            try:
                all_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/posts/') or contains(@href, '/videos/')]")
                for l in all_links:
                    try:
                        if abs(l.location['y'] - title_y) < 400:
                            href = l.get_attribute("href")
                            if "facebook.com" in href:
                                post_link = href
                                break
                    except: continue
            except: pass
            
            return True, post_link

        except Exception as e:
            print(f"[Automator] [Primary] Error during Feed \u0026 Grid comment: {e}")
            return False, None

    def _verify_comment_posted(self):
        """
        Verify that a comment was successfully posted by checking for the 'Remove Preview' clickable text.
        Checks 3 times with 5-second intervals to account for network lag and Facebook moderation.
        """
        preview_selectors = [
            # Clickable text elements (span, a, div)
            "//span[contains(text(), 'Remove preview') or contains(text(), 'Gá»¡ báº£n xem trÆ°á»›c')]",
            "//a[contains(text(), 'Remove preview') or contains(text(), 'Gá»¡ báº£n xem trÆ°á»›c')]",
            "//div[contains(text(), 'Remove preview') or contains(text(), 'Gá»¡ báº£n xem trÆ°á»›c')]",
            # Case-insensitive search
            "//*[contains(translate(text(), 'REMOVE PREVIEW', 'remove preview'), 'remove preview')]",
            "//*[contains(translate(text(), 'Gá»  Báº¢N XEM TRÆ¯á»šC', 'gá»¡ báº£n xem trÆ°á»›c'), 'gá»¡ báº£n xem trÆ°á»›c')]"
        ]
        
        for attempt in range(3):
            print(f"[Automator] Verification attempt {attempt+1}/3...")
            # Event-driven: check immediately, wait up to 3s between tries
            self.driver.implicitly_wait(0)
            try:
                for sel in preview_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, sel)
                        for elem in elements:
                            try:
                                if elem.is_displayed():
                                    txt = elem.text.strip()
                                    if txt and ("remove" in txt.lower() or "gá»¡" in txt.lower()):
                                        print(f"[Automator] ✓ Found Remove Preview text: '{txt}'")
                                        return True
                            except: continue
                    except: continue
            finally:
                self.driver.implicitly_wait(10)
        
        print("[Automator] âœ— Remove Preview text not found after 3 attempts.")
        return False

    def comment_in_published_posts_inline(self, asset_id, title_text, comment_template):
        """
        Tier 3: Comment directly on Published Posts list without opening panel.
        Similar to Feed & Grid but on the Published Posts page.
        """
        try:
            url = f"https://business.facebook.com/latest/posts/published_posts/?asset_id={asset_id}"
            print(f"[Automator] [Tier3] Navigating to: {url}")
            self._safe_get(url)
            # Event-driven: proceed when published posts appear
            self._wait_for_element(["//div[@role='main']", "//div[@role='article']"], timeout=5)
            self._close_popups_v2()
            
            # --- FIND POST WITH 3 SCROLLS ---
            clean_title = self._get_clean_title(title_text)
            
            target_post = None
            for scroll_attempt in range(1, 4):
                print(f"[Automator] [Tier3] Searching for post (Attempt {scroll_attempt}/3): {clean_title[:80]}...")
                target_post = self._find_target_post_element(clean_title)
                
                if target_post:
                    print(f"[Automator] [Tier3] Found post on attempt {scroll_attempt}.")
                    break
                
                if scroll_attempt < 3:
                    print(f"[Automator] [Tier3] Post not found. Attempting robust JS scroll...")
                    self._robust_js_scroll()
                    time.sleep(4)
                    self._close_popups_v2()
            
            if not target_post:
                print(f"[Automator] [Tier3] Post '{clean_title[:40]}' not found after 3 scrolls.")
                return False, None

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_post)
            time.sleep(2)
            
            # Try to find comment textbox or button
            textbox_selectors = [
                "//div[@role='textbox'][contains(@aria-label, 'Comment as') or contains(@aria-label, 'BÃ¬nh luáº­n dÆ°á»›i tÃªn')]",
                "//div[@contenteditable='true']"
            ]
            
            btn_selectors = [
                "//div[@aria-label='Leave a comment' or @aria-label='Viáº¿t bÃ¬nh luáº­n' or @aria-label='BÃ¬nh luáº­n']",
                "//span[contains(text(), 'Comment') or contains(text(), 'BÃ¬nh luáº­n')]/ancestor::div[@role='button']"
            ]
            
            textbox = None
            title_y = target_post.location['y']
            
            # Try textbox first
            for sel in textbox_selectors:
                elements = self.driver.find_elements(By.XPATH, sel)
                for el in elements:
                    try:
                        if el.is_displayed() and abs(el.location['y'] - title_y) < 1200:
                            textbox = el
                            break
                    except: continue
                if textbox: break

            # If no textbox, try button
            if not textbox:
                for sel in btn_selectors:
                    btns = self.driver.find_elements(By.XPATH, sel)
                    for b in btns:
                        try:
                            if b.is_displayed() and abs(b.location['y'] - title_y) < 1200:
                                self.driver.execute_script("arguments[0].click();", b)
                                time.sleep(3)
                                # Re-search for textbox
                                for t_sel in textbox_selectors:
                                    elements = self.driver.find_elements(By.XPATH, t_sel)
                                    for el in elements:
                                        try:
                                            if el.is_displayed() and abs(el.location['y'] - title_y) < 1200:
                                                textbox = el
                                                break
                                        except: continue
                                    if textbox: break
                                break
                        except: continue
                    if textbox: break
            
            if not textbox:
                print("[Automator] [Tier3] Could not find comment area.")
                return False, None
            
            # Post comment
            spun_comment = self._spin_text(comment_template)
            clean_comment = "".join(c for c in spun_comment if ord(c) <= 0xFFFF)
            
            textbox.click()
            time.sleep(1)
            
            from selenium.webdriver.common.keys import Keys
            textbox.send_keys(Keys.CONTROL + "a")
            textbox.send_keys(Keys.BACKSPACE)
            
            lines = clean_comment.split('\n')
            for i, line in enumerate(lines):
                textbox.send_keys(line)
                if i < len(lines) - 1:
                    textbox.send_keys(Keys.SHIFT + Keys.ENTER)
            
            time.sleep(1)
            textbox.send_keys(Keys.ENTER)
            print("[Automator] [Tier3] Comment sent. Verifying...")
            
            # Verify
            verified = self._verify_comment_posted()
            if not verified:
                print("[Automator] [Tier3] Verification failed.")
                return False, None
            
            print("[Automator] [Tier3] Comment verified!")
            return True, None

        except Exception as e:
            print(f"[Automator] [Tier3] Error: {e}")
            return False, None

    def comment_in_insights_overview(self, asset_id, title_text, comment_template):
        """
        Tier 4: Comment via Insights Overview.
        Navigates to Insights Overview, finds the post, opens panel, and posts comment.
        """
        try:
            url = f"https://business.facebook.com/latest/insights/overview/?asset_id={asset_id}&business_id=1016985112612772"
            print(f"[Automator] [Tier4] Navigating to: {url}")
            self._safe_get(url)
            time.sleep(3)
            self._close_popups_v2()
            
            clean_title = self._get_clean_title(title_text)
        
            panel_opened = False
            for scroll_attempt in range(1, 4):
                print(f"[Automator] [Tier4] Searching for post (Attempt {scroll_attempt}/3): {clean_title[:80]}...")
                target_match = self._find_target_post_element(clean_title)
                
                if target_match:
                    print(f"[Automator] [Tier4] Found post. Opening panel...")
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_match)
                        time.sleep(2)
                        self.driver.execute_script("arguments[0].click();", target_match)
                        time.sleep(3)
                        panel_opened = True
                        break
                    except Exception as e:
                        print(f"[Automator] [Tier4] Error opening panel: {e}")
                
                if scroll_attempt < 3:
                    print(f"[Automator] [Tier4] Post not found. Attempting robust JS scroll...")
                    self._robust_js_scroll()
                    time.sleep(4)
                    self._close_popups_v2()
            
            if not panel_opened:
                print("[Automator] [Tier4] Post not found or could not open panel.")
                return False, None
            
            print("[Automator] [Tier4] Panel opened. Attempting to comment...")
            success = self.post_comment_on_panel(comment_template)
            
            link = None
            if success:
                try:
                    links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/videos/') or contains(@href, '/posts/')]")
                    for l in links:
                        href = l.get_attribute("href")
                        if href and "facebook.com" in href:
                            link = href
                            break
                except: pass
            
            return success, link

        except Exception as e:
            print(f"[Automator] [Tier4] Error: {e}")
            return False, None

    def comment_in_insights_base(self, asset_id, title_text, comment_template):
        """
        Tier 5: Comment via Base Insights Content.
        Navigates to Insights Content, finds the post, opens panel, and posts comment.
        """
        try:
            url = f"https://business.facebook.com/latest/insights/content?asset_id={asset_id}&business_id=1016985112612772"
            print(f"[Automator] [Tier5] Navigating to: {url}")
            self._safe_get(url)
            time.sleep(3)
            self._close_popups_v2()
            
            clean_title = self._get_clean_title(title_text)
        
            panel_opened = False
            for scroll_attempt in range(1, 4):
                print(f"[Automator] [Tier5] Searching for post (Attempt {scroll_attempt}/3): {clean_title[:80]}...")
                target_match = self._find_target_post_element(clean_title)
                
                if target_match:
                    print(f"[Automator] [Tier5] Found post. Opening panel...")
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_match)
                        time.sleep(2)
                        self.driver.execute_script("arguments[0].click();", target_match)
                        time.sleep(3)
                        panel_opened = True
                        break
                    except Exception as e:
                        print(f"[Automator] [Tier5] Error opening panel: {e}")
                
                if scroll_attempt < 3:
                    print(f"[Automator] [Tier5] Post not found. Attempting robust JS scroll...")
                    self._robust_js_scroll()
                    time.sleep(4)
                    self._close_popups_v2()
            
            if not panel_opened:
                print("[Automator] [Tier5] Post not found or could not open panel.")
                return False, None
            
            print("[Automator] [Tier5] Panel opened. Attempting to comment...")
            success = self.post_comment_on_panel(comment_template)
            
            link = None
            if success:
                try:
                    links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/videos/') or contains(@href, '/posts/')]")
                    for l in links:
                        href = l.get_attribute("href")
                        if href and "facebook.com" in href:
                            link = href
                            break
                except: pass
            
            return success, link

        except Exception as e:
            print(f"[Automator] [Tier5] Error: {e}")
            return False, None

    def comment_via_home_scroll(self, asset_id, title_text, comment_template):
        """
        New Tier: Navigate to Home -> Scroll 5 times -> find post -> comment.
        """
        try:
            clean_title = self._get_clean_title(title_text)
            
            home_url = f"https://business.facebook.com/latest/home?asset_id={asset_id}"
            print(f"[Automator] [HomeTier] Navigating to Home: {home_url}")
            self._safe_get(home_url)
            time.sleep(5)
            self._close_popups_v2()
            
            panel_opened = False
        
            for scroll_attempt in range(1, 6): # Increased to 5 scrolls for better results on Home
                print(f"[Automator] [HomeTier] Scroll Attempt {scroll_attempt}/5 via JS...")
                
                self._robust_js_scroll()
                time.sleep(4)
                self._close_popups_v2()
                
                target_match = self._find_target_post_element(clean_title)
                
                if target_match:
                    print(f"[Automator] [HomeTier] Found post on Home. Opening panel...")
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_match)
                        time.sleep(1)
                        self.driver.execute_script("arguments[0].click();", target_match)
                        time.sleep(5)
                        panel_opened = True
                        break
                    except: continue
                else:
                    print(f"[Automator] [HomeTier] Post not found in attempt {scroll_attempt}.")

            if not panel_opened:
                print("[Automator] [HomeTier] Post not found on Home page after 5 scrolls.")
                return False, None
                
            self._close_popups_v2()
            print("[Automator] [HomeTier] Panel opened. Attempting to comment...")
            success = self.post_comment_on_panel(comment_template)
            
            link = None
            if success:
                try:
                    links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/videos/') or contains(@href, '/posts/')]")
                    for l in links:
                        href = l.get_attribute("href")
                        if href and "facebook.com" in href:
                            link = href
                            break
                except: pass
            
            return success, link

        except Exception as e:
            print(f"[Automator] [HomeTier] Error: {e}")
            return False, None

    def comment_with_dual_strategy(self, asset_id, title_text, comment_template):
        """
        Dynamically executes enabled commenting strategies in priority order.
        Respects the 'comment_strategies' configuration from the UI.
        """
        
        # Define all available strategies in priority order
        strategy_map = [
            ("home_scroll", "Home Scroll Page", self.comment_via_home_scroll),
            ("feed_grid", "Feed & Grid Page", self.comment_in_feed_grid),
            ("published_panel", "Published Posts (Panel)", lambda a, t, c: self._backup_panel_flow(a, t, c)),
            ("published_inline", "Published Posts (Inline)", self.comment_in_published_posts_inline),
            ("insight_overview", "Insights Overview", self.comment_in_insights_overview),
            ("insight_content", "Insights Content", self.comment_in_insights_base)
        ]

        active_strategies = []
        for key, name, func in strategy_map:
            if self.strategies.get(key, True):
                active_strategies.append((name, func))
        
        if not active_strategies:
            print("[Automator] No commenting strategies enabled in settings!")
            return False, None

        print(f"[Automator] Starting custom strategy chain with {len(active_strategies)} methods.")
        
        for name, func in active_strategies:
            print(f"[Automator] >>> Trying Strategy: {name}")
            
            # Check for block before starting each tier
            if self._check_for_block():
                print(f"[Automator] âš ï¸ Facebook temporary block detected! Cannot proceed with {name}.")
                # If Home or Feed is blocked, usually all are blocked. We stop here.
                break
            
            try:
                # Most functions take (asset_id, title_text, comment_template)
                # Some are lambda wrappers
                success, link = func(asset_id, title_text, comment_template)
                
                if self._check_for_block():
                    print(f"[Automator] âš ï¸ Facebook temporary block detected after {name} attempt!")
                    break
                    
                if success:
                    print(f"[Automator] ✓ Strategy {name} Succeeded!")
                    return True, link
                    
                print(f"[Automator] âœ— Strategy {name} failed. Moving to next...")
            except Exception as e:
                print(f"[Automator] ! Error in Strategy {name}: {e}")
            
            time.sleep(5) # Small gap between tiers

        print("[Automator] All enabled strategies failed.")
        return False, None

    def _backup_panel_flow(self, asset_id, title_text, comment_template):
        """ Helper for Published Posts Panel strategy """
        panel_opened = self.find_and_open_post(asset_id, title_text)
        if panel_opened:
            success = self.post_comment_on_panel(comment_template)
            if success:
                link = None
                try:
                    links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/videos/')]")
                    for l in links:
                        href = l.get_attribute("href")
                        if href and "facebook.com" in href:
                            link = href
                            break
                except: pass
                return True, link
        return False, None

    def _spin_text(self, text):
        import re
        import random
        while True:
            match = re.search(r'\{([^{}]+)\}', text)
            if not match:
                break
            options = match.group(1).split('|')
            text = text.replace(match.group(0), random.choice(options), 1)
        return text

    def _check_for_block(self):
        """
        Checks for Facebook's 'You're Temporarily Blocked' dialog/modal.
        Returns True if blocked, False otherwise.
        """
        try:
            # check page source first (fastest)
            src = self.driver.page_source
            if "Youâ€™re Temporarily Blocked" in src or "You're Temporarily Blocked" in src or \
               "Youâ€™re temporarily blocked" in src or "You're temporarily blocked" in src or \
               "Báº¡n táº¡m thá»i bá»‹ cháº·n" in src or "bá»‹ cháº·n táº¡m thá»i" in src:
               print("[Automator] âš ï¸ Block detected in page source.")
               return True

            # check specific dialogs (more reliable for dynamic modals)
            block_selectors = [
                "//div[@role='dialog'][contains(., 'Temporarily Blocked')]",
                "//div[@role='dialog'][contains(., 'táº¡m thá»i bá»‹ cháº·n')]",
                "//span[contains(text(), 'Temporarily Blocked')]",
                "//span[contains(text(), 'táº¡m thá»i bá»‹ cháº·n')]",
                "//*[contains(text(), 'It looks like you were misusing this feature')]"
            ]
            
            for sel in block_selectors:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        if el.is_displayed():
                            print(f"[Automator] âš ï¸ Block modal detected via selector: {sel}")
                            return True
                except: continue
                
            return False
        except:
            return False

    def post_comment_on_panel(self, comment_template):
        if not comment_template: return False
        
        spun_comment = self._spin_text(comment_template)
        # Filter emojis for selenium
        spun_comment = "".join(c for c in spun_comment if ord(c) <= 0xFFFF)
        
        print(f"[Automator] Attempting to post auto-comment: {spun_comment}")
        
        selectors = [
            "//div[@role='textbox'][contains(@aria-label, 'comment') or contains(@aria-label, 'bÃ¬nh luáº­n')]",
            "//div[@role='textbox'][@contenteditable='true']",
            "//div[@aria-placeholder='BÃ¬nh luáº­n...' or @aria-placeholder='Viáº¿t bÃ¬nh luáº­n...']",
            "//div[@aria-label='BÃ¬nh luáº­n...' or @aria-label='BÃ¬nh luáº­n']",
            "//textarea[contains(@placeholder, 'comment') or contains(@placeholder, 'bÃ¬nh luáº­n')]",
            "//div[contains(@class, 'comment')]//div[@role='textbox']",
            "//div[@role='dialog']//div[@role='textbox']",
            "//div[contains(@style, 'editor')]//div[@role='textbox']",
            "//div[@contenteditable='true']"
        ]
        
        try:
            comment_box = None
            # Event-driven: wait up to 10s for comment box to appear
            found, comment_box = self._wait_for_element(selectors, timeout=10)
            
            if comment_box:
                # Scroll into view with offset to avoid sticky header
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_box)
                # No fixed sleep: proceed immediately after scroll
                
                # Use JS click for reliability and wait for focus
                self.driver.execute_script("arguments[0].click();", comment_box)
                time.sleep(0.3)
                
                # Clear if needed (though usually empty)
                # For role=textbox we might need to select all and delete
                from selenium.webdriver.common.keys import Keys
                
                # Split by lines if multi-line template given
                lines = spun_comment.split('\n')
                for i, line in enumerate(lines):
                    comment_box.send_keys(line)
                    if i < len(lines) - 1:
                        comment_box.send_keys(Keys.SHIFT + Keys.ENTER) # New line in FB comment
                
                time.sleep(1)
                comment_box.send_keys(Keys.ENTER)
                print("[Automator] Comment sent. Waiting for link preview (Remove preview button)...")
                
                # Verification loop: Wait for "Remove preview" or "Gá»¡ báº£n xem trÆ°á»›c" within Feed preview area
                preview_selectors = [
                    "//div[contains(@aria-label, 'Feed preview') or contains(@aria-label, 'Xem trÆ°á»›c báº£ng feed')]//div[@role='button'][contains(@aria-label, 'Remove preview') or contains(@aria-label, 'Gá»¡ báº£n xem trÆ°á»›c') or contains(@aria-label, 'remove preview') or contains(@aria-label, 'gá»¡ báº£n xem trÆ°á»›c')]",
                    "//div[contains(@aria-label, 'Feed preview') or contains(@aria-label, 'Xem trÆ°á»›c báº£ng feed')]//div[contains(@aria-label, 'Remove preview') or contains(@aria-label, 'Gá»¡ báº£n xem trÆ°á»›c') or contains(@aria-label, 'remove preview') or contains(@aria-label, 'gá»¡ báº£n xem trÆ°á»›c')]",
                    "//div[contains(@aria-label, 'Feed preview') or contains(@aria-label, 'Xem trÆ°á»›c báº£ng feed')]//*[contains(text(), 'Remove preview') or contains(text(), 'Gá»¡ báº£n xem trÆ°á»›c') or contains(text(), 'remove preview') or contains(text(), 'gá»¡ báº£n xem trÆ°á»›c')]",
                    "//div[@role='dialog']//div[@role='button'][contains(@aria-label, 'Remove') or contains(@aria-label, 'Gá»¡')]",
                    "//div[@role='dialog']//*[contains(text(), 'Remove preview') or contains(text(), 'Gá»¡ báº£n xem trÆ°á»›c')]"
                ]
                
                found_preview = False
                # use _wait_for_element for immediate proceed when found
                found_preview, _ = self._wait_for_element(preview_selectors, timeout=4)
                
                if found_preview:
                    print("[Automator] Link preview detected (Remove preview button found in Feed preview).")
                else:
                    print("[Automator] Notice: No removable preview detected after 4s (Proceeding).")
                    # Log Feed preview area for debugging
                    print("[Automator] Logging buttons in Feed preview/dialog area:")
                    feed_area = self.driver.find_elements(By.XPATH, "//div[contains(@aria-label, 'Feed preview') or contains(@aria-label, 'Xem trÆ°á»›c báº£ng feed') or @role='dialog']")
                    if feed_area:
                        btns_in_feed = feed_area[0].find_elements(By.XPATH, ".//div[@role='button'] | .//a[@role='button']")
                        for b in btns_in_feed[:15]:
                            try:
                                if b.is_displayed():
                                    aria = b.get_attribute("aria-label") or ""
                                    txt = b.text.strip()[:50] or ""
                                    print(f"  - aria='{aria}', text='{txt}'")
                            except: continue
                    else:
                        print("  - Could not find Feed preview area")

                print("[Automator] Comment posting task complete.")
                return True
            else:
                print("[Automator] Could not find comment box in panel.")
                return False
        except Exception as e:
            print(f"[Automator] Error posting comment: {e}")
            return False

            self.driver.implicitly_wait(0)
            try:
                # 0. Intercept "Get started" screen
                go_home_selectors = [
                    "//div[@role='button'][contains(., 'Go to Home') or contains(., 'Äi Ä‘áº¿n trang chá»§') or contains(., 'Äi Ä‘áº¿n Trang chá»§')]",
                    "//div[@role='button'][descendant::span[text()='Go to Home' or text()='Äi Ä‘áº¿n trang chá»§']]"
                ]
                for sel in go_home_selectors:
                    try:
                        btns = self.driver.find_elements(By.XPATH, sel)
                        for b in btns:
                            if b.is_displayed():
                                self.log(f"â„¹ï¸ Detected 'Get started' screen. Clicking '{b.text}'...")
                                self.driver.execute_script("arguments[0].click();", b)
                                time.sleep(5)
                                return True 
                    except: pass

                # SÆ¡ kiá»ƒm xem có dáº¥u hiá»‡u của modal/dialog/overlay khÃ´ng
                overlay_indicators = [
                    "//div[@role='dialog']",
                    "//div[contains(@class, 'x1n2onr6') and contains(@class, 'x1vjfegm')]", # Lá»›p má» của FB
                    "//div[contains(@style, 'z-index')]",
                    "//*[text()='Dismiss' or text()='Bỏ qua' or text()='Xong' or text()='Done' or text()='Get Started' or text()='Bắt đầu']"
                ]
                
                has_popup = False
                for ind in overlay_indicators[:3]: 
                    if self.driver.find_elements(By.XPATH, ind):
                        has_popup = True
                        break
                
                if not has_popup:
                    return False

                # NÃºt Æ°u tiÃªn: HoÃ n táº¥t, Bỏ qua, Xong
                popup_selectors = [
                    "//div[@role='button'][contains(., 'Done') or contains(., 'Xong') or contains(., 'HoÃ n táº¥t')]",
                    "//div[@role='button'][contains(., 'Dismiss') or contains(., 'Bỏ qua')]",
                    "//div[@role='button'][contains(., 'OK') or contains(., 'Ok')]",
                    "//div[@role='button'][contains(., 'Show later') or contains(., 'Hiá»ƒn thá»‹ sau') or contains(., 'Äá»ƒ sau') or contains(., 'LÃºc khÃ¡c')]",
                    "//div[@role='button'][@aria-label='Close' or @aria-label='ÄÃ³ng' or @aria-label='Dismiss']",
                    "//div[@aria-label='Close' or @aria-label='ÄÃ³ng']",
                    "//div[@role='dialog']//i[@data-visualcompletion='css-img' and parent::div[@role='button']]",
                    "//div[@role='dialog']//div[contains(@class, 'x1i10hfl')]//div[@role='button'][.//i]"
                ]
                
                closed_any = False
                for _ in range(3):
                    found_in_round = False
                    for sel in popup_selectors:
                        try:
                            elements = self.driver.find_elements(By.XPATH, sel)
                            for el in elements:
                                if el.is_displayed():
                                    self.log(f"â„¹ï¸ Closing detected popup: {sel}")
                                    self.driver.execute_script("arguments[0].click();", el)
                                    time.sleep(1.5)
                                    found_in_round = True
                                    closed_any = True
                                    break 
                            if found_in_round: break
                        except: continue
                    if not found_in_round:
                        break
                    
                return closed_any
            finally:
                self.driver.implicitly_wait(10)
        except:
            return False

    def _safe_get(self, url):
        """
        Navigates to a URL while handling blocking alerts and using timeouts.
        """
        try:
            # First try to handle any existing alert
            try:
                alert = self.driver.switch_to.alert
                print(f"[Automator] [Alert] Dismissing pre-navigation alert: {alert.text}")
                alert.dismiss()
            except: pass
            
            print(f"[Automator] Navigating to: {url}")
            self.driver.get(url)
        except Exception as e:
            print(f"[Automator] [Navigation Error] {e}. Trying JS fallback...")
            try:
                self.driver.execute_script(f"window.location.href = '{url}';")
            except:
                print("[Automator] [Severe] Navigation failed even via JS.")

    def close(self):
        self.driver.quit()
