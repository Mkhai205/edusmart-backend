# 🚀 Tóm tắt Dự án: EduSmart - AI Learning Hub

**Định vị sản phẩm:** Một nền tảng học tập thông minh ứng dụng LLM, đóng vai trò như một gia sư cá nhân giúp sinh viên, học sinh và người tự học tự động hóa việc ôn tập và tăng tốc độ hấp thụ kiến thức.

### 1. Phân hệ Quản lý & Tương tác Tài liệu (Document Core)

- **Hỗ trợ file:** Định dạng chuẩn PDF.
- **Trải nghiệm đọc (Reading Mode):** \* Xem tài liệu trực tiếp trên trình duyệt (Preview).
    - Tương tác sâu: Bôi đen (Highlight) và ghi chú (Annotation) ngay trên giao diện PDF.

### 2. Phân hệ Trợ lý Tóm tắt (AI Summarizer)

- **3 Chế độ xử lý linh hoạt:**
    - _Toàn bộ:_ Trích xuất dàn ý và tóm tắt theo cấu trúc chương/mục.
    - _Khoảng trang:_ Chỉ định từ trang $X$ đến $Y$.
    - _Keyword Search:_ Rút trích và tổng hợp các đoạn văn bản chứa từ khóa liên quan.
- **Tính lan tỏa:** Khởi tạo Public URL để chia sẻ bản tóm tắt mà không cần đăng nhập.

### 3. Phân hệ Đánh giá & Kiểm tra (Quiz Generator)

- **Tạo đề tự động (Trắc nghiệm 1 đáp án đúng):**
    - Tùy biến cao: Chọn số lượng câu (5-30), thiết lập đồng hồ đếm ngược, chọn mức độ (Dễ/Trung bình/Khó), và khoanh vùng nội dung (chọn chương cụ thể).
- **Gamification & Analytics:**
    - Thống kê trực quan: Biểu đồ tròn (Đúng/Sai/Bỏ qua), Biểu đồ cột (Phổ điểm).
    - Tính năng chia sẻ đề thi cho nhóm học tập.

### 4. Phân hệ Ghi nhớ (Smart Flashcards)

- **Tạo thẻ tự động:** AI tự động quét tài liệu, bóc tách khái niệm để tạo thẻ (Mặt trước: Thuật ngữ/Câu hỏi - Mặt sau: Định nghĩa/Đáp án).
- **Trực quan hóa đa nguồn:**
    - Tự động gán ảnh minh họa qua API (Unsplash, Wikipedia).
    - Sử dụng mô hình tạo ảnh AI (như Nano Banana 2) để vẽ ảnh tối giản từ từ khóa.
- **Thuật toán học tập:** Áp dụng phương pháp Spaced Repetition (Lặp lại ngắt quãng), đi kèm biểu đồ theo dõi tiến độ theo ngày/tuần.
