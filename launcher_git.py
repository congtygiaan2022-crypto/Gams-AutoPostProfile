# -*- coding: utf-8 -*-
"""
launcher_git.py - Trình khởi chạy tự động cập nhật qua Git cho AutoDangbai_nick_canhan
==================================================================================
Chạy file này trên các máy con để tự động đồng bộ code từ kho lưu trữ Git.
"""

import sys
import os
import subprocess

# Đảm bảo thư mục làm việc luôn là thư mục chứa script launcher_git.py
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR:
    os.chdir(_BASE_DIR)

# CẤU HÌNH ĐƯỜNG DẪN GIT CẬP NHẬT (Sẽ được Git_Uploader.py điền tự động khi upload)
GIT_REPO_URL = "https://github.com/congtygiaan2022-crypto/Gams-AutoPostProfile.git"

def get_requirements_content():
    if os.path.exists("requirements.txt"):
        try:
            with open("requirements.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except:
            pass
    return ""

def run_git_pull():
    print("=========================================")
    print(" ĐANG ĐỒNG BỘ CẬP NHẬT QUA GIT...")
    print("=========================================")
    
    if GIT_REPO_URL == "PLACEHOLDER_GIT_URL":
        print("⚠️ Cảnh báo: URL Git chưa được cấu hình.")
        print("Vui lòng cấu hình URL Git bằng Git_Uploader.py trước khi chạy.")
        print("=========================================\n")
        return False

    # 1. Đọc nội dung requirements.txt trước khi pull
    req_before = get_requirements_content()
    
    # Tự động khởi tạo Git và liên kết Repo nếu chạy lần đầu trên máy mới
    if not os.path.exists(".git"):
        print("📁 Phát hiện cài đặt mới tinh. Đang tự động kết nối đến kho Git...")
        try:
            # Khởi tạo git cục bộ
            subprocess.run(["git", "init"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Liên kết với remote origin
            subprocess.run(["git", "remote", "add", "origin", GIT_REPO_URL], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✓ Khởi tạo Git và liên kết Repository thành công.")
        except FileNotFoundError:
            print("❌ Lỗi: Máy tính này chưa được cài đặt phần mềm Git.")
            print("-> Tải Git tại: https://git-scm.com/")
            print("=========================================\n")
            return False
        except Exception as e:
            print(f"⚠️ Lỗi khởi tạo Git: {e}")
            print("=========================================\n")
            return False
        
    try:
        # Đảm bảo remote origin trỏ đúng URL cấu hình
        subprocess.run(["git", "remote", "set-url", "origin", GIT_REPO_URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        # Chạy lệnh git pull để đồng bộ code mới nhất
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=25
        )
        
        pulled_successfully = False
        if result.returncode == 0:
            pulled_successfully = True
            output = result.stdout.strip()
            if "Already up to date" in output:
                print("✓ Bạn đang chạy phiên bản mới nhất từ Git.")
            else:
                print("🚀 ĐÃ CẬP NHẬT PHIÊN BẢN MỚI THÀNH CÔNG!")
                print(output)
        else:
            # Nếu có lỗi khi pull (ví dụ conflict, thay đổi cục bộ), tiến hành reset để đè code sạch về
            print("⚠️ Phát hiện xung đột hoặc lỗi đồng bộ. Đang tự động làm sạch và đồng bộ lại...")
            subprocess.run(["git", "fetch", "--all"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            reset_result = subprocess.run(["git", "reset", "--hard", "origin/main"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if reset_result.returncode == 0:
                pulled_successfully = True
                print("✓ Đã đồng bộ thành công phiên bản sạch từ Git (Đè các thay đổi cục bộ).")
            else:
                print("❌ Không thể đồng bộ mã nguồn sạch từ Git.")
                
        # 2. Đọc lại requirements.txt sau khi pull
        if pulled_successfully:
            req_after = get_requirements_content()
            if req_before != req_after and req_after != "":
                print("\n🔔 Phát hiện thay đổi về thư viện cần thiết.")
                print("Đang tự động cài đặt/cập nhật các thư viện Python bổ sung...")
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                        check=True
                    )
                    print("✓ Thư viện đã được cập nhật đồng bộ thành công.")
                except Exception as e:
                    print(f"⚠️ Lỗi cập nhật thư viện tự động: {e}")
                    print("-> Bạn có thể chạy thủ công file Cai_Dat_Thu_Vien.bat")
            return True
            
    except subprocess.TimeoutExpired:
        print("⚠️ Hết thời gian chờ kết nối (Timeout). Bỏ qua cập nhật.")
    except FileNotFoundError:
        print("❌ Lỗi: Máy tính này chưa được cài đặt phần mềm Git.")
        print("-> Tải Git tại: https://git-scm.com/")
    except Exception as e:
        print(f"⚠️ Không thể cập nhật: {e}")
        
    print("=========================================\n")
    return False

if __name__ == "__main__":
    # 1. Chạy cập nhật qua Git và tự động đồng bộ thư viện
    run_git_pull()
    
    # 2. Khởi tạo SQLite database (system.db) nếu chưa có
    if not os.path.exists("system.db") and os.path.exists("init_db.py"):
        print("📁 Phát hiện cài đặt mới tinh. Đang khởi tạo dữ liệu SQLite...")
        try:
            subprocess.run([sys.executable, "init_db.py"], check=True)
            print("✓ Khởi tạo dữ liệu SQLite thành công.")
        except Exception as e:
            print(f"⚠️ Lỗi khởi tạo SQLite: {e}")
            
    # 3. Khởi chạy giao diện chính của Tool
    print("Đang khởi chạy ứng dụng...")
    try:
        if os.path.exists("Chay_Khong_CMD.pyw"):
            # Chạy nền không hiện CMD phụ
            subprocess.Popen([sys.executable, "Chay_Khong_CMD.pyw"])
        elif os.path.exists("gui.py"):
            subprocess.Popen([sys.executable, "gui.py"])
        else:
            print("❌ Không tìm thấy file chạy ứng dụng (gui.py hoặc Chay_Khong_CMD.pyw).")
            print("Vui lòng kiểm tra lại quá trình Git Pull tải code.")
            input("Nhấn Enter để thoát.")
    except Exception as e:
        print(f"Lỗi khởi chạy GUI: {e}")
        input("Nhấn Enter để thoát.")
