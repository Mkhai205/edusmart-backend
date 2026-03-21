# EduSmart Backend - Docker Production trên VPS

Tai lieu nay huong dan cach su dung `docker-compose.production.yml` va `.env.production` de chay Postgres + MinIO tren VPS.

## 1) Chuan bi tren VPS

```bash
# Ubuntu
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

Dang xuat va dang nhap lai 1 lan sau khi them user vao group docker.

## 2) Trien khai stack production

Di chuyen vao thu muc backend chua 2 file:

- `docker-compose.production.yml`
- `.env.production`

Kiem tra compose parse dung truoc khi chay:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml config
```

Chay services:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

Kiem tra trang thai:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
```

Xem log:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml logs -f db
docker compose --env-file .env.production -f docker-compose.production.yml logs -f minio
```

## 3) Lenh van hanh thuong ngay

Dung services:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml down
```

Dung va xoa volume (mat du lieu DB/MinIO):

```bash
docker compose --env-file .env.production -f docker-compose.production.yml down -v
```

Cap nhat image va chay lai:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml pull
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

Khoi dong lai 1 service:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml restart db
docker compose --env-file .env.production -f docker-compose.production.yml restart minio
```

## 4) Ket noi tu may local khi code

Dat `.env` local tro vao VPS:

```env
DATABASE_URL=postgresql+asyncpg://postgres:<password>@<VPS_IP>:<POSTGRES_DB_PORT>/edusmart_db
MINIO_ENDPOINT=<VPS_IP>:<MINIO_API_PORT>
MINIO_ACCESS_KEY=<MINIO_ROOT_USER>
MINIO_SECRET_KEY=<MINIO_ROOT_PASSWORD>
```

Luu y: `MINIO_ACCESS_KEY` va `MINIO_SECRET_KEY` cua app phai trung voi `MINIO_ROOT_USER` va `MINIO_ROOT_PASSWORD` tren VPS.

## 5) Bao mat bat buoc

Khong mo cong 5432, 9000, 9001 cho toan bo Internet.
Chi mo cho IP dev hoac dung SSH tunnel:

```bash
ssh -L 8015:localhost:8015 -L 8016:localhost:8016 user@<VPS_IP>
```

Neu dung UFW, whitelist theo IP:

```bash
sudo ufw allow 22/tcp
sudo ufw allow from <YOUR_PUBLIC_IP> to any port 8015 proto tcp
sudo ufw allow from <YOUR_PUBLIC_IP> to any port 8016 proto tcp
sudo ufw allow from <YOUR_PUBLIC_IP> to any port 8017 proto tcp
sudo ufw enable
sudo ufw status
```

## 6) Luu y cau hinh production

- Doi tat ca secrets production (DB password, MinIO password, JWT secret, Google secret).
- Dat `APP_ENV=production` trong `.env.production`.
- Dat `COOKIE_SECURE=True` khi backend chay qua HTTPS.
- OAuth redirect URI phai la domain/IP backend thuc te, khong de `localhost` tren VPS.
