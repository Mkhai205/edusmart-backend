### Bước 1: Cài đặt Poetry qua PowerShell

Thay vì dùng `pip install poetry` (cách này dễ gây xung đột môi trường global), cách chuẩn nhất (Best Practice) trên Windows là dùng script cài đặt độc lập.

1. Bấm phím **Windows**, gõ `PowerShell` và mở lên.
2. Dán dòng lệnh sau vào và nhấn Enter:

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

3. **Quan trọng (Cấu hình PATH):** Sau khi chạy xong, PowerShell sẽ in ra một đường dẫn (thường là `C:\Users\<Tên_User>\AppData\Roaming\Python\Scripts`).
    - Bạn copy đường dẫn này.
    - Mở **Edit the system environment variables** (gõ "env" vào ô tìm kiếm Windows).
    - Chọn **Environment Variables** -> Tìm biến `Path` ở ô User variables -> Bấm **Edit** -> **New** -> Dán đường dẫn vừa copy vào -> Bấm OK liên tục để lưu.
4. Tắt hoàn toàn PowerShell (hoặc Terminal) và mở lại. Gõ thử lệnh `poetry --version` để kiểm tra. Nếu hiện ra số phiên bản là thành công!

---

### Bước 2: Cấu hình "Mẹo Ninja" cho VS Code

Mặc định, Poetry sẽ tạo thư mục môi trường ảo (`.venv`) ở một nơi rất sâu trong ổ C. Điều này làm VS Code khó nhận diện được các thư viện bạn đã cài. Hãy ép Poetry tạo thư mục `.venv` ngay bên trong dự án của bạn:

Mở Terminal và chạy lệnh này (chỉ cần chạy 1 lần duy nhất cho máy của bạn):

```bash
poetry config virtualenvs.in-project true
```
