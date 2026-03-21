# Tài liệu Cấu trúc Cơ sở dữ liệu (Database Schema)

## 1. Danh sách các bảng (Tables)

### `users`

Lưu trữ thông tin người dùng và tài khoản.

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                              |
| :---------------------- | :------------------ | :---------------------- | :----------------------------------- |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()`         |
| `google_id`             | `VARCHAR`           | UNIQUE                  |                                      |
| `email`                 | `VARCHAR`           | UNIQUE                  |                                      |
| `name`                  | `VARCHAR`           | NOT NULL                |                                      |
| `avatar_url`            | `TEXT`              |                         |                                      |
| `plan`                  | `VARCHAR(50)`       | NOT NULL                | Có thể dùng ENUM (VD: 'FREE', 'PRO') |
| `storage_used`          | `BIGINT`            | NOT NULL                | Mặc định `0`                         |
| `created_at`            | `TIMESTAMPTZ`       | Indexed                 | Mặc định `now()`                     |

---

### `documents`

Lưu trữ thông tin các tài liệu gốc người dùng tải lên.

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                                     |
| :---------------------- | :------------------ | :---------------------- | :------------------------------------------ |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()`                |
| `user_id`               | `UUID`              | **FOREIGN KEY**         | Tham chiếu `users(id)`                      |
| `title`                 | `TEXT`              | NOT NULL                |                                             |
| `file_url`              | `TEXT`              | NOT NULL                |                                             |
| `file_type`             | `VARCHAR(50)`       | Indexed                 | Có thể dùng ENUM (VD: 'PDF', 'DOCX')        |
| `file_size`             | `BIGINT`            |                         | Kích thước file (bytes)                     |
| `total_pages`           | `INT`               |                         |                                             |
| `status`                | `VARCHAR(50)`       | Indexed                 | Trạng thái xử lý (VD: 'PROCESSING', 'DONE') |
| `chunk_count`           | `INT`               |                         | Số lượng đoạn văn bản được chia nhỏ         |
| `tags`                  | `TEXT[]`            | Indexed (GIN)           | Mảng các thẻ phân loại                      |
| `created_at`            | `TIMESTAMPTZ`       | Indexed                 | Mặc định `now()`                            |

---

### `document_chunks`

Lưu trữ các đoạn văn bản (chunks) được trích xuất từ tài liệu và vector embedding phục vụ tìm kiếm AI.

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                                                                                            |
| :---------------------- | :------------------ | :---------------------- | :------------------------------------------------------------------------------------------------- |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()`                                                                       |
| `document_id`           | `UUID`              | **FOREIGN KEY**         | Tham chiếu `documents(id) ON DELETE CASCADE`                                                       |
| `chunk_index`           | `INT`               | NOT NULL                | Thứ tự của chunk                                                                                   |
| `text_content`          | `TEXT`              | NOT NULL                | Nội dung văn bản của chunk                                                                         |
| `page_start`            | `INT`               |                         | Trang bắt đầu                                                                                      |
| `page_end`              | `INT`               |                         | Trang kết thúc                                                                                     |
| `embedding`             | `vector(1536)`      | Indexed (HNSW)          | Vector biểu diễn ngữ nghĩa                                                                         |
| `bbox`                  | `JSONB`             | Nullable                | Mảng tọa độ `[x1, y1, x2, y2]`. Trả về cho UI để UI vẽ viền vàng đè lên file PDF khi AI trích dẫn. |

---

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

### `summaries`

Lưu trữ các bản tóm tắt tài liệu do AI tạo ra.

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                         |
| :---------------------- | :------------------ | :---------------------- | :------------------------------ |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()`    |
| `document_id`           | `UUID`              | **FOREIGN KEY**         | Tham chiếu `documents(id)`      |
| `user_id`               | `UUID`              | **FOREIGN KEY**         | Tham chiếu `users(id)`          |
| `mode`                  | `VARCHAR(50)`       | NOT NULL                | Chế độ tóm tắt                  |
| `options`               | `JSONB`             |                         | Cấu hình tóm tắt tùy chọn       |
| `content_html`          | `TEXT`              |                         | Nội dung tóm tắt định dạng HTML |
| `share_token`           | `TEXT`              | UNIQUE                  | Token để chia sẻ công khai      |
| `created_at`            | `TIMESTAMPTZ`       |                         | Mặc định `now()`                |

---

### `quizzes`

Lưu trữ các bài trắc nghiệm/câu hỏi được tạo từ tài liệu.

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                              |
| :---------------------- | :------------------ | :---------------------- | :----------------------------------- |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()`         |
| `document_id`           | `UUID`              | **FOREIGN KEY**         | Tham chiếu `documents(id)`           |
| `user_id`               | `UUID`              | **FOREIGN KEY**         | Tham chiếu `users(id)`               |
| `title`                 | `TEXT`              | NOT NULL                |                                      |
| `questions`             | `JSONB`             | NOT NULL                | Mảng cấu trúc câu hỏi và đáp án      |
| `quiz_type`             | `VARCHAR(50)`       | Indexed                 | Loại bài tập (VD: 'MULTIPLE_CHOICE') |
| `difficulty`            | `VARCHAR(50)`       |                         | Độ khó                               |
| `time_limit`            | `INT`               |                         | Giới hạn thời gian (giây)            |
| `share_token`           | `TEXT`              | UNIQUE                  |                                      |
| `created_at`            | `TIMESTAMPTZ`       | Indexed                 | Mặc định `now()`                     |

---

### `quiz_attempts`

Lưu trữ lịch sử và kết quả làm bài tập của người dùng.

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                      |
| :---------------------- | :------------------ | :---------------------- | :--------------------------- |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()` |
| `quiz_id`               | `UUID`              | **FOREIGN KEY**         | Tham chiếu `quizzes(id)`     |
| `user_id`               | `UUID`              | **FOREIGN KEY**         | Tham chiếu `users(id)`       |
| `answers`               | `JSONB`             |                         | Câu trả lời của người dùng   |
| `score`                 | `NUMERIC(5,2)`      | Indexed                 | Điểm số                      |
| `total_questions`       | `INT`               |                         | Tổng số câu hỏi              |
| `time_spent`            | `INT`               |                         | Thời gian làm bài (giây)     |
| `completed_at`          | `TIMESTAMPTZ`       | Indexed                 | Mặc định `now()`             |

---

### `flashcard_sets`

Lưu trữ các bộ thẻ ghi nhớ.

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                                    |
| :---------------------- | :------------------ | :---------------------- | :----------------------------------------- |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()`               |
| `document_id`           | `UUID`              | **FOREIGN KEY**         | Tham chiếu `documents(id)`                 |
| `user_id`               | `UUID`              | **FOREIGN KEY**         | Tham chiếu `users(id)`                     |
| `title`                 | `TEXT`              | NOT NULL                |                                            |
| `algorithm`             | `VARCHAR(50)`       |                         | Thuật toán lặp lại ngắt quãng (VD: 'SM-2') |
| `card_count`            | `INT`               |                         | Số lượng thẻ                               |
| `share_token`           | `TEXT`              | UNIQUE                  |                                            |
| `created_at`            | `TIMESTAMPTZ`       |                         | Mặc định `now()`                           |

---

### `flashcards`

Lưu trữ các thẻ ghi nhớ chi tiết (Mặt trước/Mặt sau).

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                                           |
| :---------------------- | :------------------ | :---------------------- | :------------------------------------------------ |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()`                      |
| `set_id`                | `UUID`              | **FOREIGN KEY**         | Tham chiếu `flashcard_sets(id) ON DELETE CASCADE` |
| `front`                 | `TEXT`              | NOT NULL                | Mặt trước (câu hỏi/từ vựng)                       |
| `back`                  | `TEXT`              | NOT NULL                | Mặt sau (đáp án/định nghĩa)                       |
| `image_url`             | `TEXT`              |                         | Hình ảnh minh họa                                 |
| `image_source`          | `VARCHAR(50)`       |                         | Nguồn ảnh                                         |
| `ease_factor`           | `NUMERIC(4,2)`      |                         | Hệ số ghi nhớ (Spaced Repetition)                 |
| `interval_days`         | `INT`               |                         | Khoảng cách ngày lặp lại                          |
| `repetitions`           | `INT`               |                         | Số lần đã ôn tập                                  |
| `next_review_at`        | `TIMESTAMPTZ`       | Indexed                 | Thời gian cần ôn tập tiếp theo                    |
| `last_rating`           | `INT`               |                         | Đánh giá lần cuối (khó/dễ)                        |

---

### `mind_maps`

Lưu trữ bản đồ tư duy.

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                            |
| :---------------------- | :------------------ | :---------------------- | :--------------------------------- |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()`       |
| `document_id`           | `UUID`              | **FOREIGN KEY**         | Tham chiếu `documents(id)`         |
| `user_id`               | `UUID`              | **FOREIGN KEY**         | Tham chiếu `users(id)`             |
| `title`                 | `TEXT`              | NOT NULL                |                                    |
| `nodes_json`            | `JSONB`             | NOT NULL                | Cấu trúc cây/node của sơ đồ tư duy |
| `share_token`           | `TEXT`              | UNIQUE                  |                                    |
| `created_at`            | `TIMESTAMPTZ`       |                         | Mặc định `now()`                   |

---

### `learning_goals`

Lưu trữ mục tiêu học tập của người dùng.

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                                     |
| :---------------------- | :------------------ | :---------------------- | :------------------------------------------ |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()`                |
| `user_id`               | `UUID`              | **FOREIGN KEY**         | Tham chiếu `users(id)`                      |
| `document_id`           | `UUID`              | **FOREIGN KEY**         | CÓ THỂ NULL. Tham chiếu `documents(id)`     |
| `title`                 | `TEXT`              | NOT NULL                |                                             |
| `description`           | `TEXT`              |                         |                                             |
| `target_date`           | `DATE`              | Indexed                 | Ngày mục tiêu hoàn thành                    |
| `progress`              | `INT`               |                         | Tiến độ (0-100%)                            |
| `status`                | `VARCHAR(50)`       | Indexed                 | Trạng thái (VD: 'IN_PROGRESS', 'COMPLETED') |
| `milestones`            | `JSONB`             |                         | Các cột mốc nhỏ                             |

---

### `pomodoro_sessions`

Lưu trữ các phiên tập trung Pomodoro.

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                                      |
| :---------------------- | :------------------ | :---------------------- | :------------------------------------------- |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()`                 |
| `user_id`               | `UUID`              | **FOREIGN KEY**         | Tham chiếu `users(id)`                       |
| `document_id`           | `UUID`              | **FOREIGN KEY**         | CÓ THỂ NULL. Tham chiếu `documents(id)`      |
| `goal_id`               | `UUID`              | **FOREIGN KEY**         | CÓ THỂ NULL. Tham chiếu `learning_goals(id)` |
| `duration_min`          | `INT`               | NOT NULL                | Thời lượng phiên (phút)                      |
| `session_type`          | `VARCHAR(50)`       |                         | Loại phiên (VD: 'WORK', 'SHORT_BREAK')       |
| `completed`             | `BOOLEAN`           |                         | Trạng thái hoàn thành trọn vẹn không         |
| `started_at`            | `TIMESTAMPTZ`       | Indexed                 | Mặc định `now()`                             |

---

### `shared_links`

Quản lý các liên kết chia sẻ tài nguyên công khai.

| Trường dữ liệu (Column) | Kiểu dữ liệu (Type) | Ràng buộc (Constraints) | Ghi chú                                            |
| :---------------------- | :------------------ | :---------------------- | :------------------------------------------------- |
| **`id`**                | `UUID`              | **PRIMARY KEY**         | Mặc định `gen_random_uuid()`                       |
| `user_id`               | `UUID`              | **FOREIGN KEY**         | Tham chiếu `users(id)`                             |
| `token`                 | `TEXT`              | UNIQUE, NOT NULL        | Chuỗi token ngẫu nhiên                             |
| `resource_type`         | `VARCHAR(50)`       | Indexed, NOT NULL       | Loại tài nguyên (VD: 'quiz', 'mindmap', 'summary') |
| `resource_id`           | `UUID`              | Indexed, NOT NULL       | ID của tài nguyên tương ứng (Polymorphic)          |
| `expires_at`            | `TIMESTAMPTZ`       |                         | Thời điểm hết hạn link                             |
| `view_count`            | `INT`               |                         | Số lượt xem (Mặc định `0`)                         |
| `created_at`            | `TIMESTAMPTZ`       |                         | Mặc định `now()`                                   |

---

## 2. Các mối quan hệ (Relationships/Foreign Keys)

- `documents` thuộc về `users` (Nhiều - Một)
- `document_chunks` thuộc về `documents` (Nhiều - Một) - Xóa tài liệu sẽ xóa toàn bộ chunks (`CASCADE`).
- `summaries` liên kết với `documents` và `users` (Nhiều - Một)
- `quizzes` liên kết với `documents` và `users` (Nhiều - Một)
- `quiz_attempts` thuộc về `quizzes` do `users` thực hiện (Nhiều - Một)
- `flashcard_sets` liên kết với `documents` và `users` (Nhiều - Một)
- `flashcards` thuộc về `flashcard_sets` (Nhiều - Một) - Xóa bộ thẻ sẽ xóa các thẻ con (`CASCADE`).
- `mind_maps` liên kết với `documents` và `users` (Nhiều - Một)
- `learning_goals` thuộc về `users`, có thể tùy chọn gán với một `documents` (Nhiều - Một)
- `pomodoro_sessions` thuộc về `users`, có thể tùy chọn gán với `documents` hoặc `learning_goals` (Nhiều - Một)
- `shared_links` thuộc về `users`, trỏ đến các tài nguyên khác thông qua mô hình đa hình (Polymorphic: `resource_type` + `resource_id`).
