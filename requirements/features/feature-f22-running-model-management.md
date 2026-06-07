# F22: Running model management

## Metadata
- **ID:** F22
- **Phase:** Enhancement
- **Effort:** Large
- **Dependencies:** F11, F20
- **Acceptance Criteria Count:** 6

## Description

Feature F22 provides the complete lifecycle management interface for model inference deployments that are actively running on GPU servers. Once a model has been deployed via the deployment wizard (F19) and its Docker container is running on the target agent (F20), this feature gives the user the ability to list all running models across the fleet, view detailed health and configuration information for each, stop and restart individual deployments, permanently delete them (tearing down the container and freeing GPU resources), and stream live container-level logs. This is the operational control layer that sits between deployment (F19/F20) and the proxy (F28) — a model must be in a `healthy` or `running` state, managed by F22, before it can receive inference requests through the OpenAI proxy.

The feature is split across three architectural layers. On the **backend**, `backend/app/api/models.py` exposes JSON:API endpoints for listing, fetching details, stopping, restarting, and deleting model deployments. The business logic lives in `backend/app/services/model_manager.py`, which uses the F11 command handler to send `stop_model`, `restart_model`, and `delete_model` commands over the agent WebSocket channel, and maintains the authoritative `model_deployments` table state in PostgreSQL. The backend also serves as the log proxy: `backend/app/api/agent_logs.py` accepts HTTP POST log pushes from the agent (F12) and serves them to the frontend via WebSocket broadcast (F16) or direct REST. On the **agent**, `modelprism-agent/modelprism_agent/manager/docker_manager.py` executes the actual Docker operations — container stop (SIGTERM with grace period, then SIGKILL), container restart, and container removal with resource cleanup (GPU device release, port deallocation, state file deletion). On the **frontend**, a dedicated models listing page at `frontend/app/pages/dashboard/models/index.vue` renders all deployments in a PrimeVue `DataTable` filtered by workspace, each row showing model name, agent name, status (with color-coded badge), deployed-at timestamp, and action buttons (stop, restart, delete, view logs). A detail page at `frontend/app/pages/dashboard/models/[id].vue` shows the full deployment configuration, live health status, runtime metrics (throughput, active requests, VRAM usage, KV cache utilization streamed via F16 WebSocket), and a live log viewer.

Runtime health monitoring is a critical sub-feature. The frontend polls `GET /api/models/{id}` every 10 seconds for deployments with status `healthy` or `running` to detect transitions to `failed` or `stopped`. Concurrently, it subscribes to the dashboard WebSocket (F16) for real-time metric updates tied to this deployment's agent. If a deployment's health check fails (vLLM process crash inside the Docker container, GPU OOM, or agent disconnection), the backend updates the `model_deployments.status` to `failed` with an `error_message` and broadcasts a status-change event via WebSocket (F16) so the frontend can immediately update the status badge and surface the error to the user in an inline notification.

F22 integrates with F11 (agent command handler for stop/restart/delete commands), F12 (agent log streaming for container log retrieval), F16 (WebSocket broadcast for real-time status changes and metric updates), F20 (Docker container lifecycle on the agent), F23 (model optimization recommendations consume per-deployment metrics from F22's runtime data), F28 (the proxy layer requires healthy deployments managed by F22 to route inference requests), and F31 (request routing resolves model names to F22-managed deployment endpoints). The `model_deployments` table (F3) is the source of truth for deployment state; the agent's local container state file at `/tmp/modelprism/containers/` is a recovery cache only.

## Concrete Examples (Specification by Example)

### Example 1: List All Running Models in a Workspace

- **Input:** An authenticated user navigates to the Models page (`/dashboard/models`). The workspace has three deployments: `mistral-7b` (healthy, on agent `cyan-koala-42`), `qwen2.5-72b` (healthy, on agent `cyan-koala-42`), and `llama-3.1-8b` (stopped, on agent `lucky-bear-77`).
- **Action:** The frontend `useModels` composable calls `GET /api/models` with an `Authorization: Bearer eyJhbGci...` header. The backend route handler in `backend/app/api/models.py` queries `model_deployments WHERE workspace_id = :ws_id ORDER BY created_at DESC`, serializes the result rows into JSON:API format via the F4 serialization layer, and returns the collection.
- **Expected Output — JSON:API Response (HTTP 200):**
  ```json
  {
    "data": [
      {
        "id": "md-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "type": "modelDeployment",
        "attributes": {
          "modelName": "mistral-7b",
          "hfModelId": "mistralai/Mistral-7B-Instruct-v0.3",
          "status": "healthy",
          "dockerContainerId": "abc123def4567890abcdef1234567890abcdef1234567890abcd",
          "port": 8001,
          "config": {
            "tensor_parallel_size": 1,
            "quantization": null,
            "max_model_len": 32768,
            "max_num_seqs": 256,
            "gpu_memory_utilization": 0.9,
            "kv_cache_dtype": "auto",
            "enable_prefix_caching": true,
            "enforce_eager": false,
            "served_model_name": "mistral-7b"
          },
          "deployedAt": "2026-06-07T10:15:30.000Z",
          "stoppedAt": null,
          "createdAt": "2026-06-07T10:15:30.000Z",
          "updatedAt": "2026-06-07T12:30:00.000Z"
        },
        "relationships": {
          "agent": {
            "data": { "id": "ag_cyan_koala_42", "type": "agent" }
          }
        },
        "links": {
          "self": "/api/models/md-a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        }
      },
      {
        "id": "md-b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "type": "modelDeployment",
        "attributes": {
          "modelName": "qwen2.5-72b",
          "hfModelId": "Qwen/Qwen2.5-72B-Instruct",
          "status": "healthy",
          "dockerContainerId": "def7890abcdef7890abcdef7890abcdef7890abcdef7890abcde",
          "port": 8002,
          "config": {
            "tensor_parallel_size": 2,
            "quantization": "fp8",
            "max_model_len": 65536,
            "max_num_seqs": 128,
            "gpu_memory_utilization": 0.92,
            "kv_cache_dtype": "fp8",
            "enable_prefix_caching": true,
            "enforce_eager": false,
            "served_model_name": "qwen2.5-72b"
          },
          "deployedAt": "2026-06-06T08:00:00.000Z",
          "stoppedAt": null,
          "createdAt": "2026-06-06T08:00:00.000Z",
          "updatedAt": "2026-06-07T12:30:00.000Z"
        },
        "relationships": {
          "agent": {
            "data": { "id": "ag_cyan_koala_42", "type": "agent" }
          }
        },
        "links": {
          "self": "/api/models/md-b2c3d4e5-f6a7-8901-bcde-f12345678901"
        }
      },
      {
        "id": "md-c3d4e5f6-a7b8-9012-cdef-123456789012",
        "type": "modelDeployment",
        "attributes": {
          "modelName": "llama-3.1-8b",
          "hfModelId": "meta-llama/Llama-3.1-8B-Instruct",
          "status": "stopped",
          "dockerContainerId": null,
          "port": null,
          "config": {
            "tensor_parallel_size": 1,
            "quantization": null,
            "max_model_len": 8192,
            "max_num_seqs": 256,
            "gpu_memory_utilization": 0.85,
            "kv_cache_dtype": "auto",
            "enable_prefix_caching": false,
            "enforce_eager": false,
            "served_model_name": "llama-3.1-8b"
          },
          "deployedAt": "2026-06-05T14:00:00.000Z",
          "stoppedAt": "2026-06-07T09:00:00.000Z",
          "createdAt": "2026-06-05T14:00:00.000Z",
          "updatedAt": "2026-06-07T09:00:00.000Z"
        },
        "relationships": {
          "agent": {
            "data": { "id": "ag_lucky_bear_77", "type": "agent" }
          }
        },
        "links": {
          "self": "/api/models/md-c3d4e5f6-a7b8-9012-cdef-123456789012"
        }
      }
    ],
    "meta": {
      "total": 3,
      "filtered": 3
    },
    "links": {
      "self": "/api/models?page[limit]=20&page[offset]=0"
    }
  }
  ```

- **Expected Output — Frontend rendering:** A PrimeVue `DataTable` with columns: Model Name, HF Model ID, Status (green badge "healthy" for first two, gray badge "stopped" for third), Agent, Port, Deployed At, and Actions column. The actions column shows "Stop" and "Restart" buttons for healthy models, and "Delete" button for stopped models. The table supports sorting by model name, status, and deployed-at date. A filter dropdown at the top allows filtering by status (`healthy`, `running`, `stopped`, `failed`).

### Example 2: Stop a Running Model via Agent Command

- **Input:** The user clicks the "Stop" button on the `mistral-7b` deployment row (`md-a1b2c3d4-e5f6-7890-abcd-ef1234567890`) running on agent `ag_cyan_koala_42` at port 8001, Docker container ID `abc123def456`. The frontend shows a confirm dialog: "Stop mistral-7b? This will terminate the inference server and free GPU resources. Active requests will be dropped."
- **Action:** The user confirms. The frontend dispatches `POST /api/models/md-a1b2c3d4-e5f6-7890-abcd-ef1234567890/stop` with `Authorization: Bearer eyJhbGci...`. The backend route handler in `model_manager.py`:
  1. Validates the deployment exists in the workspace and its status is `healthy` or `running`.
  2. Updates `model_deployments.status` to `stopping`.
  3. Sends a `stop_model` command over the F7 WebSocket to the agent.
  4. Broadcasts a status-change event via F16 WebSocket to all dashboard subscribers.

  The agent's `command_handler.py` receives the `stop_model` command and delegates to `DockerManager.stop_container()`, which:
  1. Sends `docker stop --time=30 abc123def456` (SIGTERM with 30-second grace period).
  2. If the container does not exit within 30 seconds, sends `docker kill abc123def456` (SIGKILL).
  3. Verifies `docker ps` no longer lists the container.
  4. Writes a final state file entry with `status: "stopped"` to `/tmp/modelprism/containers/abc123def4567890abcdef1234567890abcdef1234567890abcd.json`.
  5. Emits `command_result` over the WebSocket.

  The backend receives the `command_result`, updates `model_deployments.status` to `stopped`, sets `stopped_at`, clears `docker_container_id` and `port`, and broadcasts the updated state via F16.

- **Expected Output — Backend → Agent WebSocket command:**
  ```json
  {
    "type": "command",
    "command_id": "e5f6a7b8-c9d0-1234-efgh-567890123456",
    "command": "stop_model",
    "params": {
      "deployment_id": "md-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "docker_container_id": "abc123def4567890abcdef1234567890abcdef1234567890abcd",
      "grace_period_seconds": 30
    }
  }
  ```

- **Expected Output — Agent → Backend command_result:**
  ```json
  {
    "type": "command_result",
    "command_id": "e5f6a7b8-c9d0-1234-efgh-567890123456",
    "status": "success",
    "result": {
      "deployment_id": "md-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "docker_container_id": "abc123def4567890abcdef1234567890abcdef1234567890abcd",
      "signal": "SIGTERM",
      "kill_required": false,
      "stop_duration_ms": 2450,
      "port_freed": 8001,
      "gpu_devices_freed": ["GPU-abc12345-abcd-1234-efgh-6789ijklmnop"]
    }
  }
  ```

- **Expected Output — Backend JSON:API response to the original POST (HTTP 200):**
  ```json
  {
    "data": {
      "id": "md-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "type": "modelDeployment",
      "attributes": {
        "modelName": "mistral-7b",
        "hfModelId": "mistralai/Mistral-7B-Instruct-v0.3",
        "status": "stopped",
        "dockerContainerId": null,
        "port": null,
        "stoppedAt": "2026-06-07T12:45:00.000Z"
      }
    }
  }
  ```

- **Expected Output — WebSocket broadcast (F16) to all dashboard subscribers:**
  ```json
  {
    "type": "deployment_status_change",
    "deployment_id": "md-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "previous_status": "healthy",
    "new_status": "stopped",
    "changed_at": "2026-06-07T12:45:00.000Z"
  }
  ```

### Example 3: Restart a Healthy Model

- **Input:** The user clicks "Restart" on the `qwen2.5-72b` deployment (`md-b2c3d4e5-f6a7-8901-bcde-f12345678901`, status `healthy`, agent `ag_cyan_koala_42`, port 8002). The frontend shows a confirm dialog: "Restart qwen2.5-72b? The inference server will be unavailable for approximately 20-60 seconds."
- **Action:** The frontend dispatches `POST /api/models/md-b2c3d4e5-f6a7-8901-bcde-f12345678901/restart`. The backend:
  1. Validates the deployment exists and is in `healthy` or `running` status.
  2. Updates status to `stopping` temporarily.
  3. Sends a `restart_model` command to the agent WebSocket.
  4. The agent's `DockerManager.restart_container()` calls `docker restart def7890abcdef7890...` (where Docker's built-in restart sends SIGTERM, waits, then starts the same container — preserving volumes, network, and GPU assignments).
  5. The agent runs the health check loop against `http://localhost:8002/v1/models` (up to 15 attempts, 2-second delay, 1.5x backoff — more lenient than initial deploy since model weights are cached and only CUDA context re-initialization is needed).
  6. On success, emits `command_result` with `status: "success"` and `restart_duration_ms`.
  7. The backend updates status back to `healthy`, retains the same `port`, `docker_container_id`, and `gpu_device_id`.
  8. Broadcasts the status change via F16.

- **Expected Output — Agent → Backend progress messages:**
  ```json
  {"type": "command_progress", "command_id": "f6a7b8c9-d0e1-2345-fghi-678901234567", "status": "stopping",  "progress_pct": null, "message": "Stopping container def7890abcdef7890... (SIGTERM)"}
  {"type": "command_progress", "command_id": "f6a7b8c9-d0e1-2345-fghi-678901234567", "status": "restarting", "progress_pct": null, "message": "Container stopped. Restarting..."}
  {"type": "command_progress", "command_id": "f6a7b8c9-d0e1-2345-fghi-678901234567", "status": "restarting", "progress_pct": null, "message": "Container restarted. Running health check..."}
  {"type": "command_progress", "command_id": "f6a7b8c9-d0e1-2345-fghi-678901234567", "status": "restarting", "progress_pct": null, "message": "Health check #3: HTTP 200 OK — vLLM ready"}
  ```

- **Expected Output — Agent → Backend command_result:**
  ```json
  {
    "type": "command_result",
    "command_id": "f6a7b8c9-d0e1-2345-fghi-678901234567",
    "status": "success",
    "result": {
      "deployment_id": "md-b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "docker_container_id": "def7890abcdef7890abcdef7890abcdef7890abcdef7890abcde",
      "restart_duration_ms": 18300,
      "health_check_attempts": 3,
      "port": 8002
    }
  }
  ```

### Example 4: Delete a Stopped Model (Full Cleanup)

- **Input:** The user clicks "Delete" on the stopped `llama-3.1-8b` deployment (`md-c3d4e5f6-a7b8-9012-cdef-123456789012`, status `stopped`, agent `ag_lucky_bear_77`). The frontend shows a confirm dialog: "Delete llama-3.1-8b? This will permanently remove the deployment record. Model weights on disk will be preserved."
- **Action:** The frontend dispatches `DELETE /api/models/md-c3d4e5f6-a7b8-9012-cdef-123456789012`. The backend:
  1. Validates the deployment exists in the workspace and its status is `stopped` or `failed` (models with `healthy`/`running` status must be stopped first).
  2. Sends a `delete_model` command to the agent if the deployment has a `docker_container_id` (safety net — ensures no orphaned containers).
  3. The agent's `DockerManager.delete_container()` calls `docker rm --force <container_id>` and removes the state file from `/tmp/modelprism/containers/`. If no container exists, the agent responds with a no-op success.
  4. The backend deletes the `model_deployments` row from PostgreSQL (or soft-deletes by setting `status = "deleted"` and `deleted_at` — the table design uses hard delete, but a soft-delete approach is preferred for auditability: the row is retained with `status = "deleted"` and `deleted_at` timestamp, excluded from all list queries by default).
  5. Broadcasts a `deployment_removed` event via F16.

- **Expected Output — DELETE request with JSON:API response (HTTP 200):**
  ```json
  {
    "data": {
      "id": "md-c3d4e5f6-a7b8-9012-cdef-123456789012",
      "type": "modelDeployment",
      "attributes": {
        "modelName": "llama-3.1-8b",
        "status": "deleted",
        "deletedAt": "2026-06-07T13:00:00.000Z"
      },
      "meta": {
        "container_removed": true,
        "state_file_removed": true
      }
    }
  }
  ```

### Example 5: View Model Detail with Live Metrics and Logs

- **Input:** The user clicks on the `mistral-7b` deployment row (`md-a1b2c3d4-e5f6-7890-abcd-ef1234567890`) from the models list and navigates to `/dashboard/models/md-a1b2c3d4-e5f6-7890-abcd-ef1234567890`.
- **Action:** The detail page mounts and performs three parallel operations:
  1. Calls `GET /api/models/md-a1b2c3d4-e5f6-7890-abcd-ef1234567890` (JSON:API) to load the full deployment record.
  2. Calls `GET /api/agents/ag_cyan_koala_42/metrics?filter[deployment_port]=8001&page[limit]=60` to fetch the last 60 metric snapshots (2 minutes at 2s intervals) for real-time chart rendering. Response format uses inline metric attributes (not JSON:API — lightweight format for high-frequency data):
  ```json
  [
    {"ts": "2026-06-07T12:30:00.000Z", "gpu_util_pct": 72.3, "vram_used_gb": 42.5, "kv_cache_util_pct": 58.2, "running_requests": 4, "tok_per_sec": 185.3, "ttft_p99_ms": 450},
    {"ts": "2026-06-07T12:30:02.000Z", "gpu_util_pct": 68.1, "vram_used_gb": 42.8, "kv_cache_util_pct": 59.1, "running_requests": 3, "tok_per_sec": 192.7, "ttft_p99_ms": 420}
  ]
  ```
  3. Calls `GET /api/agents/ag_cyan_koala_42/logs?filter[deployment_id]=md-a1b2c3d4-e5f6-7890-abcd-ef1234567890&page[limit]=50` to load the last 50 log lines for this deployment.

  The page renders three panels:
  - **Deployment Info card:** model name, HF model ID, status badge, agent name, Docker container ID (truncated), port, full vLLM config as a key-value table, deployed-at and last-updated timestamps, and action buttons (Stop, Restart, Delete).
  - **Live Metrics chart (uPlot):** Four real-time sparklines updating every 2 seconds via the F16 WebSocket metric stream: GPU utilization %, VRAM used GB, tokens per second, and active request count. The chart shows the last 5 minutes with a sliding window.
  - **Live Log viewer:** A scrollable terminal-style log viewer that fetches existing logs via REST then subscribes to the F16 WebSocket log stream for new entries. Each log line shows ISO 8601 timestamp, log level badge (`INFO`/`WARN`/`ERROR`), and message. Errors and warnings are highlighted in red and yellow respectively.

- **Expected Output — F16 WebSocket live log events scoped to this deployment:**
  ```json
  {"type": "log", "agent_id": "ag_cyan_koala_42", "deployment_id": "md-a1b2c3d4-e5f6-7890-abcd-ef1234567890", "ts": "2026-06-07T12:30:05.123Z", "level": "INFO",  "source": "vllm", "message": "Finished request 4723: GET /v1/chat/completions 200 (0.85s)"}
  {"type": "log", "agent_id": "ag_cyan_koala_42", "deployment_id": "md-a1b2c3d4-e5f6-7890-abcd-ef1234567890", "ts": "2026-06-07T12:30:05.456Z", "level": "WARN",  "source": "vllm", "message": "Request 4724: scheduling latency 320ms, consider reducing max_num_seqs"}
  {"type": "log", "agent_id": "ag_cyan_koala_42", "deployment_id": "md-a1b2c3d4-e5f6-7890-abcd-ef1234567890", "ts": "2026-06-07T12:30:06.000Z", "level": "ERROR", "source": "agent",  "message": "GPU 0 temperature 87°C approaching threshold (90°C)"}
  ```

## Acceptance Criteria

- **ACF22-1: List all model deployments with JSON:API filtering** — `GET /api/models` returns a JSON:API collection of all `model_deployments` rows scoped to the caller's workspace, ordered by `created_at DESC`. The endpoint supports the `filter[status]` parameter with values `healthy`, `running`, `stopped`, `failed`, `downloading`, `starting`, `pending` (any `deployment_status` enum value), and `filter[agent_id]` for narrowing to a specific agent. Each resource object includes `modelName`, `hfModelId`, `status`, `dockerContainerId`, `port`, `config` (full JSONB), `deployedAt`, `stoppedAt`, `createdAt`, and `updatedAt` attributes, plus the `agent` relationship linkage. Pagination uses JSON:API `page[limit]` and `page[offset]` with default limit 20, max 100. The endpoint is protected by the F5 JWT auth middleware and scoped by the caller's `workspace_id` (F34 data isolation).

- **ACF22-2: Stop a healthy deployment sends an agent command and updates state** — `POST /api/models/{id}/stop` transitions a deployment from `healthy` or `running` to `stopping` (immediately on the database row), then issues a `stop_model` command via the F11 WebSocket to the deployment's agent. The agent's `DockerManager.stop_container()` sends `docker stop --time=30` (SIGTERM) and falls back to `docker kill` (SIGKILL) after the grace period. On success, the backend sets `status = "stopped"`, `stopped_at = now()`, clears `docker_container_id` and `port`, and broadcasts a `deployment_status_change` event via F16. If the agent WebSocket is disconnected, the backend returns HTTP 503 with a JSON:API error and does not change the deployment status. Stopping an already-stopped or failed deployment returns HTTP 409 Conflict. Stopping requires the `admin` or `owner` role (F33 RBAC check).

- **ACF22-3: Restart a healthy deployment preserves port and GPU assignment** — `POST /api/models/{id}/restart` transitions a deployment from `healthy` or `running` status to `stopping` then back to `healthy` after the agent's `DockerManager.restart_container()` completes. The restart command is issued via F11 — the agent calls `docker restart` and runs a health check loop (up to 15 attempts, initial 2-second delay, 1.5x backoff multiplier). On success, the agent returns `restart_duration_ms` and health check attempt count. The backend retains the same `port`, `docker_container_id`, and `gpu_device_id` — no resource reallocation occurs. The `updated_at` timestamp is refreshed. If the health check fails (all 15 attempts exhausted), the backend sets `status = "failed"` with `error_message = "Restart health check failed after 15 attempts: <last error>"` and broadcasts the failure. Restarting a non-`healthy` or non-`running` deployment returns HTTP 409.

- **ACF22-4: Delete a stopped or failed deployment with optional container cleanup** — `DELETE /api/models/{id}` permanently removes a deployment from the workspace. The endpoint validates that the deployment's status is `stopped` or `failed` — attempting to delete a `healthy` or `running` deployment returns HTTP 409 with a JSON:API error body: `{"errors": [{"status": "409", "title": "Conflict", "detail": "Deployment must be stopped before deletion."}]}`. If the deployment has a non-null `docker_container_id`, the backend sends a `delete_model` command to the agent to `docker rm --force` the container and remove its state file, then soft-deletes by setting `status = "deleted"` and a new `deleted_at` timestamp column (added to the schema if not present). Rows with `status = "deleted"` are excluded from `GET /api/models` by default. The deployment record is preserved for audit trail purposes (referenced by `usage_records` via `model_deployment_id` FK with `ON DELETE SET NULL`). A `deployment_removed` event is broadcast via F16. Deleting a nonexistent deployment returns HTTP 404.

- **ACF22-5: Deployment detail endpoint returns full config and live data** — `GET /api/models/{id}` returns a single JSON:API resource object with all deployment attributes including the full `config` JSONB payload. The response includes `included` top-level key with the related `agent` resource (name, status, hostname, GPU model, GPU count). The frontend detail page (`frontend/app/pages/dashboard/models/[id].vue`) fetches this endpoint on mount and polls it every 10 seconds while the deployment status is `healthy` or `running`, updating the status badge in-place if a transition to `failed` or `stopped` is detected. The frontend concurrently subscribes to the F16 WebSocket for real-time metric and log streams scoped to the deployment's agent, rendering live uPlot charts and a terminal-style log viewer. If the deployment ID does not exist in the caller's workspace, the endpoint returns HTTP 404 regardless of whether it exists in another workspace (F34 data isolation).

- **ACF22-6: Frontend models page provides sortable, filterable, actionable DataTable** — The page at `frontend/app/pages/dashboard/models/index.vue` renders all deployment records in a PrimeVue `DataTable` with the following columns: Model Name (`modelName`), HF Model ID (`hfModelId`), Status (color-coded PrimeVue `Tag` component — green for `healthy`, blue for `running`, yellow for `downloading`/`starting`, gray for `stopped`, red for `failed`), Agent (linked to the agent detail page), Port (displayed only if non-null), Deployed At (relative timestamp, e.g., "2 hours ago"), and Actions (icon buttons: Stop, Restart, Delete). The table supports client-side sorting by model name, status, and deployed-at date. A filter toolbar above the table provides a PrimeVue `Select` dropdown for status filtering (default "All", options: All, Healthy, Running, Stopped, Failed) and an `InputText` search field that filters by model name and HF model ID. Each action button triggers a PrimeVue `ConfirmDialog` requiring explicit user confirmation with a clear description of the operation's impact. The page integrates with the `useModels` Pinia composable (`frontend/app/stores/models.ts`) which manages the deployment list state, handles optimistic UI updates on stop/restart/delete actions, and listens for F16 WebSocket `deployment_status_change` and `deployment_removed` events to update the list in real time without polling.

## Technical Notes

### Backend API Route Design (`backend/app/api/models.py`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/models` | List all deployments (JSON:API collection) |
| `GET` | `/api/models/{deployment_id}` | Single deployment detail |
| `POST` | `/api/models/{deployment_id}/stop` | Stop the inference server |
| `POST` | `/api/models/{deployment_id}/restart` | Restart the inference server |
| `DELETE` | `/api/models/{deployment_id}` | Delete deployment record |

All routes use the F4 JSON:API serialization layer, F5 JWT auth middleware, and F34 workspace-scoped query filters.

### Service Layer (`backend/app/services/model_manager.py`)

The `ModelManager` class handles the orchestration of all lifecycle operations:

```python
class ModelManager:
    async def list_deployments(self, workspace_id: UUID, status_filter: str | None, agent_filter: UUID | None, pagination: PaginationParams) -> tuple[list[ModelDeployment], int]: ...
    async def get_deployment(self, deployment_id: UUID, workspace_id: UUID) -> ModelDeployment: ...
    async def stop_deployment(self, deployment_id: UUID, workspace_id: UUID, user_id: UUID) -> ModelDeployment: ...
    async def restart_deployment(self, deployment_id: UUID, workspace_id: UUID, user_id: UUID) -> ModelDeployment: ...
    async def delete_deployment(self, deployment_id: UUID, workspace_id: UUID, user_id: UUID) -> ModelDeployment: ...
```

The `stop_deployment` method performs these steps in order:
1. `SELECT ... FROM model_deployments WHERE id = :did AND workspace_id = :ws_id AND status IN ('healthy', 'running')` — validates scoped access and status.
2. `UPDATE model_deployments SET status = 'stopping' WHERE id = :did` — immediate status transition.
3. Sends `stop_model` command via `AgentWebSocketManager.send_command(agent_id, command_payload)` (F7/F11).
4. On `command_result` with `status: "success"`: `UPDATE model_deployments SET status = 'stopped', stopped_at = NOW(), docker_container_id = NULL, port = NULL WHERE id = :did`.
5. On `command_result` with `status: "error"`: `UPDATE model_deployments SET status = 'failed', error_message = :msg WHERE id = :did`.
6. Calls `WebSocketBroadcaster.broadcast_event(...)` (F16) with the status change payload.

The `restart_deployment` method follows the same pattern but preserves `docker_container_id` and `port` across the restart, reverting to `healthy` on success or `failed` on health-check exhaustion.

### Agent-Side Docker Operations (`modelprism-agent/modelprism_agent/manager/docker_manager.py`)

New methods added (in addition to those from F20):

- `stop_container(container_id: str, grace_period: int = 30) -> dict` — Calls `docker_client.containers.get(container_id).stop(timeout=grace_period)`. If `ContainerError` with `is_killed=True`, catches and returns `kill_required: true`. Returns stop metadata.
- `restart_container(container_id: str, health_check_port: int, health_check_timeout: int = 60) -> dict` — Calls `docker_client.containers.get(container_id).restart(timeout=30)`, then runs health check loop. Returns restart duration and health check attempts.
- `delete_container(container_id: str) -> dict` — Calls `docker_client.containers.get(container_id).remove(force=True)`. Removes state file from `/tmp/modelprism/containers/`. Returns `container_removed: true`.

### Agent Command Dispatcher (`modelprism-agent/modelprism_agent/command_handler.py`)

Command routing additions to the F11 dispatcher:

| Command | Method Called | Expected Duration |
|---------|--------------|-------------------|
| `stop_model` | `DockerManager.stop_container()` | < 30s |
| `restart_model` | `DockerManager.restart_container()` | 20-60s |
| `delete_model` | `DockerManager.delete_container()` | < 5s |

### Frontend Pages and Components

| File | Purpose |
|------|---------|
| `frontend/app/pages/dashboard/models/index.vue` | Models listing with DataTable, filters, action buttons |
| `frontend/app/pages/dashboard/models/[id].vue` | Model detail page with config, live metrics, logs |
| `frontend/app/components/models/ModelListTable.vue` | Reusable deployment table component |
| `frontend/app/components/models/ModelDetailCard.vue` | Deployment info card with full config display |
| `frontend/app/components/models/ModelLiveMetrics.vue` | uPlot real-time charts for GPU/throughput/latency |
| `frontend/app/components/models/ModelLiveLog.vue` | Terminal-style live log viewer scoped to deployment |
| `frontend/app/stores/models.ts` | Pinia store for deployment list, current selection, WebSocket event handlers |

The `frontend/app/stores/models.ts` Pinia store structure:

```typescript
interface ModelsState {
  deployments: ModelDeployment[];           // Full list from JSON:API
  currentDeployment: ModelDeployment | null; // Currently selected detail
  totalCount: number;
  loading: boolean;
  filters: {
    status: DeploymentStatus | null;
    search: string;
  };
}
```

### Edge Cases

- **Stop on already-stopped deployment:** The backend returns HTTP 409 Conflict. The frontend's action buttons are disabled for non-healthy/non-running statuses, but the backend validates regardless.
- **Restart on failed deployment:** HTTP 409 Conflict. The user must first redeploy via F19.
- **Agent disconnected during stop/restart:** The backend sends the command over WebSocket. If the agent is offline, `AgentWebSocketManager.send_command()` raises a `ConnectionError`. The backend catches this, reverts the status to the original value (e.g., `healthy` if stop failed), and returns HTTP 503 with a JSON:API error body including `detail`: "Agent ag_cyan_koala_42 is offline. Cannot stop deployment.".
- **Agent reconnects mid-operation:** If the agent crashes mid-stop (after receiving the command but before Docker completes it), the agent's F13 lifecycle handler on reconnection should detect the orphaned container via the local state file and attempt to complete the stop operation, then re-sync the deployment state with the backend via a status reconciliation message.
- **Concurrent operations on the same deployment:** The backend uses a database-level optimistic lock or advisory application lock to prevent two concurrent stop/restart/delete operations on the same deployment. If a stop is in progress and a restart is requested, the backend returns HTTP 409 with `detail`: "Deployment is currently stopping. Wait for the operation to complete.".
- **Stop when active proxy requests are in-flight:** The stop operation proceeds regardless — the Docker container receives SIGTERM, vLLM will attempt to finish in-flight requests within the grace period, then shut down. The proxy (F28) will return HTTP 502 for any requests routed to this deployment after the container stops; the router (F31) should mark this endpoint as unhealthy and route to the next available replica (if any).
- **Delete with associated usage records:** The `model_deployment_id` FK in `usage_records` uses `ON DELETE SET NULL`, so deleting the deployment record sets this FK to NULL in all associated usage rows. This preserves billing and usage history without coupling it to the deployment's existence.

### Schema Changes (F3 Extension)

The `model_deployments` table (F3) already supports the core lifecycle. One additional column is recommended:

```sql
ALTER TABLE model_deployments ADD COLUMN deleted_at TIMESTAMPTZ NULL;
```

This enables soft-deletion for audit trail purposes. All list queries should include `WHERE (status != 'deleted' OR status IS NULL) AND workspace_id = :ws_id`.

### Integration Points

- **F3** — `model_deployments` table: source of truth for all deployment state. The `deployment_status` enum defines the state machine: `pending → downloading → starting → running → healthy`, with transitions to `stopping → stopped` and `failed` on errors. The `deleted_at` field is added for soft-delete auditability.
- **F4** — JSON:API serialization layer: all model deployment endpoints use F4's `ResourceObject`, `Document`, and pagination patterns. The deployment resource type is `modelDeployment`.
- **F5** — JWT auth middleware: all model management endpoints require authentication. RBAC (F33) is enforced at the service layer for write operations (stop/restart/delete require `admin` or `owner` role).
- **F7** — Agent WebSocket connection handler: provides the transport for stop/restart/delete commands. The `send_command()` method in `AgentWebSocketManager` is used by `ModelManager` to dispatch agent-side operations.
- **F11** — Agent command handler: defines the `stop_model`, `restart_model`, and `delete_model` command schemas in `common/modelprism_common/schemas/commands.py`. Agent dispatches to `DockerManager` methods.
- **F12** — Agent log streaming: container logs are pushed by the agent to `POST /api/agents/{id}/logs` and can include a `deployment_id` field in the payload for scoping. The frontend fetches per-deployment logs via `GET /api/agents/{id}/logs?filter[deployment_id]=...`.
- **F16** — WebSocket broadcast: status change events (`deployment_status_change`, `deployment_removed`) and deployment-scoped metric streams are broadcast to all dashboard subscribers. The F16 event format uses lightweight JSON (not JSON:API) for real-time throughput.
- **F19** — Model deployment wizard: triggers the initial deployment that F22 manages. The wizard passes through to the models list page after successful deployment.
- **F20** — Docker container management: the agent side of container lifecycle. F22's stop/restart/delete operations call F20's `DockerManager` methods under the hood.
- **F23** — Model optimization recommendations: consumes per-deployment runtime metrics (GPU utilization, KV cache pressure, throughput) that F22 surfaces to make rule-based optimization suggestions.
- **F28** — OpenAI-compatible proxy: routes inference requests to healthy F22-managed deployments. A deployment must be in `healthy` status before F28 routes to it. Stop operations may cause transient errors for in-flight proxy requests.
- **F31** — Request routing: resolves the requested model name to a specific F22 deployment endpoint. The router's health checker monitors F22-managed deployments and marks stopped/failed deployments as unavailable.
- **F33** — RBAC: stop/restart/delete operations are restricted to workspace roles with `admin` or `owner` permission. List and detail views are available to `member` and `viewer` roles.
- **F34** — Workspace data isolation: all model deployment queries include `WHERE workspace_id = :current_workspace_id`. Cross-workspace access returns 404.

### JSON:API Resource Type Registration

The `modelDeployment` resource type is registered in the F4 serialization layer:

| Attribute | JSON:API Key | Source Column | Type |
|-----------|-------------|---------------|------|
| Model Name | `modelName` | `model_name` | string |
| HF Model ID | `hfModelId` | `hf_model_id` | string |
| Status | `status` | `status` | string (deployment_status enum) |
| Docker Container ID | `dockerContainerId` | `docker_container_id` | string or null |
| Port | `port` | `port` | integer or null |
| Config | `config` | `config` | object (JSONB) |
| Error Message | `errorMessage` | `error_message` | string or null |
| Deployed At | `deployedAt` | `deployed_at` | ISO 8601 timestamp or null |
| Stopped At | `stoppedAt` | `stopped_at` | ISO 8601 timestamp or null |
| Deleted At | `deletedAt` | `deleted_at` | ISO 8601 timestamp or null (added) |
| Created At | `createdAt` | `created_at` | ISO 8601 timestamp |
| Updated At | `updatedAt` | `updated_at` | ISO 8601 timestamp |

Relationships: `agent` (type: `agent`, to-one).

## Depends on: F11 (Agent command handler — WebSocket-based command transport for stop/restart/delete), F20 (Docker model deployment — container lifecycle on the agent side)
