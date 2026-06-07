# F21 — Resumable Model Download with Streaming Progress

**Status:** Draft  
**Version:** 1.0  
**Last Updated:** 2026-06-07  

---

## 1. Objective

Enable the backend to download third-party model artifacts (GGUF, safetensors, etc.) to the orchestrator host with **resumability**, **streaming progress**, **timeout handling**, and **disk-space pre‑check**.  

The client triggers a download and receives a stream of `download_progress` WebSocket events (or SSE chunks) until the artifact is fully written to disk, or a terminal error occurs. If a previous download was interrupted (connection drop, server restart, graceful timeout) the system SHALL resume from the last cached byte range without re‑fetching completed segments.

---

## 2. Acceptance Criteria

### ACF21-1 — Initiate a resumable download  
**Priority:** P0  
**Actor:** Authenticated Client → Backend → Orchestrator  

The system SHALL expose a POST endpoint (or WebSocket message) that accepts a model identifier (e.g. `"hf:meta-llama/Llama-3.1-70B"`), a target artifact path, and an optional Hugging Face token.  

- A **download job** SHALL be created and persisted immediately with status `"PENDING"`.  
- The job SHALL include a unique `job_id`, the source URL, the target file path, the total byte size (if known), and a `created_at` timestamp.  
- If a **disk-space pre‑check** determines that the target mount has fewer free bytes than the artifact needs (plus a 10 % headroom buffer), the system SHALL reject the download with a `DISK_SPACE_ERROR` and **no bytes** SHALL be transferred.  
- On acceptance, the status SHALL transition to `"DOWNLOADING"` and the download SHALL begin immediately on the orchestrator.  

### ACF21-2 — Stream progress events to the client  
**Priority:** P0  
**Actor:** Orchestrator → Backend → Client  

While the download is in flight the orchestrator SHALL emit progress events at least every **500 ms** or every **10 MB**, whichever comes first.  

Each event SHALL contain:  

- `job_id`  
- `status`: `"DOWNLOADING"`  
- `bytes_downloaded` (integer)  
- `total_bytes` (integer, or `null` if unknown)  
- `speed_bytes_per_sec` (float)  
- `estimated_seconds_remaining` (integer, or `null`)  
- `timestamp` (ISO 8601)  

The backend SHALL forward these events to the authenticated client via the negotiated channel (WebSocket or SSE).  

### ACF21-3 — Resume after interruption  
**Priority:** P0  
**Actor:** Orchestrator → Hugging Face / Remote Storage  

If an **interrupted download job** (status `"INTERRUPTED"` or `"TIMEOUT"`) is resumed via the same POST endpoint with a `resume_job_id` parameter, the orchestrator SHALL:  

1. Verify the partial file exists and has a size matching the recorded `bytes_downloaded`.  
2. Issue an HTTP **Range** request with `Range: bytes=<last_byte+1>-` to the source.  
3. Append new bytes to the partial file (do NOT overwrite).  
4. Continue emitting progress events from the resumed byte offset.  

If the partial file is missing or corrupted the system SHALL fall back to a full re‑download and log a warning.  

### ACF21-4 — Graceful timeout and cleanup  
**Priority:** P1  
**Actor:** Orchestrator  

The system SHALL enforce a configurable per‑download timeout (default: **30 minutes**).  

- When the timeout fires:  
  1. The download process SHALL be terminated.  
  2. The job status SHALL be set to `"TIMEOUT"`.  
  3. Any bytes already received SHALL be kept in the partial file (for later resume).  
  4. A `timeout` terminal event SHALL be sent to the client.  
- The system SHALL NOT delete partial files on timeout; cleanup is an explicit client or admin action.  

---

## 3. Concrete Examples

### Example 1 — Successful download of Mistral 7B

```
Client:   POST /api/agents/download    
          { "model_id": "hf:mistralai/Mistral-7B-Instruct-v0.3",
            "artifact": "model-q4_k_m.gguf",
            "hf_token": null }

Backend:  201 Created
          { "job_id": "dl_mistral7b_001",
            "status": "PENDING",
            "created_at": "2026-06-07T10:00:00Z" }

[disk-space pre‑check passes → status → "DOWNLOADING"]

Orchestrator emits 10 progress messages over ~45 s:

  { "job_id": "dl_mistral7b_001", "status": "DOWNLOADING",
    "bytes_downloaded": 4194304000, "total_bytes": 4194304000,
    "speed_bytes_per_sec": 95420000.0,
    "estimated_seconds_remaining": 0,
    "timestamp": "2026-06-07T10:00:47Z" }

Client receives final event:

  { "job_id": "dl_mistral7b_001", "status": "COMPLETED",
    "bytes_downloaded": 4194304000, "total_bytes": 4194304000,
    "timestamp": "2026-06-07T10:00:48Z",
    "file_path": "/data/models/mistral-7b/model-q4_k_m.gguf" }
```

### Example 2 — Interrupted download resumed

```
1. Initial attempt — interrupted at 72 %

  Client:   POST /api/agents/download
            { "model_id": "hf:meta-llama/Llama-3.1-70B",
              "artifact": "model-q4_k_m.gguf",
              "hf_token": "hf_xxxx" }

  [Progress reaches 72 % → connection drops]

2. Client reconnects and resumes:

  Client:   POST /api/agents/download
            { "model_id": "hf:meta-llama/Llama-3.1-70B",
              "artifact": "model-q4_k_m.gguf",
              "hf_token": "hf_xxxx",
              "resume_job_id": "dl_llama70b_001" }

  Backend:  200 OK
            { "job_id": "dl_llama70b_001",
              "status": "DOWNLOADING",
              "resumed_from_bytes": 3023659008 }

  Orchestrator issues Range request → appends remaining 28 %
  Progress events start at 72 % and reach 100 %.

  Final event:

  { "job_id": "dl_llama70b_001", "status": "COMPLETED",
    "bytes_downloaded": 4198400000, "total_bytes": 4198400000,
    "timestamp": "2026-06-07T11:15:00Z",
    "file_path": "/data/models/llama-3.1-70b/model-q4_k_m.gguf" }
```

### Example 3 — Timeout with partial result

```
  Client:   POST /api/agents/download
            { "model_id": "hf:mistralai/Mixtral-8x22B-Instruct-v0.1",
              "artifact": "model-q4_k_m.gguf",
              "hf_token": null }

  [Slow network – only 34 % downloaded in 30 min → timeout]

  Terminal event:

  { "job_id": "dl_mixtral8x22_001",
    "status": "TIMEOUT",
    "partial_result": {
      "bytes_downloaded": 5872025600,
      "total_bytes": 17239900160,
      "percent_complete": 34.0,
      "partial_file_path": "/data/models/mixtral-8x22b/partial_model-q4_k_m.gguf"
    },
    "timestamp": "2026-06-07T14:30:00Z" }

  Client can later resume with `resume_job_id: "dl_mixtral8x22_001"`.
```

### Example 4 — Disk space rejection

```
  Client:   POST /api/agents/download
            { "model_id": "hf:meta-llama/Llama-3.1-405B",
              "artifact": "model-q4_k_m.gguf",
              "hf_token": "hf_xxxx" }

  Backend:  507 Insufficient Storage
            { "job_id": "dl_llama405b_001",
              "status": "DISK_SPACE_ERROR",
              "error": "Target mount /data/models has 450 GB free; "
                       "artifact requires 820 GB (with 10 % headroom).",
              "created_at": "2026-06-07T09:00:00Z" }

  No bytes were transferred.
```

---

## 4. Integration Points

| Feature | Relationship |
|---|---|
| **F11 — Model Catalog** | Provides the source URL, artifact list, and file sizes for each model. F21 reads the catalog to construct download requests. |
| **F13 — Agent Execution** | After a download completes, the agent execution engine (F13) can reference `file_path` from the job record. |
| **F18 — WebSocket Broker** | Carries the `download_progress` events from orchestrator → backend → client. The broker SHALL maintain a channel per `job_id`. |
| **F19 — SSE Channel** | Alternative delivery mechanism for progress events when WebSocket is unavailable. |
| **F20 — Execution Engine** | Inspects download job status before launching a model; declined if status is not `"COMPLETED"`. |

---

## 5. Affected Source Files

| File | Role |
|---|---|
| `modelprism-agent/modelprism_agent/manager/model_downloader.py` | New — orchestrator-side download orchestration, Range‑request resume, progress callbacks. |
| `backend/app/api/agents.py` | New or extended route `POST /api/agents/download`. |
| `backend/app/models/download_job.py` | New — Pydantic / SQLAlchemy model for download jobs. |
| `backend/app/services/download_manager.py` | New — job lifecycle, progress fan‑out to WebSocket/SSE, timeout watch. |
| `backend/app/services/disk_checker.py` | New — pre‑flight disk‑space check against the target mount. |
