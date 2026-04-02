# Flashcards API

Module flashcards ho tro 2 nhom chinh:

- Sinh flashcard tu dong (AI): queue + xem trang thai + review.
- Quan ly flashcard thu cong: tao/sua/xoa bo the va card.

Base prefix: `/api/v1/learning/flashcards`

## 1) Tao bo flashcard thu cong

**POST** `/manual/sets`

Request:

```json
{
  "document_id": "2b2551f9-7b35-4f22-915f-27b4f337b421",
  "title": "Sinh hoc co ban - Manual"
}
```

`document_id` la optional cho bo the thu cong. Co the gui `null` hoac bo qua field nay.

Response `201`:

```json
{
  "set_id": "8a603873-b6e6-4ca2-98cc-2de8a0d265eb",
  "document_id": "2b2551f9-7b35-4f22-915f-27b4f337b421",
  "title": "Sinh hoc co ban - Manual",
  "algorithm": "manual_v1",
  "generation_status": "completed",
  "card_count": 0,
  "completed_at": "2026-04-02T15:10:10.000000+00:00",
  "created_at": "2026-04-02T15:10:10.000000+00:00"
}
```

## 2) Sua ten bo the thu cong

**PATCH** `/manual/sets/{set_id}`

Request:

```json
{
  "title": "Sinh hoc co ban - Chapter 1"
}
```

Response `200`: cung schema voi create set.

## 3) Xoa bo the thu cong

**DELETE** `/manual/sets/{set_id}`

Response: `204 No Content`

## 4) Them card thu cong vao bo the

**POST** `/manual/sets/{set_id}/cards`

Request:

```json
{
  "card_type": "term_definition",
  "front": "Ty the",
  "back": "Bao quan tong hop ATP cho te bao.",
  "image_url": null,
  "image_keyword": "mitochondria"
}
```

Response `201`:

```json
{
  "card_id": "efd1f1f7-d59f-4cb2-bcb6-4f47f6b21394",
  "set_id": "8a603873-b6e6-4ca2-98cc-2de8a0d265eb",
  "card_type": "term_definition",
  "front": "Ty the",
  "back": "Bao quan tong hop ATP cho te bao.",
  "image_url": null,
  "image_keyword": "mitochondria",
  "ease_factor": 2.5,
  "interval_days": 1,
  "repetitions": 0,
  "next_review_at": "2026-04-02T15:11:00.000000+00:00",
  "last_rating": null
}
```

## 5) Sua card thu cong

**PATCH** `/manual/cards/{card_id}`

Request (gui field nao thi cap nhat field do):

```json
{
  "front": "Ty the (Mitochondria)",
  "back": "Bao quan tao ATP thong qua ho hap te bao.",
  "image_keyword": "cell mitochondria"
}
```

Response `200`: schema card item.

## 6) Xoa card thu cong

**DELETE** `/manual/cards/{card_id}`

Response: `204 No Content`

## 7) Endpoint hien co de hien thi/review

- `GET /` list bo flashcard
- `GET /{set_id}` chi tiet bo the
- `GET /{set_id}/cards` list card trong bo
- `POST /cards/{card_id}/review` review card hard|medium|easy
- `POST /generate` queue sinh bo card bang AI
- `GET /review/today` list card den han on tap

## Notes

- Cac endpoint manual van enforce owner: chi thao tac tren document/set/card cua user hien tai.
- Khi tao/xoa card thu cong, `card_count` cua set duoc cap nhat dong bo.
- Update card thu cong se chi sua nhung field co trong payload.
