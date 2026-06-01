"""
page_worker.py - Per-profile CMD subprocess worker
===================================================
Called by gui.py to run all work tasks for ONE browser profile.
Each instance runs in its own CMD window for full isolation.

Usage: python page_worker.py <job_json_file>

job_json_file: path to a temp JSON file containing:
{
    "run_mode": "post_and_comment",
    "skip_commented": true,
    "auto_delete": true,
    "browser_config": {...},
    "profile_id": "3",
    "pages": [
        {
            "name": "Nick Cá Nhân A",
            "link": "https://...",
            "folders": [...],
            "unposted_files": [["folderA", "video1.mp4"], ...]
        },
        ...
    ]
}
"""

import sys
import os
import json
import time

# Ensure tool directory is in path
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BASE_DIR)
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

# ── Timestamp stdout wrapper ────────────────────────────────────────────────
# Wraps EVERY print() (including from facebook_automator.py) with [HH:MM:SS]
class _TimestampWriter:
    def __init__(self, stream):
        self._stream = stream
        self._at_line_start = True

    def write(self, text):
        if not text:
            return
        parts = text.split('\n')
        out = []
        for i, part in enumerate(parts):
            if i < len(parts) - 1:          # not the last fragment
                if self._at_line_start and part:
                    out.append(f"[{time.strftime('%H:%M:%S')}] {part}\n")
                elif part:
                    out.append(part + '\n')
                else:
                    out.append('\n')
                self._at_line_start = True
            else:                            # last (possibly empty) fragment
                if part:
                    if self._at_line_start:
                        out.append(f"[{time.strftime('%H:%M:%S')}] {part}")
                    else:
                        out.append(part)
                    self._at_line_start = False
        self._stream.write(''.join(out))
        self._stream.flush()

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)

# Force UTF-8 for stdout and stderr to prevent crash on Windows console (CP1252 / CP932 etc.)
# Must set BEFORE wrapping with _TimestampWriter
import io
try:
    # Highest priority: reconfigure with utf-8 + errors='replace' so we NEVER crash on Vietnamese/emoji
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    pass
try:
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    else:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    pass

sys.stdout = _TimestampWriter(sys.stdout)
sys.stderr = _TimestampWriter(sys.stderr)
# ────────────────────────────────────────────────────────────────────────────

from database import Database
from gemlogin_api import GemLoginAPI
from gpmlogin_api import GPMLoginAPI
from facebook_automator import FacebookAutomator

def log(msg):
    # TimestampWriter adds [HH:MM:SS] prefix automatically to every print()
    print(msg, flush=True)

def run_worker(job_path):
    # Load job manifest
    with open(job_path, 'r', encoding='utf-8') as f:
        job = json.load(f)

    run_mode = job['run_mode']
    skip_commented = job.get('skip_commented', True)
    auto_delete = job.get('auto_delete', False)
    b_config = job['browser_config']
    p_id = str(job['profile_id'])
    pages = job['pages']
    profile_label = job.get('profile_label', f'Profile {p_id}')

    db = Database()

    log(f"[Worker:{profile_label}] Bắt đầu xử lý {len(pages)} Nick Cá Nhân...")

    # Determine browser API
    if b_config['type'] == 'gemlogin':
        api = GemLoginAPI(b_config['api_url'])
    else:
        api = GPMLoginAPI(b_config['api_url'])

    # --- Luôn stop trước rồi mới start để tránh session cũ bị treo ---
    log(f"[Worker:{profile_label}] Đảm bảo profile sạch: stop → start...")
    try:
        api.stop_profile(p_id)
        time.sleep(1)
    except: pass

    launch_data = None
    for attempt in range(3):
        launch_data = api.start_profile(p_id)
        if launch_data and launch_data.get('success'):
            break
        log(f"[Worker:{profile_label}] Start thất bại lần {attempt+1}, thử lại sau 2s...")
        try:
            api.stop_profile(p_id)
        except: pass
        time.sleep(2)

    if not launch_data or not launch_data.get('success'):
        log(f"[Worker:{profile_label}] LỖI: Không thể mở profile {p_id} sau 3 lần thử. Thoát.")
        return

    try:
        data_content = launch_data.get('data', {}) if isinstance(launch_data.get('data'), dict) else {}
        debugger_address = data_content.get('remote_debugging_address') or data_content.get('debugger_address')
        driver_path = data_content.get('driver_path')
        
        if not debugger_address:
            log(f"[Worker:{profile_label}] LỖI: Không tìm thấy địa chỉ debugger (port).")
            return

        strats = db.get_comment_strategies()
        automator = FacebookAutomator(debugger_address, driver_path, strats)
        log(f"[Worker:{profile_label}] Đã kết nối trình duyệt.")

        # --- Process each page sequentially ---
        total_pages = len(pages)
        for idx, page in enumerate(pages, 1):
            page_name = page.get('name', 'Page_Không_Tên')
            stt = f"[{idx}/{total_pages}]"
            unposted_files = page.get('unposted_files', [])  # list of [folder, filename]
            to_comment_historic = page.get('to_comment_historic', [])

            if not unposted_files and not to_comment_historic:
                log(f"[Worker:{profile_label}] {stt} [{page_name}] Bỏ qua (Không có việc cần làm)")
                continue

            log(f"[Worker:{profile_label}] {stt} [{page_name}] Bắt đầu...")

            try:
                min_v = db.get_global_video_limits()[0]
                max_v = db.get_global_video_limits()[1]
                if min_v > max_v: min_v = max_v

                # Upload new videos
                if unposted_files and run_mode in ('post_and_comment', 'post_only'):
                    log(f"[Worker:{profile_label}] [{page_name}] Đăng {len(unposted_files)} video mới.")
                    # Nick Cá Nhân: Upload từng video qua facebook.com/reels/create
                    batch_to_post = []
                    for folder, vf in unposted_files:
                        video_path = os.path.join(folder, vf)
                        title = os.path.splitext(vf)[0]
                        batch_to_post.append((video_path, title))

                    # Upload individually
                    batch_size = max(1, min(max_v, 10))
                    for chunk_start in range(0, len(batch_to_post), batch_size):
                        chunk = batch_to_post[chunk_start: chunk_start + batch_size]
                        
                        # Track results per video to ensure we only delete on success
                        chunk_results = {} 
                        for video_path, title in chunk:
                            try:
                                result = automator.upload_reel_personal(video_path, title)
                                chunk_results[video_path] = result
                                log(f"[Worker:{profile_label}] [{page_name}] Upload: {result}")
                            except Exception as up_e:
                                chunk_results[video_path] = f"Error: {up_e}"
                                log(f"[Worker:{profile_label}] [{page_name}] Upload failed: {up_e}")

                        for video_path, title in chunk:
                            res = chunk_results.get(video_path, "")
                            # Chỉ log và xóa nếu kết quả trả về có chữ 'Uploaded' hoặc 'Success'
                            if "Uploaded" in str(res) or "Success" in str(res):
                                vf_name = os.path.basename(video_path)
                                db.log_upload(page['link'], vf_name, 'Uploaded')
                                if auto_delete and os.path.exists(video_path):
                                    try:
                                        os.remove(video_path)
                                        log(f"[Worker:{profile_label}] [{page_name}] ✓ Đã xóa video: {vf_name}")
                                    except Exception as del_e:
                                        log(f"[Worker:{profile_label}] [{page_name}] Lỗi xóa video: {del_e}")
                            else:
                                log(f"[Worker:{profile_label}] [{page_name}] ⚠ Bỏ qua việc xóa video do upload chưa được xác nhận thành công: {res}")

                    # Comment on newly uploaded videos
                    if run_mode == 'post_and_comment':
                        comment_template = db.get_comment_template()
                        if comment_template.strip():
                            asset_id = automator.resolve_asset_id(page['link'])
                            for folder, vf in unposted_files:
                                time.sleep(2)
                                title = os.path.splitext(vf)[0]
                                ok, link = automator.comment_with_dual_strategy(asset_id, title, comment_template)
                                if ok:
                                    db.add_comment_history(page['link'], vf, link or '')
                                    log(f"[Worker:{profile_label}] [{page_name}] Comment thành công: {vf}")

                # Handle historical comments (comment_only mode)
                if to_comment_historic and run_mode == 'comment_only':
                    log(f"[Worker:{profile_label}] [{page_name}] Comment {len(to_comment_historic)} bài cũ.")
                    asset_id = automator.resolve_asset_id(page['link'])
                    if not asset_id:
                        log(f"[Worker:{profile_label}] [{page_name}] LỖI: Không resolve được asset_id.")
                        continue
                        
                    comment_template = db.get_comment_template()
                    if comment_template.strip():
                        for v_name in to_comment_historic:
                            title = os.path.splitext(v_name)[0]
                            ok, link = automator.comment_with_dual_strategy(asset_id, title, comment_template)
                            if ok:
                                db.add_comment_history(page['link'], v_name, link or '')
                                log(f"[Worker:{profile_label}] [{page_name}] Comment lịch sử thành công: {v_name}")

            except Exception as page_e:
                log(f"[Worker:{profile_label}] {stt} [{page_name}] LỖI: {page_e}")
                import traceback
                traceback.print_exc()

        log(f"[Worker:{profile_label}] Hoàn tất tất cả {len(pages)} Nick Cá Nhân.")

    except Exception as e:
        log(f"[Worker:{profile_label}] LỖI NGHIÊM TRỌNG: {e}")
        import traceback
        traceback.print_exc()
    finally:
        log(f"[Worker:{profile_label}] Đóng trình duyệt profile {p_id}...")
        try:
            api.stop_profile(p_id)
        except: pass
        # Clean up job file
        try:
            os.remove(job_path)
        except: pass
        log(f"[Worker:{profile_label}] ✓ Worker thoát.")

def watchdog(parent_pid):
    """ Monitoring thread to ensure worker dies if parent GUI dies """
    import time
    # Dùng psutil để kiểm tra process còn sống hay không - an toàn trên Windows
    # os.kill(pid, 0) không hoạt động đúng trên Windows và luôn throw OSError
    try:
        import psutil
        use_psutil = True
    except ImportError:
        use_psutil = False

    while True:
        try:
            alive = False
            if use_psutil:
                alive = psutil.pid_exists(parent_pid)
            else:
                # Fallback: thử dùng os.kill nhưng bắt tất cả exceptions
                try:
                    import os as _os
                    _os.kill(parent_pid, 0)
                    alive = True
                except (OSError, SystemError, ValueError):
                    # Trên Windows: OSError = process không tồn tại, hoặc không có quyền
                    # Nhưng cũng có thể lỗi quyền (process vẫn tồn tại)
                    # Để an toàn, kiểm tra thêm qua subprocess
                    try:
                        import subprocess
                        result = subprocess.run(
                            ['tasklist', '/FI', f'PID eq {parent_pid}', '/NH'],
                            capture_output=True, text=True, timeout=3,
                            creationflags=0x08000000
                        )
                        alive = str(parent_pid) in result.stdout
                    except Exception:
                        alive = True  # Không chắc => giả định còn sống để tránh false kill
        except Exception:
            alive = True  # Nếu có lỗi không rõ => giả định còn sống

        if not alive:
            import os as _os
            _os._exit(1)
        time.sleep(5)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python page_worker.py <job_json_file> [parent_pid]")
        sys.exit(1)
    
    job_path = sys.argv[1]
    if not os.path.exists(job_path):
        print(f"ERROR: Job file not found: {job_path}")
        sys.exit(1)

    # Start watchdog if parent PID provided
    if len(sys.argv) >= 3:
        try:
            p_pid = int(sys.argv[2])
            import threading
            t = threading.Thread(target=watchdog, args=(p_pid,), daemon=True)
            t.start()
        except: pass
    
    run_worker(job_path)
