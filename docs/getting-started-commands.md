# EduSmart Backend - Command Guide cho người mới

Tài liệu này tập trung vào các câu lệnh cần dùng hằng ngày để làm việc với backend.

## 1. Điều kiện cần trước khi chạy

- Python 3.13
- Poetry 2.x
- Docker Desktop (để chạy PostgreSQL + MinIO)

Kiểm tra nhanh:

```bash
python --version
poetry --version
docker --version
docker compose version
```

## 2. Setup project lần đầu

Đứng tại thư mục backend:

```bash
cd <your-path>/backend
```

Cài dependencies:

```bash
poetry install
```

Tạo file môi trường local:

```bash
cp .env.example .env
```

Lưu ý:

- Khi chạy local bằng Poetry, `DATABASE_URL` nên là `localhost`.
- Giá trị mẫu đang dùng:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres_password@localhost:5432/edusmart_db
```

## 3. Chạy hạ tầng (PostgreSQL + MinIO)

Khởi động services:

```bash
docker compose up -d
```

Kiểm tra trạng thái:

```bash
docker compose ps
```

Xem log database:

```bash
docker compose logs -f db
```

Dừng services:

```bash
docker compose down
```

## 4. Chạy migration database (Alembic)

Apply migration mới nhất:

```bash
poetry run alembic upgrade head
```

Xem revision hiện tại:

```bash
poetry run alembic current
```

Rollback 1 bước:

```bash
poetry run alembic downgrade -1
```

Tạo migration mới (khi đổi models):

```bash
poetry run alembic revision -m "your_migration_name"
```

## 5. Chạy FastAPI backend

Chạy local:

```bash
poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Kiểm tra API:

- Health: `GET http://localhost:8000/`
- Swagger: `http://localhost:8000/docs`

## 6. Test Auth khi chưa có frontend

Bạn vẫn test được OAuth flow bằng cách tạm redirect về backend endpoint.

### 6.1 Cập nhật trong `.env`

```env
FRONTEND_LOGIN_SUCCESS_REDIRECT=http://localhost:8000/api/v1/auth/me
FRONTEND_LOGIN_FAILURE_REDIRECT=http://localhost:8000/docs
```

### 6.2 Khởi động lại backend và test

```bash
poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Mở trình duyệt:

- `http://localhost:8000/api/v1/auth/google/login`

Sau khi đăng nhập Google xong:

- Nếu redirect về `/api/v1/auth/me` và thấy JSON user thì login + cookie hoạt động.

Test thêm refresh/logout (dùng cùng browser session):

```bash
curl -i -X POST http://localhost:8000/api/v1/auth/refresh
curl -i -X POST http://localhost:8000/api/v1/auth/logout
```

## 7. Lệnh kiểm tra code

Lint:

```bash
poetry run ruff check src
```

Format check nhanh (nếu cần):

```bash
poetry run ruff format --check src
```

Run test:

```bash
poetry run pytest -q
```
