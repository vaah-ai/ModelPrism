# ModelPrism API Design

> **Version:** 1.0  
> **Status:** Draft  
> **Last updated:** 2026-06-07

---

## 1. Overview

ModelPrism exposes three API surfaces:

| Surface | Protocol | Content-Type | Base Path |
|---|---|---|---|
| **Dashboard REST** | HTTP/HTTPS | `application/vnd.api+json` | `/api/{version}/` |
| **Auth & User** | HTTP/HTTPS | `application/json` | `/api/auth/` |
| **LLM Proxy** | HTTP/HTTPS | `application/json` | `/v1/` |
| **Real-time** | WebSocket | N/A (JSON messages) | `/ws/{resource}/` |

The Dashboard REST API adheres to the [JSON:API 1.0](https://jsonapi.org/format/) specification. Auth, user endpoints, and the OpenAI-compatible proxy use standard JSON.

---

## 2. Base URL & Versioning

### URL-prefix versioning

```
/api/v1/{resource}
/api/v1/{resource}/{id}
```

The version segment (`v1`) is part of the URL path. Backwards-incompatible changes increment the version number; backwards-compatible additions (new fields, new resource types) do not.

### Accept-header versioning (future)

Clients may optionally specify a media-type parameter:

```
Accept: application/vnd.api+json; version=1.2
```

When omitted the latest stable version is used.

---

## 3. Resource Types

| Resource | Endpoint | Description |
|---|---|---|
| `agents` | `/api/v1/agents` | Deployed model agents with configuration |
| `models` | `/api/v1/models` | Registered LLM models and provider metadata |
| `benchmarks` | `/api/v1/benchmarks` | Benchmark definitions and runs |
| `users` | `/api/v1/users` | User profiles |
| `workspaces` | `/api/v1/workspaces` | Collaborative workspaces |
| `api-keys` | `/api/v1/api-keys` | Programmatic API key management |
| `usage-records` | `/api/v1/usage-records` | Token-usage records and aggregations |
| `billing` | `/api/v1/billing` | Invoices, plans, payment methods |

### Resource identifiers

Every resource has a `type` and `id`:

```json
{
  "type": "agents",
  "id": "ag_01JABCDEFGHIJKLMNOPQRSTUV"
}
```

IDs are globally unique strings (prefixed by resource type where practical). UUIDs or NanoID-style identifiers are acceptable for resources without natural keys.

---

## 4. JSON:API Specification Adherence

### 4.1 Media Type

All **Dashboard REST** requests and responses MUST set:

```
Content-Type: application/vnd.api+json
Accept: application/vnd.api+json
```

### 4.2 Document Structure

#### Successful response (single resource)

```json
{
  "data": {
    "type": "agents",
    "id": "ag_01JABCDEFGHIJKLMNOPQRSTUV",
    "attributes": {
      "name": "Code Reviewer",
      "provider": "anthropic",
      "model": "claude-sonnet-4-20250514",
      "status": "active",
      "created-at": "2026-06-01T12:00:00Z",
      "updated-at": "2026-06-07T08:30:00Z"
    },
    "relationships": {
      "workspace": {
        "data": { "type": "workspaces", "id": "ws_98765" }
      },
      "api-keys": {
        "data": [
          { "type": "api-keys", "id": "ak_001" }
        ]
      }
    },
    "links": {
      "self": "/api/v1/agents/ag_01JABCDEFGHIJKLMNOPQRSTUV"
    }
  }
}
```

#### Successful response (collection)

```json
{
  "data": [
    { "type": "agents", "id": "ag_001", "attributes": { ... } },
    { "type": "agents", "id": "ag_002", "attributes": { ... } }
  ],
  "meta": {
    "total": 42,
    "count": 2
  },
  "links": {
    "self": "/api/v1/agents?page[offset]=0&page[limit]=2",
    "next": "/api/v1/agents?page[offset]=2&page[limit]=2",
    "prev": null
  }
}
```

### 4.3 Member Name Format

All member names use **kebab-case** (JSON:API recommendation):

- `created-at` ✓
- `last-seen-at` ✓
- `api-key-count` ✓
- `createdAt` ✗
- `last_seen_at` ✗

### 4.4 Resource Creation (POST)

```json
{
  "data": {
    "type": "agents",
    "attributes": {
      "name": "Code Reviewer",
      "provider": "anthropic",
      "model": "claude-sonnet-4-20250514"
    },
    "relationships": {
      "workspace": {
        "data": { "type": "workspaces", "id": "ws_98765" }
      }
    }
  }
}
```

Response: `201 Created` with `Location` header pointing to the new resource.

### 4.5 Resource Updates (PATCH)

```json
{
  "data": {
    "type": "agents",
    "id": "ag_01JABCDEFGHIJKLMNOPQRSTUV",
    "attributes": {
      "name": "Senior Code Reviewer"
    }
  }
}
```

Response: `200 OK` with the updated resource.

### 4.6 Resource Deletion (DELETE)

```
DELETE /api/v1/agents/ag_01JABCDEFGHIJKLMNOPQRSTUV
```

Response: `204 No Content`.

### 4.7 Relationship Endpoints

```
GET    /api/v1/agents/{id}/relationships/workspace
PATCH  /api/v1/agents/{id}/relationships/workspace
POST   /api/v1/agents/{id}/relationships/api-keys
DELETE /api/v1/agents/{id}/relationships/api-keys
```

---

## 5. Common Query Patterns

### 5.1 Pagination (offset / limit)

```
GET /api/v1/agents?page[offset]=0&page[limit]=25
```

| Parameter | Default | Max | Description |
|---|---|---|---|
| `page[offset]` | `0` | – | Number of records to skip |
| `page[limit]` | `25` | `100` | Max records per page |

Response includes a `meta` object with `total` (server-side record count) and a `links` object with `self`, `next`, `prev`, `first`, `last` URLs.

### 5.2 Sorting

```
GET /api/v1/agents?sort=-created-at, name
```

Prefix with `-` for descending order. Multiple sort fields are comma-separated. Supported fields are resource-specific and documented per endpoint.

### 5.3 Filtering

```
GET /api/v1/agents?filter[status]=active&filter[provider]=anthropic
```

Filters are AND-combined. Filterable fields are resource-specific. Complex filters (OR, ranges, `LIKE`) use an extended syntax:

```
GET /api/v1/usage-records?filter[created-at][gte]=2026-06-01&filter[created-at][lte]=2026-06-07
```

Standard operators: `eq` (default), `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `in`.

### 5.4 Sparse Fieldsets

```
GET /api/v1/agents?fields[agents]=name,status,model&fields[workspaces]=name
```

Only the listed attribute keys are returned. Omitting fieldsets returns all attributes.

### 5.5 Inclusion of Related Resources

```
GET /api/v1/agents?include=workspace,api-keys
```

Related resources are returned in a top-level `included` array:

```json
{
  "data": { ... },
  "included": [
    {
      "type": "workspaces",
      "id": "ws_98765",
      "attributes": { "name": "Engineering" }
    }
  ]
}
```

Depth is limited to one level by default. Deep includes (e.g., `?include=workspace.owner`) are evaluated on a per-endpoint basis.

---

## 6. Error Format

All errors adhere to the JSON:API `errors` top-level member:

```json
{
  "errors": [
    {
      "status": "422",
      "code": "VALIDATION_ERROR",
      "title": "Validation Failed",
      "detail": "The 'name' attribute must be between 1 and 255 characters.",
      "source": {
        "pointer": "/data/attributes/name"
      }
    },
    {
      "status": "422",
      "code": "VALIDATION_ERROR",
      "title": "Validation Failed",
      "detail": "The 'provider' attribute is required.",
      "source": {
        "pointer": "/data/attributes/provider"
      }
    }
  ]
}
```

### Common error codes

| HTTP Status | `code` | `title` | When |
|---|---|---|---|
| 400 | `BAD_REQUEST` | Bad Request | Malformed JSON or invalid query parameters |
| 401 | `UNAUTHORIZED` | Unauthorized | Missing or invalid API key |
| 403 | `FORBIDDEN` | Forbidden | Valid key but insufficient permissions |
| 404 | `NOT_FOUND` | Not Found | Resource does not exist |
| 409 | `CONFLICT` | Conflict | Resource already exists (e.g., duplicate name) |
| 422 | `VALIDATION_ERROR` | Validation Failed | Attribute or relationship validation failure |
| 429 | `RATE_LIMITED` | Rate Limited | Too many requests |
| 500 | `INTERNAL_ERROR` | Internal Server Error | Unexpected server failure |
| 503 | `SERVICE_UNAVAILABLE` | Service Unavailable | Temporary outage or maintenance |

Rate-limit responses include a `Retry-After` header (seconds) and may include a `meta` block with rate-limit details:

```json
{
  "errors": [
    {
      "status": "429",
      "code": "RATE_LIMITED",
      "title": "Rate Limited"
    }
  ],
  "meta": {
    "rate-limit": {
      "limit": 100,
      "remaining": 0,
      "reset-at": "2026-06-07T09:00:00Z"
    }
  }
}
```

---

## 7. Authentication (`/api/auth/`)

Auth endpoints use `application/json` (not JSON:API) to keep login/signup flows simple for client SDKs.

### 7.1 Auth Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/signup` | Create account |
| `POST` | `/api/auth/login` | Authenticate, receive session token |
| `POST` | `/api/auth/logout` | Invalidate session |
| `POST` | `/api/auth/refresh` | Refresh access token |
| `POST` | `/api/auth/reset-password` | Request password reset email |
| `POST` | `/api/auth/reset-password/confirm` | Complete password reset |

### 7.2 Auth Request / Response

```json
// POST /api/auth/login
// Request
{
  "email": "user@example.com",
  "password": "••••••••"
}

// Response (200 OK)
{
  "token_type": "Bearer",
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "expires_in": 3600,
  "user": {
    "id": "usr_001",
    "email": "user@example.com",
    "display_name": "Alice"
  }
}
```

### 7.3 API Key Authentication (for programmatic access)

```
Authorization: Bearer mpk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

API keys are managed through the Dashboard REST API at `/api/v1/api-keys`. They inherit the permissions of the user who created them, optionally scoped to a workspace.

---

## 8. OpenAI-Compatible Proxy (`/v1/`)

ModelPrism proxies LLM requests through OpenAI-compatible endpoints. These use `application/json` to maximize compatibility with existing OpenAI SDKs.

### 8.1 Chat Completions

```
POST /v1/chat/completions
```

```json
{
  "model": "claude-sonnet-4-20250514",
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "Explain quantum computing." }
  ],
  "temperature": 0.7,
  "max_tokens": 1024,
  "stream": true
}
```

The response follows the standard OpenAI chat completion format. When `stream: true`, the server sends SSE (Server-Sent Events) with `data: [DONE]` termination. Provider-specific fields (e.g., Anthropic extended thinking) are mapped to OpenAI equivalents where possible or exposed as additional response fields.

### 8.2 Completions (Legacy)

```
POST /v1/completions
```

Standard OpenAI text completions format. Planned for deprecation; new integrations should use chat completions.

### 8.3 Models

```
GET /v1/models
GET /v1/models/{model_id}
```

Returns the list of models available through the proxy, or a single model's details. Response format matches the OpenAI models API.

```json
{
  "object": "list",
  "data": [
    {
      "id": "claude-sonnet-4-20250514",
      "object": "model",
      "created": 1746057600,
      "owned_by": "anthropic"
    }
  ]
}
```

### 8.4 Usage Tracking

When proxied through ModelPrism, usage records are created asynchronously. The proxy response includes ModelPrism-specific usage metadata in a top-level `usage_metadata` block (non-standard, but additive):

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "usage": {
    "prompt_tokens": 45,
    "completion_tokens": 123,
    "total_tokens": 168
  },
  "usage_metadata": {
    "record_id": "ur_abc123",
    "cost_usd": 0.00147,
    "provider": "anthropic"
  }
}
```

---

## 9. WebSocket Protocol

### 9.1 Connection

```
wss://{host}/ws/metrics?token={bearer_or_api_key}
wss://{host}/ws/agents/{agent_id}/logs?token={bearer_or_api_key}
```

Authentication is required. The server MAY close the connection with a `4001` close code if the token is invalid or expired.

### 9.2 Message Format

All WebSocket messages are type-discriminated JSON objects:

```json
{
  "type": "metric",
  "ts": "2026-06-07T12:00:00.000Z",
  "payload": { ... }
}
```

| Field | Type | Description |
|---|---|---|
| `type` | `string` | Discriminator: one of `metric`, `log`, `command`, `heartbeat`, `ack`, `error` |
| `ts` | `string` (ISO 8601) | Timestamp of the message |
| `id` | `string` (optional) | Client-generated message ID; included in `ack` for correlation |
| `payload` | `object` | Message-specific data |

### 9.3 Message Types

#### metric (server → client)

```json
{
  "type": "metric",
  "ts": "2026-06-07T12:00:00.000Z",
  "payload": {
    "agent_id": "ag_01JABCDEFGHIJKLMNOPQRSTUV",
    "metric": "latency_p50",
    "value": 342,
    "unit": "ms",
    "tags": { "model": "claude-sonnet-4-20250514" }
  }
}
```

#### log (server → client)

```json
{
  "type": "log",
  "ts": "2026-06-07T12:00:01.000Z",
  "payload": {
    "level": "info",
    "source": "agent-runner",
    "message": "Request completed in 1.2s",
    "metadata": {
      "request_id": "req_xyz",
      "tokens_used": 450
    }
  }
}
```

#### command (client → server)

```json
{
  "type": "command",
  "id": "msg_001",
  "ts": "2026-06-07T12:00:02.000Z",
  "payload": {
    "action": "pause_agent",
    "params": {
      "agent_id": "ag_01JABCDEFGHIJKLMNOPQRSTUV"
    }
  }
}
```

#### ack (server → client)

```json
{
  "type": "ack",
  "ts": "2026-06-07T12:00:02.050Z",
  "payload": {
    "in_response_to": "msg_001",
    "status": "accepted"
  }
}
```

#### heartbeat (bidirectional)

Clients send heartbeats every 30 seconds of inactivity. The server responds with its own heartbeat. If no heartbeat is received for 60 seconds the server closes the connection.

```json
// Client → Server (every 30s)
{ "type": "heartbeat", "ts": "2026-06-07T12:01:00.000Z", "payload": {} }

// Server → Client (response)
{ "type": "heartbeat", "ts": "2026-06-07T12:01:00.001Z", "payload": {} }
```

#### error (server → client)

```json
{
  "type": "error",
  "ts": "2026-06-07T12:00:03.000Z",
  "payload": {
    "code": "INVALID_COMMAND",
    "message": "Unknown action: 'destroy'"
  }
}
```

### 9.4 Connection Lifecycle

```
Client                          Server
  │                               │
  │── CONNECT (wss://...) ────────→│
  │                                │── Validate token
  │←────── 101 Switching ──────────│
  │                                │
  │── { type: "command", ... } ───→│
  │←── { type: "ack", ... } ──────│
  │                                │
  │←── { type: "metric", ... } ───│
  │←── { type: "log", ... } ──────│
  │                                │
  │── { type: "heartbeat" } ──────→│
  │←── { type: "heartbeat" } ─────│
  │                                │
  │── { type: "command", ... } ───→│
  │←── { type: "ack", ... } ──────│
  │                                │
  │                                │── Close frame (1000)
  │←───── Closed ──────────────────│
```

---

## 10. CORS

Dashboard REST, Auth, and Proxy endpoints support CORS preflight (`OPTIONS`) requests. The server responds with:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PATCH, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization, Accept
Access-Control-Max-Age: 86400
```

In production, `Access-Control-Allow-Origin` MAY be restricted to configured origins.

---

## 11. Rate Limiting

Rate limits apply per API key (or per session for auth endpoints).

| Endpoint Group | Limit | Window |
|---|---|---|
| Dashboard REST | 1,000 requests | 1 minute |
| Auth (`/api/auth/*`) | 20 requests | 1 minute |
| Proxy (`/v1/*`) | Based on billing plan | 1 minute |

Exceeded limits return `429 Too Many Requests`. See [§6 Error Format](#6-error-format) for the error body.

---

## 12. Appendix: Example Endpoint Summary

### Dashboard REST (`/api/v1/`)

| Method | Path | JSON:API |
|---|---|---|
| `GET` | `/agents` | ✅ List agents |
| `POST` | `/agents` | ✅ Create agent |
| `GET` | `/agents/{id}` | ✅ Get agent |
| `PATCH` | `/agents/{id}` | ✅ Update agent |
| `DELETE` | `/agents/{id}` | ✅ Delete agent |
| `GET` | `/models` | ✅ List models |
| `POST` | `/benchmarks` | ✅ Run benchmark |
| `GET` | `/usage-records` | ✅ Usage history |
| `GET` | `/usage-records/summary` | ✅ Aggregated usage |
| `GET` | `/api-keys` | ✅ List API keys |
| `POST` | `/api-keys` | ✅ Create API key |
| `DELETE` | `/api-keys/{id}` | ✅ Revoke API key |
| `GET` | `/billing/invoices` | ✅ Invoice list |
| `GET` | `/workspaces` | ✅ List workspaces |

### Auth (`/api/auth/`)

| Method | Path | Standard JSON |
|---|---|---|
| `POST` | `/signup` | ✅ |
| `POST` | `/login` | ✅ |
| `POST` | `/logout` | ✅ |
| `POST` | `/refresh` | ✅ |
| `POST` | `/reset-password` | ✅ |

### Proxy (`/v1/`)

| Method | Path | OpenAI format |
|---|---|---|
| `POST` | `/chat/completions` | ✅ |
| `POST` | `/completions` | ✅ |
| `GET` | `/models` | ✅ |

### WebSocket (`/ws/`)

| Path | Description |
|---|---|
| `/ws/metrics` | Real-time metrics stream |
| `/ws/agents/{id}/logs` | Agent log stream |
| `/ws/agents/{id}/events` | Agent lifecycle events |
