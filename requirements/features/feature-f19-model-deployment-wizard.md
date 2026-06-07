# F19: Model deployment wizard

## Metadata
- **ID:** F19
- **Phase:** Enhancement
- **Effort:** XL
- **Dependencies:** F2, F5, F18
- **Acceptance Criteria Count:** 8

## Description

Feature F19 implements the five-step model deployment wizard that guides users through deploying a HuggingFace model onto a target GPU server via the modelprism-agent. The wizard is the primary user-facing orchestration UI for the model lifecycle: it consumes the HuggingFace Hub browser from F18 (model selection), the agent list from F14 (GPU server selection), a vLLM parameter configuration form, a real-time capacity calculator that estimates VRAM requirements and throughput projections, and a final review-and-deploy step that triggers the agent-side deployment pipeline.

The wizard is rendered as a PrimeVue `Stepper` component at `frontend/app/pages/dashboard/models/deploy.vue`, with five steps backed by child components in `frontend/app/components/deployment/`. Each step validates its input before allowing forward navigation. The backend endpoint `POST /api/models/deploy` (defined in `backend/app/api/models.py`) receives the complete deployment payload, validates it against the selected agent's hardware capabilities (GPU count, VRAM per GPU, available disk), allocates a port from the atomic port allocation table, creates a `model_deployments` row in `pending` status, and sends a `deploy_model` command to the agent over WebSocket (F11) with the full vLLM configuration. Progress is streamed back via the agent's command progress reporting (F11) and log streaming (F12), which the dashboard displays in real-time through the `DeploymentLogViewer` and `GpuLoadingGraph` components.

The deployment wizard integrates with F5 (JWT auth middleware protects the deploy endpoint), F3 (`model_deployments` table tracks lifecycle state), F11 (agent command handler executes the actual deployment), F12 (log streaming shows real-time deployment progress), F18 (HF Hub browser provides model search and VRAM estimation), F20 (Docker container management), and F21 (resumable model download). The capacity calculator logic lives in `backend/app/services/capacity_calculator.py` and is also available as a standalone estimation endpoint at `POST /api/hub/estimate-vram` for pre-deployment planning (F18).

## Concrete Examples (Specification by Example)

### Example 1: Full Deploy — Mistral 7B on a Single A100-80G

**Step 1 — Select Model:**
- User searches for `"Mistral-7B-Instruct"` in the HF Hub browser (F18).
- Frontend calls `GET /api/hub/search?q=Mistral-7B-Instruct` (JSON:API).
- User selects `mistralai/Mistral-7B-Instruct-v0.3` from results.
- Wizard pre-fills `hf_model_id`, `model_name`, and estimated parameter count (7B).

**Step 2 — Select Agent:**
- Frontend calls `GET /api/agents?filter[status]=online` (JSON:API).
- Response includes agents with their `hardware_info` (GPU model, VRAM, count, disk).
- User selects agent `cyan-koala-42` (1x A100-80G, 512GB RAM, 1.5TB free disk).
- Wizard validates agent has sufficient VRAM for model.

**Step 3 — Configure vLLM:**
- User configures:
  - Tensor parallel size: 1 (single GPU)
  - Quantization: none (FP16)
  - Max model length: 32768
  - Max number of sequences: 256
  - GPU memory utilization: 0.9
  - KV cache dtype: `auto`
  - Enable prefix caching: true
  - Enforce eager mode: false
  - Served model name: `mistral-7b`

**Step 4 — Capacity Calculator:**
- Frontend calls `POST /api/hub/estimate-vram` with the config:
  ```json
  {
    "hf_model_id": "mistralai/Mistral-7B-Instruct-v0.3",
    "quantization": null,
    "max_model_len": 32768,
    "gpu_memory_utilization": 0.9,
    "dtype": "bfloat16"
  }
  ```
- Backend returns estimated VRAM requirement:
  ```json
  {
    "estimated_vram_gb": 14.8,
    "available_vram_gb": 72.0,
    "max_concurrent_full_context": 4,
    "max_concurrent_avg_context": 28,
    "kv_cache_budget_gb": 57.2,
    "feasible": true
  }
  ```
- Capacity calculator component shows: green checkmark, metric gauges for VRAM headroom, concurrent request estimates, and KV cache budget.

**Step 5 — Review and Deploy:**
- Review panel shows all selections as a read-only summary card:
  - Model: `mistralai/Mistral-7B-Instruct-v0.3`
  - Agent: `cyan-koala-42` (1× A100-80G)
  - Config: TP=1, FP16, max_len=32K, `gpu_mem_util=0.9`
  - Estimated VRAM: 14.8 GB / 72.0 GB available
- User clicks "Deploy".
- Frontend sends `POST /api/models/deploy` with JSON:API `POST` body:
  ```json
  {
    "data": {
      "type": "model-deployments",
      "attributes": {
        "agent_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "model_name": "mistral-7b",
        "hf_model_id": "mistralai/Mistral-7B-Instruct-v0.3",
        "config": {
          "tensor_parallel_size": 1,
          "pipeline_parallel_size": 1,
          "quantization": null,
          "max_model_len": 32768,
          "max_num_seqs": 256,
          "gpu_memory_utilization": 0.9,
          "kv_cache_dtype": "auto",
          "enable_prefix_caching": true,
          "enforce_eager": false,
          "served_model_name": "mistral-7b",
          "dtype": "bfloat16",
          "port": 8001
        }
      }
    }
  }
  ```
- Backend creates `model_deployments` row with status `pending`, sends WebSocket command `deploy_model` to agent, returns 202 Accepted:
  ```json
  {
    "data": {
      "id": "md-22222222-3333-4444-5555-666666666666",
      "type": "model-deployments",
      "attributes": {
        "model_name": "mistral-7b",
        "hf_model_id": "mistralai/Mistral-7B-Instruct-v0.3",
        "agent_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "status": "pending",
        "config": { ... },
        "created_at": "2026-07-01T14:30:00Z"
      }
    }
  }
  ```
- Frontend transitions to deployment progress view showing `DeploymentLogViewer` and `GpuLoadingGraph`, both connected to the WebSocket broadcast for the deployment.
- Progress timeline via WebSocket:
  1. `command_progress`: `downloading` 45% — "Downloading model weights... (2.4 GB / 5.3 GB)"
  2. `command_progress`: `downloading` 100% — "Download complete, verifying checksums..."
  3. `command_progress`: `starting` — "Creating Docker container with vLLM..."
  4. Agent log: `info` — "Container md-22222222... started on port 8001"
  5. `command_progress`: `running` — "Waiting for health check..."
  6. `command_progress`: `healthy` — "Model ready at http://localhost:8001/v1"
  7. `command_result`: status `success`, result includes `port: 8001`, `container_id: "abc123def456"`
- `model_deployments` row updated to status `healthy`. Model appears in running models list (F22).

### Example 2: Deployment Failed — Insufficient VRAM

**Step 4 — Capacity Calculator:**
- User attempts to deploy `Qwen/Qwen2.5-72B-Instruct` (72B parameters, FP16 ~144GB) to a single A100-80G (72GB usable VRAM with `gpu_mem_util=0.9`).
- Backend estimation endpoint returns:
  ```json
  {
    "estimated_vram_gb": 148.0,
    "available_vram_gb": 72.0,
    "feasible": false,
    "recommendations": [
      "Select a server with more VRAM (at least 160 GB total across GPUs)",
      "Enable quantization (FP8 reduces to ~74 GB, AWQ 4-bit reduces to ~38 GB)",
      "Reduce tensor parallel size and distribute across 2+ GPUs"
    ]
  }
  ```
- Capacity calculator shows: red exclamation icon, "Not enough VRAM" message, recommendation text.
- "Deploy" button is disabled. User cannot proceed to Step 5.
- User can navigate back to Step 3 and adjust config (enable FP8 quantization, reduce `max_model_len`) to try again.

### Example 3: Deployment Failed Midway — Token Expired

- User starts deployment of `meta-llama/Llama-3.1-8B-Instruct`.
- Agent begins downloading model weights from HuggingFace Hub.
- Partway through (47% progress), the download fails because the HF token has expired or is not set.
- Agent sends `command_progress`:
  ```json
  {
    "type": "command_progress",
    "command_id": "cmd_002",
    "status": "failed",
    "progress_pct": 47,
    "message": "Download failed: HTTP 401 - HuggingFace token expired or invalid"
  }
  ```
- Agent sends log entry: `error` — "Gated model meta-llama/Llama-3.1-8B-Instruct requires authentication."
- Backend updates `model_deployments.status` to `failed`, sets `error_message` to full error text.
- Frontend `DeploymentLogViewer` shows the error in red, the `GpuLoadingGraph` stops updating.
- The deployment view displays an error banner with: "Deployment failed — HuggingFace token expired" and two action buttons: "Retry with new token" (opens config step with token field pre-filled) and "Delete deployment" (cleanup).

### Example 4: Cancel Deployment Mid-Download

- User deploys `Qwen/Qwen2.5-7B-Instruct`. Agent is at 60% download progress.
- User clicks "Cancel" button in the deployment progress view.
- Frontend sends `POST /api/models/{id}/stop` (JSON:API).
- Backend sends WebSocket command `stop_deployment` to agent.
- Agent terminates the download, removes partial files, sends `command_result` with status `cancelled`.
- Backend updates `model_deployments.status` to `stopped`, frees port allocation.
- Frontend shows confirmation toast: "Deployment cancelled. Partial download cleaned up."

## Acceptance Criteria

- **ACF19-1: Five-step stepper with sequential validation** — The deploy page at `frontend/app/pages/dashboard/models/deploy.vue` renders a PrimeVue `Stepper` component with five distinct steps: (1) Select Model, (2) Select Agent, (3) Configure Parameters, (4) Capacity Estimate, (5) Review & Deploy. Each step validates its input before enabling the "Next" button. Step 1 requires a selected HF model ID (either from F18 search or manually pasted). Step 2 requires a selected online agent with sufficient VRAM. Step 3 requires all vLLM parameters to have valid values (positive integers for tensor/pipeline parallel, `max_model_len ≥ 1`, `gpu_memory_utilization` between 0.1 and 1.0). Step 4 displays the capacity estimate (green/yellow/red indicator). Step 5 shows a read-only summary. The user cannot skip steps or proceed with invalid input.

- **ACF19-2: Backend validates deployment feasibility before dispatching** — The `POST /api/models/deploy` endpoint (in `backend/app/api/models.py`) validates the request before creating a deployment record: the target agent must exist, be `online`, and have no concurrent deployment in progress (no other `model_deployments` row with status `downloading` or `starting` on the same agent). The backend checks estimated VRAM against available VRAM (hardware_info from `agents` table) and warns but does not reject when estimated VRAM exceeds 90% of available (the agent does the final validation). The port allocation table is consulted for an available port on the agent. Invalid requests return JSON:API 422 with specific error codes (`AGENT_OFFLINE`, `MODEL_IN_USE`, `INSUFFICIENT_VRAM`, `PORT_EXHAUSTION`).

- **ACF19-3: Capacity calculator provides actionable recommendations** — The `POST /api/hub/estimate-vram` endpoint (in `backend/app/services/capacity_calculator.py`) accepts a model ID and vLLM config (quantization, max_model_len, gpu_memory_utilization, dtype) and returns JSON:API `{"data": {"estimated_vram_gb": float, "available_vram_gb": float, "feasible": bool, "max_concurrent_full_context": int, "max_concurrent_avg_context": int, "kv_cache_budget_gb": float, "recommendations": [string]}}`. The VRAM estimate accounts for: model weights (parameter count × bytes per parameter based on dtype/quantization), KV cache overhead (2 × num_layers × num_heads × max_model_len × head_dim × bytes_per_elem), and vLLM framework overhead (~1-2 GB). When `feasible` is `false`, at least one recommendation string must be provided suggesting how to make the deployment feasible. The wizard's `CapacityCalculator.vue` component renders the feasible flag as a color-coded badge (green = feasible, yellow = marginal >90% VRAM, red = infeasible), a horizontal bar showing VRAM usage, and recommendation text in a PrimeVue `InlineMessage`.

- **ACF19-4: Deployment progress is streamed in real-time** — After the backend accepts the deployment request (HTTP 202), the frontend transitions to a deployment progress view that renders two live components: `DeploymentLogViewer.vue` (streaming agent logs, filtered to the current deployment's `command_id`, color-coded by log level) and `GpuLoadingGraph.vue` (real-time GPU utilization, VRAM usage, and temperature from the agent's WebSocket metric stream). Both components receive updates via the dashboard WebSocket (F16) — log entries are broadcast through the agent log stream (F12), and GPU metrics are broadcast through the metric stream (F9). The progress view displays the current `status` from `command_progress` messages (`downloading`, `starting`, `running`, `healthy`, `failed`) as a PrimeVue `ProgressBar` with percentage and status label. When status transitions to `healthy`, a success toast appears and a "View Model" button navigates to the model details page.

- **ACF19-5: Cancel or failure during deployment cleans up gracefully** — The deployment progress view includes a "Cancel" button visible only when status is `downloading` or `starting`. Clicking Cancel sends `POST /api/models/{id}/stop`, which the backend forwards as a `stop_deployment` WebSocket command. The agent terminates the download, removes partial model files from the HuggingFace cache, stops any partially-started container (if `starting`), sends `command_result` with status `cancelled`, and the backend updates `model_deployments.status` to `stopped`. If the deployment fails (agent reports `command_progress` with status `failed`), the `error_message` column on `model_deployments` is populated. The frontend displays the error message in a PrimeVue `InlineMessage` with `severity="error"`, the "Cancel" button is replaced with "Retry" (opens step 1 with pre-filled model ID) and "Delete" (stops deployment and removes the row). Manual cleanup (docker rm, port deallocation, partial file removal) always happens on the agent side regardless of cancel or failure.

- **ACF19-6: Deploy endpoint returns 202 and fires async command** — The `POST /api/models/deploy` endpoint returns HTTP 202 Accepted (not 201 Created) because the deployment is asynchronous. The response body contains the JSON:API resource with `status: "pending"`. The backend creates a `model_deployments` row before sending the WebSocket command, so the row exists even if the agent is unreachable. The backend sends the `deploy_model` command over WebSocket (F11) with the full configuration including `hf_model_id`, `huggingface_token` (if provided, masked in logs), all vLLM parameters, and the allocated port. If the agent's WebSocket is disconnected, the backend retries for up to 30 seconds with exponential backoff before marking the deployment as `failed` with error message "Agent unreachable: WebSocket connection not established."

- **ACF19-7: Port allocation is atomic and prevents conflicts** — The backend maintains a port allocation mechanism for each agent. When `POST /api/models/deploy` processes a request, it selects an available port from the agent's port range (default `8001`–`8999`) that is not currently in use by any active `model_deployments.row` (status `running` or `healthy`) on the same agent. The allocation is performed within a database transaction using `SELECT ... FOR UPDATE` on a dedicated `port_allocations` table or an advisory lock to prevent race conditions. If no ports are available, the endpoint returns JSON:API 422 with `code: "PORT_EXHAUSTION"` and `detail: "All ports on agent cyan-koala-42 are in use (max 999). Stop an existing deployment to free a port."`. Ports are freed when the deployment transitions to `stopped` or `failed` status. The allocated port is included in the WebSocket command payload and stored in `model_deployments.port`.

- **ACF19-8: Frontend persists wizard state on navigation and refresh** — If the user navigates away from the deploy wizard (e.g., to check an agent's dashboard) and returns, or refreshes the page, the wizard state (selected model, selected agent, vLLM config, current step) is preserved in a Pinia store (`frontend/stores/deployWizard.ts`) with `persistedState: true` (localStorage via VueUse `useStorage`). The stepper resumes at the last completed step. Wizard state is cleared when: the deploy completes (success or failure), the user cancels, or the user explicitly clicks "Start Over". A "Start Over" button is visible in the sidebar of the deploy wizard page at all times.

## Technical Notes

### Frontend File Map

- `frontend/app/pages/dashboard/models/deploy.vue` — Wizard container page. Uses PrimeVue `Stepper` with `StepperPanel` for each step. Orchestrates step transitions, mounts/unmounts step child components. Guards against una authenticated access via the `auth` middleware (F2/F5).
- `frontend/app/components/deployment/DeployWizard.vue` — Root wizard component containing the stepper, step content slots, and navigation buttons (Back / Next / Deploy / Cancel). Emits `deploy` event with full payload.
- `frontend/app/components/deployment/ModelConfigForm.vue` — Step 3 form. Renders PrimeVue `InputNumber`, `InputSwitch`, `Select`, and `InputText` for each vLLM parameter. Validates inputs inline. Emits `update:config` on change.
- `frontend/app/components/deployment/CapacityCalculator.vue` — Step 4 display. Calls `POST /api/hub/estimate-vram` when mounted (debounced 500ms after config changes). Renders VRAM bar chart, feasibility badge, concurrent request estimates, and recommendations list.
- `frontend/app/components/deployment/DeploymentLogViewer.vue` — Live log stream during deployment. WebSocket-connected, color-coded by level, auto-scroll with pause. Filters logs by `command_id` to show only deployment-related entries.
- `frontend/app/components/deployment/GpuLoadingGraph.vue` — Live GPU metrics during deployment. uPlot chart (real-time line) showing GPU util %, VRAM used, and GPU temp. Updates from WebSocket metric stream for the target agent.
- `frontend/stores/deployWizard.ts` — Pinia store. State: `step`, `selectedModel`, `selectedAgent`, `config`, `capacityEstimate`, `deploymentId`. Persisted to localStorage via `useStorage('deploy-wizard', ...)`. Actions: `setStep`, `setModel`, `setAgent`, `setConfig`, `reset`, `loadFromStorage`.
- `frontend/app/composables/useModels.ts` — Composables for model operations. Methods: `deployModel(payload)`, `stopModel(id)`, `restartModel(id)`, `getModel(id)`, `listModels(params)`.

### Backend File Map

- `backend/app/api/models.py` — Route handlers:
  - `POST /api/models/deploy` — Route handler. Validates request, checks agent availability, allocates port, creates `model_deployments` row (status `pending`), dispatches WebSocket command, returns 202.
  - `POST /api/models/{id}/stop` — Route handler. Stops/cancels a deployment.
  - `POST /api/models/{id}/restart` — Route handler. Restarts a healthy deployment.
  - `DELETE /api/models/{id}` — Route handler. Stops and removes a deployment.
  - `GET /api/models` — List deployments (JSON:API with pagination, filters: `status`, `agent_id`).
  - `GET /api/models/{id}` — Single deployment details.
  - `GET /api/models/{id}/logs` — Deployment-specific logs.
  - `POST /api/hub/estimate-vram` — VRAM estimation endpoint.
- `backend/app/services/model_manager.py` — Business logic. Handles deployment lifecycle: creation, validation, WebSocket command dispatch, port allocation/freeing, status transitions. Methods: `deploy_model()`, `stop_model()`, `restart_model()`, `delete_model()`, `handle_command_result()`.
- `backend/app/services/capacity_calculator.py` — Static VRAM estimation logic (no external API calls). Functions: `estimate_vram(model_id, config)`, `estimate_kv_cache_budget(config)`, `estimate_max_concurrency(vram_budget, config)`.
- `backend/app/models/model_deployment.py` — SQLAlchemy ORM model (defined in F3). Key columns: `id` (UUID), `workspace_id` (UUID FK), `agent_id` (UUID FK), `model_name`, `hf_model_id`, `status` (enum: `pending`, `downloading`, `starting`, `running`, `healthy`, `stopping`, `stopped`, `failed`), `docker_container_id`, `port`, `config` (JSONB), `error_message`, `deployed_at`, `stopped_at`, `created_at`, `updated_at`.

### Backend Endpoint: `POST /api/models/deploy`

**Request format (JSON:API):**
```json
{
  "data": {
    "type": "model-deployments",
    "attributes": {
      "agent_id": "uuid-string",
      "model_name": "mistral-7b",
      "hf_model_id": "mistralai/Mistral-7B-Instruct-v0.3",
      "huggingface_token": "hf_..." ,
      "config": {
        "tensor_parallel_size": 1,
        "pipeline_parallel_size": 1,
        "quantization": null,
        "max_model_len": 32768,
        "max_num_seqs": 256,
        "gpu_memory_utilization": 0.9,
        "kv_cache_dtype": "auto",
        "enable_prefix_caching": true,
        "enforce_eager": false,
        "served_model_name": "mistral-7b",
        "dtype": "bfloat16"
      }
    }
  }
}
```

**Response format (HTTP 202 Accepted):**
```json
{
  "data": {
    "id": "md-22222222-3333-4444-5555-666666666666",
    "type": "model-deployments",
    "attributes": {
      "agent_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "model_name": "mistral-7b",
      "hf_model_id": "mistralai/Mistral-7B-Instruct-v0.3",
      "status": "pending",
      "port": 8001,
      "config": { ... },
      "created_at": "2026-07-01T14:30:00Z"
    }
  }
}
```

**Error responses (JSON:API):**
- HTTP 422 `AGENT_OFFLINE` — `{"errors": [{"status": "422", "code": "AGENT_OFFLINE", "title": "Agent is offline", "detail": "Agent cyan-koala-42 has status 'offline' and cannot accept deployments."}]}`
- HTTP 422 `INSUFFICIENT_VRAM` — `{"errors": [{"status": "422", "code": "INSUFFICIENT_VRAM", "title": "Insufficient VRAM", "detail": "Estimated VRAM (148 GB) exceeds available VRAM (72 GB) on agent cyan-koala-42. Enable quantization or select a different agent."}]}`
- HTTP 422 `PORT_EXHAUSTION` — `{"errors": [{"status": "422", "code": "PORT_EXHAUSTION", "title": "No available ports", "detail": "All ports on agent cyan-koala-42 are in use. Maximum 999 deployments per server."}]}`
- HTTP 409 `DEPLOYMENT_IN_PROGRESS` — `{"errors": [{"status": "409", "code": "DEPLOYMENT_IN_PROGRESS", "title": "Deployment in progress", "detail": "Agent cyan-koala-42 already has a deployment in progress (status: downloading). Wait for completion before deploying another model."}]}`

### WebSocket Command: `deploy_model`

Sent from backend to agent (F11 format):
```json
{
  "type": "command",
  "command_id": "cmd_002",
  "command": "deploy_model",
  "params": {
    "deployment_id": "md-22222222-3333-4444-5555-666666666666",
    "model_id": "mistralai/Mistral-7B-Instruct-v0.3",
    "huggingface_token": "hf_...",
    "vllm_params": {
      "tensor_parallel_size": 1,
      "pipeline_parallel_size": 1,
      "quantization": null,
      "max_model_len": 32768,
      "max_num_seqs": 256,
      "gpu_memory_utilization": 0.9,
      "kv_cache_dtype": "auto",
      "enable_prefix_caching": true,
      "enforce_eager": false,
      "served_model_name": "mistral-7b",
      "dtype": "bfloat16",
      "port": 8001
    }
  }
}
```

### Status Transition Diagram

```
pending ──► downloading ──► starting ──► running ──► healthy
   │                            │            │
   │                            │            ├──► stopping ──► stopped
   │                            │            │
   │                            │            └──► failed
   │                            │
   │                            └──► failed
   │
   └──► failed (agent unreachable, validation error)

failed ──► pending (retry with new config)
stopped ──► pending (redeploy)
```

Status transitions are enforced at the service layer (`model_manager.py`). The model does not allow transitions from `healthy` directly to `pending`, nor from `failed` to `downloading`. All transitions are atomic and logged.

### Capacity Calculator Estimation Formula

The VRAM estimation in `backend/app/services/capacity_calculator.py` uses the following approach without calling external APIs:

1. **Model weights size** = parameter_count × bytes_per_param
   - FP32: 4 bytes/param
   - FP16/BF16: 2 bytes/param
   - FP8: 1 byte/param
   - INT4/AWQ/GPTQ: 0.5 bytes/param
2. **KV cache size** = 2 × num_hidden_layers × num_key_value_heads × head_dim × max_model_len × bytes_per_elem (FP16 default)
3. **Framework overhead**: 1.5 GB (empirical for vLLM)
4. **Total VRAM** = weights + KV cache + overhead
5. **VRAM budget** = total_agent_vram × gpu_memory_utilization
6. **Available for KV cache** = budget − weights − overhead
7. **Max concurrent at full context** = floor(available_for_kv / kv_cache_per_sequence)
8. **Max concurrent at avg context** = floor(available_for_kv / (kv_cache_per_sequence × target_avg_context_ratio))

The estimator does not know architecture-specific parameters (num_layers, num_heads) for arbitrary HF models. For models it cannot identify, it falls back to heuristics: layers = param_count_B × 8 (empirical), kv_heads = sqrt(hidden_size / 64). The result includes a `confidence: "low"` tag. A future improvement will download architecture metadata from the HF Hub API.

### Port Allocation Details

Port allocation uses an application-level advisory lock to prevent races:
```python
# backend/app/services/model_manager.py
async def allocate_port(agent_id: UUID) -> int:
    async with db_session.begin():
        # Advisory lock scoped to the agent
        await db_session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:agent_id))"),
            {"agent_id": str(agent_id)}
        )
        used_ports = await db_session.scalars(
            select(ModelDeployment.port).where(
                ModelDeployment.agent_id == agent_id,
                ModelDeployment.status.in_(["running", "healthy", "starting"])
            )
        )
        used_set = set(used_ports.all())
        for port in range(MIN_PORT, MAX_PORT + 1):
            if port not in used_set:
                return port
        raise PortExhaustionError(agent_id)
```

### Edge Cases

- **Concurrent deployments on same agent:** The backend rejects a second `POST /api/models/deploy` for the same agent if a deployment with status `downloading` or `starting` already exists. This is checked before the transaction to avoid wasted work.
- **Agent goes offline mid-deployment:** If the agent's WebSocket disconnects while a deployment is in progress (status `downloading` or `starting`), the backend starts a 5-minute grace period timer. If the agent does not reconnect within 5 minutes, the deployment is marked as `failed` with error "Agent disconnected during deployment." The port is freed. The user sees a failure toast and can retry.
- **Duplicate model names:** Two deployments on the same agent cannot share the same `served_model_name` (application-level enforced). Duplicate names for `model_name` across different agents are allowed.
- **Large model downloads:** The agent-side download (F21) supports resumable downloads via `huggingface_hub.snapshot_download` with `resume_download=True`. If the user cancels mid-download, partial files are cleaned up from the HF cache directory.
- **Wizard timeout:** If the user leaves the wizard open for more than 30 minutes, the capacity estimate is re-fetched from the backend (agents' hardware status may have changed — e.g., another deployment consumed VRAM). A stale estimate warning bar appears: "Estimates may be outdated. Recalculate before deploying."
- **HuggingFace token handling:** The `huggingface_token` field in the deploy payload is optional. If provided, the backend stores it in the `config` JSONB column (masked as `"hf_****..."` on read). The token is forwarded to the agent in the WebSocket command for authenticated model downloads. The token is never logged or exposed in responses after the initial deploy call.

### Integration Points

- **F2 (Frontend scaffolding):** The deploy wizard page at `frontend/app/pages/dashboard/models/deploy.vue` uses the dashboard layout, auth middleware, `useApi` composable, and PrimeVue components (Stepper, InputNumber, Select, InputSwitch, ProgressBar, InlineMessage, Toast, Message) scaffolded in F2. The pinia store `deployWizard.ts` follows the same pattern as `auth.ts` from F2.

- **F3 (Database schema):** The `model_deployments` table defined in F3 stores all deployment lifecycle state (`id` as UUID, `workspace_id` FK, `agent_id` FK, `status` as `deployment_status` enum, `config` as JSONB with full vLLM params). Port allocation logic reads/writes `model_deployments.port`. Deleting a workspace cascades to all its deployments via `ON DELETE CASCADE`.

- **F5 (Email/password auth):** All model deployment endpoints under `/api/models/*` are protected by the JWT auth middleware from F5. Unauthenticated requests return HTTP 401. The middleware also enforces role-based access (F33) — only `owner`, `admin`, and `member` roles can deploy; `viewer` gets 403.

- **F11 (Agent command handler):** The backend sends the `deploy_model` command over the agent's WebSocket connection (established in F7). The agent's command handler (F11) receives it, executes the deployment pipeline, and sends progress updates via `command_progress` and a final `command_result` message. The `command_id` field links all progress/result messages back to the deployment.

- **F12 (Agent log streaming):** The agent emits log entries during deployment (download progress, Docker commands, vLLM startup). These are pushed via HTTP POST to `POST /api/agents/{id}/logs` and broadcast to the dashboard via WebSocket (F16). The `DeploymentLogViewer.vue` component filters by `command_id` or a `deployment_id` tag to show only deployment-relevant logs.

- **F16 (WebSocket broadcast):** Both live GPU metrics (F9) and agent logs (F12) are broadcast from the backend to the frontend dashboard WebSocket. The `GpuLoadingGraph.vue` and `DeploymentLogViewer.vue` components subscribe to these streams, filtering by agent ID and (for logs) command ID. The 500ms client-side batching (F16) applies to both streams.

- **F18 (HF Hub browser):** The wizard's Step 1 embeds the HF Hub search from F18. The `POST /api/hub/estimate-vram` endpoint (shared between F18 and F19) provides VRAM estimation. The model detail card from F18 is reused in the wizard's review step.

- **F20 (Docker container management):** The agent-side deployment (triggered by the WebSocket command) uses Docker to run the vLLM container. The `docker_manager.py` on the agent handles `docker run` with `--gpus` device reservation, port mapping, volume mounts, and resource limits. Container lifecycle events (start, stop, health check) are streamed back as logs.

- **F21 (Resumable model download):** The agent's `model_downloader.py` handles downloading model weights from HuggingFace Hub with `snapshot_download(resume_download=True)` and checksum verification. Download progress (bytes downloaded vs total) is reported back via `command_progress` messages.

- **F22 (Running model management):** Once a deployment reaches `healthy` status via this wizard, it appears in the running models list (F22). The model can then be stopped, restarted, or deleted through the F22 management UI. The `model_manager.py` service is shared between F19 and F22.

## Depends on: F2, F5, F18
