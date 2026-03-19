### 1. Frontend (Next.js) gọi backend endpoint đăng nhập

- `GET /api/v1/auth/google/login`
- Backend sinh `state`, set cookie `edusmart_oauth_state`, rồi redirect sang Google.

### 2. User đăng nhập Google

### 3. Google redirect về backend với `authorization code`

- `GET /api/v1/auth/google/callback?code=...&state=...`

### 4. Backend xử lý callback

- Validate `state` từ query so với cookie.
- Exchange `code` lấy `access_token` và `id_token`.
- Verify `id_token` (hoặc fallback lấy userinfo).
- Lấy thông tin user: `sub`, `email`, `name`, `picture`.
- Upsert user vào bảng `users`.
- Tạo access token (60 phút) + refresh token.
- Lưu hash của refresh token vào DB (`refresh_tokens`) để revoke/rotate.
- Set HTTP-only cookies:
	- `edusmart_access_token`
	- `edusmart_refresh_token`

### 5. Backend redirect về frontend

- Success: `FRONTEND_LOGIN_SUCCESS_REDIRECT`
- Fail: `FRONTEND_LOGIN_FAILURE_REDIRECT?message=...`

### 6. Refresh token flow

- Frontend gọi `POST /api/v1/auth/refresh`.
- Backend validate refresh token + check token hash còn hiệu lực trong DB.
- Revoke token cũ, cấp access+refresh token mới (rotation).

### 7. Logout flow

- Frontend gọi `POST /api/v1/auth/logout`.
- Backend revoke refresh token hiện tại (và token liên quan user nếu xác định được).
- Backend xóa toàn bộ auth cookies.
