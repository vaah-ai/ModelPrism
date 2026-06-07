# F5: Email password auth

## Metadata
- **ID:** F5
- **Phase:** Foundation
- **Effort:** Medium
- **Dependencies:** F1, F3
- **Acceptance Criteria Count:** 7

## Description

Feature F5 implements the entire authentication layer for ModelPrism, covering user registration, login, JWT session management with access/refresh token rotation, password reset, and account lockout. Authentication is email/password only — no OAuth providers — as defined in ADR-003. The backend handles all auth logic in FastAPI route handlers and services, while the frontend uses a custom Pinia `useAuth` composable that calls the FastAPI JWT endpoints directly, bypassing sidebase/nuxt-auth.

The auth system integrates with the F3 database schema at three tables: `users` (account data, password hash, failed login tracking), `sessions` (refresh token storage with hash, expiry, revocation), and `password_reset_tokens` (time-limited reset tokens). The JWT token format uses `python-jose` with RS256 or HS256 signing: a short-lived access token (15 minutes, stored in memory on the frontend) and a longer-lived refresh token (7 days, stored in an httpOnly cookie). Refresh token rotation ensures that each refresh cycle invalidates the previous token, preventing replay attacks.

Account lockout triggers after 5 consecutive failed login attempts, locking the account for 1 hour. Password reset flows through a time-limited email token (15-minute expiry) sent to the registered email address. The auth system also powers workspace membership in F32 by associating authenticated users with their workspace membership records and enforcing role-based access (Owner/Admin/Member/Viewer) at the middleware level.

## Concrete Examples (Specification by Example)

### Example 1: Successful User Registration and Automatic Workspace Creation

- **Input:** `POST /api/auth/register` with `application/json` body:
  ```json
  {
    "email": "alice@example.com",
    "password": "secure-password-123",
    "display_name": "Alice Johnson"
  }
  ```
- **Action:** Backend validates email format (RFC 5321, max 320 chars), enforces minimum password length of 8 characters, lowercases the email, hashes the password with bcrypt (cost factor 12), creates a new `users` row with UUID `a1b2c3d4-e5f6-7890-abcd-ef1234567890`, creates a default workspace named `"Alice's Workspace"` with UUID `ws-11111111-2222-3333-4444-555555555555`, creates a `workspace_members` row with role `owner`, creates a `sessions` row with a fresh refresh token hash, and issues a JWT access token and refresh token.
- **Expected Output:** HTTP 201 Created. Response body:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "rt_v2_abc123def456...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "email": "alice@example.com",
      "display_name": "Alice Johnson"
    },
    "workspace": {
      "id": "ws-11111111-2222-3333-4444-555555555555",
      "name": "Alice's Workspace",
      "slug": "alices-workspace",
      "role": "owner"
    }
  }
  ```
  A Set-Cookie header sets the refresh token as an httpOnly, Secure, SameSite=Strict cookie with path=/api/auth and max-age=604800 (7 days).

### Example 2: Login, Token Refresh, and Expired Token Rejection

- **Input (Login):** `POST /api/auth/login` with:
  ```json
  {
    "email": "alice@example.com",
    "password": "secure-password-123"
  }
  ```
- **Action (Login):** Backend looks up user by lowercased email, verifies bcrypt hash, creates a new session row with refresh token hash, and returns access + refresh tokens.
- **Expected Output (Login):** HTTP 200 OK. Response contains `access_token` (expires 900s), `refresh_token` (raw), `user` object, and `workspace` object. The access token JWT payload decodes to `{"sub": "a1b2c3d4-...", "exp": 1718000000, "iat": 1717999100, "type": "access"}`.

- **Input (Refresh):** `POST /api/auth/refresh` with httpOnly cookie containing the refresh token (or body `{"refresh_token": "rt_v2_abc123def456..."}`).
- **Action (Refresh):** Backend looks up session by refresh token hash, verifies it is not expired (`expires_at` >= now) and not revoked (`revoked_at` IS NULL), creates a new session row with a new refresh token hash, marks the old session row as revoked (`revoked_at = now()`), and returns a new access token + new refresh token.
- **Expected Output (Refresh):** HTTP 200 OK. Fresh `access_token` and `refresh_token`. The old refresh token is now invalid — any attempt to reuse it returns HTTP 401.

- **Input (Expired):** `GET /api/auth/me` with `Authorization: Bearer eyJhbGciOiJIUzI1NiIs...` where the access token has expired (past `exp` claim).
- **Expected Output (Expired):** HTTP 401 Unauthorized. Response body:
  ```json
  {
    "detail": "Token expired",
    "code": "TOKEN_EXPIRED"
  }
  ```

### Example 3: Account Lockout After 5 Failed Attempts

- **Input:** Sequential `POST /api/auth/login` requests with correct email `alice@example.com` but wrong password, repeated 5 times.
- **Action:** Backend increments `users.failed_login_attempts` on each failure. On the 5th failure, the backend sets `locked_until` to `now() + 1 hour`.
- **Expected Output:**
  - Attempts 1-4: HTTP 401 Unauthorized — `{"detail": "Invalid email or password", "code": "INVALID_CREDENTIALS"}`.
  - Attempt 5: HTTP 429 Too Many Requests — `{"detail": "Account locked. Try again after 2026-06-07T14:30:00Z.", "code": "ACCOUNT_LOCKED", "locked_until": "2026-06-07T14:30:00Z"}`.
  - Any attempt during lockout period: HTTP 429 with same body (does not increment counter).

- **Input (After Lockout Expires):** Same credentials attempted after `locked_until` passes.
- **Expected Output:** HTTP 200 OK with normal login response. `failed_login_attempts` reset to 0.

### Example 4: Password Reset Flow

- **Input (Request):** `POST /api/auth/password-reset` with:
  ```json
  {
    "email": "alice@example.com"
  }
  ```
- **Action:** Backend looks up user by email. If found, generates a secure random token, stores its SHA-256 hash in `password_reset_tokens` with `user_id`, `expires_at = now() + 15 minutes`, and emits a console log message (in development) or sends an email (in production) with the reset URL: `https://dashboard.modelprism.io/reset-password?token=<raw_token>`.
- **Expected Output:** HTTP 200 OK — always returns success to prevent email enumeration:
  ```json
  {
    "message": "If the email exists, a password reset link has been sent."
  }
  ```

- **Input (Reset):** `POST /api/auth/password-reset/confirm` with:
  ```json
  {
    "token": "prt_v2_abc123def456...",
    "new_password": "new-secure-password-456"
  }
  ```
- **Action:** Backend hashes the raw token, looks up `password_reset_tokens` by hash, verifies `expires_at >= now()` and `used_at IS NULL`, marks the token as used (`used_at = now()`), hashes the new password with bcrypt, updates the user's `password_hash`, revokes all active sessions for that user (sets `revoked_at = now()` on all session rows with `user_id` where `revoked_at IS NULL`), and resets `failed_login_attempts` to 0.
- **Expected Output:** HTTP 200 OK:
  ```json
  {
    "message": "Password has been reset successfully."
  }
  ```

- **Edge case:** Reusing the same token returns HTTP 400:
  ```json
  {
    "detail": "Reset token has already been used",
    "code": "TOKEN_USED"
  }
  ```

## Acceptance Criteria

- **ACF5-1: User registration creates user, workspace, and session** — A `POST /api/auth/register` with valid email (RFC 5321), password >= 8 characters, and optional display name returns HTTP 201 with an access token (expires 900s), refresh token, user object (id as UUID), and workspace object (id as UUID, role `owner`). The response includes a Set-Cookie header with the refresh token as httpOnly, Secure, SameSite=Strict. The `users` table contains a row with the lowercased email, bcrypt-hashed password (cost factor 12), and `failed_login_attempts = 0`. The `workspaces` table contains a row with a generated name and unique slug. The `workspace_members` table contains a row linking the user to the workspace with role `owner`. The `sessions` table contains a row with the refresh token hash.

- **ACF5-2: Duplicate email registration returns 409** — A `POST /api/auth/register` with an email that already exists in the `users` table returns HTTP 409 Conflict with a JSON:API-formatted error body: `{"errors": [{"status": "409", "code": "EMAIL_EXISTS", "title": "Email already registered", "detail": "An account with this email already exists."}]}`. No new rows are created in any table. The existing user's password hash, session, and workspace data are unmodified.

- **ACF5-3: Login validates credentials, creates session, and enforces lockout** — A `POST /api/auth/login` with correct credentials returns HTTP 200 with access token (JWT with `sub` as user UUID, `exp` at 900s, `type: "access"`), refresh token, user, and workspace. A `sessions` row is created. Wrong password returns HTTP 401 with `code: "INVALID_CREDENTIALS"` and increments `failed_login_attempts`. After 5 consecutive failures, the account is locked for 1 hour (`locked_until = now() + 3600s`). Subsequent attempts during lockout return HTTP 429 with `code: "ACCOUNT_LOCKED"` and the `locked_until` timestamp, without incrementing the counter. Successful login after lockout expiry resets `failed_login_attempts` to 0.

- **ACF5-4: Refresh token rotation invalidates old tokens** — A `POST /api/auth/refresh` with a valid, non-expired, non-revoked refresh token returns HTTP 200 with a new access token and a new refresh token. The old session row has its `revoked_at` set to the current timestamp. Reusing the old refresh token after rotation returns HTTP 401 with `code: "TOKEN_REVOKED"`. The new refresh token is valid for 7 days from creation. The frontend stores the access token in memory (Pinia store) and the refresh token in an httpOnly cookie.

- **ACF5-5: Password reset generates time-limited, single-use tokens** — A `POST /api/auth/password-reset` with a registered email creates a `password_reset_tokens` row with `expires_at = now() + 15 minutes` and returns HTTP 200 with a generic success message (same message for registered and unregistered emails). The `POST /api/auth/password-reset/confirm` endpoint accepts the raw token and new password (min 8 chars), hashes both, verifies the token is not expired and not used, updates the user's `password_hash`, revokes all active sessions for that user, marks the token as used (`used_at = now()`), and returns HTTP 200. Reusing a consumed or expired token returns HTTP 400 with `code: "TOKEN_USED"` or `code: "TOKEN_EXPIRED"` respectively.

- **ACF5-6: Authenticated user can fetch profile and update it** — A `GET /api/auth/me` with a valid JWT access token in the `Authorization: Bearer` header returns HTTP 200 with the user object: `{"id": "...", "email": "...", "display_name": "...", "is_active": true, "created_at": "2026-06-07T12:00:00Z"}`. A `PUT /api/auth/me` with a valid token and body `{"display_name": "Alice J."}` updates the user's `display_name` and returns the updated user object. A request without a token, with an expired token, or with a malformed token returns HTTP 401.

- **ACF5-7: Auth middleware protects all dashboard API endpoints** — All dashboard REST endpoints under `/api/agents`, `/api/models`, `/api/keys`, `/api/usage`, `/api/benchmarks`, `/api/workspace`, and `/api/admin` return HTTP 401 Unauthorized when no valid JWT access token is provided. The middleware extracts the JWT from the `Authorization: Bearer` header, verifies the signature and expiry, extracts the `sub` claim (user UUID), loads the user from the database (verifying `is_active = true` and account is not locked), attaches the user + workspace context to the request via `request.state`, and passes control to the route handler. If the user is not found or is inactive, the middleware returns HTTP 401 with `code: "USER_INACTIVE"`. The auth middleware does **not** protect the auth endpoints themselves (`/api/auth/register`, `/api/auth/login`, `/api/auth/refresh`, `/api/auth/password-reset`, `/api/auth/password-reset/confirm`), the health endpoint (`/api/health`), or the OpenAI proxy endpoints (`/v1/...`, which have their own token auth).

## Technical Notes

### File Map

**Backend (FastAPI):**
- `backend/app/api/auth.py` — Route handlers: `register`, `login`, `refresh`, `logout`, `me` (GET + PUT), `password_reset`, `password_reset_confirm`. Standard `application/json` (not JSON:API — auth endpoints are the documented exception).
- `backend/app/services/auth_service.py` — Business logic: password hashing/verification (bcrypt, cost 12), JWT creation/verification (python-jose, HS256), refresh token generation (secrets.token_urlsafe(48) with `rt_v2_` prefix), token hashing (SHA-256), account lockout check, session management, password reset token lifecycle.
- `backend/app/middleware/auth.py` — ASGI middleware that intercepts all dashboard `/api/*` requests (except excluded paths), verifies the JWT access token, loads the user and workspace, and attaches them to `request.state`. Returns 401 with JSON:API error format.
- `backend/app/models/user.py` — SQLAlchemy ORM model for `users` table (defined in F3).
- `backend/app/schemas/user.py` — Pydantic schemas: `RegisterRequest`, `LoginRequest`, `RefreshRequest`, `PasswordResetRequest`, `PasswordResetConfirmRequest`, `ProfileUpdateRequest`, `AuthResponse`, `UserResponse`, `WorkspaceResponse`.

**Frontend (Nuxt 4):**
- `frontend/app/composables/useAuth.ts` — Custom Pinia composable wrapping all auth operations. Methods: `register()`, `login()`, `logout()`, `refreshAccessToken()`, `getProfile()`, `updateProfile()`, `requestPasswordReset()`, `confirmPasswordReset()`. Handles token storage (access token in Pinia state, refresh token in httpOnly cookie set by backend; fallback: localStorage access token + cookie refresh token).
- `frontend/stores/auth.ts` — Pinia store: `state` (user, workspace, accessToken, isAuthenticated, isLoading), `getters` (currentUser, currentWorkspace, isOwner, isAdmin), `actions` (login, logout, refresh, setTokens, clearAuth).
- `frontend/app/pages/login.vue` — Login page with email/password form, error display (invalid credentials, account locked with countdown timer), "Forgot password?" link, register link.
- `frontend/app/pages/register.vue` — Registration page with email/password/display-name form, password length validation, error display (email already exists), login link.
- `frontend/app/pages/reset-password.vue` — Two-step flow: step 1 email entry to request reset, step 2 token + new password submission.
- `frontend/app/layouts/dashboard.vue` — Authenticated layout that checks `useAuth().isAuthenticated` on mount, redirects to `/login` if not authenticated, and sets up the axios interceptor for automatic token refresh on 401 responses.
- `frontend/server/api/auth/session.get.ts` — Nitro server route that verifies the JWT from the httpOnly cookie and returns the user session. Used on initial page load to hydrate the auth store without the client needing to expose the access token in JavaScript.

### JWT Token Format

```python
# backend/app/services/auth_service.py

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 900   # 15 minutes
REFRESH_TOKEN_EXPIRE_SECONDS = 604800  # 7 days
REFRESH_TOKEN_BYTES = 48
REFRESH_TOKEN_PREFIX = "rt_v2_"
PASSWORD_RESET_TOKEN_BYTES = 48
PASSWORD_RESET_TOKEN_PREFIX = "prt_v2_"
PASSWORD_RESET_EXPIRE_SECONDS = 900  # 15 minutes
BCRYPT_COST = 12
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_SECONDS = 3600  # 1 hour

def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "exp": now + timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS),
        "iat": now,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

def create_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, token_hash)."""
    raw = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
    return f"{REFRESH_TOKEN_PREFIX}{raw}", sha256(raw.encode()).hexdigest()
```

### Auth Middleware Flow

```
Request arrives at /api/agents/*, /api/models/*, etc.
    │
    ├─ Excluded paths? → Skip middleware → Pass through
    │  [/api/auth/*, /api/health, /v1/*, /docs, /openapi.json]
    │
    ├─ No Authorization header? → 401 {"errors": [{"status":"401", "code":"MISSING_TOKEN", ...}]}
    │
    ├─ JWT decode fails (bad signature, malformed)? → 401 {"code": "INVALID_TOKEN"}
    │
    ├─ JWT expired? → 401 {"code": "TOKEN_EXPIRED"}
    │
    ├─ JWT type !== "access"? → 401 {"code": "INVALID_TOKEN_TYPE"}
    │
    ├─ User not found or inactive? → 401 {"code": "USER_INACTIVE"}
    │
    └─ All checks pass → Attach request.state.user, request.state.workspace
                        → Route handler executes
```

### Frontend Auth Composable Pattern

```typescript
// frontend/app/composables/useAuth.ts
export const useAuth = () => {
  const store = useAuthStore();
  const router = useRouter();
  const api = useApi(); // axios instance with interceptors

  const login = async (email: string, password: string) => {
    const { data } = await api.post('/api/auth/login', { email, password });
    store.setTokens(data.access_token);
    store.setUser(data.user, data.workspace);
    // Refresh token is set as httpOnly cookie by the backend
    // No client-side access needed
    return data;
  };

  const logout = async () => {
    await api.post('/api/auth/logout');
    store.clearAuth();
    router.push('/login');
  };

  // Axios interceptor (registered in plugin):
  // On 401: attempt POST /api/auth/refresh (cookie sent automatically),
  //   on success: retry original request with new access token,
  //   on failure: redirect to /login.
  //
  // Hydration on page load:
  // Call GET /api/auth/me (cookie sends refresh, nitro session handler
  //   validates, returns user + new access token if needed).
};
```

### Important Implementation Details

- **Email lowercasing:** All email addresses are lowercased with `.lower().strip()` before storage and comparison. No `citext` dependency — application-level normalization.
- **Password policy:** Minimum 8 characters. No complexity rules (uppercase, digit, special char not required). This is intentionally permissive to avoid frustration in a developer tool. The bcrypt cost factor of 12 provides adequate protection for the chosen minimum length.
- **Refresh token rotation security:** When a refresh token is used, the old session row is marked `revoked_at = now()`. If a revoked token is presented, all sessions for that user are revoked (compromise detection — someone may have stolen the token). The user must log in again.
- **CORS:** The backend `CORSMiddleware` (configured in F1) allows credentials and permits the frontend origin for auth endpoints that use cookies.
- **Graceful token refresh:** The frontend Axios interceptor queues concurrent requests that arrive during a refresh cycle (a single refresh call is made; all queued requests resume with the new token).
- **Rate limiting on auth endpoints:** Auth endpoints are rate-limited via Redis (configured in F1 rate-limiting middleware): `POST /api/auth/login` at 10 requests/minute per IP (prevents brute-force beyond the account lockout mechanism), `POST /api/auth/register` at 3 requests/minute per IP (prevents account creation spam), `POST /api/auth/password-reset` at 2 requests/5 minutes per email address.
- **Password reset in development:** In development mode (`MODELPRISM_CLOUD=false` or `ENVIRONMENT=development`), the reset token URL is printed to the server console log instead of sending an email. The URL format is `http://localhost:3000/reset-password?token=<raw_token>`.
- **Security at rest:** All sensitive tokens (refresh tokens, password reset tokens) are stored as SHA-256 hashes. The `users.password_hash` column stores the bcrypt hash. The `users.failed_login_attempts` counter has a maximum of 255 to prevent overflow (though practical max is 5 before lockout).
- **Error responses follow JSON:API format** (as established in F4) — all auth error responses use the standard `{"errors": [...]}` envelope with `status`, `code`, `title`, and `detail` fields.

## Depends on: F1, F3
