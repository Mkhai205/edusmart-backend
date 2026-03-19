### 1. Phân hệ Xác thực & Người dùng (Auth)

Vì dùng Google Auth 100%, chúng ta không cần lưu mật khẩu. Chỉ cần lưu ID định danh của Google để đối chiếu cho các lần đăng nhập sau.

**Bảng: `users`**
| Field | Data Type | Constraints | Ý nghĩa / Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | ID nội bộ của hệ thống EduSmart. |
| `google_id` | `VARCHAR` | Unique, Not Null | ID duy nhất do Google trả về (sub trong JWT của Google). Dùng để check user cũ/mới. |
| `email` | `VARCHAR` | Unique, Not Null | Email người dùng (để hiển thị hoặc gửi thông báo sau này). |
| `full_name` | `VARCHAR` | Nullable | Tên hiển thị trên Dashboard. |
| `avatar_url` | `TEXT` | Nullable | Link ảnh đại diện lấy từ Google. |
| `created_at` | `TIMESTAMPTZ` | Default: NOW() | Ngày tham gia hệ thống. |

---

### 2. Phân hệ Quản lý Tài liệu & RAG (Document Core)

Đây là nhóm bảng phức tạp nhất, phục vụ việc lưu trữ file gốc, bóc tách vector để AI đọc, và lưu tọa độ để vẽ Highlight trên giao diện PDF.

**Bảng: `documents` (Thông tin file gốc)**
| Field | Data Type | Constraints | Ý nghĩa / Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | ID của tài liệu. |
| `user_id` | `UUID` | Foreign Key (`users.id`) | Ai là người upload file này. |
| `title` | `VARCHAR` | Not Null | Tên hiển thị của file. |
| `file_url` | `TEXT` | Not Null | Đường dẫn file PDF lưu trên MinIO (VD: `http://minio.../file.pdf`). |
| `total_pages` | `INTEGER` | Nullable | Tổng số trang (phục vụ validate khi user chọn tóm tắt theo khoảng trang). |
| `is_public` | `BOOLEAN` | Default: False | Bật/tắt trạng thái chia sẻ link public. |
| `created_at` | `TIMESTAMPTZ` | Default: NOW() | Thời gian tải lên. |

**Bảng: `document_chunks` (Dữ liệu cho AI / Vector DB)**
| Field | Data Type | Constraints | Ý nghĩa / Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | ID của đoạn text. |
| `document_id` | `UUID` | FK (`documents.id`) | Thuộc tài liệu nào (ON DELETE CASCADE). |
| `page_number` | `INTEGER` | Not Null | Nằm ở trang số mấy (Để filter "Tóm tắt từ trang X đến Y"). |
| `text_content` | `TEXT` | Not Null | Nội dung chữ đã bóc tách. Dùng làm Context ném cho LLM. |
| `bbox` | `JSONB` | Nullable | Mảng tọa độ `[x1, y1, x2, y2]`. Trả về cho UI để UI vẽ viền vàng đè lên file PDF khi AI trích dẫn. |
| `embedding` | `VECTOR(768)`| Not Null | Vector ngữ nghĩa sinh ra từ Google/Langchain để so sánh độ tương đồng. |

**Bảng: `annotations` (Lưu lịch sử bôi đen & ghi chú của User)**
| Field | Data Type | Constraints | Ý nghĩa / Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | ID của ghi chú. |
| `document_id` | `UUID` | FK (`documents.id`) | Ghi chú nằm trên tài liệu nào. |
| `page_number` | `INTEGER` | Not Null | Nằm ở trang nào. |
| `bbox` | `JSONB` | Not Null | Tọa độ user dùng chuột bôi đen. Khi load lại trang, React-PDF dùng tọa độ này để tô màu lại. |
| `selected_text` | `TEXT` | Not Null | Đoạn text user vừa bôi đen (Để nếu có hỏi AI thì lấy đoạn này làm context). |
| `note` | `TEXT` | Nullable | Nội dung user tự gõ thêm. |
| `color` | `VARCHAR` | Default: `#FFFF00` | Mã màu highlight (phục vụ UI). |

---

### 3. Phân hệ Đánh giá (Quizzes & Analytics)

Nhóm bảng này cung cấp dữ liệu đầu vào cho tính năng "Làm trắc nghiệm" và xuất số liệu để vẽ biểu đồ thống kê (Chart.js / Recharts).

**Bảng: `quizzes` (Cấu hình đề thi)**
| Field | Data Type | Constraints | Ý nghĩa / Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | ID đề thi. |
| `document_id` | `UUID` | FK (`documents.id`) | AI sinh đề thi từ tài liệu nào. |
| `title` | `VARCHAR` | Not Null | Tiên đề thi (VD: "Ôn tập Chương 1"). |
| `difficulty` | `VARCHAR` | Enum | Mức độ: `easy`, `medium`, `hard`. |
| `time_limit` | `INTEGER` | Nullable | Giới hạn thời gian (tính bằng giây). Null là không giới hạn. |

**Bảng: `quiz_questions` (Ngân hàng câu hỏi của đề)**
| Field | Data Type | Constraints | Ý nghĩa / Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | ID câu hỏi. |
| `quiz_id` | `UUID` | FK (`quizzes.id`) | Thuộc đề thi nào. |
| `question_text` | `TEXT` | Not Null | Nội dung câu hỏi. |
| `options` | `JSONB` | Not Null | Mảng các lựa chọn. VD: `["A", "B", "C", "D"]`. Dùng JSONB để tiện xuất thẳng ra API. |
| `correct_answer` | `TEXT` | Not Null | Đáp án đúng khớp với mảng options. |
| `explanation` | `TEXT` | Nullable | Lời giải thích từ AI (Chỉ hiện ra sau khi nộp bài). |

**Bảng: `quiz_attempts` (Lịch sử làm bài - Nguồn nuôi Biểu đồ)**
| Field | Data Type | Constraints | Ý nghĩa / Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | ID lần làm bài. |
| `quiz_id` | `UUID` | FK (`quizzes.id`) | Làm đề nào. |
| `user_id` | `UUID` | FK (`users.id`) | Ai làm. |
| `score` | `FLOAT` | Not Null | Điểm số đạt được (Thang 10 hoặc 100). |
| `total_correct` | `INTEGER` | Not Null | Số câu đúng -> Vẽ **Biểu đồ tròn**. |
| `total_incorrect`| `INTEGER` | Not Null | Số câu sai -> Vẽ **Biểu đồ tròn**. |
| `total_skipped` | `INTEGER` | Not Null | Số câu bỏ trống -> Vẽ **Biểu đồ tròn**. |
| `completed_at` | `TIMESTAMPTZ` | Default: NOW() | Thời gian nộp bài -> Vẽ **Biểu đồ cột phân bố điểm theo thời gian**. |

---

### 4. Phân hệ Flashcards (Spaced Repetition)

Bảng này không chỉ lưu Thẻ học mà còn tích hợp luôn các biến số của thuật toán lặp lại ngắt quãng (SuperMemo-2).

**Bảng: `flashcard_decks` (Bộ thẻ)**
| Field | Data Type | Constraints | Ý nghĩa / Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | ID bộ thẻ. |
| `document_id` | `UUID` | FK (`documents.id`) | AI tạo bộ thẻ từ tài liệu nào. |
| `title` | `VARCHAR` | Not Null | Tên bộ thẻ. |

**Bảng: `flashcards` (Chi tiết từng thẻ)**
| Field | Data Type | Constraints | Ý nghĩa / Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | ID của thẻ. |
| `deck_id` | `UUID` | FK (`flashcard_decks.id`) | Thuộc bộ thẻ nào. |
| `front_text` | `TEXT` | Not Null | Mặt trước (Thuật ngữ/Câu hỏi). |
| `back_text` | `TEXT` | Not Null | Mặt sau (Định nghĩa/Giải thích). |
| `image_url` | `TEXT` | Nullable | Link ảnh minh họa (từ Wikipedia / Nano Banana / Unsplash). |
| `repetition` | `INTEGER` | Default: 0 | Số lần user đã ôn thẻ này thành công. |
| `easiness_factor`| `FLOAT` | Default: 2.5 | Hệ số độ khó. User đánh giá "Khó" thì giảm, "Dễ" thì tăng. |
| `interval_days` | `INTEGER` | Default: 0 | Khoảng cách số ngày cho lần ôn tiếp theo. |
| `next_review_date`| `TIMESTAMPTZ`| Default: NOW() | Ngày phải ôn lại thẻ này. (API sẽ filter: `WHERE next_review_date <= TODAY`). |

---

### Mối quan hệ tổng quan (Relationships)

- **1 User** có nhiều **Documents** và **Quiz Attempts**.
- **1 Document** có nhiều **Chunks (Vector)**, **Annotations**, **Quizzes**, và **Flashcard Decks**.
- Khi xóa 1 `Document` (`ON DELETE CASCADE`), toàn bộ vector chunks, thẻ flashcard, ghi chú và đề thi liên quan đến tài liệu đó sẽ bị xóa sạch, giúp DB không bị rác.
