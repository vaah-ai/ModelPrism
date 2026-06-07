# F30: Rate Limiting

## Metadata
- **ID:** F30
- **Phase:** Scale
- **Effort:** Medium
- **Dependencies:** F27, F28
- **Acceptance Criteria Count:** 5

## Description

Rate limiting provides multi-layered request throttling for ModelPrism's OpenAI-compatible proxy endpoints (F28). Every `/v1/chat/completions`, `/v1/completions`, and `/v1/models` request passes through a Redis-backed sliding-window rate limiter before reaching the upstream vLLM instance. The system enforces three independent tiers of limits — per-key, per-IP, and per-workspace — and applies the most restrictive of the applicable tiers before admitting a request. This prevents single misbehaving clients from saturating GPU capacity, guards against token-extraction attacks, and ensures fair resource allocation across all workspace members.

The rate limiter runs as FastAPI middleware (`backend/app/middleware/rate_limit.py`) positioned after proxy authentication (F27) and before request routing (F31). At proxy-auth time (F28 middleware), the authenticated API key's `scope.rateLimits` JSONB (from the `api_keys` table) is loaded into the request context; both per-key overrides and the workspace default limits from `workspaces.settings.rateLimits` are evaluated. The middleware examines `rpm_max` (requests per minute) and `tpm_max` (tokens per minute) for each tier, computes a compound effective limit using a min-of-applicable strategy, and compares the current request against Redis-backed sliding-window counters before allowing it through.

Redis is the authoritative counter store. Each counter key has the format `ratelimit:{tier}:{scope_id}:{granularity}` — for example, `ratelimit:key:sk-mp-a3f8k2:rpm` for a per-key RPM counter, or `ratelimit:ip:203.0.113.42:tpm` for a per-IP TPM counter. Counters use a sorted-set sliding-window approach: each request appends a timestamp member to a sorted set keyed by the window identifier, the window is trimmed to `[now - window_seconds, now]`, and the cardinality of the trimmed set is compared against the limit. Expired sorted sets are evicted via Redis `EXPIRE` set to the window duration plus a 10-second grace period. For TPM counters, the estimated request size (input_tokens + output_tokens) is used as the score weight rather than counting each request as 1.

After the proxy completes serving a request, the middleware performs a post-request increment: for non-streaming responses it receives the exact token counts from the response; for streaming responses it receives final usage from the completion event (if the upstream reports it, as vLLM does in its final SSE chunk). The TPM counter is then incremented by the difference between the pre-estimate and the actual count, correcting any over-counting from the pre-request estimate. Integration with F29 (Usage Tracking) captures the final token counts in `usage_records` alongside the rate-limit evaluation metadata — the effective limits that were applied and whether any counter was within 10 % of its ceiling at admission time.

When a limit is exceeded, the middleware returns HTTP 429 Too Many Requests with a JSON body matching OpenAI's rate-limit error format, including a `Retry-After` header calculated as the number of seconds until the next window slot opens. The error response also populates a `meta.rateLimits` object in the proxy's standard JSON:API envelope (or the OpenAI-format error body for proxy endpoints) indicating which limit was hit, the current counter value, and the limit ceiling. This enables client-side backoff and transparent debugging.

Rate-limit configuration is surfaced in two places: (1) per-key overrides in the `api_keys.scope.rateLimits` JSONB (managed via F27's `PATCH /api/keys/{id}`), and (2) workspace defaults in `workspaces.settings.rateLimits` (managed via the workspace settings UI, F32). The workspace defaults apply to all keys in that workspace unless a key explicitly overrides a given dimension with a non-null value in its own scope. On the frontend, the dashboard's settings page at `dashboard/settings/index.vue` includes a "Rate Limits" section where workspace admins can configure default RPM and TPM ceilings, and the API key management page (F27) shows per-key overrides inline in the key detail panel.

## Concrete Examples (Specification by Example)

### Example 1: Per-Key Rate Limit Exceeded (RPM)

- **Input:** A client sends requests using API key `sk-mp-a3f8k2...` at a rate of 75 requests in one minute. The key's `scope.rateLimits` is set to `{"rpmMax": 60, "tpmMax": 100000}` and the workspace default is `{"rpmMax": 100, "tpmMax": 500000}`.

- **Action:** The first 60 requests within the 60-second sliding window pass the RPM check. The 61st request arrives within the same window. The middleware queries Redis sorted set `ratelimit:key:sk-mp-a3f8k2:rpm` with `ZCOUNT timestamp_window -60s +inf` and obtains a count of 60. It compares 60 >= 60 (the limit) and determines the request exceeds the per-key RPM limit. It calculates the earliest expiry of any member in the set (e.g., 2.3 seconds from now) and sets `Retry-After: 3`.

- **Expected Output:** HTTP 429 Too Many Requests. Response body:
  ```json
  {
    "error": {
      "message": "Rate limit exceeded: 60 requests per minute per key. Retry after 3 seconds.",
      "type": "rate_limit_error",
      "code": "rate_limit_exceeded",
      "param": null
    },
    "meta": {
      "rateLimits": {
        "tier": "key",
        "scope": "rpm",
        "limit": 60,
        "current": 60,
        "remaining": 0,
        "resetAt": "2026-06-07T14:01:03+00:00"
      }
    }
  }
  ```

- **Side effect:** The Redis sorted set `ratelimit:key:sk-mp-a3f8k2:rpm` is not modified for this rejected request. The client receives `Retry-After: 3` and may retry after 3 seconds. The F29 usage tracker records the rejected request as a `rate_limited` event (no token count, but a zero-cost row for audit).

### Example 2: Per-Key Rate Limit Exceeded (TPM)

- **Input:** A client makes a streaming chat completion request with `max_tokens: 40000` to `POST /v1/chat/completions` using a key whose `scope.rateLimits.tpmMax` is `100000`. The key already has 95000 tokens counted in the current sliding window.

- **Action:** The middleware estimates the request will consume `input_tokens` (≈ 500 from the prompt) + `max_tokens` (40000) = ~40500 tokens. It queries Redis sorted set `ratelimit:key:sk-mp-a3f8k2:tpm` — each member is weighted by the token count of the request it represents. `ZREVRANGEBYSCORE ... WITHSCORES` computes the sum of scores (total tokens) over the window. The sum is 95000. The estimated addition of 40500 would exceed 100000, so the middleware rejects the request pre-emptively.

- **Expected Output:** HTTP 429 Too Many Requests. Response body:
  ```json
  {
    "error": {
      "message": "Rate limit exceeded: 100000 tokens per minute per key. Retry after approximately 12 seconds.",
      "type": "rate_limit_error",
      "code": "rate_limit_exceeded",
      "param": null
    },
    "meta": {
      "rateLimits": {
        "tier": "key",
        "scope": "tpm",
        "limit": 100000,
        "current": 95000,
        "estimated": 40500,
        "remaining": 5000,
        "resetAt": "2026-06-07T14:01:12+00:00"
      }
    }
  }
  ```

- **Side effect:** The request is rejected before reaching any upstream vLLM instance. No tokens are consumed, no inference is initiated. If the client retries with `max_tokens: 4000`, the estimate drops to ~4500 tokens, which fits within the 5000 remaining — the request is admitted, processed, and the actual token count is debited post-response from the TPM counter (replacing the estimate with the real count).

### Example 3: Per-IP Rate Limit (Workspace Default)

- **Input:** A workspace admin has not configured per-key rate limits on their API keys but has set workspace defaults to `{"rpmMax": 200, "tpmMax": 1000000}`. A client behind IP `203.0.113.42` sends 220 requests in one minute using a key with no per-key overrides. Another client behind a different IP `198.51.100.7` sends only 50 requests in the same minute using the same key.

- **Action:** For the first client, the middleware determines no per-key RPM override exists (`scope.rateLimits.rpmMax` is null). It falls back to the workspace default RPM of 200. It queries `ratelimit:ip:203.0.113.42:rpm` (the per-IP counter, scoped to the workspace's effective limit). The ZCOUNT returns 200 → limit exceeded. For the second client, `ratelimit:ip:198.51.100.7:rpm` returns 50 → within the limit.

- **Expected Output (client 1):** HTTP 429 Too Many Requests:
  ```json
  {
    "error": {
      "message": "Rate limit exceeded: 200 requests per minute per IP. Retry after 2 seconds.",
      "type": "rate_limit_error",
      "code": "rate_limit_exceeded",
      "param": null
    },
    "meta": {
      "rateLimits": {
        "tier": "ip",
        "scope": "rpm",
        "limit": 200,
        "current": 200,
        "remaining": 0,
        "resetAt": "2026-06-07T14:02:02+00:00"
      }
    }
  }
  ```

- **Expected Output (client 2):** HTTP 200 OK. The request is routed to the appropriate vLLM instance (F31) and served normally.

- **Side effect:** Since the key has no per-key RPM override, the effective limit is determined solely by the IP-tier workspace default. If the workspace admin later sets a per-key RPM of 100 on the key, both clients (regardless of source IP) would be limited to 100 RPM through that key, per the `min(rpm_max_key, rpm_max_workspace, rpm_max_ip)` compound minimum logic.

### Example 4: Compound Limits — Minimum of Applicable Tiers Wins

- **Input:** Three limits are active for a request:
  - Key-level: `rpmMax: 60`, `tpmMax: 100000`
  - IP-level (workspace default for this IP): `rpmMax: 200`, `tpmMax: 200000`
  - Workspace-level default: `rpmMax: 200`, `tpmMax: 500000`

  The client sends the 59th request within the sliding window. The per-key RPM counter is at 58 (within the 60 limit). The per-IP RPM counter is at 59 (the IP has other traffic from other keys). The workspace-level counter is at 30.

- **Action:** The middleware evaluates each tier:
  - Key RPM: 58 < 60 ✅
  - IP RPM: 59 < 200 ✅
  - Workspace RPM: 30 < 200 ✅
  All three tiers pass — the request is admitted. The effective limit for the response metadata is `min(60, 200, 200) = 60` RPM, which is the per-key limit.

- **Expected Output:** HTTP 200 OK. The request is served. The response headers include:
  ```
  X-RateLimit-Limit: 60
  X-RateLimit-Remaining: 1
  X-RateLimit-Reset: 1717754460
  ```

- **Side effect:** Each tier's Redis counter is incremented independently. The counters for key, IP, and workspace all advance by 1 (for RPM) or by the estimated/posterior token count (for TPM). This ensures that if one tier's limit is hit, the other tiers' counters reflect the traffic that passed through them, keeping the compound enforcement accurate across all tiers.

### Example 5: Workspace-Level Rate Limit Configuration via Dashboard

- **Input:** A workspace owner navigates to the workspace settings page at `dashboard/settings/index.vue`, clicks the "Rate Limits" section, and configures:
  - Workspace default RPM: `500`
  - Workspace default TPM: `2000000`
  - Per-IP RPM: `100` (default when no key-level override exists)
  - Per-IP TPM: `500000`

- **Action:** The frontend calls `PATCH /api/workspaces/{workspace_id}` with a JSON:API request body:
  ```json
  {
    "data": {
      "type": "workspaces",
      "id": "w-f1a2b3c4-d5e6-7890-abcd-ef1234567890",
      "attributes": {
        "settings": {
          "rateLimits": {
            "rpmMax": 500,
            "tpmMax": 2000000,
            "ipRpmMax": 100,
            "ipTpmMax": 500000
          }
        }
      }
    }
  }
  ```

- **Expected Output:** HTTP 200 OK. The response reflects the updated settings:
  ```json
  {
    "data": {
      "type": "workspaces",
      "id": "w-f1a2b3c4-d5e6-7890-abcd-ef1234567890",
      "attributes": {
        "name": "My Workspace",
        "settings": {
          "rateLimits": {
            "rpmMax": 500,
            "tpmMax": 2000000,
            "ipRpmMax": 100,
            "ipTpmMax": 500000
          },
          "dataRetention": { ... }
        },
        "updatedAt": "2026-06-07T15:30:00+00:00"
      }
    }
  }
  ```

- **Side effect:** The `workspaces.settings` JSONB column is updated. Within 5 seconds of the response, all subsequent proxy requests in the workspace evaluate against the new defaults. Existing in-flight requests complete against the old limits. The frontend shows a success toast and updates the displayed values in the Rate Limits configuration panel. Key-level overrides that were previously set via F27 remain in effect and take precedence over the new workspace defaults.

## Acceptance Criteria

- **ACF30-1: Per-key sliding-window RPM enforcement** — When an API key has `scope.rateLimits.rpmMax` set to a positive integer, the rate limiter rejects every request that would cause the count of requests in the 60-second sliding window to exceed that integer, returning HTTP 429 within 100 ms with the OpenAI-format error body and a `Retry-After` header rounded up to the nearest whole second. The sliding window uses Redis sorted sets with millisecond-precision timestamps, and expired members are automatically evicted via the set's TTL (70 seconds). Keys without `rpmMax` (null or absent) never trigger per-key RPM rejection; they fall through to the workspace default and per-IP tiers.

- **ACF30-2: TPM pre-request estimation with post-response correction** — For the `tpmMax` check, the middleware estimates the request's token consumption as `len(prompt_tokens) + max_tokens` before admitting the request (the prompt is tokenised with `tiktoken` at the proxy layer if not provided in the request body, or uses `prompt_tokens` from the request if present). If the estimated total would exceed the remaining TPM budget, the request is rejected with HTTP 429. After the response is complete (both streaming and non-streaming), the middleware loads the actual `usage.total_tokens` from the response and adjusts the Redis TPM counter by `(actual - estimate)` — a positive delta increases the counter, a negative delta decreases it (refund). The correction must complete within 500 ms of the response headers being sent. If the upstream fails before producing a response, the estimate is final and remains in the counter.

- **ACF30-3: Compound minimum of applicable tiers** — The effective rate limit for any request is `min(limit_key, limit_ip, limit_workspace)` for each dimension (RPM, TPM). If a tier has no configured limit for a dimension (value is null or absent), the tier is excluded from the min calculation. The middleware evaluates all three tiers independently, increments each tier's counter for admitted requests, and returns HTTP 429 if any single tier's limit would be exceeded, with `meta.rateLimits` indicating which tier triggered the rejection. The per-IP limit uses the source IP extracted from `X-Forwarded-For` (first hop) or `REMOTE_ADDR`, and the IP tier uses the workspace-level `settings.rateLimits.ipRpmMax` and `settings.rateLimits.ipTpmMax` as its limit values.

- **ACF30-4: Workspace rate-limit defaults are configurable via the dashboard and take effect within 5 seconds** — Calling `PATCH /api/workspaces/{workspace_id}` with a modified `settings.rateLimits` object updates the workspace's default rate limits. Within 5 seconds of a successful response, all subsequent proxy requests evaluate against the new values. The `settings.rateLimits` JSONB supports four optional integer keys: `rpmMax`, `tpmMax`, `ipRpmMax`, `ipTpmMax`. Setting any key to `null` removes the workspace default for that dimension (no workspace-tier limit applies). The workspace settings cache in Redis (`ws:settings:{workspace_id}`) is invalidated on update so the proxy middleware always reads the latest values. Workspace owners and admins (F33) can modify these settings; members and viewers have read-only access.

- **ACF30-5: Rate-limit headers on every proxy response** — Every admitted proxy response (both streaming and non-streaming) includes the following HTTP response headers, computed from the compound effective limit and current counter state:
  - `X-RateLimit-Limit`: the numeric effective limit for the most restrictive tier
  - `X-RateLimit-Remaining`: `limit - current_count` (0 if at or over the limit)
  - `X-RateLimit-Reset`: Unix timestamp (seconds) when the sliding window will reset for the most restrictive tier
  These headers must be present on successful (2xx) proxy responses and on 429 responses. For 429 responses, `Retry-After` is also set (integer seconds, rounded up). Headers are computed from the Redis counter state at request admission time and are not modified mid-stream for streaming responses.

## Technical Notes

### File Paths

| Layer | File | Purpose |
|-------|------|---------|
| Middleware | `backend/app/middleware/rate_limit.py` | FastAPI `BaseHTTPMiddleware` that intercepts `/v1/*` proxy requests, evaluates all three tiers, applies compound minimum, increments Redis counters, and returns 429 or passes through |
| Proxy auth integration | `backend/app/middleware/proxy_auth.py` | Positioned before rate_limit.py in the middleware stack; loads `api_key_id`, `workspace_id`, and `scope.rateLimits` into `request.state` for the rate limiter to consume |
| Service layer | `backend/app/services/rate_limit_service.py` | Core business logic: `RateLimitService` class with `check_rate_limit()`, `increment_counter()`, `correct_tpm()`, `get_effective_limit()` methods; encapsulates all Redis sorted-set operations |
| Redis client | `backend/app/database.py` | Shared `redis_client` instance (Redis `aioredis` / `redis-py` async client) — the rate limiter uses the same connection pool |
| Workspace settings model | `backend/app/models/workspace.py` | SQLAlchemy `Workspace` model with `settings` JSONB column (updated by F32); rate-limit defaults stored at `settings["rateLimits"]` |
| API key model | `backend/app/models/api_key.py` | SQLAlchemy `ApiKey` model with `scope` JSONB column; per-key overrides at `scope["rateLimits"]` |
| Route handler (workspace settings) | `backend/app/api/workspaces.py` | `PATCH /api/workspaces/{workspace_id}` enpoint for updating workspace settings including rate limits |
| Frontend settings page | `frontend/app/pages/dashboard/settings/index.vue` | Workspace settings page with "Rate Limits" configuration section (RPM, TPM, IP-RPM, IP-TPM fields) |
| Frontend key detail panel | `frontend/app/components/keys/ApiKeyList.vue` | Inline display of per-key rate-limit overrides in the API key management page (F27) |
| Proxy config | `backend/app/config.py` | `RATE_LIMIT_WINDOW_SECONDS` (default 60), `RATE_LIMIT_GRACE_SECONDS` (default 10), `RATE_LIMIT_KEY_PREFIX` (default `"ratelimit:"`) |
| Tests | `backend/tests/test_rate_limit.py` | Integration tests for rate-limit middleware with mocked Redis |

### Redis Key Schema

```
ratelimit:{tier}:{scope_id}:rpm       # Sorted set — each member = timestamp, score = timestamp
ratelimit:{tier}:{scope_id}:tpm       # Sorted set — each member = timestamp, score = token_count
```

Where:
- `{tier}` is one of `key`, `ip`, `ws` (workspace)
- `{scope_id}` is:
  - For `key`: the API key prefix (e.g., `sk-mp-a3f8k2`)
  - For `ip`: the source IP string (e.g., `203.0.113.42`)
  - For `ws`: the workspace UUID (e.g., `w-f1a2b3c4-d5e6-7890-abcd-ef1234567890`)

TTL: `window_seconds + grace_seconds` (default 70s). Set via `EXPIRE` immediately after each write.

### Rate-Limit Evaluation Algorithm

```python
# Pseudocode for rate_limit_service.py

async def check_rate_limit(
    request_state: RequestState,
    redis: Redis,
    config: Settings,
) -> RateLimitResult:
    """Returns PASS or FAIL with the limiting tier and metadata."""

    key_limits = request_state.api_key_scope.get("rateLimits", {}) or {}
    ws_limits = request_state.workspace_settings.get("rateLimits", {}) or {}
    ip = request_state.client_ip

    effective = {
        "rpm": min(
            key_limits.get("rpmMax", INF),
            ws_limits.get("rpmMax", INF),
            ws_limits.get("ipRpmMax", INF),   # ← per-IP falls under ws default
        ),
        "tpm": min(
            key_limits.get("tpmMax", INF),
            ws_limits.get("tpmMax", INF),
            ws_limits.get("ipTpmMax", INF),
        ),
    }

    window_seconds = config.rate_limit_window_seconds  # 60
    now = time.time()
    cutoff = now - window_seconds

    for dimension in ("rpm", "tpm"):
        limit = effective[dimension]
        if limit == INF:
            continue

        for tier in ("key", "ip", "ws"):
            # Determine the actual limit for this specific tier
            tier_limit = _get_tier_limit(tier, dimension, key_limits, ws_limits)
            if tier_limit is None:
                continue

            counter_key = f"ratelimit:{tier}:{_scope_id(tier, request_state)}:{dimension}"
            current = await _count_window(redis, counter_key, cutoff, dimension)

            # For RPM: compare request count
            # For TPM: compare sum-of-tokens; pre-estimate the next request
            estimate = 0
            if dimension == "tpm":
                estimate = _estimate_tokens(request_state)
                if current + estimate > tier_limit:
                    return RateLimitResult.FAIL(tier, dimension, tier_limit, current, estimate)

            if current >= tier_limit:
                return RateLimitResult.FAIL(tier, dimension, tier_limit, current, 0)

        # If we passed all tiers for this dimension, admit
    return RateLimitResult.PASS(effective)
```

### Token Estimation for TPM Pre-Check

The middleware estimates prompt tokens before admitting the request:

1. If the request body contains a `prompt_tokens` field (from an OpenAI client SDK that pre-computes it), use it directly.
2. Otherwise, use `tiktoken` to encode the last `messages` entry's `content` (the user message) and count tokens. For `completions` endpoints, tokenise the `prompt` string directly.
3. If `max_tokens` is present in the request, use it as the output estimate. If absent, default to 4096 (the typical vLLM default).
4. Estimated total = `estimated_input_tokens + estimated_output_tokens`.

After the response completes, the service reads `usage.total_tokens` and corrects the TPM counter:

```python
async def correct_tpm(
    request_state: RequestState,
    actual_total_tokens: int,
    estimated_total_tokens: int,
    redis: Redis,
) -> None:
    delta = actual_total_tokens - estimated_total_tokens
    for tier in ("key", "ip", "ws"):
        counter_key = f"ratelimit:{tier}:{_scope_id(tier, request_state)}:tpm"
        # Add a new member with score = delta
        # The member value is a unique request ID so we can identify corrections
        await redis.zadd(counter_key, {f"corr:{request_state.request_id}": delta})
        await redis.expire(counter_key, 70)
```

The correction member's score is the delta (positive or negative), so `ZREVRANGEBYSCORE` summing naturally reflects the net correct count.

### Edge Cases

- **Concurrent requests at window boundary:** Two requests arriving at the exact same millisecond may both see a counter at 59 when the limit is 60, and both pass. The counter then becomes 61 for that window — one request exceeded the limit by 1. This is acceptable: Redis sorted-set operations are atomic per-key but there is no cross-request locking. The overage is bounded by the number of concurrent workers and resolves at the next window boundary.

- **Key revocation mid-window (F27 integration):** When a key is revoked, its Redis rate-limit counters are not explicitly cleaned up. They expire naturally via TTL (70 seconds). A revoked key is rejected by the proxy auth middleware (F27) before reaching the rate limiter, so stale counters for revoked keys pose no risk.

- **Workspace settings cache staleness:** The `ws:settings:{workspace_id}` Redis cache is set with a 30-second TTL. When workspace settings are updated via `PATCH /api/workspaces/{id}`, the cache key is explicitly `DEL`eted to force a fresh read from PostgreSQL on the next proxy request. If the DEL fails (network blip), the cache serves stale values for up to 30 seconds — acceptable for rate-limit ceiling changes.

- **Streaming response correction:** For streaming responses, the middleware listens for the final SSE data chunk from vLLM. The final chunk contains a `usage` object with `total_tokens`. The middleware intercepts this chunk, extracts the token count, performs the TPM correction, and forwards the chunk to the client. If the stream disconnects before the final chunk arrives, the pre-request estimate remains as the final count. Type: OpenAI SSE format for the final chunk:
  ```json
  {"id":"chatcmpl-abc","object":"chat.completion.chunk","created":1717754460,"model":"Qwen2.5-72B-Instruct","choices":[],"usage":{"prompt_tokens":512,"completion_tokens":384,"total_tokens":896}}
  ```

- **Overflow beyond workspace capacity:** Rate limits are a soft admission gate. If all active keys within a workspace are below their individual limits but the aggregate load exceeds the backend GPU capacity, the vLLM queue depth grows and requests experience higher latency (and eventually time out). This is by design — rate limits prevent runaway single-tenant abuse; total capacity management is handled by deployment provisioning (F20, F31). A future enhancement could add a concurrent-requests-per-GPU limit tied to `vllm.max_num_seqs` for hard capacity admission.

- **Redis outage:** If Redis is unreachable, the rate limiter enters a fail-open mode: all requests are admitted without rate-limiting checks. A dedicated health-check tick (`redis.ping()` on each request, cached for 5 seconds) detects the outage, and the middleware logs a `CRITICAL` level warning every 30 seconds that rate limiting is degraded. The `request.state` is annotated with `rate_limit_degraded: true` so the F29 usage tracker can flag records from the degraded period. On Redis recovery, normal operation resumes within one request cycle.

- **Header overflow for large values:** The `X-RateLimit-*` header values are capped to platform-appropriate ranges: `Limit` and `Remaining` are clamped to `[0, 2^31 - 1]`, `Reset` is a Unix timestamp as integer. All three headers are added by the middleware as late-stage ASGI response hook (the `send` wrapper pattern) so streaming responses also carry them.

- **IP extraction behind proxies:** The source IP is extracted from the first hop of `X-Forwarded-For` when present, falling back to `request.client.host` (`REMOTE_ADDR`). If `X-Forwarded-For` contains a comma-separated chain (e.g., `203.0.113.42, 10.0.0.1`), the leftmost IP is used. IPv6 addresses are stored as their canonical string representation (e.g., `2001:db8::1`) and are rate-limited independently from IPv4.

### Integration Points

- **F27 (API Key Management):** The rate limiter reads `scope.rateLimits` from the authenticated API key object loaded into `request.state` by the proxy auth middleware (F27). Key creation and update endpoints accept `rateLimits` in the scope payload. Key-level rate limits are optional and default to null (defer to workspace defaults).
- **F28 (OpenAI-Compatible Proxy):** The rate limiter sits as middleware in the proxy request path, immediately after proxy auth. It intercepts all `/v1/chat/completions`, `/v1/completions`, and `/v1/models` requests. The middleware hook is registered in `backend/app/main.py` in the middleware stack order: `ProxyAuthMiddleware` → `RateLimitMiddleware` → routing.
- **F29 (Usage Tracking):** After rate-limit evaluation and proxy completion, the usage tracker (F29) records rate-limit metadata (`rate_limited: true/false`, `effective_limit_rpm`, `effective_limit_tpm`, `tier_hit` if rate-limited) alongside token counts in `usage_records.metadata` JSONB. The F29 `UsageRecord` schema includes an optional `rate_limit_info` field for this purpose.
- **F31 (Request Routing):** The rate limiter passes admitted requests to F31 for upstream vLLM selection. If a request exceeds rate limits, it is rejected before F31 is reached, saving the routing and connection overhead.
- **F32 (Workspace Management):** Workspace settings for rate-limit defaults are part of `workspaces.settings` JSONB and are managed via the workspace settings API and UI. The workspace settings page at `dashboard/settings/index.vue` includes the rate-limits configuration panel.
- **F33 (RBAC):** Only workspace owners and admins may modify rate-limit settings via `PATCH /api/workspaces/{id}`. Members and viewers can view but not edit. Permission enforcement is handled by the existing F33 middleware on the workspace settings endpoint.
- **F35 (Data Retention):** Rate-limit counter data in Redis is ephemeral (max 70-second TTL) and is not subject to PostgreSQL data-retention policies. Usage records that include rate-limit metadata (F29) are retained per the workspace's usage record retention policy.

### Configuration

| Config Key | Default | Description |
|-----------|---------|-------------|
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding window duration for RPM and TPM counters |
| `RATE_LIMIT_GRACE_SECONDS` | `10` | Additional TTL beyond the window for Redis sorted-set keys |
| `RATE_LIMIT_KEY_PREFIX` | `"ratelimit:"` | Redis key prefix for all rate-limit counters |
| `RATE_LIMIT_FAIL_OPEN` | `true` | Whether to admit all requests when Redis is unreachable |
| `RATE_LIMIT_TOKEN_ESTIMATE_DEFAULT_MAX_TOKENS` | `4096` | Default `max_tokens` value when the request omits it (for TPM estimation) |
| `RATE_LIMIT_DEGRADED_LOG_INTERVAL` | `30` | Seconds between degraded-mode CRITICAL log lines |

### Test Scenarios

1. **Basic RPM limit rejection:** Send 61 requests in quick succession with a key limited to 60 RPM. Assert the 61st returns 429 with correct `Retry-After`.
2. **TPM pre-emptive rejection:** Send a request with `max_tokens: 100000` against a key with `tpmMax: 50000`. Assert 429 before any upstream call.
3. **TPM post-response correction:** Admit a request with `max_tokens: 8192` against a key with `tpmMax: 100000`. The estimate is ~8692 tokens. The response uses 4120 tokens. Assert the Redis TPM counter is debited by -4572 after correction (the delta).
4. **Compound minimum wins:** Configure key at 100 RPM, IP at 50 RPM, workspace at 200 RPM. Send 51 requests from one IP. Assert HTTP 429 with tier `ip`.
5. **Workspace default fallthrough:** Create a key with `rateLimits: null` in a workspace with `rpmMax: 30`. Send 31 requests. Assert HTTP 429 with tier `workspace`.
6. **Per-key override beats workspace default:** Same as test 5 but set key-level `rpmMax: 100`. Send 31 requests. Assert HTTP 200 (workspace default of 30 is overridden).
7. **Rate-limit headers on admitted request:** Assert `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` are present on a 200 response to the proxy.
8. **Redis fail-open:** Kill the Redis connection, send a request. Assert HTTP 200 (request admitted) and `request.state.rate_limit_degraded == true`.
9. **IP rate limiting across different source IPs:** Two IPs share one key with IP-limits at 10 RPM. Send 11 requests from IP A and 5 from IP B. Assert IP A's 11th returns 429; all 5 from IP B succeed.
10. **Workspace settings update propagation:** Update workspace `rateLimits.rpmMax` from 100 to 200 via `PATCH /api/workspaces/{id}`. Within 5 seconds, send the 101st request — previously would 429, now returns 200.

## Depends on: F27 (API key management — key scope and per-key rate-limit overrides in `scope.rateLimits`), F28 (OpenAI-compatible proxy — proxy middleware stack, streaming, response interception for TPM correction)
