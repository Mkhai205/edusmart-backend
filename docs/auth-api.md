## Auth API (Backend)

Base URL local: `http://localhost:8000`
API prefix: `/api/v1`

### 1) Start Google Login
- Method: `GET`
- Path: `/api/v1/auth/google/login`
- Behavior:
  - Redirect browser to Google consent screen.
  - Set cookie `edusmart_oauth_state` (HTTP-only) to validate OAuth state.

### 2) Google Callback
- Method: `GET`
- Path: `/api/v1/auth/google/callback`
- Query params: `code`, `state`
- Behavior:
  - Validate OAuth state.
  - Exchange authorization code with Google.
  - Verify/get Google profile.
  - Create/update user.
  - Issue `access` + `refresh` token cookies (HTTP-only).
  - Redirect to frontend success URL.

### 3) Refresh Access Token
- Method: `POST`
- Path: `/api/v1/auth/refresh`
- Cookie required: `edusmart_refresh_token`
- Behavior:
  - Validate refresh JWT.
  - Check refresh token hash in DB and revoke old token.
  - Issue new access + refresh cookies.

### 4) Logout
- Method: `POST`
- Path: `/api/v1/auth/logout`
- Behavior:
  - Revoke current refresh token if present.
  - Revoke all active refresh tokens of current user if access token exists.
  - Clear auth cookies.

### 5) Current User
- Method: `GET`
- Path: `/api/v1/auth/me`
- Cookie required: `edusmart_access_token`
- Returns:
  - `id`, `email`, `full_name`, `avatar_url`

## Cookie policy (local)
- `HttpOnly`: true
- `Secure`: false
- `SameSite`: `lax`

## Production notes
- Set `COOKIE_SECURE=true` and use HTTPS.
- Consider `COOKIE_SAMESITE=none` if frontend/backend cross-site.
- Rotate `JWT_SECRET_KEY` periodically.
