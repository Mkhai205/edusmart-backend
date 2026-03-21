### Kế hoạch Triển khai Backend EduSmart MVP

#### 📍 Sprint 1: Đổ móng Hạ tầng & Cánh cửa Xác thực (Foundation & Auth)

**Mục tiêu:** Dựng xong môi trường, database chạy ổn định và user có thể đăng nhập lấy Token.

1. **Setup Môi trường (Day 1):**
    - Khởi tạo dự án với Poetry.
    - Dựng `docker-compose.yml` (PostgreSQL `pgvector`, MinIO).
    - Thiết lập cấu trúc thư mục chuẩn (Core, Models, Infrastructure, Modules).
2. **Database & ORM (Day 2):**
    - Chuyển hóa bản thiết kế Database thành code SQLAlchemy (`app/models/`).
    - Cài đặt **Alembic** và chạy lệnh migration đầu tiên để tạo các bảng trong Postgres.
3. **Xác thực Google (Day 3):**
    - Tạo Credentials trên Google Cloud Console.
    - Viết API `POST /api/v1/auth/google`.
    - Viết logic giải mã Google Token và sinh JWT nội bộ của hệ thống.

#### 📍 Sprint 2: Quản lý File & Bóc tách Dữ liệu (Document Core)

**Mục tiêu:** Hệ thống nhận được file PDF, lưu trữ an toàn và bóc tách được dữ liệu thô.

1. **Storage Service (Day 1):**
    - Viết class kết nối MinIO (Upload/Download) trong thư mục `infrastructure/storage`.
    - Viết API `POST /api/v1/documents/upload`.
2. **Trích xuất PDF (Day 2-3):**
    - Tích hợp thư viện `unstructured` hoặc `PyMuPDF`.
    - Viết logic đọc file PDF vừa upload -> Lấy Text -> Lấy tọa độ `bbox` -> Lấy số trang.
3. **Lưu trữ Metadata (Day 4):**
    - Ghi thông tin file vào bảng `documents`.
    - Ghi các đoạn text và tọa độ vào bảng `document_chunks` (Lưu ý: Lúc này chưa có vector, chỉ lưu text thô).

#### 📍 Sprint 3: RAG Engine & Bộ não AI (Intelligence Layer)

**Mục tiêu:** Biến text thô thành Vector, nhúng vào DB và gọi Gemini trả lời các câu hỏi tóm tắt.

1. **Vectorization (Day 1-2):**
    - Cấu hình Langchain kết nối với mô hình Embedding.
    - Chạy vòng lặp lấy các `document_chunks` chưa có vector -> Nhúng thành Vector 768 chiều -> Update lại vào PostgreSQL.
2. **Truy vấn Ngữ nghĩa (Day 3):**
    - Viết hàm Search dùng pgvector: Tìm các đoạn text có độ tương đồng (Cosine Similarity) cao nhất với câu hỏi.
3. **Tính năng Tóm tắt (Day 4):**
    - Viết API `POST /api/v1/documents/{id}/summary`.
    - Xử lý 3 option: Tóm tắt toàn bộ (Map-Reduce), Khoảng trang (Filter `page_number`), Keyword (Hybrid Search). Đưa Context vào Gemini để sinh Markdown.

#### 📍 Sprint 4: Không gian Học tập Chủ động (Learning Features)

**Mục tiêu:** Hoàn thiện các tính năng cốt lõi cho sinh viên theo đúng chuẩn MVP.

1. **Sinh đề thi & Chấm điểm (Day 1-2):**
    - Viết API `POST /api/v1/learning/quizzes/generate`.
    - Ép Gemini trả về định dạng JSON nghiêm ngặt (Câu hỏi, 4 đáp án, đáp án đúng).
    - Viết API Nộp bài thi (`POST /api/v1/learning/quizzes/{id}/submit`) và lưu kết quả vào `quiz_attempts`.
2. **Hệ thống Flashcard (Day 3):**
    - Viết API quét tài liệu sinh Flashcard.
    - Viết API duyệt thẻ ngày hôm nay dựa trên thuật toán Spaced Repetition (`next_review_date`).
3. **UI Highlight (Day 4):**
    - Viết API `POST /api/v1/documents/{id}/annotations` để lưu tọa độ user bôi đen trên Frontend.

#### 📍 Sprint 5: Đóng gói & Về đích (Polish & Deployment)

**Mục tiêu:** Dọn dẹp code, bắt lỗi và chuẩn bị sẵn sàng để tích hợp với Frontend.

1. **Xử lý Ngoại lệ (Exceptions):** Bọc try-catch, trả về HTTP Status Code chuẩn (400, 401, 404, 500) để Frontend dễ bắt lỗi.
2. **Kiểm thử API:** Dùng Swagger UI (`/docs`) test luồng End-to-End từ lúc login đến lúc sinh đề thi.
3. **Tối ưu Docker:** Kiểm tra lại dung lượng Image, đảm bảo `docker-compose` chạy trơn tru trên máy ảo hoặc server nộp bài.

---

### Bảng Tổng hợp Tiến độ (Gantt Chart Tracking)

| Giai đoạn    | Tính năng trọng tâm | Đầu ra (Deliverables)                             | Rủi ro cần lưu ý                                |
| :----------- | :------------------ | :------------------------------------------------ | :---------------------------------------------- |
| **Sprint 1** | Auth & Database     | API Login trả về Token, DB có các bảng.           | Lỗi mapping kiểu dữ liệu UUID hoặc Vector.      |
| **Sprint 2** | Upload & Parsing    | File nằm trên MinIO, Text và Bbox nằm trong DB.   | `unstructured` bóc tách file quá chậm.          |
| **Sprint 3** | RAG & Summarize     | Hàm Search Vector chạy được, Tóm tắt ra nội dung. | Quá giới hạn Token của Gemini (Rate limit).     |
| **Sprint 4** | Quiz & Flashcard    | Sinh được JSON đề thi, tính được ngày ôn thẻ.     | Prompt không chặt khiến Gemini trả về JSON lỗi. |
| **Sprint 5** | Polish              | Hệ thống không chết khi nhập dữ liệu sai.         | Xung đột phiên bản khi build Docker.            |
