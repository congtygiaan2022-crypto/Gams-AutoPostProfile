"""
Reels Inspector — kết nối vào browser GPM đang chạy, điều hướng đến Reels Create,
upload 1 video test, chụp screenshot tại bước Next và dump toàn bộ button DOM.
Chạy: python reels_inspector.py
"""
import os, json, time, sys, glob, requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

# ─── CẤU HÌNH ─────────────────────────────────────────────────────────────────
GPM_PORT       = "19995"
PROFILE_ID     = "03ade8a9-3727-476c-a0fe-b19b795da82d"
DRIVER_PATH    = r"F:\phan_mem\GPM_nhhtool\GPMLogin\gpm_browser\gpm_browser_chromium_core_139\gpmdriver.exe"
OUTPUT_DIR     = os.path.dirname(os.path.abspath(__file__))

# Video test — tìm bất kỳ file .mp4 nào trong thư mục downloads
VIDEO_FOLDERS = [
    r"G:\Documentss\Antigravity_Gams_Youtubedownload\downloads",
    r"G:\Documentss",
    OUTPUT_DIR,
]

def find_test_video():
    for folder in VIDEO_FOLDERS:
        hits = glob.glob(os.path.join(folder, "**", "*.mp4"), recursive=True)
        if hits:
            return hits[0]
    return None

# ─── STEP 1: Lấy debug address từ GPM ────────────────────────────────────────
def get_debug_address():
    url = f"http://127.0.0.1:{GPM_PORT}/api/v3/profiles/start/{PROFILE_ID}"
    try:
        r = requests.get(url, timeout=30)
        data = r.json()
        if data.get("success"):
            return data["data"]["remote_debugging_address"], data["data"].get("driver_path", DRIVER_PATH)
        # Already open — get from list
        r2 = requests.get(f"http://127.0.0.1:{GPM_PORT}/api/v3/profiles", timeout=10)
        for p in r2.json().get("data", []):
            if p.get("profile_id") == PROFILE_ID:
                dbg = p.get("remote_debugging_address", "")
                if dbg: return dbg, DRIVER_PATH
    except Exception as e:
        print(f"GPM API error: {e}")
    # Fallback: last known port
    return "127.0.0.1:55231", DRIVER_PATH

# ─── STEP 2: Kết nối Selenium ─────────────────────────────────────────────────
def connect(debug_addr, driver_path):
    import socket
    host, port = debug_addr.split(":")
    # Phase A: port open?
    for _ in range(15):
        with socket.socket() as s:
            s.settimeout(1)
            if s.connect_ex((host, int(port))) == 0: break
        time.sleep(1)
    # Phase B: page target?
    for _ in range(30):
        try:
            targets = requests.get(f"http://{host}:{port}/json", timeout=5).json()
            if any(t["type"] == "page" for t in targets): break
            requests.put(f"http://{host}:{port}/json/new", timeout=3)
        except: pass
        time.sleep(1)

    opts = Options()
    opts.add_experimental_option("debuggerAddress", debug_addr)
    svc = Service(executable_path=driver_path) if os.path.exists(driver_path) else None
    for _ in range(5):
        try:
            d = webdriver.Chrome(service=svc, options=opts) if svc else webdriver.Chrome(options=opts)
            d.set_page_load_timeout(120)
            d.implicitly_wait(5)
            print(f"Connected. Current URL: {d.current_url}")
            return d
        except Exception as e:
            print(f"Retry connect: {e}")
            try: requests.put(f"http://{host}:{port}/json/new", timeout=3)
            except: pass
            time.sleep(5)
    raise RuntimeError("Cannot connect to browser")

# ─── STEP 3: Dump buttons ─────────────────────────────────────────────────────
def dump_buttons(driver, label):
    data = driver.execute_script("""
        return Array.from(document.querySelectorAll(
            'div[role="button"],button,span[role="button"],div[aria-label],div[class*="x1n2onr6"]'
        )).map(el => {
            let r = el.getBoundingClientRect();
            return {
                tag: el.tagName,
                text: el.innerText.trim().substring(0, 60),
                aria: el.getAttribute('aria-label'),
                role: el.getAttribute('role'),
                cls_snippet: (el.className || '').substring(0, 80),
                vis: el.offsetHeight > 0 && el.offsetWidth > 0,
                rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}
            };
        }).filter(b => b.vis && (b.text || b.aria));
    """)
    out = os.path.join(OUTPUT_DIR, f"buttons_{label}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[{label}] Dumped {len(data)} buttons → {out}")
    # Quick summary
    for b in data[:30]:
        print(f"  [{b['rect']['x']},{b['rect']['y']}] [{b['rect']['w']}x{b['rect']['h']}] "
              f"role={b['role']} text='{b['text'][:40]}' aria='{(b['aria'] or '')[:40]}'")
    return data

def screenshot(driver, label):
    path = os.path.join(OUTPUT_DIR, f"screen_{label}.png")
    driver.save_screenshot(path)
    print(f"Screenshot saved: {path}")
    return path

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    video = find_test_video()
    if not video:
        print("ERROR: Không tìm thấy file .mp4 nào để test!")
        return
    print(f"Test video: {video}")

    debug_addr, driver_path = get_debug_address()
    print(f"Debug address: {debug_addr}")

    driver = connect(debug_addr, driver_path)

    # Switch to best available tab (avoid extension background pages)
    print(f"Current URL after connect: {driver.current_url}")
    handles = driver.window_handles
    print(f"Available tabs: {len(handles)}")
    switched = False
    for h in handles:
        try:
            driver.switch_to.window(h)
            url = driver.current_url.lower()
            print(f"  Tab: {url[:80]}")
            if "facebook.com" in url:
                print("  -> Switching to Facebook tab")
                switched = True
                break
        except: pass
    if not switched:
        # Find any non-extension, navigable tab
        navigable = ["blank", "newtab", "chrome://new-tab-page", "about:"]
        for h in handles:
            try:
                driver.switch_to.window(h)
                url = driver.current_url.lower()
                is_ext = url.startswith("chrome-extension://")
                if not is_ext:
                    print(f"  -> Switching to navigable tab: {url}")
                    switched = True
                    break
            except: pass
    if not switched:
        driver.switch_to.window(handles[0])
        print(f"  -> Fallback to first tab: {driver.current_url}")

    # Navigate
    print("Navigating to Reels Create...")
    try:
        driver.get("https://www.facebook.com/reels/create")
    except Exception as e:
        print(f"Navigation error (may be OK): {e}")
    time.sleep(12)
    screenshot(driver, "01_reels_create")

    # Wait for file input
    file_input = None
    for _ in range(30):
        els = driver.find_elements(By.XPATH, "//input[@type='file']")
        if els:
            file_input = els[0]
            break
        time.sleep(2)

    if not file_input:
        print("ERROR: No file input found!")
        dump_buttons(driver, "no_file_input")
        screenshot(driver, "02_no_file_input")
        return

    print(f"Found file input. Uploading: {video}")
    driver.execute_script("""
        arguments[0].style.display='block'; arguments[0].style.opacity='1';
        arguments[0].style.position='fixed'; arguments[0].style.top='0';
        arguments[0].style.left='0'; arguments[0].style.width='50px'; arguments[0].style.height='50px';
    """, file_input)
    file_input.send_keys(video)
    print("Video sent. Waiting for processing...")

    # Wait up to 60s for Next/Share to appear
    next_btn = None
    for i in range(60):
        time.sleep(1)
        btns = driver.find_elements(By.XPATH,
            "//*[contains(text(),'Next') or contains(text(),'Tiếp') or contains(text(),'Share') or contains(text(),'Chia sẻ')]"
        )
        visible = [b for b in btns if b.is_displayed()]
        if visible:
            next_btn = visible[0]
            print(f"Next/Share button appeared after {i+1}s: '{next_btn.text}'")
            break
        if i % 10 == 9:
            print(f"  Still waiting... {i+1}s")

    screenshot(driver, "03_after_upload")
    dump_buttons(driver, "03_after_upload")

    if not next_btn:
        print("ERROR: Next button never appeared!")
        return

    # ─── THIS IS THE KEY STEP: dump buttons inside dialog ─────────────────
    print("\n=== INSPECTING DIALOG ===")
    dialogs = driver.find_elements(By.XPATH, "//div[@role='dialog']")
    print(f"Found {len(dialogs)} dialog(s)")
    
    if dialogs:
        dlg = dialogs[-1]
        dlg_buttons = dlg.find_elements(By.XPATH,
            ".//*[self::div or self::span or self::button]"
        )
        print(f"Total elements in dialog: {len(dlg_buttons)}")
        
        # Find ones with text
        with_text = [(b.text.strip(), b.get_attribute("role"), b.get_attribute("aria-label"), b.get_attribute("class")) 
                     for b in dlg_buttons 
                     if b.text.strip() and b.is_displayed()]
        
        out = os.path.join(OUTPUT_DIR, "dialog_elements.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump([{"text": t, "role": r, "aria": a, "cls": (c or "")[:100]} 
                      for t,r,a,c in with_text], f, indent=2, ensure_ascii=False)
        print(f"Dialog text elements saved → {out}")
        print("\nFirst 20 visible text elements in dialog:")
        for t, r, a, c in with_text[:20]:
            print(f"  role='{r}' aria='{a}' text='{t[:50]}'")

    # Try to click Next
    print("\n=== CLICKING NEXT ===")
    from selenium.webdriver.common.action_chains import ActionChains
    ActionChains(driver).move_to_element(next_btn).click().perform()
    time.sleep(5)
    screenshot(driver, "04_after_next_click")
    dump_buttons(driver, "04_after_next_click")
    print(f"URL after click: {driver.current_url}")

if __name__ == "__main__":
    main()
