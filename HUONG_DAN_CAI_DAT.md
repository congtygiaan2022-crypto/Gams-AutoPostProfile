# HƯỚNG DẪN CÀI ĐẶT CÔNG CỤ ĐĂNG REELS TỰ ĐỘNG

Tài liệu này hướng dẫn bạn cách thiết lập môi trường để chạy công cụ trên một máy tính mới từ đầu.

---

## 1. Yêu cầu hệ thống
- **Hệ điều hành**: Windows 10/11 (64-bit).
- **Python**: Phiên bản 3.10 trở lên.
- **Phần mềm hỗ trợ**: GemLogin (để quản lý trình duyệt và proxy).

---

## 2. Các bước cài đặt phần mềm

### Bước 1: Cài đặt Python
1. Truy cập [python.org/downloads](https://www.python.org/downloads/) và tải bản mới nhất.
2. **QUAN TRỌNG**: Khi cài đặt, hãy tích chọn ô **"Add Python to PATH"** trước khi nhấn Install.
3. Sau khi cài xong, mở CMD và gõ `python --version` để kiểm tra.

### Bước 2: Cài đặt thư viện Python (Dependencies)
Mở CMD (hoặc Terminal trong VS Code) tại thư mục chứa code và chạy lệnh sau:

```bash
pip install -r requirements.txt
```

*Lưu ý: Nếu không có file requirements.txt, bạn có thể cài thủ công bằng lệnh:*
```bash
pip install customtkinter selenium requests
```

### Bước 3: Thiết lập GemLogin
1. Tải và cài đặt phần mềm **GemLogin**.
2. Đăng nhập và tạo một Profile có tên chính xác là: `Đăng bài Fanpage + comment`.
3. Đảm bảo GemLogin đang mở khi chạy Tool để API có thể kết nối.

---

## 3. Cách vận hành Tool

1. **Khởi chạy**: Double-click vào file `gui.py` hoặc chạy lệnh `python gui.py` trong CMD.
2. **Cấu hình Folder**:
   - Nhấn **+ Thêm Fanpage** để thêm link Page.
   - Nhấn **Thêm Folder** tại mỗi Page để trỏ link đến thư mục chứa Video.
3. **Cài đặt Bình luận**: Nhấn **Cài đặt Bình luận** để nhập mẫu nội dung (hỗ trợ spin nội dung `{a|b|c}`).
4. **Bắt đầu**: Chọn chế độ chạy (Đăng + Comment, Chỉ Đăng, v.v.) và nhấn **Bắt đầu**.

---

## 4. Giải quyết lỗi thường gặp

- **Lỗi "ModuleNotFoundError"**: Do chưa cài thư viện ở Bước 2. Hãy chạy lại lệnh `pip install`.
- **Lỗi không mở được trình duyệt**: Hãy kiểm tra GemLogin đã mở chưa và Profile có đúng tên `Đăng bài Fanpage + comment` không.
- **Lỗi Video không xóa**: Đảm bảo quyền ghi (Write permission) trong thư mục chứa video và đã bật tùy chọn "Tự động xóa" trong database.json.

---

*Chúc bạn sử dụng công cụ hiệu quả!*
