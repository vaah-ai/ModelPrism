# F27: API Key Management

## Metadata
- **ID:** F27
- **Phase:** Scale
- **Effort:** Medium
- **Dependencies:** F1, F3, F4, F5
- **Acceptance Criteria Count:** 7

## Description

API key management provides the full lifecycle for the `sk-mp-` prefixed keys that external clients use to authenticate against ModelPrism's OpenAI-compatible proxy endpoints (F28). Every API key belongs to a workspace, is hashed at rest using SHA-256, and carries a scope JSONB payload that controls which models the key may access, what rate limits apply, and which source IPs are permitted. The backend surfaces four JSON:API endpoints — list (`GET /api/keys`), create (`POST /api/keys`), revoke (`DELETE /api/keys/{id}`), and update scope/label (`PATCH /api/keys/{id}`) — while the frontend renders a dedicated API key management page at `frontend/app/pages/dashboard/keys/index.vue` with a key-list table, a one-time-visible key-creation dialog (the raw key is shown exactly once), inline controls for revocation, label editing, and scope changes, and a per-key usage drilldown linking to F29.

Key creation follows the same one-time-visibility pattern as agent registration tokens (F6): the backend generates a cryptographically random 48-byte token using `secrets.token_urlsafe(48)`, prepends `sk-mp-` plus a 6-character hex entropy prefix for recognizability (e.g., `sk-mp-a3f8k2...`), computes the SHA-256 hash, stores only the hash in the `api_keys.key_hash` column (F3), and returns the full plaintext key exactly once in the JSON:API creation response. A `meta.warning` field in the response instructs the frontend to display a strongly worded copy-now prompt. If the user navigates away or dismisses the dialog without copying, the key is unrecoverable — they must generate a new one. The full key is never written to any log, database column, error response, or audit trail.

The scope JSONB field (`api_keys.scope`, F3) controls three dimensions of access per key: (1) `allowedModels` — an array of `model_deployments.id` UUIDs or `["*"]` for unrestricted access (default `["*"]`); (2) `rateLimits` — optional per-key rate limit overrides (`rpmMax`, `tpmMax`) that supersede workspace defaults when set (F30); and (3) `allowedIps` — optional CIDR whitelist (`["10.0.0.0/8", "192.168.1.0/24"]`) for restricting which source networks may use the key, enforced at the proxy middleware layer in `backend/app/middleware/proxy_auth.py`. Keys can be `active`, `revoked`, or `expired` (the `key_status` enum from F3). Revocation is immediate and irreversible: the `status` column is set to `revoked` and any in-flight requests using that key are rejected from the next middleware check onward (no grace period). Expired keys (past `expires_at`) are automatically treated as `revoked` at the middleware level but retain their row with `status = "expired"` for audit trail purposes.

The feature integrates with F5 (auth) by deriving the caller's workspace from their JWT session — a user can only manage keys within their own workspace, enforced by the `workspace_id` filter on all queries (F3 data isolation, F34). It integrates with F29 (usage tracking) by recording each proxy request's `api_key_id` in the `usage_records` table via foreign key `api_key_id → api_keys.id ON DELETE SET NULL` (F3), enabling per-key usage breakdowns on the dashboard. It integrates with F30 (rate limiting) by reading the key's `scope.rateLimits` at proxy-auth time to apply key-specific throttling. It integrates with F28 (proxy) as the primary authentication mechanism: every `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, and `/v1/models` request carries `Authorization: Bearer sk-mp-...`, and the proxy middleware performs a SHA-256 hash lookup against the `api_keys` table before routing. It integrates with F32 (workspace settings) for workspace-level defaults on key rate limits and with F33 (RBAC) for role-based permission enforcement on key CRUD operations.

## Concrete Examples (Specification by Example)

### Example 1: Create a New API Key with Default Scope

- **Input:** A workspace admin navigates to `dashboard/keys/index.vue` and clicks "Create API Key". A modal dialog appears asking for a label (optional) and an expiry date (optional, default none). The admin enters `"Production app key"`, leaves the expiry blank, and clicks "Generate".

- **Action:** The frontend calls `POST /api/keys` with a JSON:API request body:
  ```json
  {
    "data": {
      "type": "apiKeys",
      "attributes": {
        "label": "Production app key",
        "expiresAt": null,
        "scope": {
          "allowedModels": ["*"],
          "rateLimits": null,
          "allowedIps": null
        }
      }
    }
  }
  ```

  The backend validates the JWT (F5), extracts `workspace_id` and `user_id`, checks that the workspace's active key count is below its tier limit (default 5 for free tier, configurable in `workspaces.settings` JSONB per F32), generates a 48-byte cryptographically random token via `secrets.token_urlsafe(48)`, prepends `sk-mp-` and a 6-character prefix derived from the first 3 entropy bytes hex-encoded (e.g., `sk-mp-a3f8k2`), producing the full key `sk-mp-a3f8k2.7g8h9i0j...rest`, computes SHA-256 of the full key string, inserts a row into `api_keys` with the hash, prefix, label, `scope = {"allowedModels": ["*"], "rateLimits": null, "allowedIps": null}`, `status = "active"`, `workspace_id`, and `user_id`, and returns the full plaintext key in the response.

- **Expected Output:** HTTP 201 Created. Response body (JSON:API):
  ```json
  {
    "data": {
      "type": "apiKeys",
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "attributes": {
        "prefix": "sk-mp-a3f8k2",
        "label": "Production app key",
        "status": "active",
        "scope": {
          "allowedModels": ["*"],
          "rateLimits": null,
          "allowedIps": null
        },
        "key": "sk-mp-a3f8k2.7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0r1s2t",
        "lastUsedAt": null,
        "expiresAt": null,
        "createdAt": "2026-06-07T14:00:00+00:00",
        "updatedAt": "2026-06-07T14:00:00+00:00"
      },
      "links": {
        "self": "/api/keys/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
      }
    },
    "meta": {
      "warning": "Copy this API key now — it will not be shown again. Treat it like a password."
    }
  }
  ```

- **Side effect:** The `api_keys` table stores `key_hash = sha256("sk-mp-a3f8k2.7g8h...")` and `prefix = "sk-mp-a3f8k2"`. The full plaintext key is never persisted in the database. If the admin dismisses the modal without copying, they must generate a new key.

### Example 2: List and Filter API Keys

- **Input:** A user with an active JWT session navigates to `dashboard/keys/index.vue`. The workspace has 5 API keys: 3 active, 1 revoked, 1 expired.

- **Action:** The frontend calls `GET /api/keys?page[offset]=0&page[limit]=20&sort=-createdAt` to fetch all keys in the workspace.

- **Expected Output:** HTTP 200 OK. Response body (JSON:API paginated collection):
  ```json
  {
    "data": [
      {
        "type": "apiKeys",
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "attributes": {
          "prefix": "sk-mp-a3f8k2",
          "label": "Production app key",
          "status": "active",
          "scope": {
            "allowedModels": ["*"],
            "rateLimits": null,
            "allowedIps": null
          },
          "lastUsedAt": "2026-06-07T13:55:00+00:00",
          "expiresAt": null,
          "createdAt": "2026-06-07T14:00:00+00:00",
          "updatedAt": "2026-06-07T14:00:00+00:00"
        },
        "links": {
          "self": "/api/keys/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        }
      },
      {
        "type": "apiKeys",
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "attributes": {
          "prefix": "sk-mp-b4e7f1",
          "label": "CI/CD pipeline key",
          "status": "revoked",
          "scope": {
            "allowedModels": ["md_abc123", "md_def456"],
            "rateLimits": { "rpmMax": 60, "tpmMax": 100000 },
            "allowedIps": ["10.0.0.0/8"]
          },
          "lastUsedAt": "2026-06-06T18:30:00+00:00",
          "expiresAt": "2026-07-01T00:00:00+00:00",
          "createdAt": "2026-06-01T10:00:00+00:00",
          "updatedAt": "2026-06-06T18:35:00+00:00",
          "revokedAt": "2026-06-06T18:35:00+00:00"
        },
        "links": {
          "self": "/api/keys/b2c3d4e5-f6a7-8901-bcde-f12345678901"
        }
      }
    ],
    "meta": {
      "total": 5,
      "count": 5,
      "offset": 0,
      "limit": 20
    },
    "links": {
      "self": "/api/keys?page%5Boffset%5D=0&page%5Blimit%5D=20&sort=-createdAt",
      "first": "/api/keys?page%5Boffset%5D=0&page%5Blimit%5D=20&sort=-createdAt",
      "last": "/api/keys?page%5Boffset%5D=0&page%5Blimit%5D=20&sort=-createdAt",
      "next": null,
      "prev": null
    }
  }
  ```

  Note: The `key` attribute is NEVER included in list or single-get responses — it is only present in the `201 Created` response from key generation. The frontend renders the `prefix` column (e.g., `sk-mp-a3f8k2...`) as a truncated display value in the table.

### Example 3: Revoke an API Key Immediately

- **Input:** A workspace admin identifies a compromised key (`sk-mp-a3f8k2...`) on the dashboard and clicks the "Revoke" button in the key row.

- **Action:** The frontend calls `DELETE /api/keys/a1b2c3d4-e5f6-7890-abcd-ef1234567890` with the authenticated JWT session. The backend looks up the key, verifies it belongs to the caller's workspace (`WHERE id = :uuid AND workspace_id = :ws_id`), verifies the key's current `status` is not already `revoked` or `expired`, sets `status = "revoked"` and `updated_at = now()`, and records a `revoked_at` timestamp.

- **Expected Output:** HTTP 200 OK. Response body:
  ```json
  {
    "data": {
      "type": "apiKeys",
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "attributes": {
        "prefix": "sk-mp-a3f8k2",
        "label": "Production app key",
        "status": "revoked",
        "lastUsedAt": "2026-06-07T13:55:00+00:00",
        "revokedAt": "2026-06-07T14:05:00+00:00",
        "createdAt": "2026-06-07T14:00:00+00:00",
        "updatedAt": "2026-06-07T14:05:00+00:00"
      },
      "links": {
        "self": "/api/keys/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
      }
    }
  }
  ```

- **Side effect:** Any subsequent proxy request carrying `Authorization: Bearer sk-mp-a3f8k2...` will be rejected by the proxy middleware with HTTP 401 and error code `key_revoked`. The usage-records tied to this key (F29) remain intact for audit — the key ID is referenced from `usage_records.api_key_id` with `ON DELETE SET NULL`, so usage history is preserved even after revocation.

### Example 4: Update Key Scope and Label

- **Input:** The admin wants to restrict an existing key (`sk-mp-a3f8k2`) to only access `Qwen2.5-72B-Instruct` and `Llama-3.1-8B-Instruct` (deployment UUIDs `md_abc123` and `md_def456`), cap it at 30 RPM and 50,000 TPM, and add an IP whitelist.

- **Action:** The frontend calls `PATCH /api/keys/a1b2c3d4-e5f6-7890-abcd-ef1234567890` with a JSON:API partial-update body:
  ```json
  {
    "data": {
      "type": "apiKeys",
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "attributes": {
        "label": "Production app key (restricted)",
        "scope": {
          "allowedModels": ["md_abc123", "md_def456"],
          "rateLimits": { "rpmMax": 30, "tpmMax": 50000 },
          "allowedIps": ["203.0.113.0/24", "198.51.100.0/24"]
        }
      }
    }
  }
  ```

- **Expected Output:** HTTP 200 OK. Response body reflects the updated attributes:
  ```json
  {
    "data": {
      "type": "apiKeys",
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "attributes": {
        "prefix": "sk-mp-a3f8k2",
        "label": "Production app key (restricted)",
        "status": "active",
        "scope": {
          "allowedModels": ["md_abc123", "md_def456"],
          "rateLimits": { "rpmMax": 30, "tpmMax": 50000 },
          "allowedIps": ["203.0.113.0/24", "198.51.100.0/24"]
        },
        "lastUsedAt": "2026-06-07T13:55:00+00:00",
        "expiresAt": null,
        "createdAt": "2026-06-07T14:00:00+00:00",
        "updatedAt": "2026-06-07T14:10:00+00:00"
      },
      "links": {
        "self": "/api/keys/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
      }
    }
  }
  ```

- **Side effect:** Subsequent proxy requests using this key will be subject to 30 RPM / 50,000 TPM limits (enforced by F30) and restricted to model deployments `md_abc123` and `md_def456`. Requests from IPs outside `203.0.113.0/24` or `198.51.100.0/24` are rejected with HTTP 403 and error code `ip_not_allowed`.

### Example 5: Proxy Authentication Flow — Valid, Revoked, Expired, and Unknown Keys

- **Input:** An external client sends a POST to the OpenAI-compatible proxy endpoint:
  ```
  POST /v1/chat/completions
  Authorization: Bearer sk-mp-a3f8k2.7g8h9i0j...
  Content-Type: application/json
  ```

- **Action:** The proxy middleware (`backend/app/middleware/proxy_auth.py`) extracts the token from the `Authorization` header, strips the `Bearer ` prefix, computes SHA-256 of the full token string, queries the `api_keys` table for a row where `key_hash = :hash` AND `status = 'active'` AND (`expires_at IS NULL` OR `expires_at > now()`). On a match, it loads the `scope` JSONB to enforce model access, reads `rateLimits` to configure per-key throttling in F30, performs CIDR IP whitelist matching using Python's `ipaddress` module against the client's source IP (extracted from `X-Forwarded-For` first hop, falling back to `REMOTE_ADDR`), and attaches `api_key_id`, `workspace_id`, and `scope` to the request context for downstream routing (F31) and usage tracking (F29).

- **Expected Output (valid key):** HTTP 200 OK. The proxy routes the request to the appropriate vLLM instance (F31), streams the response (if `stream: true`), and writes a `usage_records` row (F29) with the `api_key_id`.

- **Expected Output (revoked key):** HTTP 401 Unauthorized. Response body:
  ```json
  {
    "error": {
      "message": "API key has been revoked.",
      "type": "authentication_error",
      "code": "key_revoked"
    }
  }
  ```

- **Expected Output (expired key):** HTTP 401 Unauthorized. Response body:
  ```json
  {
    "error": {
      "message": "API key has expired.",
      "type": "authentication_error",
      "code": "key_expired"
    }
  }
  ```

- **Expected Output (unknown key — hash not found):** HTTP 401 Unauthorized. Response body:
  ```json
  {
    "error": {
      "message": "Invalid API key.",
      "type": "authentication_error",
      "code": "invalid_key"
    }
  }
  ```

- **Expected Output (IP not whitelisted):** HTTP 403 Forbidden. Response body:
  ```json
  {
    "error": {
      "message": "IP address not allowed by this API key's whitelist.",
      "type": "permission_error",
      "code": "ip_not_allowed"
    }
  }
  ```

### Example 6: Per-Key Usage Breakdown on Dashboard

- **Input:** A workspace admin viewing `dashboard/keys/index.vue` clicks on a key row to see its usage details. The frontend fetches the key's usage records for the current billing period.

- **Action:** The frontend calls `GET /api/usage?filter[apiKeyId]=a1b2c3d4-e5f6-7890-abcd-ef1234567890&filter[from]=2026-06-01T00:00:00Z&filter[to]=2026-06-07T23:59:59Z` with the authenticated JWT session. The backend queries `usage_records WHERE api_key_id = :key_id AND workspace_id = :ws_id AND created_at BETWEEN :from AND :to`, aggregating total input tokens, output tokens, request count, and cost for the period.

- **Expected Output:** HTTP 200 OK. Response body (JSON:API):
  ```json
  {
    "data": {
      "type": "keyUsage",
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "attributes": {
        "totalRequests": 1250,
        "totalInputTokens": 850000,
        "totalOutputTokens": 320000,
        "totalTokens": 1170000,
        "estimatedCostCents": 2340,
        "periodStart": "2026-06-01T00:00:00+00:00",
        "periodEnd": "2026-06-07T23:59:59+00:00"
      }
    }
  }
  ```

- **Side effect:** The frontend renders a usage summary card for the key, showing request count, token breakdown, and estimated cost. A link to the full usage page (F29) with the `api_key_id` filter pre-applied allows deeper drill-down.

## Acceptance Criteria

- **ACF27-1: Key generation returns full plaintext key exactly once** — `POST /api/keys` with a valid JWT access token (F5) and a complete JSON:API request body returns HTTP 201 with the full plaintext API key in `data.attributes.key`. The `key` field is present only in this creation response. Subsequent `GET /api/keys` and `GET /api/keys/{id}` responses never include the `key` attribute. The `api_keys.key_hash` column stores `sha256(full_key_string)`. The raw key is never written to any server log, database column, error response, or Celery/APScheduler background task output. A CI lint rule (`no-full-api-key-log`) greps for `sk-mp-` patterns in f-strings, `logger.*()` calls, and `print()` statements within `backend/app/api/keys.py` and `backend/app/middleware/proxy_auth.py` and flags them as build errors.

- **ACF27-2: Key revocation is immediate and irreversible** — Calling `DELETE /api/keys/{id}` with a valid JWT from an admin/owner role sets `api_keys.status = "revoked"` and populates `revoked_at`. Within 5 seconds of the response being sent, a proxy request using the revoked key returns HTTP 401 with `{"error": {"code": "key_revoked"}}`. Revoked keys cannot be re-activated by any endpoint — calling `PATCH` on a revoked key returns HTTP 422 with error code `key_revoked`. The `revoked_at` timestamp is recorded and visible in the JSON:API response attributes. Calling `DELETE` on an already revoked or expired key returns HTTP 409 Conflict with error code `key_already_inactive`.

- **ACF27-3: Scope changes take effect on the next proxy request** — Calling `PATCH /api/keys/{id}` with a modified `scope.allowedModels` array takes effect immediately for all subsequent proxy requests. Within 5 seconds of the PATCH response, a proxy request targeting a model not in the new `allowedModels` list returns HTTP 403 with `{"error": {"code": "model_not_allowed"}}`. The IDs in the `allowedModels` array must correspond to valid `model_deployments.id` UUIDs within the same workspace, or the update is rejected with HTTP 422 and an error details array listing which IDs are invalid. The `scope.rateLimits` update causes the next Redis sliding-window check (F30) to use the new RPM/TPM values.

- **ACF27-4: IP whitelist enforcement at the proxy middleware** — When a key's `scope.allowedIps` is non-null and non-empty, any proxy request whose source IP (extracted from the first hop of `X-Forwarded-For`, falling back to `REMOTE_ADDR`) does not match at least one CIDR block in the array is rejected with HTTP 403 and error code `ip_not_allowed`. The middleware performs CIDR matching using Python's `ipaddress` module (`ipaddress.ip_address(src_ip) in ipaddress.ip_network(cidr)`) before the key hash lookup. If `scope.allowedIps` is null or an empty array, no IP restriction applies and the request proceeds to key hash lookup. The IP check runs before the hash lookup to avoid exposing key validity to unapproved networks.

- **ACF27-5: Expired keys are automatically rejected and swept** — Creating a key with `expiresAt` set to a past date returns HTTP 422 with error code `expires_at_in_past`. A key whose `expires_at` is in the future but has since passed current time is treated as `status = "expired"` at the proxy middleware level: the middleware applies `WHERE status = 'active' AND (expires_at IS NULL OR expires_at > now())` in its lookup query, so an expired key returns HTTP 401 with error code `key_expired`. A background sweep task (APScheduler running every 5 minutes) sets `api_keys.status = 'expired'` on rows where `expires_at < now() AND status = 'active'`, keeping the table in sync for dashboard queries filtered by `status = 'active'`. Creating a key without an `expiresAt` field (null) results in a permanent key that never expires.

- **ACF27-6: Workspace data isolation and cross-workspace access prevention** — A user authenticated with a workspace `ws_A` JWT can only see, create, update, and revoke keys where `api_keys.workspace_id = ws_A`. All management queries include `WHERE workspace_id = :current_workspace_id` as a mandatory filter. Attempting to access a key belonging to workspace `ws_B` via its UUID returns HTTP 404 (not 403, to avoid leaking key existence). A user from workspace `ws_A` with role `viewer` or `member` can list keys (`GET /api/keys`) and view individual keys (`GET /api/keys/{id}`) but receives HTTP 403 Forbidden with error code `insufficient_permissions` when calling `POST /api/keys`, `PATCH /api/keys/{id}`, or `DELETE /api/keys/{id}`. Users with role `admin` or `owner` have full CRUD access. Role enforcement is handled by the F5 auth middleware comparing `request.state.user.role` against the required permission level.

- **ACF27-7: Key count limits are enforced per workspace tier** — Free-tier workspaces (identified by `workspaces.cloud_mode = true` and no active billing subscription, F37) are limited to 5 active API keys simultaneously. Paid-tier workspaces are limited to 100 active keys by default (configurable via `workspaces.settings.maxActiveKeys`). The limit is enforced in `backend/app/services/key_service.py` by counting `SELECT COUNT(*) FROM api_keys WHERE workspace_id = :ws_id AND status = 'active'` before insertion. Exceeding the limit returns HTTP 422 with error code `max_keys_reached` and a detail message including the current count and limit. Revoked and expired keys do not count toward the limit. The key count is cached in Redis with key `key_count:{workspace_id}` and a 30-second TTL to avoid counting on every creation, invalidated on key create/revoke/expire.

## Technical Notes

### File Paths

| Layer | File | Purpose |
|-------|------|---------|
| ORM model | `backend/app/models/api_key.py` | SQLAlchemy `ApiKey` model with columns from F3 schema |
| Pydantic schemas | `backend/app/schemas/key.py` | JSON:API request/response schemas for `apiKeys` resource type: `ApiKeyCreateSchema`, `ApiKeyUpdateSchema`, `ApiKeyResponseSchema` (list/detail), `ApiKeyCreatedResponseSchema` (includes `key`), `KeyUsageResponseSchema` |
| Route handler | `backend/app/api/keys.py` | FastAPI router with `GET /api/keys`, `POST /api/keys`, `DELETE /api/keys/{id}`, `PATCH /api/keys/{id}` |
| Service layer | `backend/app/services/key_service.py` | Business logic: key generation with hashing, revocation, scope validation, expiry sweep count enforcement |
| Crypto utility | `backend/app/utils/crypto.py` | Shared `generate_api_key()`, `hash_api_key()` functions (also used by F6 agent token generation) |
| Proxy auth middleware | `backend/app/middleware/proxy_auth.py` | Middleware that intercepts `/v1/*` requests, performs key hash lookup + IP whitelist + scope loading |
| Frontend page | `frontend/app/pages/dashboard/keys/index.vue` | API key management page |
| Frontend component | `frontend/app/components/keys/ApiKeyList.vue` | Reusable key list table component with status badges, copy-prefix, revoke action, scope edit |
| Frontend composable | `frontend/app/composables/useApiKeys.ts` | Pinia composable for API key state management; wraps all CRUD calls to `/api/keys` |

### API Key Format

```
sk-mp-{prefix6}.{base64_urlsafe_48_bytes}
```

- Prefix: First 3 bytes of entropy hex-encoded = 6 hex characters (readable, collision-resistant at small scale)
- Body: 48 bytes via `secrets.token_urlsafe(48)` = 64 characters in base64url
- Total length: `sk-mp-` (6) + prefix (6) + `.` (1) + body (64) = 77 characters
- Example: `sk-mp-a3f8k2.7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0r1s2t`
- Stored hash: `sha256(full_string)` → 64 hex characters

### Key Generation Algorithm

```python
# backend/app/utils/crypto.py
import secrets, hashlib

def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix, key_hash).
    
    - full_key: the complete plaintext key returned to the user exactly once
    - prefix: "sk-mp-{6hex}" stored in plaintext for UI display
    - key_hash: SHA-256 hexdigest stored in the database
    """
    body = secrets.token_urlsafe(48)              # 64 base64url chars
    prefix_bytes = secrets.token_bytes(3)
    prefix_hex = prefix_bytes.hex()               # 6 hex chars
    prefix = f"sk-mp-{prefix_hex}"
    full_key = f"{prefix}.{body}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash
```

### Scope JSONB Structure

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

- `allowedModels`: Array of `model_deployments.id` UUIDs or `["*"]` for all models. Default `["*"]`. Validated against `model_deployments WHERE workspace_id = :ws_id` on create/update.
- `rateLimits.rpmMax`: Max requests per minute (integer, null = use workspace default from `workspaces.settings.defaults.rateLimits.rpmMax` per F32).
- `rateLimits.tpmMax`: Max tokens per minute (integer, null = use workspace default from F32).
- `allowedIps`: Array of CIDR notation strings or null for no IP restriction. Individual entries are validated against the `ipaddress` module on create/update.

### Database Columns (from F3)

The `api_keys` table schema (defined in `backend/app/models/api_key.py`):

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default `uuid.uuid4` |
| `workspace_id` | UUID | FK → `workspaces.id` ON DELETE CASCADE, NOT NULL |
| `user_id` | UUID | FK → `users.id` ON DELETE SET NULL, NULL |
| `prefix` | VARCHAR(20) | NOT NULL (e.g., `sk-mp-a3f8k2`) |
| `key_hash` | VARCHAR(255) | NOT NULL, UNIQUE (SHA-256 hexdigest) |
| `label` | VARCHAR(255) | NULL |
| `status` | key_status | NOT NULL, default `active` (enum: `active`, `revoked`, `expired`) |
| `scope` | JSONB | NOT NULL, default `{}` |
| `last_used_at` | TIMESTAMPTZ | NULL |
| `expires_at` | TIMESTAMPTZ | NULL |
| `revoked_at` | TIMESTAMPTZ | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

Indexes: `ix_api_keys_key_hash` on `key_hash`, `ix_api_keys_workspace_id` on `workspace_id`, composite index `(key_hash, workspace_id)` for proxy auth lookups.

### Edge Cases

- **Re-creation race:** If two simultaneous `POST /api/keys` requests arrive, each gets a unique random token. No uniqueness constraint on the full key beyond SHA-256 hash collisions (astronomically unlikely). No deduplication logic required. The `key_count` Redis check uses `INCR` + expiry to prevent double-counting.

- **Revoke while proxy request in-flight:** The middleware checks key hash at request start. If a key is revoked after the request has passed auth but before the response is written, the in-flight request completes normally. Revocation only affects subsequent requests. This is acceptable — F29 tracks the `api_key_id` on the completed `usage_record` for audit.

- **Key count limits:** Free-tier workspaces are limited to 5 active API keys; paid tiers scale to 100+. Enforced in `key_service.py` by counting `WHERE workspace_id = :ws_id AND status = 'active'` before creation. The limit is configurable per workspace via `workspaces.settings.maxActiveKeys` JSONB (F32).

- **Expiry sweep:** An APScheduler background task running every 5 minutes sets `status = 'expired'` on rows where `expires_at < now() AND status = 'active'`. This is an optimization — the proxy middleware already rejects expired keys via the SQL WHERE clause. The sweep keeps the `api_keys` table in sync for dashboard queries filtered by status.

- **Log sanitisation:** All log lines in `backend/app/api/keys.py` and `backend/app/middleware/proxy_auth.py` must log only the `prefix` (e.g., `sk-mp-a3f8k2...`). Logging the full key is prohibited. A CI lint rule (`no-full-api-key-log`) greps for `sk-mp-` patterns in f-string or format arguments and flags them as build errors.

- **last_used_at update strategy:** The `last_used_at` column is updated by the proxy middleware on each successful request. To avoid write amplification, the update is performed in a background task (Fire-and-forget via Redis queue or Celery) rather than synchronously in the proxy hot path. The update queries `UPDATE api_keys SET last_used_at = now() WHERE id = :key_id AND last_used_at < now() - INTERVAL '60 seconds'` to limit writes to at most one per minute per key.

- **Expired key update rejection:** PATCH on an expired key is allowed — the admin may update the label or scope. Revocation of an expired key is a no-op (status already effective). Creating a key with `expiresAt` in the past is rejected at the validation layer.

### Frontend UX Notes

- **Key creation dialog:** A modal with a label text input, optional expiry date picker, and a "Generate" button. On success, the modal transitions to a "key revealed" state showing the full key in a monospace font with a "Copy to Clipboard" button. A prominent warning banner reads: "Copy this key now — it will not be shown again." The modal auto-dismisses after 5 minutes or on manual close. If dismissed without copying, the key is permanently unrecoverable.

- **Key list table:** Columns: prefix (truncated, `sk-mp-a3f8k2...`), label, status badge (active=green, revoked=red, expired=gray), last used, created, expires, actions (revoke, edit scope, view usage). Rows are sortable by created date and filterable by status. Empty state: "No API keys yet. Create one to get started." with a CTA button.

- **Revoke confirmation:** Clicking revoke shows a confirmation dialog: "Revoke key `sk-mp-a3f8k2...`? This action cannot be undone. Any services using this key will immediately lose access." with Cancel and Confirm Revoke buttons.

- **Scope editor:** An inline panel or side-drawer with three sections: model access (multi-select of available model deployments in the workspace), rate limits (RPM/TPM inputs, pre-filled with workspace defaults), and IP whitelist (CIDR input with add/remove chips).

### Integration Points

- **F1 (Backend scaffolding):** Uses the FastAPI router system, database engine, Redis connection pool, and APScheduler for the expiry sweep task.
- **F3 (Database schema):** Reads and writes the `api_keys` table with `key_hash`, `prefix`, `scope`, `status`, `expires_at`, `last_used_at`, `revoked_at` columns. The `(key_hash, workspace_id)` composite index enables fast proxy auth lookups.
- **F4 (JSON:API serialization):** All dashboard endpoints use JSON:API format. The `ApiKeySchema` extends `ResourceObject` with `type: "apiKeys"`, camelCase-ified attributes, and conditional `key` field (only in creation response). The `ApiKeyCreateSchema`, `ApiKeyUpdateSchema`, and `ApiKeyResponseSchema` are distinct Pydantic models.
- **F5 (Auth):** API key management endpoints require JWT authentication (same middleware). Workspace membership and role are checked via the `workspace_members` table — the `current_user` dependency from F5 provides `user_id`, `workspace_id`, and `role`.
- **F28 (OpenAI proxy / F31 routing):** The proxy middleware reads key scope to enforce model access. See `backend/app/middleware/proxy_auth.py`.
- **F29 (Usage tracking):** Each proxy request records `api_key_id` in `usage_records`. The dashboard `GET /api/usage?filter[apiKeyId]=...` endpoint (F29) provides per-key usage breakdowns. The `api_key_id` FK is defined in F3 with `ON DELETE SET NULL`.
- **F30 (Rate limiting):** Reads `scope.rateLimits` from the key to apply per-key throttling before per-IP throttling. Detailed in F30 spec.
- **F32 (Workspace management):** Reads `workspaces.settings.defaults.rateLimits` and `workspaces.settings.maxActiveKeys` for workspace-level defaults and key count limits.
- **F33 (RBAC):** Key management permissions follow the role matrix defined in F33. Viewer and member roles are read-only for keys. Admin and owner roles have full CRUD.
- **F34 (Workspace data isolation):** The `workspace_id` filter on every query ensures cross-workspace key access is impossible. See F34 for the full isolation pattern.

### Dependency Graph

```
F1 (FastAPI + DB + Redis) ──→ F3 (api_keys schema) ──→ F4 (JSON:API deserialization)
                                         │
                                         ├─→ F27 (This feature)
                                         │
    F5 (JWT auth + roles) ───────────────┘
                                         │
    F3 (usage_records.api_key_id FK) ───┼─→ F29 (Usage tracking)
                                         │
    F3 (scope.rateLimits) ──────────────┼─→ F30 (Rate limiting)
                                         │
    F27 key_hash lookup ────────────────┼─→ F28 (Proxy auth middleware)
                                         │
    F27 scope.allowedModels ────────────┼─→ F31 (Request routing)
                                         │
    F32 workspace settings defaults ────┘
                                         │
    F33 role-based permission matrix ────┘
```

## Depends on: F1 (Backend scaffolding), F3 (Database schema — api_keys table), F4 (JSON:API serialization), F5 (Email/password auth — JWT sessions, workspace membership, role enforcement)
