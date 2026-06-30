"""
Chay_Khong_CMD.pyw
------------------
Double-click file này để mở chương trình KHÔNG hiện cửa sổ CMD.
File .pyw được Windows chạy bằng pythonw.exe (ẩn console).
"""
import os, sys

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BASE_DIR)
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from gui import App, ProfileSelector

if __name__ == "__main__":
    selector = ProfileSelector()
    selector.mainloop()
    
    if selector.selected_profile:
        prof = selector.selected_profile
        app = App(
            db_file=prof['db_file'],
            sqlite_file=prof['sqlite_file'],
            profile_name=prof['name']
        )
        app.mainloop()
