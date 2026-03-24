# Goals API (MVP)

Module Goals hỗ trợ:

- Tao muc tieu hoc tap theo chu ky `daily | weekly | monthly`
- Theo doi tien do va lich su cap nhat
- Tong quan dashboard muc tieu
- Reminder feed + cau hinh nhac nho
- Goi y milestones bang AI

Base path: `/api/v1/learning/goals`

## 1) Tao goal

**POST** `/api/v1/learning/goals`

Body mau:

```json
{
    "title": "Hoan thanh chuong 1",
    "description": "Doc va tom tat 3 bai",
    "document_id": "2b2551f9-7b35-4f22-915f-27b4f337b421",
    "recurrence_type": "weekly",
    "target_date": "2026-03-28",
    "milestones": [
        { "title": "Doc bai 1", "completed": false },
        { "title": "Doc bai 2", "completed": false }
    ],
    "reminder_enabled": true
}
```

Response: `201 Created` + thong tin goal.

## 2) Danh sach goals

**GET** `/api/v1/learning/goals?limit=20&offset=0&status=in_progress&recurrence_type=weekly&document_id=<optional>&due_from=2026-03-20&due_to=2026-03-31`

Filter ho tro:

- `status`: `in_progress | completed | overdue | archived`
- `recurrence_type`: `daily | weekly | monthly`
- `document_id`
- `due_from`, `due_to`

## 3) Chi tiet / cap nhat / xoa goal

- **GET** `/api/v1/learning/goals/{goal_id}`
- **PATCH** `/api/v1/learning/goals/{goal_id}`
- **DELETE** `/api/v1/learning/goals/{goal_id}` (`204 No Content`)

PATCH co the cap nhat:

- `title`, `description`, `document_id`
- `recurrence_type`, `target_date`
- `milestones`, `reminder_enabled`, `status`

## 4) Theo doi tien do

- **POST** `/api/v1/learning/goals/{goal_id}/progress`
- **GET** `/api/v1/learning/goals/{goal_id}/progress`

Body cap nhat tien do:

```json
{
    "progress": 60,
    "note": "Da hoc xong 2/3 bai"
}
```

Rule:

- `progress` trong khoang `0..100`
- Moi lan update duoc ghi vao `goal_progress_logs`
- Service tu dong cap nhat `status` (`completed`/`overdue`/`in_progress`)

## 5) Dashboard

**GET** `/api/v1/learning/goals/dashboard/overview`

Tra ve cac chi so nhanh:

- `in_progress_count`
- `completed_count`
- `overdue_count`
- `due_today_count`
- `due_this_week_count`

## 6) Reminder API

- **GET** `/api/v1/learning/goals/reminders/feed?limit=20&offset=0&channel=in_app`
- **GET** `/api/v1/learning/goals/reminders/preferences`
- **PATCH** `/api/v1/learning/goals/reminders/preferences`

`channel` ho tro: `in_app | email`.

## 7) AI milestone suggestions

**POST** `/api/v1/learning/goals/milestones/suggestions`

Body mau:

```json
{
    "title": "On tap giai tich",
    "description": "Can chia nho ke hoach hoc trong 1 tuan",
    "desired_count": 5
}
```

Response:

```json
{
    "milestones": [
        { "title": "On lai dao ham", "completed": false },
        { "title": "Luyen tap 20 bai", "completed": false }
    ]
}
```

## 8) Quick flow de frontend tich hop

1. Tao goal (`POST /goals`).
2. Hien thi danh sach (`GET /goals`).
3. User update tien do (`POST /goals/{id}/progress`).
4. Poll dashboard + reminder feed (`/dashboard/overview`, `/reminders/feed`).
5. Cho phep user chinh gio digest/timezone (`PATCH /reminders/preferences`).
