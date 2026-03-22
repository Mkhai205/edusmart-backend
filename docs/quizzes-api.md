# Quizzes API (MVP)

Module quizzes hiện hỗ trợ luồng:

- Queue sinh đề tự động (AI)
- Theo dõi trạng thái / lấy chi tiết đề
- Liệt kê lịch sử đề đã tạo của user
- Nộp bài và chấm điểm tự động
- Xem lịch sử attempt theo từng quiz

## 1) Tạo đề tự động

**POST** `/api/v1/learning/quizzes/generate`

### Request body

```json
{
    "document_id": "2b2551f9-7b35-4f22-915f-27b4f337b421",
    "question_count": 10,
    "difficulty": "medium",
    "start_page": 1,
    "end_page": 12,
    "time_limit_seconds": 900
}
```

### Rule validate

- `question_count`: từ 5 đến 30.
- `difficulty`: `easy` | `medium` | `hard`.
- `start_page` và `end_page` phải truyền cùng nhau (hoặc cùng null).
- Nếu có page range thì `start_page <= end_page` và `end_page` không vượt `document.total_pages`.
- Tài liệu phải thuộc user hiện tại và có `extraction_status = completed`.

### Response

- `202 Accepted` khi đã queue thành công.

```json
{
    "quiz_id": "9c4f4d26-b838-4f64-b6c5-b43fe29d691a",
    "document_id": "2b2551f9-7b35-4f22-915f-27b4f337b421",
    "quiz_status": "pending",
    "quiz_type": "multiple_choice_single",
    "question_count": 10,
    "difficulty": "medium",
    "start_page": 1,
    "end_page": 12,
    "time_limit_seconds": 900,
    "created_at": "2026-03-22T17:10:00.000000+00:00"
}
```

## 2) Lấy danh sách quizzes của user

**GET** `/api/v1/learning/quizzes?limit=20&offset=0&document_id=<optional-uuid>`

### Response

```json
[
    {
        "quiz_id": "9c4f4d26-b838-4f64-b6c5-b43fe29d691a",
        "document_id": "2b2551f9-7b35-4f22-915f-27b4f337b421",
        "title": "Quiz - Data Structures",
        "quiz_type": "multiple_choice_single",
        "quiz_status": "completed",
        "question_count": 10,
        "difficulty": "medium",
        "time_limit_seconds": 900,
        "completed_at": "2026-03-22T17:11:32.000000+00:00",
        "created_at": "2026-03-22T17:10:00.000000+00:00"
    }
]
```

## 3) Lấy trạng thái/chi tiết 1 quiz

**GET** `/api/v1/learning/quizzes/{quiz_id}`

### Trạng thái

- `pending`: đã queue.
- `processing`: đang gọi AI để sinh đề.
- `completed`: đã sinh xong, có trường `questions`.
- `failed`: sinh thất bại, có `quiz_error`.

### Cấu trúc câu hỏi trả về khi completed

```json
{
    "question_index": 1,
    "question_text": "...",
    "options": ["A", "B", "C", "D"],
    "correct_option_index": 2,
    "hint": "...",
    "correct_explanation": "...",
    "incorrect_explanations": ["...", "...", "..."],
    "option_explanations": ["...", "...", "...", "..."]
}
```

`option_explanations` luôn theo đúng thứ tự `options` và bao gồm cả đáp án đúng lẫn sai.

## 4) Nộp bài và chấm điểm

**POST** `/api/v1/learning/quizzes/{quiz_id}/submit`

### Request body

```json
{
    "answers": [
        { "question_index": 1, "selected_option_index": 2 },
        { "question_index": 2, "selected_option_index": 0 },
        { "question_index": 3, "selected_option_index": null }
    ],
    "time_spent_seconds": 540
}
```

### Rule validate

- `question_index` khong duoc trung trong cung payload.
- `selected_option_index` la `0..3` hoac `null` (bo qua cau hoi).
- Chi cho phep submit khi `quiz_status = completed`.

### Response

```json
{
    "attempt_id": "07a5f8c7-5f73-4ce9-ae27-3efb52b771d4",
    "quiz_id": "9c4f4d26-b838-4f64-b6c5-b43fe29d691a",
    "score": 70.0,
    "total_questions": 10,
    "correct_count": 7,
    "incorrect_count": 2,
    "skipped_count": 1,
    "time_spent_seconds": 540,
    "completed_at": "2026-03-22T18:30:00.000000+00:00",
    "results": [
        {
            "question_index": 1,
            "selected_option_index": 2,
            "correct_option_index": 2,
            "is_correct": true,
            "is_skipped": false,
            "explanation": "..."
        }
    ]
}
```

## 5) Lich su attempt theo quiz

**GET** `/api/v1/learning/quizzes/{quiz_id}/attempts?limit=20&offset=0`

### Response

```json
[
    {
        "attempt_id": "07a5f8c7-5f73-4ce9-ae27-3efb52b771d4",
        "quiz_id": "9c4f4d26-b838-4f64-b6c5-b43fe29d691a",
        "score": 70.0,
        "total_questions": 10,
        "time_spent_seconds": 540,
        "completed_at": "2026-03-22T18:30:00.000000+00:00"
    }
]
```

## 6) Ghi chú kỹ thuật

- Timer hiện là `frontend-only countdown`; backend lưu `time_limit_seconds` để UI hiển thị và gửi kèm metadata.
- Prompt AI ép định dạng JSON chặt; backend retry tối đa 3 lần nếu JSON lỗi hoặc thiếu cấu trúc.
- Submit luu du lieu vao bang `quiz_attempts` (answers, score, total_questions, time_spent, completed_at).
