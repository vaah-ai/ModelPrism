# F34: Workspace data isolation

## Metadata
- **ID:** F34
- **Phase:** Scale
- **Effort:** Medium
- **Dependencies:** F3, F32
- **Acceptance Criteria Count:** 5

## Description

Feature F34 implements a layered data isolation mechanism that guarantees every resource query on the ModelPrism platform returns data belonging only to the requesting workspace and no other. The isolation layer spans all workspace-scoped resources defined in the F3 schema — agents, model deployments, API keys, usage records, benchmark runs, agent logs, and metrics — and enforces scoping at three tiers: the database schema (structural `workspace_id` foreign key on every scoped table), the backend middleware layer (injecting a `WHERE workspace_id = <active_ws>` predicate on every query), and the repository layer (a `WorkspaceScopedRepository` base class that route handlers delegate to, eliminating the possibility of a handler forgetting to apply the filter).

The architecture distinguishes two authentication paths. **Dashboard REST endpoints** authenticate via JWT (F5), and the JWT payload carries an `active_workspace_id` claim set at login and updated when the user switches workspaces via `PUT /api/auth/workspace`. A `WorkspaceScopeMiddleware` extracts this claim, verifies the user is an active member of that workspace (querying `workspace_members` from F32), and attaches the resolved workspace ID to `request.state.workspace_id`. Every route handler passes this value to repository methods. **OpenAI-compatible proxy endpoints** (`/v1/chat/completions`, `/v1/completions`, `/v1/models`) authenticate via `sk-` API keys (F27). The proxy middleware resolves the key's `workspace_id` from the `api_keys.key_hash` lookup during authentication — the key itself carries the scope, so no JWT or `X-Workspace-ID` header is consulted on the proxy path. This dual-path design means a workspace can expose models via the OpenAI proxy without any dashboard user session being active.

Agent-side ingestion (metric pushes over WebSocket, log streaming via HTTP POST) uses a third scoping mechanism: the agent's `workspace_id` is stored immutably in the `agents` row at registration time (F6). When an agent pushes data, the backend writes it under the agent's stored workspace ID, derived from the agent's authentication (the `mp_` token or the WebSocket session). A compromised agent cannot write data to a different workspace because the server always reads the workspace from the agent's own database row, never from the incoming payload.

## Concrete Examples (Specification by Example)

### Example 1: Two Workspaces See Disjoint Agent Lists

- **Input:** User Alice belongs to workspace `ws-alpha` (UUID `aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa`) and workspace `ws-beta` (UUID `bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb`). Each workspace has two registered agents. Alice logs in with `active_workspace_id` set to `ws-alpha` and makes `GET /api/agents`.

- **Action:** The `WorkspaceScopeMiddleware` reads `active_workspace_id` from the JWT claims (`aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa`) and attaches it to `request.state.workspace_id`. The agents repository method `AgentRepository.list(session, workspace_id=request.state.workspace_id)` executes `SELECT * FROM agents WHERE workspace_id = 'aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa' AND status != 'removed' ORDER BY created_at DESC`. The two agents from `ws-beta` are excluded by the WHERE clause.

- **Expected Output:** HTTP 200 OK. JSON:API document containing exactly two agent resource objects:
  ```json
  {
    "data": [
      {
        "type": "agents",
        "id": "ag-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "attributes": {
          "friendlyName": "cyan-koala-42",
          "status": "online",
          "agentVersion": "0.1.0",
          "hardwareInfo": {
            "gpu_models": ["NVIDIA A100-SXM4-80GB"],
            "gpu_count": 4,
            "total_vram_gb": 320
          },
          "lastSeenAt": "2026-06-07T12:34:56+00:00",
          "registeredAt": "2026-06-01T08:00:00+00:00"
        },
        "links": {
          "self": "/api/agents/ag-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        }
      },
      {
        "type": "agents",
        "id": "ag-ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj",
        "attributes": {
          "friendlyName": "lime-panda-17",
          "status": "offline",
          "agentVersion": "0.1.0",
          "hardwareInfo": {
            "gpu_models": ["NVIDIA RTX 4090"],
            "gpu_count": 2,
            "total_vram_gb": 48
          },
          "lastSeenAt": "2026-06-06T08:12:33+00:00",
          "registeredAt": "2026-06-02T10:00:00+00:00"
        },
        "links": {
          "self": "/api/agents/ag-ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj"
        }
      }
    ],
    "meta": {
      "total": 2,
      "count": 2,
      "offset": 0,
      "limit": 20
    },
    "links": {
      "self": "/api/agents?page%5Boffset%5D=0&page%5Blimit%5D=20",
      "first": "/api/agents?page%5Boffset%5D=0&page%5Blimit%5D=20",
      "last": "/api/agents?page%5Boffset%5D=0&page%5Blimit%5D=20",
      "next": null,
      "prev": null
    }
  }
  ```
  Alice cannot enumerate, view, or access any resource belonging to `ws-beta` while her active workspace is `ws-alpha`.

### Example 2: Cross-Workspace by-ID Access Returns 404 (Not 403 or 401)

- **Input:** Alice (active workspace `ws-alpha`) knows the UUID of a model deployment running in `ws-beta`: `550e8400-e29b-41d4-a716-446655440000`. She sends `GET /api/models/550e8400-e29b-41d4-a716-446655440000`.

- **Action:** The models repository method `ModelRepository.get(session, deployment_id, workspace_id=ws-alpha)` executes:
  ```sql
  SELECT * FROM model_deployments
  WHERE id = '550e8400-e29b-41d4-a716-446655440000'
    AND workspace_id = 'aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa'
  ```
  The query returns zero rows because the deployment's `workspace_id` is `ws-beta`. The repository returns `None`. The route handler produces a JSON:API 404 response.

- **Expected Output:** HTTP 404 Not Found. JSON:API error document:
  ```json
  {
    "errors": [
      {
        "status": "404",
        "code": "RESOURCE_NOT_FOUND",
        "title": "Model deployment not found",
        "detail": "No model deployment with ID '550e8400-e29b-41d4-a716-446655440000' exists in this workspace."
      }
    ]
  }
  ```
  The backend does not reveal whether the deployment exists in another workspace — the 404 response is structurally and temporally identical to the response for a UUID that does not exist in any workspace. Response time must not differ by more than 50 ms between the two cases.

### Example 3: OpenAI Proxy Resolves Workspace from API Key, Not JWT

- **Input:** A CI/CD pipeline sends `POST /v1/chat/completions` with `Authorization: Bearer sk-mp-a1b2c3d4e5f6...`. The API key has `workspace_id: ws-beta` (UUID `bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb`) in the `api_keys` table, and its `scope.rateLimits` defines `rpmMax: 60`. The pipeline has no dashboard session.

- **Action:** The proxy middleware hashes the received key (`sha256("sk-mp-a1b2c3d4e5f6...")`), looks up `api_keys` by `key_hash`, resolves `workspace_id = ws-beta` from the key's row, and attaches `ws-beta` to the proxy request context. The model router (F31) queries `model_deployments` with `WHERE workspace_id = 'bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb' AND served_model_name = 'mistral-7b'` to find the target vLLM endpoint. The rate limiter (F30) evaluates the 60 RPM cap against the key's scope. After the response is streamed back, a usage record (F29) is inserted with `workspace_id = ws-beta` and `api_key_id` pointing to the resolved key.

- **Expected output from proxy:**
  ```json
  {
    "id": "chatcmpl-9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d",
    "object": "chat.completion",
    "created": 1717000100,
    "model": "mistral-7b",
    "choices": [
      {
        "index": 0,
        "message": {
          "role": "assistant",
          "content": "I can help you with that request."
        },
        "finish_reason": "stop"
      }
    ],
    "usage": {
      "prompt_tokens": 142,
      "completion_tokens": 38,
      "total_tokens": 180
    }
  }
  ```
- **Side effect:** The `usage_records` row has `workspace_id = bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb`. Alice, viewing the `ws-alpha` usage dashboard, sees zero token usage from this request — the proxy request is invisible to her workspace. The CI/CD pipeline's workspace (`ws-beta`) sees the usage in its own dashboard.

### Example 4: Workspace Switch Triggers Full Frontend Data Refresh

- **Input:** Alice is viewing the GPU server overview page (`/dashboard`) under workspace `ws-alpha`. She clicks a workspace switcher dropdown in the sidebar and selects `ws-beta`.

- **Action:** The frontend calls `PUT /api/auth/workspace` with the authenticated JWT:
  ```json
  {
    "workspace_id": "bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb"
  }
  ```
  The backend validates that Alice is a member of `ws-beta` with role `admin` by querying `workspace_members WHERE user_id = 'alice-uuid' AND workspace_id = 'ws-beta'` (returns one row with `role = 'admin'`). It issues a new access token with `active_workspace_id: ws-beta` and `workspace_role: admin`. The refresh token is unchanged (rotation is unnecessary for workspace switching). The response returns:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 900,
    "workspace": {
      "id": "bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb",
      "name": "Beta Team",
      "slug": "beta-team",
      "role": "admin"
    }
  }
  ```

- **Frontend side effect:** The `useAuth` composable updates the stored JWT and emits a `workspace-changed` reactive event. Every Pinia store (`agents`, `metrics`, `models`, `keys`, `benchmarks`, `user`) listens for this event. Each store:
  1. Calls `reset()` — sets `items = []`, `total = 0`, `loading = true`, `error = null`.
  2. Dispatches its initial fetch action with the new workspace scope: `GET /api/agents`, `GET /api/models`, `GET /api/keys`, etc.
  3. The WebSocket connection (`stores/metrics.ts`) disconnects the `ws-alpha` metric stream and opens a new connection scoped to `ws-beta`.
  4. The sidebar updates the workspace label from "Alpha Team" to "Beta Team".
  5. During the transition, a loading skeleton is displayed instead of stale data.

  No stale resource from `ws-alpha` remains in any store's data.

### Example 5: Agent Ingestion Uses Its Own Stored Workspace ID

- **Input:** An agent registered under workspace `ws-alpha` (UUID `aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa`) pushes a metrics snapshot over WebSocket. The WebSocket path is `/ws/agents/ag-cyan-koala-uuid`. Simultaneously, a malicious actor tries to POST a log entry to `POST /api/agents/ag-different-agent/logs` with a fabricated `workspace_id` in the request body.

- **Action (metrics):** The WebSocket handler reads the `agent_id` from the connection path, looks up the agent in the `agents` table, retrieves the stored `workspace_id = ws-alpha`, and writes the metric to `agent_metrics` with `workspace_id = ws-alpha`. The incoming payload contains no `workspace_id` field — the server always derives it from the agent's database record.

- **Action (logs):** The `POST /api/agents/{agent_id}/logs` endpoint loads the agent record from the database, extracts the agent's `workspace_id`, and inserts the log row with that value. Any `workspace_id` in the request body is silently ignored.

- **Expected Output (metrics):** The `agent_metrics` row:
  ```json
  {
    "id": 1048576,
    "agent_id": "ag-cyan-koala-uuid",
    "workspace_id": "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa",
    "ts": "2026-06-07T12:00:02+00:00",
    "data": {
      "gpu_util_pct": 87.2,
      "vram_used_gb": 42.5,
      "tok_per_sec": 185.3,
      "running_requests": 3,
      "waiting_requests": 2
    }
  }
  ```
  The fabricated log request either succeeds (if the agent ID belongs to `ws-alpha`) and the log is stored under `ws-alpha`, or fails with 404 (if the agent ID does not exist). In neither case does data flow into a workspace the agent does not belong to.

## Acceptance Criteria

- **ACF34-1: Every dashboard REST endpoint on a workspace-scoped table enforces `WHERE workspace_id = active_workspace`** — All GET, POST, PATCH/PUT, and DELETE handlers for agents (`/api/agents`), model deployments (`/api/models`), API keys (`/api/keys`), usage records (`/api/usage`), benchmark runs (`/api/benchmarks`), agent logs (`/api/agents/{id}/logs`), and historical metrics (`/api/metrics/{agent_id}`) include a `workspace_id` filter derived from the JWT's `active_workspace_id` claim. This filter is injected by repository layer methods (`WorkspaceScopedRepository.list()`, `.get()`, `.create()`, `.update()`, `.delete()`), not by individual route handlers. An automated integration test suite verifies each of the seven resource types by: (a) creating 2+ resources under workspace A, (b) authenticating as a member of workspace B, (c) asserting list endpoints return zero resources from workspace A, (d) asserting by-ID endpoints for workspace A resources return HTTP 404, and (e) asserting POST/PATCH/DELETE operations only affect rows within workspace B. The suite covers all seven resource types × `list`/`get`/`create`/`update`/`delete` where applicable (28 endpoint variants minimum).

- **ACF34-2: The OpenAI-compatible proxy resolves workspace scope from the API key, not any dashboard session** — When a request arrives at `/v1/chat/completions`, `/v1/completions`, or `/v1/models` with `Authorization: Bearer sk-...`, the proxy middleware SHA-256 hashes the key, looks up the `api_keys` row by `key_hash`, and extracts `workspace_id` from the row. All downstream operations — model routing (F31 selecting from `model_deployments WHERE workspace_id = key.ws`), usage recording (F29 writing `usage_records.workspace_id = key.ws`), and rate-limit evaluation (F30 reading workspace-level defaults from `workspaces.settings`) — use this key-derived workspace ID. No JWT, no `X-Workspace-ID` header, and no dashboard session state is consulted on the proxy path. A test creates API keys under two different workspaces, sends identical chat completion requests with each key, and asserts that the resulting usage records have different `workspace_id` values matching each key's owning workspace.

- **ACF34-3: Workspace membership is enforced as a gate before any data access on dashboard endpoints** — Every authenticated request to a dashboard REST endpoint passes through a membership check implemented in the `WorkspaceScopeMiddleware`: the middleware queries `workspace_members` with the JWT's `sub` (user ID) and `active_workspace_id`, and rejects the request with HTTP 403 and error code `WORKSPACE_ACCESS_DENIED` if no membership row exists. This membership check runs before any database query on scoped tables. The middleware is bypassed only for the auth endpoints (`/api/auth/register`, `/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout`) and the workspace-switch endpoint (`PUT /api/auth/workspace`), which legitimately operate outside an active workspace context. Proxy endpoints (`/v1/...`) are also bypassed because they derive scope from the API key rather than workspace membership. A test verifies: invite user U to workspace A but not workspace B, log in with workspace A set as active, craft a request targeting workspace B resources via a modified JWT (if possible without invalidating the signature) or via an `X-Workspace-ID` override attempt → HTTP 403 with `WORKSPACE_ACCESS_DENIED`.

- **ACF34-4: Frontend stores clear and re-fetch on workspace switch, and a loading skeleton prevents stale data display** — When the user triggers a workspace switch via `PUT /api/auth/workspace` (or the workspace switch response returns a new JWT), the `useAuth` composable emits a reactive `workspace-changed` event. Every Pinia store (`agents`, `metrics`, `models`, `keys`, `benchmarks`, `user`) registers a handler for this event that:
  1. Sets `items = []`, `total = 0`, `loading = true`, `error = null`.
  2. Dispatches the store's initial `fetchAll()` action with the new workspace scope.
  3. Sets `loading = false` once the fetch completes or errors.
  
  Any active WebSocket connection for metrics or logs is closed by the `metrics` store's `reset()` method, and a new connection is opened targeting the now-current workspace's agent IDs. The UI renders a loading skeleton (CSS pulse animation on placeholder blocks) for each panel while `loading = true`. A test verifies: populate the agents store with 3 agents from workspace A (confirmed by `items.length === 3`), call `switchWorkspace('ws-beta-uuid')`, and assert that `items.length === 0` during the transition and equals the correct agent count for workspace B after fetch completes. No stale resource IDs from the previous workspace appear in any store's `items` array at any point after `reset()` executes.

- **ACF34-5: Agent-side data ingestion (metrics, logs) uses the agent's stored workspace ID, never the incoming payload** — When an agent pushes metrics over WebSocket or streams logs via `POST /api/agents/{agent_id}/logs`, the backend resolves the workspace scope from the agent's database record (`SELECT workspace_id FROM agents WHERE id = :agent_id`) rather than from any field in the incoming payload, any header, or any session. The agent's `workspace_id` is set immutably at registration time (F6, `agent_registration_tokens` → `agents` creation in a single transaction), and no API exists to change it after creation. Any `workspace_id` field present in the incoming JSON body of a log POST or metric push is silently stripped or ignored by the route handler. An integration test verifies: register agent under workspace A, authenticate as a member of workspace B, capture the agent's currently-authenticated session (which has no dashboard JWT — agents authenticate via their persistent agent token, which is unchanged), send a log POST from the agent, and confirm `agent_logs.workspace_id` is `ws-alpha`, not `ws-beta`. A negative test attempts to register an agent under workspace A, then impersonate a different agent by manipulating the `{agent_id}` in the log POST URL path — the handler loads the agent by ID from the DB and uses that agent's stored `workspace_id`, so even successful impersonation (stopped by the agent's own auth token in F12) would still write data under the impersonated agent's correct workspace.

## Technical Notes

### Middleware Architecture

The workspace isolation layer is implemented as a single FastAPI middleware class at `backend/app/middleware/workspace.py`:

```python
# backend/app/middleware/workspace.py
from fastapi import Request, HTTPException, status
from sqlalchemy import select
from backend.app.models.workspace import WorkspaceMember

# Endpoints that do not require workspace scope
WORKSPACE_EXEMPT_PATHS = {
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/auth/workspace",
}

# Proxy endpoints resolve scope via API key
PROXY_PREFIX = "/v1/"

class WorkspaceScopeMiddleware:
    """Extract workspace scope from JWT, verify membership, attach to request state."""

    async def resolve_workspace_id(self, request: Request) -> str | None:
        if request.url.path.startswith(PROXY_PREFIX):
            # Workspace ID already attached by proxy auth middleware
            return getattr(request.state, "resolved_workspace_id", None)
        if request.url.path in WORKSPACE_EXEMPT_PATHS:
            return None
        # Read active_workspace_id from JWT, verify membership
        jwt_ws = getattr(request.state, "active_workspace_id", None)
        if jwt_ws is None:
            raise HTTPException(status_code=401, detail="No workspace scope in token")
        user_id = request.state.user_id
        # Verify membership
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.workspace_id == jwt_ws,
        )
        result = await request.state.db.execute(stmt)
        member = result.scalar_one_or_none()
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not a member of workspace {jwt_ws}",
            )
        return jwt_ws
```

### Repository Layer Pattern: `WorkspaceScopedRepository`

All workspace-scoped database access flows through a base repository class at `backend/app/services/base_repository.py`. Every route handler in the API layer (agents, models, keys, usage, benchmarks, logs, metrics) must use repository methods rather than calling `session.execute()` directly.

```python
# backend/app/services/base_repository.py
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

class WorkspaceScopedRepository:
    """Base CRUD for models with workspace_id FK.
    
    Subclasses set `model_class` to the SQLAlchemy ORM model.
    """
    model_class = None  # Must override

    async def list(
        self, session: AsyncSession, workspace_id: UUID,
        offset: int = 0, limit: int = 20,
        **filters
    ):
        query = select(self.model_class).where(
            self.model_class.workspace_id == workspace_id
        )
        # Apply dynamic filters, sort, pagination
        count_query = select(func.count()).select_from(
            self.model_class
        ).where(self.model_class.workspace_id == workspace_id)
        total = await session.scalar(count_query) or 0
        result = await session.execute(query.offset(offset).limit(limit))
        return result.scalars().all(), total

    async def get(
        self, session: AsyncSession, resource_id: UUID, workspace_id: UUID
    ):
        query = select(self.model_class).where(
            self.model_class.id == resource_id,
            self.model_class.workspace_id == workspace_id,
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def create(
        self, session: AsyncSession, workspace_id: UUID, **data
    ):
        instance = self.model_class(workspace_id=workspace_id, **data)
        session.add(instance)
        await session.flush()
        return instance

    async def update(
        self, session: AsyncSession, resource_id: UUID,
        workspace_id: UUID, **data
    ):
        instance = await self.get(session, resource_id, workspace_id)
        if instance is None:
            return None
        for key, value in data.items():
            setattr(instance, key, value)
        await session.flush()
        return instance

    async def delete(
        self, session: AsyncSession, resource_id: UUID, workspace_id: UUID
    ) -> bool:
        instance = await self.get(session, resource_id, workspace_id)
        if instance is None:
            return False
        await session.delete(instance)
        await session.flush()
        return True
```

### Concrete Repository Implementations

| Repository | `model_class` | API Route File |
|---|---|---|
| `AgentRepository` | `Agent` (from `backend/app/models/agent.py`) | `backend/app/api/agents.py` |
| `ModelDeploymentRepository` | `ModelDeployment` (from `backend/app/models/model_deployment.py`) | `backend/app/api/models.py` |
| `ApiKeyRepository` | `ApiKey` (from `backend/app/models/api_key.py`) | `backend/app/api/keys.py` |
| `UsageRecordRepository` | `UsageRecord` (from `backend/app/models/usage_record.py`) | `backend/app/api/usage.py` |
| `BenchmarkRunRepository` | `BenchmarkRun` (from `backend/app/models/benchmark.py`) | `backend/app/api/benchmarks.py` |
| `AgentLogRepository` | `AgentLog` (from `backend/app/models/agent.py`) | `backend/app/api/agent_logs.py` |
| `AgentMetricRepository` | `AgentMetric` (from `backend/app/models/agent.py`) | `backend/app/api/metrics.py` |

### JWT Claim Format

The access token JWT payload includes workspace scope claims:

```json
{
  "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "email": "alice@example.com",
  "active_workspace_id": "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa",
  "workspace_role": "admin",
  "exp": 1717000000,
  "iat": 1716999100,
  "jti": "unique-token-id-xyz"
}
```

The `active_workspace_id` is set at login (to the user's first workspace as determined by the earliest `workspace_members.created_at`) and updated on every workspace switch. The `workspace_role` reflects the user's role within the active workspace, which the F33 RBAC middleware uses for authorization decisions.

### API Endpoint: Workspace Switch

```
PUT /api/auth/workspace
Content-Type: application/json
Authorization: Bearer <current_access_token>

{
  "workspace_id": "bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb"
}
```

Response (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900,
  "workspace": {
    "id": "bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb",
    "name": "Beta Team",
    "slug": "beta-team",
    "role": "admin"
  }
}
```

The old access token remains valid until its natural 15-minute expiry — the frontend replaces it immediately. The backend verifies workspace membership before issuing the new token. If the user is not a member of the requested workspace, the response is HTTP 403 with `code: "WORKSPACE_ACCESS_DENIED"`.

### WebSocket Scope

The dashboard WebSocket endpoints (`/ws/dashboard/{agent_id}`, `/ws/dashboard`) enforce workspace scope on the `on_connect` handler:

```python
# backend/app/ws/dashboard_ws.py (conceptual)
async def on_connect(websocket: WebSocket, agent_id: str | None):
    # Extract JWT from query params
    token = websocket.query_params.get("token")
    payload = verify_jwt(token)
    ws_id = payload["active_workspace_id"]
    
    if agent_id:
        # Verify the agent belongs to the user's workspace
        agent = await get_agent(agent_id)
        if agent.workspace_id != ws_id:
            await websocket.close(code=4003, reason="Agent not in workspace")
            return
    
    # Accept the connection and scope it
    await websocket.accept()
    websocket.state.workspace_id = ws_id
```

If the user switches workspace while a WebSocket connection is open, the frontend closes the existing connection and opens a new one. The backend does not support mid-connection workspace re-scoping.

### Agent-Side Metric and Log Scoping

The agent's `workspace_id` is stored immutably in the `agents` table at registration time (F6). All data ingestion paths derive the workspace scope from the agent's database record:

1. **WebSocket metric push (F9):** The WebSocket handler for `/ws/agents/{agent_id}` authenticates the agent via its persistent WebSocket session (established during registration). When metrics arrive as `{"type": "metrics", "data": {gpu_util: ...}}`, the handler reads the agent's stored `workspace_id` and writes `agent_metrics` with that value. The incoming payload is validated by the shared schema in `common/modelprism_common/schemas/metrics.py` but workspace fields are not part of the schema — the server always overrides.

2. **Log streaming POST (F12):** `POST /api/agents/{agent_id}/logs` authenticates the agent via a persistent bearer token (stored in the agent's `config.toml`, separate from the registration token). The handler loads the `Agent` record by `agent_id`, extracts `workspace_id`, and writes `agent_logs` with that value:
   ```python
   # backend/app/api/agent_logs.py
   @router.post("/api/agents/{agent_id}/logs")
   async def push_logs(agent_id: str, logs: list[LogEntry], request: Request):
       agent = await agent_repo.get_by_agent_prefix(agent_id)
       if agent is None:
           raise HTTPException(404)
       enriched = [LogRow(
           agent_id=agent.id,
           workspace_id=agent.workspace_id,  # Always from DB, never from payload
           level=log.level,
           message=log.message,
           ts=log.ts or datetime.now(timezone.utc),
       ) for log in logs]
       # ... bulk insert ...
   ```

### Affected Files

| File | Change |
|---|---|
| `backend/app/middleware/workspace.py` | **New.** `WorkspaceScopeMiddleware` — JWT workspace extraction, membership verification, attachment to `request.state`. |
| `backend/app/middleware/auth.py` | Update JWT issuance at login, refresh, and workspace switch to include `active_workspace_id` and `workspace_role` claims. |
| `backend/app/main.py` | Register `WorkspaceScopeMiddleware` in the middleware stack after the auth middleware. |
| `backend/app/services/base_repository.py` | **New.** `WorkspaceScopedRepository` — generic CRUD with `workspace_id` filter on every method. |
| `backend/app/services/agent_manager.py` | Refactor all methods to accept `workspace_id` and delegate to `AgentRepository(WorkspaceScopedRepository)`. |
| `backend/app/services/model_manager.py` | Refactor to use `ModelDeploymentRepository`. |
| `backend/app/services/log_service.py` | Refactor log retrieval to accept `workspace_id` parameter scoped via repository. |
| `backend/app/services/usage_tracker.py` | Refactor proxy usage recording to accept key-resolved `workspace_id`. |
| `backend/app/services/billing_service.py` | Ensure billing queries (usage aggregation) filter by `workspace_id`. |
| `backend/app/api/agents.py` | Replace inline workspace filters with `AgentRepository` method calls. |
| `backend/app/api/models.py` | Replace inline workspace filters with `ModelDeploymentRepository` method calls. |
| `backend/app/api/keys.py` | Replace inline workspace filters with `ApiKeyRepository` method calls. |
| `backend/app/api/usage.py` | Replace inline workspace filters with `UsageRecordRepository` method calls. |
| `backend/app/api/benchmarks.py` | Replace inline workspace filters with `BenchmarkRunRepository` method calls. |
| `backend/app/api/agent_logs.py` | Replace inline workspace filters with `AgentLogRepository` method calls. |
| `backend/app/api/metrics.py` | Replace inline workspace filters with `AgentMetricRepository` method calls. |
| `backend/app/api/proxy.py` | Update proxy auth middleware to attach key-resolved `workspace_id` to `request.state.resolved_workspace_id`. |
| `backend/app/api/auth.py` | Add `PUT /api/auth/workspace` route handler for workspace switching. |
| `backend/app/schemas/user.py` | Add `WorkspaceSwitchRequest` and `WorkspaceSwitchResponse` Pydantic schemas. |
| `frontend/stores/auth.ts` | Add `activeWorkspace`, `workspaceRole`, `switchWorkspace(workspaceId)` action, `workspace-changed` event emitter. |
| `frontend/stores/agents.ts` | Add `reset()` method cleared on workspace switch; re-fetch via `fetchAll()`. |
| `frontend/stores/models.ts` | Add `reset()` method called on workspace switch. |
| `frontend/stores/metrics.ts` | Add `reset()` method that closes the active WebSocket connection. |
| `frontend/stores/keys.ts` | Add `reset()` method called on workspace switch. |
| `frontend/stores/benchmarks.ts` | Add `reset()` method called on workspace switch. |
| `frontend/stores/user.ts` | Add `reset()` method called on workspace switch. |
| `frontend/composables/useAuth.ts` | Add `switchWorkspace(workspaceId)` public method; propagate `workspace-changed` event on success. |
| `frontend/app/components/dashboard/WorkspaceSwitcher.vue` | **New.** Dropdown component in sidebar showing workspaces the user belongs to, with current workspace highlighted and a separate "Switch" action. |
| `frontend/app/pages/restore-workspace.vue` | Not directly modified by F34, but the auth middleware must allow requests to this page without an active workspace context. |

### Configuration

Add to `backend/app/config.py`:

```python
class WorkspaceSettings(BaseSettings):
    """Settings for workspace data isolation."""
    membership_check_enabled: bool = True  # Toggle for testing/development
    membership_cache_ttl_seconds: int = 300  # Cache membership lookups in Redis
    allow_x_workspace_override: bool = False  # Only True in admin endpoints (F40)

class AppSettings(BaseSettings):
    # Existing settings...
    workspace: WorkspaceSettings = WorkspaceSettings()
```

### Edge Cases

- **User with no workspaces:** A freshly registered user always has exactly one workspace (created during F5 registration). If a user's last membership is removed (F32), they have zero workspaces — the `active_workspace_id` in their JWT points to a workspace they no longer belong to. The middleware returns HTTP 403 with `code: "NO_ACTIVE_WORKSPACE"` and a `detail` explaining they have no workspace memberships. The frontend redirects to a "No workspaces" page with instructions to contact an existing workspace owner for an invitation.

- **Deleted workspace access:** When a workspace is soft-deleted (F32 sets `workspaces.deleted_at`), the membership check middleware additionally verifies `workspaces.deleted_at IS NULL`. If the workspace is deleted, the middleware returns HTTP 403 with `code: "WORKSPACE_DELETED"`. The frontend redirects to a "Workspace Pending Deletion" page with a countdown and a contact-support message. The workspace switch endpoint (`PUT /api/auth/workspace`) also rejects soft-deleted workspaces.

- **Agent registration race:** During the two-phase registration (F6), the `agent_registration_tokens` row carries the target `workspace_id`. The `agents` row is created with that `workspace_id` in the same transaction. No isolation concern exists here — the registration flow is single-workspace by design and the token never moves between workspaces.

- **Bulk operations:** Any future bulk delete or bulk export endpoint must use the repository's `list()` + iteration pattern, not bare `session.execute("DELETE FROM ...")`. A `workspace_id` filter is mandatory even on bulk operations. The repository pattern prevents accidental unbounded queries.

- **Data retention cleanup (F35):** The background cleanup job runs as a system service with elevated privileges. It must still iterate workspaces individually and delete per workspace, using the agent's stored `workspace_id` as the filter key. This prevents a bug in the cleanup job from deleting metrics across all workspaces simultaneously.

- **Timing side-channels:** On by-ID endpoints, the WHERE clause `id = :id AND workspace_id = :ws` executes identically regardless of whether the resource exists under a different workspace. The query plan is the same (index seek on the primary key, then a check on the indexed `workspace_id` column). Both cases return zero rows within the same query structure, preventing timing-based workspace enumeration. A CI benchmark test asserts that the response time for "exists in other workspace" and "does not exist anywhere" differ by less than 50 ms over 100 runs.

### Testing Strategy

#### Integration Tests (`backend/tests/`)

| Test Name | Input | Expected |
|---|---|---|
| `test_isolation_list_agents` | Create 3 agents in workspace A, 2 in B. Auth as A, GET `/api/agents`. | 2 agents returned, `meta.total = 2`. |
| `test_isolation_get_model_404` | Create model in workspace B. Auth as A, GET `/api/models/{model_id}`. | HTTP 404, `code: "RESOURCE_NOT_FOUND"`. |
| `test_isolation_create_api_key` | Auth as A, POST `/api/keys` with label. | Created key DB row has `workspace_id = A`. |
| `test_isolation_update_benchmark` | Create benchmark in workspace B. Auth as A, PATCH the benchmark. | HTTP 404 (benchmark not scoped to A). |
| `test_isolation_delete_agent` | Create agent in workspace B. Auth as A, DELETE the agent. | HTTP 404 (agent not scoped to A). No deletion in DB. |
| `test_proxy_scope_from_key` | POST `/v1/chat/completions` with key from workspace A. | Usage record created with `workspace_id = A`. |
| `test_proxy_different_key_different_ws` | Same request with key from workspace B. | Usage record created with `workspace_id = B`. |
| `test_membership_gate_403` | JWT with `active_workspace_id = C` where user has no membership. | HTTP 403, `code: "WORKSPACE_ACCESS_DENIED"`. |
| `test_auth_exempt_paths_ok` | Access `/api/auth/login`, `/api/auth/refresh` without workspace scope. | No 403. Works normally. |
| `test_agent_log_uses_agent_workspace` | Register agent in A, push log via POST `/api/agents/{id}/logs`. | Log row has `workspace_id = A`. |
| `test_agent_metric_uses_agent_workspace` | Agent in A pushes metrics over WS. | Metric row has `workspace_id = A`. |
| `test_cross_ws_enumeration_timing` | 100 iterations: measure 404 for non-existent ID vs. existent-in-other-workspace ID. | Δ < 50 ms. |
| `test_workspace_switch_issues_new_jwt` | Auth as A, PUT `/api/auth/workspace` with workspace B. | New JWT with `active_workspace_id = B`. |
| `test_workspace_switch_forbidden_non_member` | PUT `/api/auth/workspace` with workspace user is not a member of. | HTTP 403. |

#### Frontend Tests (`frontend/` — Vitest + @vue/test-utils)

| Test Name | Input | Expected |
|---|---|---|
| `stores_clear_on_workspace_switch` | Populate agents, models, keys stores with data. Call `switchWorkspace('B')`. | All stores `items.length === 0` immediately after switch. |
| `stores_refetch_on_workspace_switch` | After switch, mock API returns workspace B data. | Stores populated with workspace B data within 1 second. |
| `websocket_reconnects_on_switch` | Active WS connection to workspace A metrics. Call `switchWorkspace('B')`. | WS closed. New WS opened. |
| `loading_skeleton_during_transition` | Switch workspace while fetch is pending. | Skeleton visible. No stale data. |

### Integration Points

- **F3 (Database schema):** Provides the structural isolation foundation — every scoped table has a non-null `workspace_id` FK to `workspaces.id` with `ON DELETE CASCADE`. Composite indexes like `ix_agents_workspace_status` and `ix_model_deployments_workspace_status` ensure the mandatory `WHERE workspace_id = :ws` predicates are performant. The `WorkspaceScopedMixin` base class (defined in F3) is used by all scoped ORM models.

- **F5 (Email/password auth):** The JWT is the carrier of `active_workspace_id`. F5's login handler sets `active_workspace_id` to the user's first workspace (the one with the earliest `workspace_members.created_at`). F5's `require_auth` dependency extracts the user ID from the JWT, which F34's middleware uses for the membership check. The `PUT /api/auth/workspace` endpoint added by F34 extends F5's auth router.

- **F32 (Workspace management):** Provides the `workspace_members` table that F34's membership gate queries. Workspace deletion (F32 ACF32-4) initiates the teardown cascade that F34's middleware detects via `workspaces.deleted_at`. Workspace settings (F32 ACF32-1) include retention periods that the F35 cleanup job reads per-workspace using the isolation middleware's user context. The member invitation flow (F32 ACF32-2) creates the membership rows that F34's middleware checks.

- **F33 (Role-based access control):** F33 builds on F34's `workspace_role` JWT claim. F34 extracts and verifies workspace scope; F33 then checks whether the user's role within that scope permits the requested action (e.g., `admin` can create API keys, `viewer` cannot). The two middleware layers compose: `WorkspaceScopeMiddleware` runs first, then `RoleBasedAccessMiddleware` (F33) reads `request.state.workspace_id` and `request.state.workspace_role` for authorization decisions.

- **F27 (API key management):** API keys are workspace-scoped via `api_keys.workspace_id`. F34 ensures that key listing, creation, and revocation are scoped to the active workspace. The proxy auth path (F27) resolves the key's workspace for proxy requests, which F34's proxy middleware consumes.

- **F28 (OpenAI-compatible proxy):** The proxy endpoints (`/v1/...`) bypass F34's JWT-based membership gate. Instead, F28's authentication middleware resolves the workspace from the API key (F27) and sets `request.state.resolved_workspace_id`. F34's middleware reads this field when the request URL starts with `/v1/` and skips the membership check. This dual-path design is documented in the architecture as the "key-as-scope" model.

- **F29 (Usage tracking):** F34 ensures usage records are always written and queried with the correct `workspace_id`. For proxy requests, the workspace ID comes from the API key. For dashboard-side usage queries (e.g., `GET /api/usage` for the billing dashboard), it comes from the JWT's `active_workspace_id`.

- **F30 (Rate limiting):** Rate-limit counters in Redis are keyed by `{workspace_id}:{api_key_id}` for per-key limits and `{workspace_id}:ip:{client_ip}` for per-IP limits. F34 ensures the correct workspace ID feeds into these Redis key prefixes.

- **F31 (Request routing):** The model router filters `model_deployments` by `workspace_id` before selecting a target vLLM endpoint. F34's repository layer ensures this filter is applied. For proxy requests, the workspace ID comes from the API key's row — routing is isolated per workspace even when two workspaces serve the same `model_name` (e.g., both serve `mistral-7b` from different GPU servers).

- **F35 (Data retention):** The background cleanup job iterates over each workspace, reads `workspaces.settings.retentionDays`, and deletes expired rows per-workspace using `DELETE FROM agent_metrics WHERE workspace_id = :ws AND ts < :cutoff`. This pattern prevents a single overly-broad DELETE statement from affecting all workspaces.

- **F40 (Admin panel):** System-level admin endpoints (F40) may need to access resources across workspaces. These endpoints authenticate as a system owner (a user with a special system-level role, distinct from workspace roles) and use an explicit `workspace_id` query parameter or `X-Workspace-ID` header. F34's middleware allows this override only when `request.state.is_system_owner` is `True`. A system audit log records every cross-workspace access.

## Depends on: F3 (Database schema — workspace-scoped tables with `workspace_id` FK on every scoped resource table), F32 (Workspace management — `workspace_members` table for membership gating, `workspaces.deleted_at` for detecting deleted workspaces, settings for retention defaults)
