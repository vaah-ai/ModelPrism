# Security — ModelPrism

> **Audience:** Backend engineers, DevOps, security reviewers, penetration testers  
> **Status:** Draft / Living document  
> **Last updated:** 2026-06-07

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [API Key Security](#2-api-key-security)
3. [Agent Tokens](#3-agent-tokens)
4. [HTTPS / WSS](#4-https--wss)
5. [Docker Security](#5-docker-security)
6. [SQL Injection Prevention](#6-sql-injection-prevention)
7. [XSS / CSRF](#7-xss--csrf)
8. [Rate Limiting](#8-rate-limiting)
9. [Data Isolation](#9-data-isolation)
10. [Secrets Management](#10-secrets-management)
11. [Audit Logging](#11-audit-logging)
12. [Dependency and Supply Chain](#12-dependency-and-supply-chain)
13. [Security Checklist](#13-security-checklist)

---

## 1. Authentication

### 1.1 Credential Policy

- **Method:** Email/password only. No OAuth, no social login, no SMS. (See ADR-003.)
- **Password minimum length:** 8 characters. No mandatory complexity rules (uppercase, digit, special char not required by policy, but bcrypt cost 12 provides adequate protection for the chosen minimum).
- **Email normalization:** All email addresses lowercased with `.lower().strip()` before storage and comparison. No `citext` dependency — application-level normalization.
- **Duplicate email registration:** Returns HTTP 409 with code `EMAIL_EXISTS`. No user, workspace, or session rows are created.

### 1.2 Password Hashing

| Property | Value |
|----------|-------|
| Algorithm | bcrypt |
| Cost factor | 12 |
| Salt | Auto-generated per password (bcrypt built-in) |
| Storage | `users.password_hash` column |

- The bcrypt cost factor (12) yields approximately 250 ms per hash on modern hardware — slow enough to deter brute-force, fast enough for UX on login.
- Password hashes are never logged, exposed in API responses, or shipped in debug dumps.
- The `users.password_hash` column is excluded from all serialization schemas by default (Pydantic `exclude` set).

### 1.3 JWT Tokens

| Property | Access Token | Refresh Token |
|----------|-------------|---------------|
| Algorithm | HS256 | N/A (opaque) |
| Expiry | 15 minutes (900 s) | 7 days (604800 s) |
| Storage (frontend) | In-memory (Pinia store) | httpOnly, Secure, SameSite=Strict cookie |
| Storage (backend) | Not persisted | SHA-256 hash in `sessions` table |
| Prefix | — | `rt_v2_` |
| Random bytes | — | `secrets.token_urlsafe(48)` (48 bytes, 64 base64url chars) |

**JWT payload (access token):**
```json
{
  "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "email": "alice@example.com",
  "active_workspace_id": "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa",
  "workspace_role": "admin",
  "exp": 1717000000,
  "iat": 1716999100,
  "jti": "unique-token-id-xyz",
  "type": "access"
}
```

**Refresh token rotation:**
- Each time a refresh token is used, the backend creates a new `sessions` row and marks the old one as `revoked_at = now()`.
- If a revoked refresh token is presented, **all active sessions for that user are revoked** — this detects token theft.
- The user must log in again after a detected rotation attack.

**Cookie configuration:**
- `Set-Cookie: refresh_token=<value>; Path=/api/auth; HttpOnly; Secure; SameSite=Strict; Max-Age=604800`
- The cookie is scoped to `/api/auth` so only auth endpoints can read it.
- Frontend JavaScript never accesses the refresh token value.

### 1.4 Account Lockout

| Property | Value |
|----------|-------|
| Max failed attempts | 5 consecutive |
| Lockout duration | 1 hour (3600 s) |
| Counter column | `users.failed_login_attempts` (max 255) |
| Lockout column | `users.locked_until` (TIMESTAMPTZ) |

**Flow:**
1. On each failed login, `failed_login_attempts` is incremented.
2. On the 5th failure, `locked_until = now() + 1 hour` is set.
3. During lockout: HTTP 429, code `ACCOUNT_LOCKED`, body includes `locked_until` timestamp.
4. Failed attempts during lockout do **not** increment the counter.
5. Successful login after lockout expiry resets `failed_login_attempts = 0`.
6. Error messages are intentionally generic before lockout (`"Invalid email or password"`) to prevent email enumeration.

### 1.5 Password Reset

| Property | Value |
|----------|-------|
| Token prefix | `prt_v2_` |
| Token entropy | 48 bytes (`secrets.token_urlsafe(48)`) |
| Token expiry | 15 minutes |
| Storage | SHA-256 hash in `password_reset_tokens` |
| Reuse prevention | Single-use (`used_at` column) |

**Request flow:**
1. `POST /api/auth/password-reset` with email — always returns HTTP 200 with generic message to prevent email enumeration.
2. Token URL printed to server console in development; sent via email in production.
3. `POST /api/auth/password-reset/confirm` validates the token hash, expiry, and `used_at IS NULL`.
4. On success: password hash updated, all active sessions revoked, `failed_login_attempts` reset.
5. Reusing an expired or consumed token returns HTTP 400 with `TOKEN_USED` or `TOKEN_EXPIRED`.

### 1.6 Auth Endpoint Rate Limiting

| Endpoint | Limit | Scope |
|----------|-------|-------|
| `POST /api/auth/login` | 10 req/min | Per IP |
| `POST /api/auth/register` | 3 req/min | Per IP |
| `POST /api/auth/password-reset` | 2 req/5 min | Per email address |

All enforced via Redis-backed sliding window counters (see [§8 Rate Limiting](#8-rate-limiting)).

### 1.7 Auth Middleware Exclusions

The JWT auth middleware protects all dashboard REST endpoints (`/api/agents`, `/api/models`, `/api/keys`, `/api/usage`, `/api/benchmarks`, `/api/workspace`, `/api/admin`).

**Excluded paths** (no JWT required):
- `/api/auth/register`
- `/api/auth/login`
- `/api/auth/refresh`
- `/api/auth/password-reset`
- `/api/auth/password-reset/confirm`
- `/api/health`
- `/v1/*` (proxy endpoints — use `sk-` API key authentication)
- `/docs`, `/openapi.json`

---

## 2. API Key Security

API keys (`sk-mp-` format) authenticate external clients against the OpenAI-compatible proxy (`/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, `/v1/models`).

### 2.1 Key Format

```
sk-mp-{prefix6}.{base64url_48_bytes}
```

| Segment | Length | Source |
|---------|--------|--------|
| `sk-mp-` | 6 chars | Static prefix (recognisable, grep-able) |
| `{prefix6}` | 6 hex chars | First 3 bytes of `secrets.token_bytes(3)`, hex-encoded |
| `.` | 1 char | Separator |
| `{base64url}` | 64 chars | `secrets.token_urlsafe(48)` |

Total: 77 characters. Example: `sk-mp-a3f8k2.7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0r1s2t`

### 2.2 Storage and Hashing

- **Algorithm:** SHA-256
- **Stored:** `api_keys.key_hash` — SHA-256 hexdigest of the full key string.
- **Prefix stored in plaintext:** `api_keys.prefix` (e.g., `sk-mp-a3f8k2`) — used for UI display and log correlation.
- **Full key is never persisted** — returned exactly once in the `201 Created` response.
- The hash column has a `UNIQUE` constraint to prevent collision.

```python
# backend/app/utils/crypto.py
import secrets, hashlib

def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix, key_hash)."""
    body = secrets.token_urlsafe(48)
    prefix_bytes = secrets.token_bytes(3)
    prefix_hex = prefix_bytes.hex()
    prefix = f"sk-mp-{prefix_hex}"
    full_key = f"{prefix}.{body}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash
```

### 2.3 One-Time Display

- The full key is included in the `data.attributes.key` field of the JSON:API creation response.
- The `meta.warning` field instructs the frontend to display: *"Copy this API key now — it will not be shown again. Treat it like a password."*
- Subsequent `GET /api/keys` and `GET /api/keys/{id}` responses **never** include the `key` attribute.
- If the user dismisses the creation dialog without copying, the key is permanently unrecoverable.

### 2.4 Scope Model

Each key carries a `scope` JSONB object controlling three dimensions:

```json
{
  "allowedModels": ["*"],
  "rateLimits": {
    "rpmMax": 60,
    "tpmMax": 100000
  },
  "allowedIps": ["203.0.113.0/24", "198.51.100.0/24"]
}
```

- **`allowedModels`:** Array of `model_deployments.id` UUIDs or `["*"]` for unrestricted access. Validated against workspace deployments on create/update.
- **`rateLimits`:** Per-key rate limit overrides (see [§8 Rate Limiting](#8-rate-limiting)).
- **`allowedIps`:** CIDR whitelist. Enforced via `ipaddress.ip_address(src_ip) in ipaddress.ip_network(cidr)` at the proxy middleware layer (F27). Check runs **before** the key hash lookup to avoid exposing key validity to unapproved networks.

### 2.5 Key States

| State | Description | Transition |
|-------|-------------|------------|
| `active` | Key is valid and can authenticate proxy requests | Created in this state |
| `revoked` | Key manually revoked — irreversible | `DELETE /api/keys/{id}` |
| `expired` | Key passed its `expires_at` timestamp | Background sweep task (every 5 min) or automatic slug reject |

### 2.6 Revocation

- Revocation is immediate and irreversible. The `status` column is set to `revoked` and `revoked_at` is recorded.
- No grace period — in-flight requests that pass auth before revocation complete; all subsequent requests receive HTTP 401 with code `key_revoked`.
- Revoked keys cannot be re-activated. Calling `PATCH` on a revoked key returns HTTP 422.

### 2.7 Proxy Authentication Flow

```
Client → POST /v1/chat/completions
         Authorization: Bearer sk-mp-a3f8k2...
                │
                ▼
Proxy middleware:
  1. Extract token from Authorization header
  2. Compute SHA-256 hash of full token
  3. Query api_keys WHERE key_hash = :hash
     AND status = 'active'
     AND (expires_at IS NULL OR expires_at > now())
  4. If not found → HTTP 401 (invalid_key / key_revoked / key_expired)
  5. If IP whitelist present → check client IP against CIDR blocks
     → mismatch → HTTP 403 (ip_not_allowed)
  6. Load scope.allowedModels for downstream model routing
  7. Load scope.rateLimits for per-key throttling
  8. Attach api_key_id, workspace_id, scope to request context
                │
                ▼
          Route to vLLM (F31)
```

### 2.8 Log Sanitisation

- All log lines in `backend/app/api/keys.py` and `backend/app/middleware/proxy_auth.py` must log only the `prefix` (e.g., `sk-mp-a3f8k2...`).
- Logging the full key is prohibited.
- CI lint rule `no-full-api-key-log` greps for `sk-mp-` patterns in f-strings, `logger.*()` calls, and `print()` statements within key-related files and flags them as build errors.

### 2.9 Expiry Sweep

- An APScheduler background task runs every 5 minutes.
- Sets `status = 'expired'` on rows where `expires_at < now() AND status = 'active'`.
- This is an optimisation — the proxy middleware already rejects expired keys via the SQL WHERE clause.
- Expired keys retain their row for audit trail purposes.

---

## 3. Agent Tokens

Agent tokens (`mp_` prefix) authenticate GPU server agents during the registration and WebSocket connection lifecycle.

### 3.1 Token Properties

| Property | Value |
|----------|-------|
| Prefix | `mp_` |
| Entropy | 48 bytes (`secrets.token_urlsafe(48)`) |
| Expiry | 24 hours from generation |
| Storage | SHA-256 hash in `agent_registration_tokens` table |
| Display | One-time (same pattern as API keys) |

### 3.2 Two-Phase Registration

Agent registration uses a two-phase claim flow with a 5-minute timeout:

```
Phase 1 — Claim:
  Agent sends token to POST /api/agents/register
  Backend validates SHA-256 hash, checks expiry, marks token as `claimed`
  Agent receives temporary credentials + WebSocket URL
  Timer starts: agent must complete registration within 5 minutes

Phase 2 — Complete:
  Agent connects to WebSocket with temporary credentials
  Backend verifies the temporary credentials match the claimed token
  Backend creates the `agents` row with the workspace_id from the token
  Token is marked as `completed` (single-use enforced)
  Agent receives persistent WebSocket session + agent_id

On timeout (5 min):
  Claimed-but-incomplete registration is rolled back
  Token returns to `available` state for re-use
```

### 3.3 Security Properties

- **Single-use:** A token used once (Phase 2 complete) cannot be replayed. `agent_registration_tokens.status` transitions: `available` → `claimed` → `completed`.
- **24-hour window:** Tokens expire 24 hours after generation. Expired tokens are rejected at Phase 1 validation.
- **Two-phase isolation:** The claim separates token validation from agent identity creation, preventing a race where two agents claim the same token.
- **Workspace binding:** The token carries an immutable `workspace_id` at generation time. The agent is always created in the generating workspace.
- **Rollback on failure:** If the agent disconnects or fails during Phase 2, the 5-minute timer triggers an automatic rollback (`available` + `claimed_reason = "timeout"` recorded).

---

## 4. HTTPS / WSS

### 4.1 TLS Requirements

- **All production traffic** must use TLS 1.2 minimum (TLS 1.3 preferred).
- **Dashboard frontend:** HTTPS via Caddy (recommended) or Nginx + Let's Encrypt.
- **Backend API:** HTTPS via Caddy reverse-proxy terminating TLS.
- **Agent WebSocket:** WSS (WebSocket over TLS) for all metric streaming. The agent connects outbound, so TLS is termination on the backend-facing endpoint.
- **Agent registration:** HTTPS POST before the WebSocket connection is established.

### 4.2 Cipher Suites

Minimum allowed:
```
TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
```

Blocked: all TLS 1.0/1.1 ciphers, all RC4, 3DES, CBC-mode ciphers.

### 4.3 HSTS Headers

All HTTP responses from the reverse proxy must include:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

- `max-age` = 1 year (31536000 seconds)
- `includeSubDomains` — covers all ModelPrism subdomains
- `preload` — eligible for browser HSTS preload lists

### 4.4 Certificate Management

- **Caddy** auto-provisions and renews TLS certificates via Let's Encrypt's ACME protocol.
- If using Nginx: `certbot` with cron-based auto-renewal. Renewal checked daily.
- Monitoring alert if certificate expires within 14 days.

### 4.5 mTLS (Self-Hosted)

For self-hosted deployments with strict network security requirements:
- Optional mutual TLS between agent and backend.
- The backend presents a server certificate (standard TLS).
- The agent presents a client certificate signed by a deployment-specific CA.
- Configured via environment variables `AGENT_CLIENT_CERT_PATH` and `AGENT_CLIENT_KEY_PATH`.

---

## 5. Docker Security

### 5.1 Agent Container Policy

vLLM model instances run in Docker containers managed by the agent (`modelprism-agent`). The agent launcher applies these security settings:

| Setting | Value | Rationale |
|---------|-------|-----------|
| `--privileged` | **Never** | Containers must not have unrestricted host access |
| `--security-opt no-new-privileges:true` | Always | Prevents privilege escalation inside container |
| `--cap-drop ALL` | Container entry | Drops all Linux capabilities |
| `--cap-add` | `SYS_PTRACE` (if needed by vLLM) | Only if vLLM requires it |
| `--read-only` | Rootfs read-only where possible | Prevents container filesystem tampering |
| `--tmpfs /tmp:noexec,nosuid,size=1G` | Writable tmpfs for scratch | Limits write surface |
| `--memory` | Hard memory limit per vLLM config | Prevents OOM from starving host |
| `--cpus` | CPU pinning (optional) | Prevents CPU contention |
| `--gpus` | `device=0,1` (explicit GPU indices) | GPU device reservation, no blanket access |
| `--network` | `host` or bridge with port mapping | Host network for vLLM performance, bridge for isolation |
| `--restart` | `unless-stopped` | Auto-restart on crash without manual intervention |
| `--stop-timeout` | 30 s | Graceful shutdown window |

**Explicit prohibition:**
```
--privileged                        ✗ Never
--security-opt seccomp=unconfined   ✗ Never
--cap-add=ALL                       ✗ Never
--pid=host                          ✗ Never
--network=host (for agent itself)   ✗ Agent container uses bridge
```

### 5.2 Agent Host Isolation

- The agent itself runs as a **non-root user** (`modelprism`) on the host, not as root.
- The agent is installed via `install.sh` which creates the `modelprism` system user with no login shell (`/usr/sbin/nologin`).
- The agent's Docker socket access is minimal: the agent only needs `docker` CLI or the Docker API socket (`/var/run/docker.sock`). If the socket is mounted, it is mounted read-only where possible.
- GPU device access is mediated through the NVIDIA Container Toolkit (`nvidia-ctk`), not through raw `/dev/nvidia*` files.

### 5.3 Image Policy

- All Docker images (`backend`, `frontend`, `agent`) are built from **distroless** or **slim** base images (e.g., `python:3.11-slim`, `node:22-alpine`).
- No shell or package manager in production images (`rm -rf /var/lib/apt/lists/*` enforced in Dockerfiles).
- Images are scanned for CVEs in CI (Trivy or Grype). Build fails on CRITICAL or HIGH vulnerabilities.
- Images are signed with `cosign` and verified at deployment time.

### 5.4 Docker Compose Security

`docker-compose.yml` (self-hosted deployment):

```yaml
services:
  backend:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=512M

  postgres:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - DAC_OVERRIDE
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password

  redis:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - SETGID
      - SETUID
```

- No service runs as `root` (each image defines a `USER` directive).
- Secrets passed via Docker secrets or environment files, never in compose YAML literals.
- No external port exposure for PostgreSQL or Redis (no `ports:` block unless explicitly required).

---

## 6. SQL Injection Prevention

### 6.1 Policy

**All database queries must use parameterised statements through SQLAlchemy ORM or Core.** Raw SQL string concatenation or f-string interpolation into SQL is prohibited.

### 6.2 Enforcement

| Layer | Mechanism | Rule |
|-------|-----------|------|
| ORM | SQLAlchemy ORM (`session.execute(select(...))`) | All CRUD operations |
| Core | SQLAlchemy Core with `text()` + bound parameters | Complex aggregation queries |
| Raw SQL | `text("SELECT * FROM users WHERE email = :email")` with `.params(email=...)` | Only when ORM cannot express the query |
| F-strings in SQL | **Prohibited** | `text(f"SELECT ... {user_input}")` fails CI |

### 6.3 CI Lint Rule

A `no-raw-sql-injection` ruff lint plugin (or pre-commit hook) scans for patterns matching:
- `execute(f"...`)` with f-strings inside SQL contexts
- String formatting (`%s`, `.format()`) in SQL statements
- Direct string concatenation of request data into query strings

### 6.4 Safe Patterns

```python
# ✅ Safe — SQLAlchemy ORM
stmt = select(Agent).where(Agent.workspace_id == workspace_id)
result = await session.execute(stmt)

# ✅ Safe — Core with bound parameters
stmt = text("""
    SELECT * FROM usage_records
    WHERE workspace_id = :ws_id
      AND created_at BETWEEN :since AND :until
""").params(ws_id=ws_id, since=since, until=until)
result = await session.execute(stmt)

# ❌ Unsafe — never do this
stmt = text(f"SELECT * FROM users WHERE email = '{user_input}'")
```

---

## 7. XSS / CSRF

### 7.1 Frontend Protections

The Nuxt 4 frontend inherits Vue.js's default XSS protections:

- **Template interpolation** (`{{ }}`): Automatically escapes HTML entities. Never renders raw HTML unless explicitly using `v-html`.
- **`v-html` usage:** Prohibited except for rendering trusted, server-sanitised markdown (e.g., benchmark report bodies). All uses reviewed in code review.
- **Attribute binding:** `v-bind` escapes attributes. Dynamic `href` values validated against an allowlist of protocols (`https:`, `mailto:`, `tel:`).
- **`useHead` / `useSeoMeta`:** User-supplied content (model names, agent names) sanitised before being set in page title or meta tags. No raw injection into `<title>` or `<meta>`.

### 7.2 Content-Security-Policy (CSP)

The reverse proxy (Caddy / Nginx) sets the following CSP header on all frontend responses:

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https://huggingface.co;
  font-src 'self';
  connect-src 'self' wss://*.modelprism.io https://huggingface.co;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
```

- **`'unsafe-inline'` for styles:** Required by PrimeVue's dynamic style injection. A future improvement would switch to a nonce-based approach once PrimeVue supports it.
- **`frame-ancestors 'none'`:** Prevents clickjacking by disallowing framing on other domains.
- **`connect-src`:** Allows WebSocket connections to `wss://*.modelprism.io` for real-time metric streaming.
- **`img-src`:** Allows `https://huggingface.co` for HuggingFace model card avatar images.

### 7.3 CSRF Protections

- **Refresh token in httpOnly cookie:** The cookie is scoped to `/api/auth` and uses `SameSite=Strict`. The frontend never exposes the refresh token to JavaScript, preventing CSRF-style token theft.
- **Access token in memory:** The JWT access token is stored in the Pinia store (in-memory, not localStorage/sessionStorage). It is never accessible to other origins.
- **`SameSite=Lax` for session cookies:** Where additional cookies are used, `SameSite=Lax` is the default, preventing cross-site request forgery on state-changing operations.
- **CORS configuration:** `CORSMiddleware` in FastAPI restricts `allow_origins` to the configured frontend origin. Credentials (`allow_credentials=True`) are enabled only for the auth cookie path. All other endpoints use token-based auth with no cookie dependency.

### 7.4 Additional Headers

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

---

## 8. Rate Limiting

Rate limiting operates at multiple layers and is enforced for both the dashboard REST API and the OpenAI-compatible proxy.

### 8.1 Where Rate Limiting Applies

| Path | Limiter | Backend |
|------|---------|---------|
| `POST /api/auth/login` | Per-IP | Redis sliding window |
| `POST /api/auth/register` | Per-IP | Redis sliding window |
| `POST /api/auth/password-reset` | Per-email | Redis sliding window |
| `/v1/chat/completions` and `/v1/completions` | Per-key / Per-IP / Per-workspace (compound) | Redis sliding window |
| `POST /api/agents/register` | Per-IP | Redis sliding window |

### 8.2 Proxy Rate Limiting (F30)

The proxy rate limiter uses a Redis-backed sliding-window approach with sorted sets. Three independent tiers are evaluated and the most restrictive applies:

| Tier | Scope | Counter Key |
|------|-------|-------------|
| Per-key | `api_keys.scope.rateLimits.rpmMax/tpmMax` | `ratelimit:key:{prefix}:rpm` |
| Per-IP | `workspaces.settings.rateLimits.ipRpmMax/ipTpmMax` | `ratelimit:ip:{source_ip}:rpm` |
| Per-workspace | `workspaces.settings.rateLimits.rpmMax/tpmMax` | `ratelimit:ws:{workspace_id}:rpm` |

**Compound minimum:** `effective_limit = min(key_limit, ip_limit, workspace_limit)` for each dimension (RPM, TPM). If a tier has no configured limit, it is excluded from the min.

**Post-response TPM correction:**
- Pre-request: estimate tokens (prompt + `max_tokens`), compare against TPM budget.
- Post-response: read actual `usage.total_tokens` from vLLM response.
- Correct the TPM counter by `(actual - estimate)`. Positive deltas consume more budget; negative deltas refund.

**Rate-limit headers on all proxy responses:**
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 1
X-RateLimit-Reset: 1717754460
```
On 429 responses, additionally:
```
Retry-After: 3
```

### 8.3 Fail-Open Behaviour

- If Redis is unreachable, rate limiting enters **fail-open mode**: all requests are admitted.
- A health-check tick (`redis.ping()` cached 5 s) detects the outage.
- A `CRITICAL` log line is emitted every 30 seconds during degradation.
- `request.state.rate_limit_degraded = true` is set so F29 usage tracking can flag records from the degraded period.
- On Redis recovery, normal operation resumes within one request cycle.

### 8.4 Dashboard API Rate Limiting

Dashboard REST endpoints (non-proxy) use a simpler per-IP rate limit:

| Endpoint group | Limit | Scope |
|----------------|-------|-------|
| All dashboard GET endpoints | 100 req/min | Per IP |
| All dashboard POST/PUT/PATCH/DELETE | 30 req/min | Per IP |

Auth endpoints have their own lower limits (see [§1.6](#16-auth-endpoint-rate-limiting)).

---

## 9. Data Isolation

ModelPrism enforces workspace-level data isolation at three layers: schema, middleware, and repository.

### 9.1 Structural Isolation (Database Schema)

Every workspace-scoped table has a non-null `workspace_id` foreign key:

| Table | FK Column | Target |
|-------|-----------|--------|
| `agents` | `workspace_id` | `workspaces.id` ON DELETE CASCADE |
| `model_deployments` | `workspace_id` | `workspaces.id` ON DELETE CASCADE |
| `api_keys` | `workspace_id` | `workspaces.id` ON DELETE CASCADE |
| `usage_records` | `workspace_id` | `workspaces.id` ON DELETE CASCADE |
| `benchmark_runs` | `workspace_id` | `workspaces.id` ON DELETE CASCADE |
| `agent_logs` | `workspace_id` | `workspaces.id` ON DELETE CASCADE |
| `agent_metrics` | `workspace_id` | `workspaces.id` ON DELETE CASCADE |

Composite indexes (`(workspace_id, ...)`) ensure the mandatory `WHERE workspace_id = :ws` predicates are performant.

### 9.2 Middleware Isolation (Workspace Scope)

**Dashboard path (JWT):**
1. `WorkspaceScopeMiddleware` reads `active_workspace_id` from JWT claims.
2. Verifies the user is an active member of that workspace (`workspace_members` lookup).
3. Attaches `workspace_id` to `request.state`.
4. All repository methods receive `workspace_id` as a mandatory parameter.

**Proxy path (API key):**
1. Proxy auth middleware hashes the `sk-` key and looks up `api_keys.key_hash`.
2. Resolves `workspace_id` from the key's row — no JWT or dashboard session consulted.
3. Attaches resolved workspace to `request.state.resolved_workspace_id`.

**Agent ingestion path (WebSocket / log POST):**
1. Backend derives `workspace_id` from the agent's database record (set immutably at registration).
2. Any `workspace_id` in the incoming payload is silently ignored.

### 9.3 Repository Layer Isolation

All workspace-scoped database access flows through `WorkspaceScopedRepository`:

```python
class WorkspaceScopedRepository:
    model_class = None  # Override in subclass

    async def list(self, session, workspace_id, ...):
        query = select(self.model_class).where(
            self.model_class.workspace_id == workspace_id
        )
        ...

    async def get(self, session, resource_id, workspace_id):
        query = select(self.model_class).where(
            self.model_class.id == resource_id,
            self.model_class.workspace_id == workspace_id,
        )
        ...
```

Individual route handlers never write raw `SELECT` queries — they always delegate to repository methods that inject the workspace filter.

### 9.4 Cross-Workspace Access

- By-ID endpoint for a resource in another workspace returns **HTTP 404** (not 403), to avoid leaking resource existence.
- Response times for "exists in another workspace" and "does not exist anywhere" must differ by less than 50 ms (timing side-channel prevention, verified by CI benchmark).

### 9.5 RBAC Enforcement

Role-based access control (F33) builds on workspace isolation:

| Role | Read resources | Create/Update/Delete |
|------|---------------|---------------------|
| Viewers | ✅ | ❌ |
| Members | ✅ | ❌ (on keys, billing, settings) |
| Admins | ✅ | ✅ |
| Owners | ✅ | ✅ (including workspace deletion) |

- Roles are encoded in the JWT as `workspace_role`.
- A `@requires_role("admin")` decorator at the endpoint level enforces minimum role.
- Service-layer guard clauses re-verify the role from the database on sensitive operations (defence against stale JWT claims).
- Role changes take effect immediately via Redis pub/sub + WebSocket `role_changed` events.

---

## 10. Secrets Management

### 10.1 Principle

**No secrets in code, no secrets in version control.** All secrets are injected at runtime via environment variables.

### 10.2 Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `SECRET_KEY` | JWT signing key (HS256). Min 32 bytes, generated via `openssl rand -hex 32`. | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `HUGGINGFACE_TOKEN` | HF Hub access token for gated models | Agent only |
| `STRIPE_SECRET_KEY` | Stripe API secret key | Cloud only |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret | Cloud only |
| `SMTP_PASSWORD` | Email sending password | Production only |
| `AGENT_CLIENT_CERT_PATH` | mTLS client certificate path | Optional |

### 10.3 `.env.example`

The repository includes `deploy/.env.example` with **placeholder values only**:

```bash
# Security: generate a random secret
SECRET_KEY=change-me-to-a-random-64-hex-string

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/modelprism

# Redis
REDIS_URL=redis://localhost:6379/0

# HuggingFace
HUGGINGFACE_TOKEN=hf_your_token_here

# Stripe (cloud only)
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# SMTP (production only)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=your_smtp_password
```

- `.env` is in `.gitignore`. `.env.example` is committed with placeholders.
- A pre-commit hook (`detect-secrets`) prevents accidental commits of `.env` files.

### 10.4 Production Secret Injection

| Deployment mode | Mechanism |
|----------------|-----------|
| Docker Compose | `.env` file loaded by `docker-compose.yml` via `env_file:` directive, or Docker secrets |
| Manual (systemd) | Environment file (`EnvironmentFile=/etc/modelprism/backend.env`) with `0600` permissions, owned by `modelprism` user |
| Cloud / SaaS | Environment variables set in the hosting platform's secret manager |

### 10.5 Key Rotation

- `SECRET_KEY` rotation invalidates all existing JWT tokens. Rotation procedure:
  1. Generate new key: `openssl rand -hex 32`
  2. Set both `SECRET_KEY` (new) and `SECRET_KEY_PREVIOUS` (old, for grace period) as env vars.
  3. The auth service tries `SECRET_KEY` for JWT decoding first, falls back to `SECRET_KEY_PREVIOUS`.
  4. All new tokens are signed with `SECRET_KEY`.
  5. After one max token lifetime (7 days), remove `SECRET_KEY_PREVIOUS`.
- API keys and agent tokens are rotated by creating new ones and revoking old ones (no batch rotation).
- Stripe webhook secrets rotated via Stripe dashboard.

---

## 11. Audit Logging

### 11.1 Events That Are Audited

| Event | Data Logged | Retention |
|-------|-------------|-----------|
| User registration | User ID, email, IP, timestamp | Indefinite |
| Login (success/failure) | User ID or email, IP, success flag, `failed_login_attempts` after event | Indefinite |
| Password change | User ID, IP, timestamp | Indefinite |
| Password reset | User ID, IP, timestamp | Indefinite |
| API key creation | Key prefix, user ID, workspace ID, IP | Indefinite |
| API key revocation | Key prefix, user ID, workspace ID, IP | Indefinite |
| Agent registration | Agent ID, workspace ID, hostname, IP | Indefinite |
| Agent deregistration | Agent ID, workspace ID, user ID, IP | Indefinite |
| Model deployment | Model deployment ID, workspace ID, user ID, model name, IP | Indefinite |
| Model undeployment | Model deployment ID, workspace ID, user ID, IP | Indefinite |
| Workspace member invite | Inviting user ID, invited email, workspace ID, IP | Indefinite |
| Role change | Changed by user ID, target user ID, old role, new role, workspace ID | Indefinite |
| Workspace deletion | Workspace ID, user ID, IP, timestamp | Indefinite |
| Cross-workspace admin access | Admin user ID, target workspace ID, resource accessed, IP | Indefinite |

### 11.2 Audit Log Storage

- Audit events are stored in a dedicated `audit_log` table (not mixed with application logs).
- The table is append-only: no updates, no deletes (except by legal data-purge request).
- SQLAlchemy ORM writes are synchronous within the request transaction (the audit log is committed atomically with the operation).
- Sensitive fields (passwords, tokens, full API keys) are **never** written to audit logs.

### 11.3 Application Logging

- Application logs (stdout/stderr) are structured JSON with `timestamp`, `level`, `module`, `message`, `request_id`, `user_id` (if authenticated), and `workspace_id` (if scoped).
- Logs never contain: passwords, JWT bodies, full API keys, full agent tokens, session tokens, or credit card numbers.
- Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- `CRITICAL` level triggers an alert (PagerDuty / Slack webhook) in production.

### 11.4 Log Streaming and Retention

- Agent logs are pushed to the backend via `POST /api/agents/{agent_id}/logs` and stored in PostgreSQL with configurable retention per workspace (defaults: 30 days for debug, 90 days for info, 1 year for warnings/errors).
- Backend application logs are rotated daily (logrotate) with 30-day retention.

---

## 12. Dependency and Supply Chain

### 12.1 Dependency Management

| Ecosystem | Tool | Practices |
|-----------|------|-----------|
| Python | `uv` / `pip` + `requirements.txt` | Pinned versions (`==x.y.z`), lock files (`requirements.lock`) |
| Node.js | `pnpm` + `package.json` | `pnpm-lock.yaml` committed to version control |
| Docker | Multi-stage builds | Intermediate artifacts excluded from final image |

### 12.2 Vulnerability Scanning

- **CI pipeline** runs `pip-audit` (Python) and `npm audit` (Node.js) on every PR.
- **Docker images** scanned with Trivy or Grype before publishing.
- **GitHub Dependabot** configured for automated PRs on vulnerable dependencies.
- **Build failure** on any CRITICAL or HIGH severity vulnerability with a fix available.
- **Weekly full-dependency scan** with `safety` (Python) for PyPI vulnerabilities.

### 12.3 Supply Chain Controls

- All images signed with `cosign`. Signature verified before deployment.
- GitHub Actions workflows pin action versions by commit SHA, not tag (prevents tag hijacking).
- Third-party dependencies reviewed for license compatibility (Apache 2.0 project).
- No dependencies pulled from untrusted registries (no custom PyPI indexes, no GitHub Package Registry for deps).

---

## 13. Security Checklist

### 13.1 Pre-Launch

- [ ] Authentication
  - [ ] bcrypt cost factor 12 confirmed in config
  - [ ] Account lockout triggers after 5 failed attempts
  - [ ] Password reset tokens are time-limited (15 min) and single-use
  - [ ] Refresh token rotation implemented
  - [ ] Auth rate limits configured (login: 10/min, register: 3/min)

- [ ] API Keys
  - [ ] Full key shown exactly once on creation
  - [ ] SHA-256 hash stored; plaintext never persisted
  - [ ] Log sanitisation lint rule passes in CI
  - [ ] Expiry sweep background task configured (5-minute interval)

- [ ] Agent Tokens
  - [ ] Two-phase registration with 5-minute timeout
  - [ ] SHA-256 hashed, 24-hour expiry
  - [ ] Single-use enforcement (status transitions: available → claimed → completed)

- [ ] Network
  - [ ] TLS 1.2+ enforced (Caddy / Nginx config)
  - [ ] HSTS header set (`max-age=31536000; includeSubDomains; preload`)
  - [ ] CSP header set
  - [ ] CORS restricted to frontend origin
  - [ ] No inbound ports on GPU servers (agent connects outbound)

- [ ] Docker
  - [ ] No `--privileged` containers
  - [ ] `--cap-drop ALL` on all containers
  - [ ] Read-only rootfs where possible
  - [ ] GPU device reservation explicit (`--gpus device=0,1`)
  - [ ] No shell in production images (distroless/slim base)

- [ ] Database
  - [ ] No raw SQL string concatenation (CI lint rule active)
  - [ ] All queries use SQLAlchemy ORM or parameterised Core
  - [ ] Workspace `workspace_id` filter on every scoped query

- [ ] Secrets
  - [ ] `SECRET_KEY` generated with `openssl rand -hex 32`
  - [ ] `.env` in `.gitignore`; `.env.example` with placeholders
  - [ ] No secrets in code or version control
  - [ ] Production secrets injected via environment files (0600 permissions)

- [ ] Monitoring
  - [ ] Audit log table created with all required event types
  - [ ] Rate-limiting fail-open degraded-mode logging configured
  - [ ] CVE scanning in CI pipeline
  - [ ] Docker image signing with cosign

### 13.2 Ongoing

- [ ] Monthly dependency audit (`pip-audit`, `npm audit`)
- [ ] Quarterly penetration test (in-house or third-party)
- [ ] Key rotation drill every 6 months (`SECRET_KEY`, Stripe keys)
- [ ] Certificate expiry monitoring (alert at 14 days)
- [ ] Review audit logs weekly for anomalous patterns
- [ ] Verify CSP header is present and correct on all frontend responses

---

## References

| Document | Description |
|----------|-------------|
| ADR-003 (auth-approach.md) | Decision to use email/password + custom Pinia composable |
| F5 (email-password-auth.md) | Full authentication feature specification |
| F6 (agent-registration.md) | Agent registration and token lifecycle (two-phase) |
| F27 (api-key-management.md) | API key creation, scoping, revocation lifecycle |
| F28 (openai-proxy.md) | OpenAI-compatible proxy with sk- key authentication |
| F30 (rate-limiting.md) | Redis sliding-window rate limiter specification |
| F33 (role-based-access.md) | RBAC permission matrix and enforcement |
| F34 (workspace-data-isolation.md) | Multi-layer workspace isolation architecture |
| NFR3 (non-functional-requirements.md) | Security non-functional requirements (NFR3.1–3.4) |
| data-models.md | Database schema showing all workspace_id foreign keys |
| deployment.md | TLS, Caddy, Docker Compose security configuration |
