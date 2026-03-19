# EduSmart Backend - Hướng dẫn Git/GitHub cho người mới

Tài liệu này dành cho người mới bắt đầu làm việc nhóm với Git và GitHub.

## 1. Cài đặt và kiểm tra Git

Kiểm tra Git đã cài chưa:

```bash
git --version
```

Cấu hình thông tin commit (chỉ cần làm 1 lần):

```bash
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
```

Kiểm tra cấu hình:

```bash
git config --global --list
```

## 2. Clone project từ GitHub

```bash
git clone https://github.com/Mkhai205/edusmart-backend.git
cd edusmart-backend
```

Kiểm tra remote:

```bash
git remote -v
```

## 3. Các lệnh Git cơ bản dùng hằng ngày

Xem trạng thái file:

```bash
git status
```

Xem lịch sử commit ngắn gọn:

```bash
git log --oneline --graph --decorate -n 15
```

Xem thay đổi chưa stage:

```bash
git diff
```

Xem thay đổi đã stage:

```bash
git diff --staged
```

## 4. Workflow chuẩn khi làm task mới

### Bước 1: Cập nhật code mới nhất từ `main`

```bash
git checkout main
git pull origin main
```

### Bước 2: Tạo branch mới theo task

```bash
git checkout -b feature/auth-refresh-token
```

Gợi ý đặt tên branch:

- `feature/<ten-tinh-nang>`
- `fix/<ten-loi>`
- `docs/<ten-tai-lieu>`

### Bước 3: Code và kiểm tra thay đổi

```bash
git status
git diff
```

### Bước 4: Stage + Commit

Stage toàn bộ file đã sửa:

```bash
git add .
```

Hoặc stage file cụ thể:

```bash
git add src/modules/auth/router.py
```

Commit:

```bash
git commit -m "feat(auth): add refresh token rotation"
```

### Bước 5: Push branch lên GitHub

Push lần đầu cho branch:

```bash
git push -u origin feature/auth-refresh-token
```

Lần sau chỉ cần:

```bash
git push
```

### Bước 6: Tạo Pull Request (PR)

- Vào GitHub repo
- Chọn branch vừa push
- Tạo PR vào `main`
- Mô tả rõ: mục tiêu, file thay đổi, cách test

## 5. Quy ước message commit (gợi ý)

Mẫu:

```text
type(scope): short description
```

Ví dụ:

- `feat(auth): add google oauth callback handler`
- `fix(alembic): load DATABASE_URL from .env`
- `docs(git): add onboarding command guide`
- `refactor(auth): split token logic into service`

Các type hay dùng:

- `feat`: thêm tính năng
- `fix`: sửa lỗi
- `docs`: tài liệu
- `refactor`: cải tiến code không đổi behavior
- `test`: thêm/sửa test
- `chore`: việc phụ trợ (tooling, config)

## 6. Đồng bộ branch với `main` khi có thay đổi mới

Trong lúc đang làm branch `feature/...`, nếu `main` có cập nhật:

```bash
git fetch origin
git merge origin/main
```

Nếu có conflict:

1. Mở file conflict, sửa các vùng `<<<<<<<`, `=======`, `>>>>>>>`
2. Stage lại file đã sửa
3. Commit merge

```bash
git add .
git commit -m "merge: resolve conflicts with main"
```

## 7. Undo an toàn (không mất lịch sử)

Bỏ stage file:

```bash
git restore --staged <file>
```

Bỏ thay đổi chưa commit ở 1 file:

```bash
git restore <file>
```

Sửa commit message gần nhất:

```bash
git commit --amend -m "new message"
```

Tạo commit đảo ngược 1 commit cũ (an toàn khi đã push):

```bash
git revert <commit_sha>
```

## 8. Xử lý lỗi thường gặp

### Lỗi 1: `fatal: not a git repository`

Nguyên nhân:

- Bạn chưa đứng trong thư mục project chứa `.git`.

Cách xử lý:

```bash
cd <your-path>/backend
```

### Lỗi 2: `rejected` khi `git push`

Nguyên nhân:

- Remote có commit mới hơn local.

Cách xử lý:

```bash
git pull --rebase origin <your-branch>
git push
```

### Lỗi 3: `Please commit your changes or stash them before you merge`

Nguyên nhân:

- Bạn đang có thay đổi local chưa commit.

Cách xử lý nhanh:

```bash
git add .
git commit -m "wip: save local changes"
# hoặc dùng stash
git stash
```

## 9. Bộ lệnh nhanh dùng mỗi ngày

```bash
# 1) về main và cập nhật
git checkout main
git pull origin main

# 2) tạo branch task mới
git checkout -b feature/your-task-name

# 3) sau khi code xong
git add .
git commit -m "feat(scope): your message"
git push -u origin feature/your-task-name
```

## 10. Checklist trước khi tạo PR

- `git status` phải sạch (không còn file lạ chưa kiểm soát).
- Chạy được lệnh test/lint tối thiểu của project.
- Commit message rõ ràng, dễ review.
- PR mô tả cách kiểm thử và ảnh hưởng của thay đổi.
