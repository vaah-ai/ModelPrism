# Feature F20: Docker-based Model Deployment

**Status:** Draft  
**Date:** 2026-06-07  
**Author:** ModelPrism Team  
**Priority:** P1 — Core  
**Dependencies:** F3 (Backend API), F8 (Agent Runner), F11 (GPU Monitoring), F12 (Model Registry), F13 (System Monitoring), F16 (Log Collection), F19 (Conversation API), F21 (Task Scheduling), F22 (Secrets Management), F33 (Authentication)

---

## Table of Contents

1. [Overview](#overview)
2. [Acceptance Criteria](#acceptance-criteria)
3. [Examples](#examples)
4. [Integration Points](#integration-points)
5. [Error Codes](#error-codes)
6. [Edge Cases](#edge-cases)

---

## Overview

ModelPrism deploys LLMs by launching Docker containers that expose an OpenAI-compatible `/v1/chat/completions` endpoint. The **modelprism-agent** (one per host) is the sole executor of Docker operations. It receives commands from the backend, writes state files for crash recovery, and reports lifecycle progress. The backend validates every deployment request before dispatching it.

### Key Design Decisions

| Decision | Rationale |
|---|---|
| Agent is the only component with `docker` socket access | Keeps Docker credentials off the web API surface |
| State files written to `/var/lib/modelprism/states/` | Survives agent restarts; enables crash recovery |
| Container label `ai.modelprism.managed=true` | Discoverability; prevents manual container conflicts |
| Exclusive GPU reservation (`CUDA_VISIBLE_DEVICES`) | Prevents GPU contention; one model per GPU |
| Health checks via exponential backoff (1 s → 32 s) | Balances quick startup detection with long-tail waits |
| `SIGTERM` → 30 s drain → `SIGKILL` | Graceful shutdown with request draining |
| Backend validates deploy requests before dispatch | Fail-fast: no agent round-trip for obvious errors |

### Agent Architecture

```
                    ┌──────────────┐
                    │   Backend    │
                    │  (FastAPI)   │
                    └──────┬───────┙
                           │ Redis pub/sub
                    ┌──────▼───────┐
                    │  modelprism- │
                    │  agent       │
                    └──────┬───────┙
                           │ Docker socket
                    ┌──────▼───────┐
                    │  Docker      │
                    │  Daemon      │
                    └──────────────┘
```

---

## Acceptance Criteria

### ACF20-1: Container Lifecycle Management  
**Given** a validated deployment request targeting GPU `uuid-2` with model `mistralai/Mistral-7B-Instruct-v0.3`  
**When** the agent receives the `DEPLOY` command  
**Then** the agent SHALL:
- Pull the image `docker.io/vllm/vllm-openai:latest` if not present locally
- Create a container with GPU device `uuid-2` exclusively reserved via `CUDA_VISIBLE_DEVICES`
- Mount `/var/lib/modelprism/logs/<deployment_id>` as `/var/log/modelprism` inside the container
- Set environment variables: `MODEL_NAME=mistralai/Mistral-7B-Instruct-v0.3`, `HUGGING_FACE_HUB_TOKEN=<redacted>`, `CUDA_VISIBLE_DEVICES=uuid-2`, `MAX_MODEL_LEN=4096`
- Map host port 8200 to container port 8000
- Tag the container with labels: `ai.modelprism.managed=true`, `ai.modelprism.deployment-id=<deployment_id>`, `ai.modelprism.model=mistralai/Mistral-7B-Instruct-v0.3`, `ai.modelprism.gpu=uuid-2`
- Write a deployment state file at `/var/lib/modelprism/states/<deployment_id>.json`
- Run a health-check loop (exponential backoff 1 s → 2 s → 4 s → 8 s → 16 s → 32 s, cap at 32 s, max 10 attempts)
- Report the container ID (abbreviated 12-char hex) back to the backend via Redis `DEPLOY_RESULT`

### ACF20-2: GPU Device Reservation  
**Given** an active deployment on GPU `uuid-2`  
**When** a second deployment request targets the same GPU `uuid-2`  
**Then** the backend SHALL reject the request with error code `GPU_IN_USE` (HTTP 409) before the agent ever sees it  
**And** when a deployment is stopped (successfully), the backend SHALL mark GPU `uuid-2` as available in Redis under `gpu:<uuid-2>:status`

### ACF20-3: Health Check & Diagnostics  
**Given** a container has been started  
**When** the agent performs the health check loop  
**Then** each attempt SHALL:
- Send `POST /v1/chat/completions` with `{"model":"mistralai/Mistral-7B-Instruct-v0.3","messages":[{"role":"user","content":"ping"}],"max_tokens":1}`
- Expect HTTP 200 within 30 seconds
- On success, report `DEPLOY_RESULT` with status `running`
- On repeated failure after 10 attempts, report `DEPLOY_RESULT` with status `failed` and include the last error message in the `error` field
- Record each attempt outcome (`attempt`, `timestamp`, `status`, `error`) in the state file under `health_check_attempts`

### ACF20-4: Container Labels for Discovery  
**Given** a running managed container  
**When** the agent lists containers with the label filter `ai.modelprism.managed=true`  
**Then** the agent SHALL include every managed container's abbreviated ID, deployment ID, model name, GPU UUID, and container status in the response  
**And** the backend SHALL expose this information at `GET /api/v1/deployments`

### ACF20-5: State Files for Crash Recovery  
**Given** the agent process restarts after an unexpected crash  
**When** the agent starts up  
**Then** it SHALL:
- Read all state files from `/var/lib/modelprism/states/*.json`
- For each state file where `status` is `deploying`, resume the health check loop and record the recovery in the state file
- For each state file where `status` is `running`, verify the container still exists via `docker inspect` and update the state accordingly
- For each state file where `status` is `stopped` or `failed`, take no action (historical record)

### ACF20-6: F11 / F13 Integration  
**Given** a deployment is in `running` state  
**When** F11 (GPU Monitoring) polls GPU metrics or F13 (System Monitoring) polls system metrics  
**Then** the metrics pipeline SHALL include:
- GPU UUID → deployment ID mapping so dashboards can correlate GPU load to a specific model
- Container-level memory / CPU stats via Docker stats API
- Per-request throughput and latency (from the OpenAI-compatible endpoint's response headers)

### ACF20-7: Backend Deployment Validation  
**Given** a `POST /api/v1/deployments` request  
**When** the backend receives it  
**Then** the backend SHALL validate **before** dispatching to the agent:
- `image` is not empty and is a valid Docker image reference
- `model` references a registered model in F12 (Model Registry)
- `gpu_uuid` is valid and not already in use (checked via Redis `gpu:<uuid>:status`)
- `port` is within range 1024–65535 and not already allocated
- `env_vars` contains `HUGGING_FACE_HUB_TOKEN` (or equivalent auth for the model source)
- `max_model_len` is a positive integer ≤ 131072
- The requesting user has the `deploy:create` permission via F33
- The agent is online (heartbeat within last 30 seconds)

Validation failures SHALL return a JSON:API error response with status `422` for field errors or `409` for resource conflicts.

---

## Examples

### Example 1: Full Mistral 7B Docker Lifecycle

**Deployment request (POST /api/v1/deployments):**

```json
{
  "data": {
    "type": "deployment",
    "attributes": {
      "image": "docker.io/vllm/vllm-openai:latest",
      "model": "mistralai/Mistral-7B-Instruct-v0.3",
      "gpu_uuid": "uuid-2",
      "port": 8200,
      "env_vars": {
        "HUGGING_FACE_HUB_TOKEN": "hf_xxxx",
        "MAX_MODEL_LEN": "4096"
      }
    }
  }
}
```

**Backend validation passes** → dispatch via Redis to `agent:host-01:commands` → `DEPLOY`

**Agent state file** (`/var/lib/modelprism/states/dep-a1b2c3d4-e5f6-7890-abcd-ef1234567890.json`):

```json
{
  "deployment_id": "dep-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "deploying",
  "gpu_uuid": "uuid-2",
  "port": 8200,
  "image": "docker.io/vllm/vllm-openai:latest",
  "model": "mistralai/Mistral-7B-Instruct-v0.3",
  "container_id": "",
  "created_at": "2026-06-07T14:30:00Z",
  "updated_at": "2026-06-07T14:30:00Z",
  "health_check_attempts": []
}
```

**Agent creates container** → updates state file:

```json
{
  "deployment_id": "dep-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "deploying",
  "gpu_uuid": "uuid-2",
  "port": 8200,
  "container_id": "a1b2c3d4e5f6",
  "created_at": "2026-06-07T14:30:00Z",
  "updated_at": "2026-06-07T14:30:05Z",
  "health_check_attempts": [],
  "container_created_at": "2026-06-07T14:30:05Z"
}
```

**Health check loop** → attempt 3 succeeds:

```json
{
  "deployment_id": "dep-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "running",
  "gpu_uuid": "uuid-2",
  "port": 8200,
  "container_id": "a1b2c3d4e5f6",
  "created_at": "2026-06-07T14:30:00Z",
  "updated_at": "2026-06-07T14:30:19Z",
  "health_check_attempts": [
    {"attempt": 1, "timestamp": "2026-06-07T14:30:06Z", "status": "failed", "error": "connection refused"},
    {"attempt": 2, "timestamp": "2026-06-07T14:30:08Z", "status": "failed", "error": "connection refused"},
    {"attempt": 3, "timestamp": "2026-06-07T14:30:12Z", "status": "success", "error": null}
  ]
}
```

**Agent dispatches DEPLOY_RESULT** → Redis channel `agent:host-01:results`:

```json
{
  "type": "DEPLOY_RESULT",
  "deployment_id": "dep-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "running",
  "container_id": "a1b2c3d4e5f6",
  "port": 8200,
  "gpu_uuid": "uuid-2"
}
```

**Backend** marks GPU as in-use, records deployment in database, returns 201:

```json
{
  "data": {
    "id": "dep-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "type": "deployment",
    "attributes": {
      "image": "docker.io/vllm/vllm-openai:latest",
      "model": "mistralai/Mistral-7B-Instruct-v0.3",
      "gpu_uuid": "uuid-2",
      "port": 8200,
      "status": "running",
      "container_id": "a1b2c3d4e5f6",
      "created_at": "2026-06-07T14:30:00Z",
      "started_at": "2026-06-07T14:30:19Z"
    }
  }
}
```

---

### Example 2: Graceful Shutdown with Request Draining

**Undeploy request (DELETE /api/v1/deployments/dep-a1b2c3d4-e5f6-7890-abcd-ef1234567890):**

No request body needed; backend authorizes via F33, checks F3 permissions.

**Backend** dispatches `UNDEPLOY` via Redis → agent receives command.

**Agent** sends `SIGTERM` → waits 30 s → checks if container is still running → sends `SIGKILL` if needed.

```
Agent sends SIGTERM                           Agent sends SIGKILL (if still alive)
    │                                                 │
    ▼                                                 ▼
├─────────────────────────────────┬───────────────────────────┤
│          Drain Window           │        Force Stop         │
│           30 seconds            │                           │
└─────────────────────────────────┴───────────────────────────┘
```

**Agent updates state file:**

```json
{
  "deployment_id": "dep-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "stopped",
  "stopped_at": "2026-06-07T15:00:12Z",
  "stop_reason": "user_request",
  "drain_completed": true
}
```

**Agent dispatches UNDEPLOY_RESULT** → `status: "stopped"`, `drain_completed: true`.

**Backend** marks GPU `uuid-2` as available in Redis, updates database record with `stopped_at`.

---

### Example 3: Multi-GPU (TP=2) — Qwen 72B Deployment

**Some deployments require tensor parallelism across multiple GPUs.**

**Deployment request:**

```json
{
  "data": {
    "type": "deployment",
    "attributes": {
      "image": "docker.io/vllm/vllm-openai:latest",
      "model": "Qwen/Qwen-72B-Chat",
      "gpu_uuids": ["uuid-1", "uuid-4"],
      "port": 8201,
      "env_vars": {
        "HUGGING_FACE_HUB_TOKEN": "hf_xxxx",
        "TENSOR_PARALLEL_SIZE": "2",
        "MAX_MODEL_LEN": "8192",
        "CUDA_VISIBLE_DEVICES": "uuid-1,uuid-4"
      }
    }
  }
}
```

**Validation differences from single-GPU deployment:**
- `gpu_uuids` (plural, array) is used instead of `gpu_uuid` (singular)
- All GPUs in the array are checked for availability
- Port range validation unchanged
- TP=2 requires both GPUs to share the same host (validated by agent)

**Agent creates container** with `CUDA_VISIBLE_DEVICES=uuid-1,uuid-4` and `--gpus '"device=uuid-1,device=uuid-4"'`. Health check is identical (single endpoint).

**State file labels** include both GPU UUIDs:

```json
{
  "deployment_id": "dep-b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "status": "running",
  "gpu_uuids": ["uuid-1", "uuid-4"],
  "tensor_parallel_size": 2,
  "port": 8201,
  "container_id": "b2c3d4e5f6a7",
  "created_at": "2026-06-07T16:00:00Z",
  "updated_at": "2026-06-07T16:00:22Z",
  "health_check_attempts": [
    {"attempt": 1, "timestamp": "2026-06-07T16:00:05Z", "status": "failed", "error": "connection refused"},
    {"attempt": 2, "timestamp": "2026-06-07T16:00:09Z", "status": "success", "error": null}
  ]
}
```

**Docker labels:**

```
ai.modelprism.managed=true
ai.modelprism.deployment-id=dep-b2c3d4e5-f6a7-8901-bcde-f12345678901
ai.modelprism.model=Qwen/Qwen-72B-Chat
ai.modelprism.gpu=uuid-1,uuid-4
```

---

### Example 4: vLLM OOM Crash — Deployment Failure

**Deployment request** for a model that exceeds available GPU memory.

```json
{
  "data": {
    "type": "deployment",
    "attributes": {
      "image": "docker.io/vllm/vllm-openai:latest",
      "model": "meta-llama/Llama-3.1-70B-Instruct",
      "gpu_uuid": "uuid-3",
      "port": 8202,
      "env_vars": {
        "HUGGING_FACE_HUB_TOKEN": "hf_xxxx",
        "MAX_MODEL_LEN": "16384"
      }
    }
  }
}
```

**Backend validation passes** (model is registered; GPU is free; port is free). Dispatches to agent.

**Agent creates container** successfully. Container starts, vLLM loads the model, then **OOM-killed by kernel**.

**Health check loop:**

| Attempt | Timestamp | Result | Error |
|---|---|---|---|
| 1 | 14:30:06Z | failed | connection refused |
| 2 | 14:30:08Z | failed | connection refused |
| 3 | 14:30:12Z | failed | connection refused |
| 4 | 14:30:16Z | failed | connection refused |
| 5 | 14:30:24Z | failed | connection refused |
| 6 | 14:30:40Z | failed | connection refused |
| 7 | 14:31:12Z | failed | `docker inspect` shows container exited with code 137 (OOM) |
| 8 | 14:32:16Z | failed | container no longer running |
| 9 | 14:33:48Z | failed | container no longer running |
| 10 | 14:35:20Z | failed | container exited code 137 — OOM kill |

**Final state file:**

```json
{
  "deployment_id": "dep-c3d4e5f6-a7b8-9012-cdef-123456789012",
  "status": "failed",
  "gpu_uuid": "uuid-3",
  "port": 8202,
  "container_id": "c3d4e5f6a7b8",
  "created_at": "2026-06-07T14:30:00Z",
  "updated_at": "2026-06-07T14:35:20Z",
  "health_check_attempts": [
    {"attempt": 1, "timestamp": "2026-06-07T14:30:06Z", "status": "failed", "error": "connection refused"},
    {"attempt": 2, "timestamp": "2026-06-07T14:30:08Z", "status": "failed", "error": "connection refused"},
    {"attempt": 3, "timestamp": "2026-06-07T14:30:12Z", "status": "failed", "error": "connection refused"},
    {"attempt": 4, "timestamp": "2026-06-07T14:30:16Z", "status": "failed", "error": "connection refused"},
    {"attempt": 5, "timestamp": "2026-06-07T14:30:24Z", "status": "failed", "error": "connection refused"},
    {"attempt": 6, "timestamp": "2026-06-07T14:30:40Z", "status": "failed", "error": "connection refused"},
    {"attempt": 7, "timestamp": "2026-06-07T14:31:12Z", "status": "failed", "error": "docker inspect shows exited code 137"},
    {"attempt": 8, "timestamp": "2026-06-07T14:32:16Z", "status": "failed", "error": "container no longer running"},
    {"attempt": 9, "timestamp": "2026-06-07T14:33:48Z", "status": "failed", "error": "container no longer running"},
    {"attempt": 10, "timestamp": "2026-06-07T14:35:20Z", "status": "failed", "error": "container exited code 137 — OOM kill"}
  ],
  "failure_reason": "OOM",
  "failure_detail": "Container exited with code 137 (OOM killed). GPU uuid-3 (24 GB VRAM) insufficient for meta-llama/Llama-3.1-70B-Instruct with max_model_len=16384."
}
```

**Agent dispatches DEPLOY_RESULT** → `status: "failed"`, `error`: `"container exited code 137 — OOM kill"`, `failure_reason`: `"OOM"`.

**Backend** marks GPU `uuid-3` as available (the container is dead), records failure in database, returns 201 but with `status: "failed"` and diagnostic info in the response body.

---

### Example 5: Backend Validation Rejection — Multiple Errors

**Invalid deployment request:**

```json
{
  "data": {
    "type": "deployment",
    "attributes": {
      "image": "",
      "model": "unknown-model",
      "gpu_uuid": "uuid-2",
      "port": 80,
      "env_vars": {}
    }
  }
}
```

**Backend validation result — 422 Unprocessable Entity:**

```json
{
  "errors": [
    {
      "status": "422",
      "code": "FIELD_REQUIRED",
      "title": "Image is required",
      "source": { "pointer": "/data/attributes/image" }
    },
    {
      "status": "422",
      "code": "INVALID_MODEL",
      "title": "Model not found in registry",
      "detail": "The model 'unknown-model' is not registered in F12 Model Registry",
      "source": { "pointer": "/data/attributes/model" }
    },
    {
      "status": "422",
      "code": "PORT_OUT_OF_RANGE",
      "title": "Port must be between 1024 and 65535",
      "source": { "pointer": "/data/attributes/port" }
    },
    {
      "status": "422",
      "code": "FIELD_REQUIRED",
      "title": "HUGGING_FACE_HUB_TOKEN is required in env_vars",
      "source": { "pointer": "/data/attributes/env_vars" }
    }
  ]
}
```

**Backend does not dispatch to the agent.** The 422 is returned directly to the API caller. No state file is created. No GPU reservation is changed.

---

## Integration Points

| Component | Integration | File |
|---|---|---|
| **F3 — Backend API** | `POST /api/v1/deployments`, `DELETE /api/v1/deployments/{id}`, `GET /api/v1/deployments`, `GET /api/v1/deployments/{id}` | `backend/app/routes/deployments.py` |
| **F8 — Agent Runner** | Dispatches `DEPLOY` / `UNDEPLOY` / `LIST` commands to agent via Redis; receives `DEPLOY_RESULT` / `UNDEPLOY_RESULT` / `LIST_RESULT` | `modelprism-agent/src/agent_runner.py`, `modelprism-agent/src/docker_handler.py` |
| **F11 — GPU Monitoring** | GPU UUID → deployment mapping for metrics correlation; GPU in-use tracking via Redis | `backend/app/services/gpu_tracker.py` |
| **F12 — Model Registry** | Deployment references registered model by name; validation checks model exists | `backend/app/services/model_registry.py` |
| **F13 — System Monitoring** | Container memory/CPU stats; Docker stats API integration | `common/modelprism_common/monitoring/container_stats.py` |
| **F16 — Log Collection** | Logs written to `/var/lib/modelprism/logs/<deployment_id>/` inside container at `/var/log/modelprism/` | `modelprism-agent/src/log_collector.py` |
| **F19 — Conversation API** | Conversations target a deployment via `deployment_id` in chat request | `backend/app/routes/conversations.py` |
| **F21 — Task Scheduling** | Periodic health checks for running deployments (reconcile state) | `backend/app/services/deployment_health.py` |
| **F22 — Secrets Management** | Hugging Face tokens and other secrets retrieved via Vault at deploy time; never stored in deployment database | `modelprism-agent/src/secrets_resolver.py` |
| **F33 — Authentication** | `deploy:create`, `deploy:delete`, `deploy:view` permissions checked on every deployment endpoint | `backend/app/auth/permissions.py` |

### Key File Paths

| File | Purpose |
|---|---|
| `backend/app/routes/deployments.py` | API route handlers for CRUD operations |
| `backend/app/services/gpu_tracker.py` | GPU reservation and availability tracking via Redis |
| `backend/app/validators/deployment_validator.py` | Backend-side deployment request validation |
| `modelprism-agent/src/docker_handler.py` | Docker lifecycle operations (create, health, stop, list) |
| `modelprism-agent/src/state_manager.py` | State file read/write at `/var/lib/modelprism/states/` |
| `modelprism-agent/src/agent_runner.py` | Agent main loop: Redis command dispatch, state recovery on startup |
| `common/modelprism_common/monitoring/container_stats.py` | Docker stats API wrapper for container-level metrics |
| `common/modelprism_common/schemas/deployment.py` | Pydantic schemas for deployment requests and responses |

---

## Error Codes

### Backend JSON:API Errors

| HTTP Status | Code | Description |
|---|---|---|
| 400 | `INVALID_REQUEST` | Malformed JSON or missing required fields |
| 401 | `UNAUTHORIZED` | Missing or expired authentication token |
| 403 | `FORBIDDEN` | User lacks `deploy:create`, `deploy:delete`, or `deploy:view` permission |
| 404 | `NOT_FOUND` | Deployment or model not found |
| 409 | `GPU_IN_USE` | Requested GPU is already reserved by another deployment |
| 409 | `PORT_IN_USE` | Requested host port is already mapped by another deployment |
| 422 | `FIELD_REQUIRED` | A required field is missing |
| 422 | `INVALID_MODEL` | Model is not registered in F12 Model Registry |
| 422 | `PORT_OUT_OF_RANGE` | Port is outside the allowed range (1024–65535) |
| 422 | `GPU_INVALID` | GPU UUID is not valid for this host |
| 422 | `AGENT_OFFLINE` | The target agent has not reported a heartbeat within 30 seconds |
| 429 | `RATE_LIMITED` | Too many deployment requests (rate limit configured per user) |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 503 | `SERVICE_UNAVAILABLE` | Redis, database, or Docker daemon unreachable |

### Agent Command Error Codes

| Code | Description |
|---|---|
| `AGENT_ERR_DOCKER_DAEMON` | Docker daemon is not reachable on the host |
| `AGENT_ERR_PULL_FAILED` | Docker image pull failed (network, auth, or disk space) |
| `AGENT_ERR_CREATE_FAILED` | Container creation failed (invalid image, port conflict at OS level) |
| `AGENT_ERR_START_FAILED` | Container start failed (resource allocation error) |
| `AGENT_ERR_HEALTH_TIMEOUT` | Health check exceeded maximum attempts (10) |
| `AGENT_ERR_OOM` | Container exited with code 137 (OOM killed) |
| `AGENT_ERR_STOP_FAILED` | Container stop failed (container already removed or invalid ID) |
| `AGENT_ERR_INSPECT_FAILED` | Container inspection failed (container not found) |
| `AGENT_ERR_STATE_WRITE` | State file could not be written (permissions or disk space) |
| `AGENT_ERR_STATE_READ` | State file could not be read (corrupt or missing) |

---

## Edge Cases

### Docker Daemon Down
**Scenario:** The agent tries to create a container but the Docker daemon is unreachable.  
**Response:** The agent retries the Docker operation up to 3 times with 2-second intervals. If all retries fail, the agent reports `AGENT_ERR_DOCKER_DAEMON` via Redis and marks the deployment as `failed` in the state file. Backend returns 503 to the API caller with detail: `"Docker daemon unreachable on host host-01"`.

### Port Conflict
**Scenario:** Two deployments try to use the same host port simultaneously.  
**Response:** The backend checks port availability in Redis before dispatching (atomic check-and-set via Redis `SETNX`). If the race condition still produces a conflict at the Docker level (e.g., port already bound by a non-managed container), the agent catches the Docker error (`port is already allocated`), reports `AGENT_ERR_CREATE_FAILED`, and the backend releases the Redis port reservation.

### OOM Kill
**Scenario:** The vLLM process inside the container is OOM-killed by the kernel (exit code 137).  
**Response:** The health check loop detects the container has exited. The agent inspects the exit code and includes `failure_reason: "OOM"` and the detail in the state file and `DEPLOY_RESULT`. Backend marks the GPU as available and records the diagnostic information. Future deployments on the same GPU are allowed.

### Backend Restart During Deployment
**Scenario:** The backend restarts while the agent is still performing the health check loop for a deployment.  
**Response:** The agent continues the health check loop independently (it does not depend on the backend being alive). When the health check completes (success or failure), the agent publishes `DEPLOY_RESULT` to Redis. If the backend is still down, the message is buffered by Redis (pub/sub with fan-out) and delivered when the backend re-subscribes. The agent also persists the final state to the state file, which the backend can read during startup reconciliation.

### Agent Restart During Deployment
**Scenario:** The agent crashes during the health check loop.  
**Response:** On restart, the agent reads all state files. For states with `status: "deploying"`, it checks if the container exists: if yes, resumes the health check loop from where it left off (preserving previous attempt history in the state file and continuing the exponential backoff from the last attempt); if the container does not exist, the deployment is marked `failed` with reason `"agent_crash_container_lost"`.

### Concurrent Lifecycle Operations
**Scenario:** A user sends `DELETE /deployments/{id}` while the deployment is still in the `deploying` state (health check in progress).  
**Response:** The backend sets the deployment status to `stopping` in the database and dispatches `UNDEPLOY` to the agent. The agent receives the `UNDEPLOY` command: stops the health check loop, sends `SIGTERM` to the container (even if it hasn't passed health checks yet), and proceeds with the standard shutdown sequence. The state file records `stop_reason: "user_request_during_deploy"` and the final status is `stopped`.

---

## Revision History

| Date | Version | Author | Changes |
|---|---|---|---|
| 2026-06-07 | 1.0 | ModelPrism Team | Initial draft |
