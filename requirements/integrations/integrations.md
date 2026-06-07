# Integrations

> **Status:** Planning · **Last updated:** 2026-06-07

This document covers every external service and system ModelPrism integrates with. Each section includes setup steps, configuration reference, authentication methods, error handling, and fallback behaviour.

---

## Table of Contents

1. [HuggingFace Hub](#1-huggingface-hub)
2. [Docker Engine](#2-docker-engine)
3. [NVIDIA](#3-nvidia)
4. [Stripe (Cloud Only)](#4-stripe-cloud-only)
5. [Redis](#5-redis)
6. [Systemd](#6-systemd)
7. [PostgreSQL](#7-postgresql)

---

## 1. HuggingFace Hub

The HuggingFace Hub integration provides model discovery, metadata retrieval, and model weight downloads with resumability, checksum verification, and progress reporting.

### 1.1 Setup

```bash
pip install "huggingface_hub>=0.32.0"
```

As of `huggingface_hub` 0.32.0, the `hf_xet` binding (chunk-based deduplication, faster downloads) is included automatically. The legacy `hf_transfer` is deprecated and should not be installed.

### 1.2 Authentication

```python
from huggingface_hub import HfApi, login

# Token-based (preferred for automation)
login(token="hf_...")

# Or set via environment variable
# HF_TOKEN=hf_...
```

| Method | Credential | Scope |
|---|---|---|
| `login(token)` | User access token | Read/write |
| `HF_TOKEN` env var | User access token | Read/write |
| `hf_***` in config file | User access token | Read/write |
| No token | — | Public repos only, rate-limited |

### 1.3 Search API

```python
from huggingface_hub import HfApi

api = HfApi()
models = api.list_models(
    task="text-generation",
    library="transformers",
    sort="downloads",
    direction=-1,
    limit=50,
)
```

**Key parameters:**

| Parameter | Type | Description |
|---|---|---|
| `task` | `str` | Filter by task (`text-generation`, `image-classification`, …) |
| `library` | `str` | Filter by library (`transformers`, `diffusers`, `safetensors`, …) |
| `search` | `str` | Free-text search across model names and descriptions |
| `sort` | `str` | Sort field: `downloads`, `likes`, `createdAt`, `lastModified` |
| `direction` | `int` | `-1` descending, `1` ascending |
| `limit` | `int` | Max results per page (max 100) |
| `author` | `str` | Filter by author/ organisation |

### 1.4 Model Metadata

```python
from huggingface_hub import HfApi

api = HfApi()
info = api.model_info("meta-llama/Llama-3.1-8B")

info.id           # "meta-llama/Llama-3.1-8B"
info.sha          # Commit hash
info.pipeline_tag # "text-generation"
info.card_data    # YAML frontmatter as dict
info.siblings     # List of file metadata (rfilename, size, sha256)
```

**Error handling:**

| Scenario | Behaviour |
|---|---|
| Model not found | `HTTPError 404` — catch and surface to user |
| Private model without token | `HTTPError 401` — prompt for authentication |
| Rate limited | `HTTPError 429` — retry with exponential backoff (see `huggingface_hub.utils.BackoffStrategy`) |
| Network failure | `RequestException` — retry up to 3 times, then surface |

### 1.5 Snapshot Download (Resumable)

```python
from huggingface_hub import snapshot_download

path = snapshot_download(
    repo_id="meta-llama/Llama-3.1-8B",
    revision="main",
    allow_patterns=["*.safetensors", "*.json", "tokenizer*"],
    ignore_patterns=["*.pt", "*.bin"],
    cache_dir="/data/hf-cache",
    local_dir="/data/models/llama-3.1-8b",
    resume=True,
)
```

**Resumability:**

- `snapshot_download` is resumable by default — partially downloaded files resume from the last received byte via HTTP range requests.
- A `.cache/huggingface/` metadata directory inside `local_dir` tracks what has been downloaded. If the metadata is missing only the affected files are re-downloaded.
- `force_download=True` bypasses the cache and re-downloads everything.

**Checksum verification:**

- Every downloaded file is verified against the SHA256 hash published in the repo's file metadata (`info.siblings[n].sha256`).
- Verification runs automatically after each file completes. A mismatch raises `CorruptDownloadError`.
- On checksum failure the partial file is removed and the download retried once automatically.

**Speed:**

- `hf_xet` (bundled in 0.32.0+) provides chunk-level deduplication and parallel download of content-addressed blocks — this is the recommended path.
- Concurrency is controlled by `HF_HUB_DOWNLOAD_TIMEOUT` (default 10 s) and the number of parallel workers (autotuned, but can be set via `hf_hub_download(..., max_workers=8)`).

### 1.6 Progress Streaming via WebSocket

ModelPrism streams download progress to the client over WebSocket using the `huggingface_hub` callback mechanism:

```python
from huggingface_hub import HfApi, snapshot_download
import json

class ProgressStreamer:
    def __init__(self, websocket):
        self.ws = websocket
        self.total = 0
        self.completed = 0

    def __call__(self, file_name, completed, total, status):
        self.ws.send_text(json.dumps({
            "event": "download_progress",
            "file": file_name,
            "completed": completed,
            "total": total,
            "status": status,  # "downloading", "completed", "failed"
        }))

# Usage
snapshot_download(
    repo_id="...",
    resume=True,
    # Note: huggingface_hub supports callbacks via HfApi
    # and the download manager emits per-file progress.
)
```

The service wraps this in an async generator:

```python
async def stream_download(ws: WebSocket, repo_id: str):
    try:
        path = await asyncio.to_thread(
            snapshot_download,
            repo_id=repo_id,
            # custom progress reporter wired via env or hook
        )
        await ws.send_text(json.dumps({"event": "done", "path": path}))
    except Exception as exc:
        await ws.send_text(json.dumps({"event": "error", "message": str(exc)}))
```

### 1.7 Error Handling & Fallback

| Error | Handling |
|---|---|
| `CorruptDownloadError` | Re-download corrupted file, retry once |
| `HTTPError 429` | Exponential backoff (base 2 s, max 60 s) |
| `HTTPError 401/403` | Surface auth error, request new token |
| `RepositoryNotFoundError` | Return 404 to client |
| `RevisionNotFoundError` | Return 404 to client |
| Disk full | Catch, clean cache files, surface to client |
| Network timeout | Retry up to 3 times, fall back to sequential download |

---

## 2. Docker Engine

ModelPrism uses the Docker Engine to run inference containers with GPU access, resource limits, health checks, and streaming log collection.

### 2.1 Setup

```bash
pip install docker>=7.0.0
```

The Docker daemon must be accessible:

- **Linux:** `/var/run/docker.sock` (default)
- **Rootless:** `$XDG_RUNTIME_DIR/docker.sock`
- **Remote:** `tcp://<host>:2375` (TLS recommended)

ModelPrism reads the socket path from config; default is `unix:///var/run/docker.sock`.

### 2.2 Authentication

```python
import docker

# Local socket (no auth)
client = docker.from_env()

# TLS-enabled remote
client = docker.DockerClient(
    base_url="tcp://docker.example.com:2376",
    tls=docker.tls.TLSConfig(
        client_cert=("/path/to/cert.pem", "/path/to/key.pem")
    ),
)

# Registry auth (for private images)
client.login(username="...", password="...", registry="ghcr.io")
```

| Method | Where |
|---|---|
| Unix socket | Local (default) |
| TCP + TLS | Remote daemon |
| Registry login | Private images (ghcr.io, Docker Hub, …) |

### 2.3 Container Create with GPU Device Reservation

```python
from docker.types import DeviceRequest

container = client.containers.create(
    image="modelprism/inference:latest",
    command=["python", "run.py"],
    
    # ── GPU reservation ──────────────────────────────────
    device_requests=[
        DeviceRequest(
            count=-1,                # All GPUs (-1). Use 1, 2, … for specific count.
            capabilities=[["gpu"]],  # Request GPU capability.
            options={"visible-devices": "0,1"},  # NVIDIA_VISIBLE_DEVICES equivalent.
        )
    ],
    
    # ── Port allocation ──────────────────────────────────
    ports={
        "8000/tcp": ("0.0.0.0", 0),  # Dynamic host port
        "8001/udp": None,            # Also dynamic
        "8080/tcp": 30080,           # Fixed host port
    },
    
    # ── Health check ─────────────────────────────────────
    healthcheck={
        "test": ["CMD-SHELL", "curl -sf http://localhost:8000/health || exit 1"],
        "interval": 30_000_000_000,     # 30 s (nanoseconds)
        "timeout": 10_000_000_000,      # 10 s
        "retries": 3,
        "start_period": 60_000_000_000, # 60 s grace period
    },
    
    # ── Resource limits ───────────────────────────────────
    mem_limit="16g",
    mem_reservation="8g",              # Soft limit
    memswap_limit="16g",               # No swap (equal to mem_limit)
    nano_cpus=4_000_000_000,           # 4 CPUs
    cpu_shares=1024,                   # Relative weight
    
    # ── Other ────────────────────────────────────────────
    name=f"modelprism-{job_id}",
    detach=True,
    restart_policy={"Name": "no"},
    network="modelprism-net",
    volumes={
        "/data/models": {"bind": "/models", "mode": "ro"},
        "/data/output": {"bind": "/output", "mode": "rw"},
    },
    environment={
        "MODEL_ID": repo_id,
        "HF_TOKEN": hf_token,
        "LOG_LEVEL": "info",
    },
    auto_remove=False,  # Keep stopped containers for log inspection
)
container.start()
```

### 2.4 Image Pull with Progress

```python
for line in client.api.pull(repository="modelprism/inference", tag="latest",
                             stream=True, decode=True):
    if "progress" in line:
        # Stream progress to WebSocket
        await ws.send_json({
            "event": "image_pull_progress",
            "id": line.get("id"),       # Layer hash
            "status": line.get("status"),
            "progress": line.get("progress"),
        })
    elif "error" in line:
        raise RuntimeError(line["error"])
```

### 2.5 Container Logs Streaming

```python
container = client.containers.get(container_id)

# Synchronous streaming (run in thread)
for log_line in container.logs(stream=True, follow=True, tail=100):
    # log_line is bytes — decode to str
    line = log_line.decode("utf-8", errors="replace").rstrip("\n")
    await ws.send_json({"event": "log", "line": line})

# Alternatively, use the raw API for multiplexed streams:
for chunk in container.attach(stream=True, logs=True, stdout=True, stderr=True):
    ...
```

### 2.6 Resource Limits Reference

| Parameter | Type | Example | Description |
|---|---|---|---|
| `mem_limit` | `str` | `"16g"` | Hard memory limit |
| `mem_reservation` | `str` | `"8g"` | Soft memory reservation |
| `memswap_limit` | `str` | `"16g"` | Total memory + swap (equal = no swap) |
| `nano_cpus` | `int` | `4_000_000_000` | CPU quota in nanocores |
| `cpu_shares` | `int` | `1024` | Relative CPU weight |
| `pids_limit` | `int` | `512` | Max PIDs in container |
| `ulimits` | `list[Ulimit]` | `[Ulimit(name="nofile", soft=65535, hard=65535)]` | POSIX ulimits |

### 2.7 Error Handling & Fallback

| Error | Handling |
|---|---|
| Docker daemon unreachable | Retry with backoff; surface "Docker not available" |
| GPU not available | Fall back to CPU; emit warning |
| Image not found | Pull first; if pull fails, surface to user |
| Port conflict | Pick next available port; log conflict |
| OOM killed | Detect via container state `OOMKilled`; surface to user |
| Container exit non-zero | Capture and stream exit code + stderr |
| Disk space for images | Check `docker.system_df()` before pull |
| Registry auth failure | Surface credential error |

---

## 3. NVIDIA

The NVIDIA integration covers GPU discovery, driver compatibility checks, container-toolkit setup, and live GPU metric collection.

### 3.1 Setup

```bash
# ── NVIDIA drivers (Linux) ───────────────────────────────
# CUDA 12.0+ requires driver >= 525.60.13
wget https://developer.download.nvidia.com/compute/cuda/repos/.../cuda-keyring.deb
sudo dpkg -i cuda-keyring.deb
sudo apt-get update
sudo apt-get install -y cuda-drivers

# ── NVIDIA Container Toolkit ────────────────────────────
# Required for GPU access inside Docker containers
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
    sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -sL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker runtime (nvidia-ctk)
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify
docker run --rm --gpus all nvidia/cuda:12.4-base nvidia-smi
```

**Prerequisites:**

| Component | Minimum Version |
|---|---|
| NVIDIA Driver | 525.60.13 (CUDA 12.0) |
| CUDA | 12.0+ |
| Docker | 19.03+ |
| nvidia-container-toolkit | 1.14+ |

### 3.2 nvidia-smi Parsing (GPU Metrics)

ModelPrism parses `nvidia-smi` JSON output to collect real-time GPU metrics:

```python
import subprocess
import json

def get_gpu_metrics() -> list[dict]:
    """Return per-GPU metrics."""
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,temperature.gpu,utilization.gpu,"
            "memory.total,memory.used,memory.free,power.draw,"
            "clocks.current.graphics,clocks.current.mem",
            "--format=json",
            "--id=0,1",  # Comma-separated list, omit for all
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    data = json.loads(result.stdout)
    return data.get("gpu", [])  # List of GPU dicts
```

**Fields available:**

| Field | Unit | Description |
|---|---|---|
| `index` | — | GPU index (0, 1, …) |
| `name` | — | GPU product name |
| `temperature.gpu` | °C | Core temperature |
| `utilization.gpu` | % | GPU core utilisation |
| `memory.total` | MiB | Total VRAM |
| `memory.used` | MiB | Used VRAM |
| `memory.free` | MiB | Free VRAM |
| `power.draw` | W | Instantaneous power draw |
| `clocks.current.graphics` | MHz | Graphics clock speed |
| `clocks.current.mem` | MHz | Memory clock speed |

### 3.3 nvtop (Loading Graph)

For interactive GPU process inspection:

```bash
# Install
sudo apt-get install -y nvtop

# ModelPrism can invoke nvtop in headless CSV mode for process-level data:
nvtop --print-stats
```

ModelPrism uses this primarily for diagnostic endpoints — not for real-time metrics (which use `nvidia-smi`).

### 3.4 Driver Compatibility Check

```python
def check_cuda_compatibility() -> dict:
    """Verify CUDA driver and toolkit compatibility."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version,compute_cap",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stdout.strip().split("\n")
        gpus = []
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            driver_version = parts[0]
            compute_cap = parts[1] if len(parts) > 1 else ""

            gpus.append({
                "driver_version": driver_version,
                "compute_capability": compute_cap,
                "cuda_compatible": version_tuple(driver_version) >= (525, 60, 13),
            })

        return {"gpus": gpus, "count": len(gpus), "toolkit_installed": _toolkit_installed()}
    except FileNotFoundError:
        return {"gpus": [], "count": 0, "error": "nvidia-smi not found"}
    except subprocess.TimeoutExpired:
        return {"gpus": [], "count": 0, "error": "nvidia-smi timed out"}
```

### 3.5 Error Handling & Fallback

| Error | Handling |
|---|---|
| No NVIDIA driver | Return empty GPU list; agent runs CPU-only |
| `nvidia-smi` not found | Surface install instructions |
| Driver < 525.60.13 | Emit upgrade warning; CPU fallback |
| nvidia-container-toolkit not installed | Agent can still use host GPU; Docker GPU requires it |
| `nvidia-ctk` not in PATH | Surface setup instructions |
| GPU ECC error | `nvidia-smi` reports XID; surface to user |
| GPU memory exhaustion | Detect in container (`OOMKilled`) or via `nvidia-smi`; suggest smaller model |

---

## 4. Stripe (Cloud Only)

Stripe is used for metered billing, payment processing, invoice generation, and payment method management. This integration is **only active in the cloud-hosted version** of ModelPrism — never in self-hosted/on-prem deployments.

### 4.1 Setup

```bash
pip install "stripe>=8.0.0"
```

```python
import stripe

stripe.api_key = "sk_live_..."
# Or from environment:
# stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
```

### 4.2 Configuration

| Variable | Description |
|---|---|
| `STRIPE_SECRET_KEY` | Secret API key (live or test) |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret |
| `STRIPE_PRICE_ID` | Price ID for the metered plan |
| `STRIPE_TAX_RATE` | Default tax rate ID (optional) |

### 4.3 Metered Billing

ModelPrism bills by usage — e.g., API calls, tokens processed, or GPU-hours.

```python
# Report usage (backend service)
stripe.billing.MeterEvent.create(
    event_name="model_inference_tokens",
    payload={
        "value": 15000,
        "stripe_customer_id": cus.id,
    },
    timestamp=int(time.time()),
)

# Timestamped batch usage
stripe.billing.MeterEventBatch.create(
    events=[
        {
            "event_name": "model_inference_tokens",
            "payload": {"value": 5000, "stripe_customer_id": "cus_..."},
            "timestamp": int(time.time()) - 300,
        },
    ],
)
```

Meter events are aggregated hourly by Stripe and applied to the next invoice.

### 4.4 Checkout Sessions

```python
session = stripe.checkout.Session.create(
    mode="subscription",
    customer=customer.id,
    line_items=[
        {
            "price": "price_...",
            "quantity": 1,
        },
    ],
    subscription_data={
        "trial_period_days": 7,
    },
    success_url="https://modelprism.com/billing/success?session_id={CHECKOUT_SESSION_ID}",
    cancel_url="https://modelprism.com/billing/cancel",
)

# Redirect user to session.url
redirect(session.url)
```

### 4.5 Webhook Idempotency

```python
from flask import Blueprint, request, jsonify

webhook = Blueprint("stripe_webhook", __name__)

@webhook.route("/stripe/webhook", methods=["POST"])
def handle_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ["STRIPE_WEBHOOK_SECRET"]
        )
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    # Idempotency: check event.id in DB
    if db.events.exists(event.id):
        return jsonify({"status": "already_processed"}), 200

    handler = {
        "invoice.paid": on_invoice_paid,
        "invoice.payment_failed": on_invoice_payment_failed,
        "customer.subscription.deleted": on_subscription_deleted,
        "customer.subscription.updated": on_subscription_updated,
        "billing.meter.error_report_triggered": on_meter_error,
    }.get(event.type)

    if handler:
        handler(event.data.object)

    db.events.record(event.id)  # Mark processed
    return jsonify({"status": "ok"}), 200
```

**Idempotency key:** Stripe automatically retries webhooks. Always deduplicate by storing `event.id` in PostgreSQL with a unique constraint.

### 4.6 Invoice Generation

Invoices are generated automatically by Stripe for subscription plans. ModelPrism retrieves and presents them:

```python
invoices = stripe.Invoice.list(customer="cus_...", limit=10)
for inv in invoices.auto_paging_iter():
    print(inv.id, inv.status, inv.total, inv.period_start, inv.period_end)
```

Manual invoice generation:

```python
invoice = stripe.Invoice.create(
    customer="cus_...",
    auto_advance=True,  # Auto-finalize and send
    collection_method="charge_automatically",
)
```

### 4.7 Payment Method Management

```python
# List saved payment methods
methods = stripe.PaymentMethod.list(
    customer="cus_...",
    type="card",
)

# Attach a new payment method
stripe.PaymentMethod.attach("pm_...", customer="cus_...")

# Set default payment method for subscription
stripe.Subscription.modify(
    "sub_...",
    default_payment_method="pm_...",
)

# Detach (delete) a payment method
stripe.PaymentMethod.detach("pm_...")
```

### 4.8 Error Handling & Fallback

| Error | Handling |
|---|---|
| `stripe.error.CardError` | Decline reason surfaced to client |
| `stripe.error.RateLimitError` | Retry with exponential backoff |
| `stripe.error.InvalidRequestError` | Log, surface to operator |
| `stripe.error.AuthenticationError` | Invalid key — alert operator |
| `stripe.error.APIConnectionError` | Retry up to 3 times |
| Webhook signature mismatch | Log and return 400 |
| Meter event failure | Queue event for retry; batch resend |

**Fallback:** If Stripe is unreachable for billing operations, ModelPriss queues the event and retries. Usage is still served — billing is eventually consistent.

---

## 5. Redis

Redis handles rate limiting (sliding window), WebSocket pub/sub messaging, caching, and session storage.

### 5.1 Setup

```bash
pip install "redis[hiredis]>=5.0.0"
```

```python
import redis.asyncio as aioredis

redis = aioredis.from_url(
    "redis://localhost:6379/0",
    encoding="utf-8",
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=3,
    retry_on_timeout=True,
    health_check_interval=30,
)
```

### 5.2 Configuration

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Connection URL |
| `REDIS_PASSWORD` | — | Optional password |
| `REDIS_SOCKET_TIMEOUT` | `5` | Socket timeout (seconds) |
| `REDIS_RETRY_ON_TIMEOUT` | `true` | Retry on timeout |

### 5.3 Rate Limiting (Sliding Window)

```python
import time
from typing import Optional

class SlidingWindowRateLimiter:
    """Sliding window log rate limiter backed by Redis sorted sets."""

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def check(
        self,
        key: str,          # e.g. "ratelimit:user:{user_id}:api"
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]: # (allowed, current_count)
        now = time.time()
        window_start = now - window_seconds

        pipe = self.redis.pipeline(transaction=True)
        pipe.zremrangebyscore(key, 0, window_start)   # Remove expired
        pipe.zcard(key)                                 # Count remaining
        pipe.zadd(key, {str(now): now})                 # Add current
        pipe.expire(key, window_seconds)                # TTL
        results = await pipe.execute()

        current_count = results[1]  # zcard result
        if current_count > max_requests:
            return False, current_count

        return True, current_count

limiter = SlidingWindowRateLimiter(redis)

# Usage
allowed, count = await limiter.check(
    key=f"ratelimit:user:{user_id}:inference",
    max_requests=100,
    window_seconds=60,
)
if not allowed:
    raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

### 5.4 WebSocket Pub/Sub

```python
# ── Publisher (e.g., inference job completes) ──
async def publish_job_event(job_id: str, event: str, data: dict):
    await redis.publish(
        f"job:{job_id}",
        json.dumps({"event": event, "data": data}),
    )

# ── Subscriber (WebSocket handler) ──
async def listen_for_job_events(ws: WebSocket, job_id: str):
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"job:{job_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])
                payload = json.loads(message["data"])
                if payload.get("event") in ("done", "failed"):
                    break
    finally:
        await pubsub.unsubscribe(f"job:{job_id}")
        await pubsub.close()
```

### 5.5 Caching

```python
# ── Write-through ──
await redis.setex(f"model:meta:{model_id}", 3600, json.dumps(metadata))

# ── Read-through ──
cached = await redis.get(f"model:meta:{model_id}")
if cached:
    return json.loads(cached)

# Fetch from source, then cache
metadata = await fetch_metadata(model_id)
await redis.setex(f"model:meta:{model_id}", 3600, json.dumps(metadata))
return metadata
```

**Cache key conventions:**

| Pattern | TTL | Purpose |
|---|---|---|
| `model:meta:{id}` | 1 h | Model metadata from HuggingFace |
| `model:list:{query_hash}` | 5 min | Search results |
| `user:session:{id}` | 24 h | Session data |
| `user:api_key:{key}` | 1 h | API key → user mapping |

### 5.6 Session Storage

```python
# Store session
await redis.setex(
    f"session:{session_id}",
    86400,  # 24 h
    json.dumps({"user_id": user_id, "role": role, "expires_at": expiry}),
)

# Retrieve session
data = await redis.get(f"session:{session_id}")
if data:
    session = json.loads(data)
```

### 5.7 Error Handling & Fallback

| Error | Handling |
|---|---|
| Connection refused | Fall back to in-memory rate limiting; degrade gracefully |
| Timeout | Retry once; fall back to in-memory |
| `OOM` / no memory | Redis evicts via `noeviction` policy; ModelPrism configured for `allkeys-lru` on cache only |
| Auth failure | Surface misconfiguration |
| Pub/sub channel full | Backpressure via slow consumer detection |

**Fallback chain:** Redis → in-memory dict (with TTL) → reject with `503 Service Unavailable` if both fail.

---

## 6. Systemd

ModelPrism provides a systemd service definition for production Linux deployments, managing the agent process lifecycle and log collection via journald.

### 6.1 Service File

File: `/etc/systemd/system/modelprism.service`

```ini
[Unit]
Description=ModelPrism Agent Service
After=network-online.target docker.service postgresql.service redis.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=simple
User=modelprism
Group=modelprism
WorkingDirectory=/opt/modelprism

# ── Executable ──
ExecStart=/opt/modelprism/venv/bin/python -m modelprism.agent \
    --config /etc/modelprism/config.yaml

# ── Restart Policy ──
Restart=on-failure
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=300

# ── Resource limits ──
LimitNOFILE=65536
LimitNPROC=4096
MemoryMax=32G
CPUShares=2048

# ── Security hardening ──
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true
CapabilityBoundingSet=
ReadWritePaths=/opt/modelprism /var/log/modelprism /data

# ── Environment ──
Environment=PYTHONUNBUFFERED=1
Environment=LOG_LEVEL=info
EnvironmentFile=-/etc/modelprism/env

[Install]
WantedBy=multi-user.target
```

**Key directives:**

| Directive | Value | Purpose |
|---|---|---|
| `Restart` | `on-failure` | Restart on crash, not on clean exit |
| `RestartSec` | `10` | Wait 10 s before restart |
| `StartLimitBurst` | `5` | Max restarts in interval |
| `StartLimitIntervalSec` | `300` | Reset counter after 5 min |
| `Type` | `simple` | Main process runs in foreground |
| `MemoryMax` | `32G` | Hard cgroup memory limit |
| `CPUShares` | `2048` | CPU weight (default 1024) |

**Restart policy reference:**

| Policy | Behaviour |
|---|---|
| `no` | Never restart |
| `on-success` | Restart only on exit code 0 |
| `on-failure` | Restart on non-zero exit, signal, or timeout |
| `on-abnormal` | Restart on signal/timeout |
| `on-abort` | Restart on uncaught signal |
| `always` | Restart unconditionally |

### 6.2 Lifecycle Commands

```bash
# Enable on boot
sudo systemctl enable modelprism

# Start / Stop / Restart
sudo systemctl start modelprism
sudo systemctl stop modelprism
sudo systemctl restart modelprism

# Status
sudo systemctl status modelprism

# Reload config (if agent supports SIGHUP)
sudo systemctl reload modelprism    # Sends SIGHUP

# View logs
sudo journalctl -u modelprism -f
sudo journalctl -u modelprism --since "1 hour ago"
```

### 6.3 Journald Log Access

ModelPrism reads its own logs via journald for the diagnostic API:

```python
import subprocess
import json

def get_recent_logs(unit: str = "modelprism", lines: int = 100) -> list[dict]:
    """Return recent journald log entries for the given unit."""
    result = subprocess.run(
        [
            "journalctl",
            "--unit", unit,
            "--output", "json",
            "--no-pager",
            f"--lines={lines}",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    entries = []
    for raw_line in result.stdout.strip().split("\n"):
        if raw_line:
            entries.append(json.loads(raw_line))
    return entries
```

**Journald output fields:**

| Field | Description |
|---|---|
| `__REALTIME_TIMESTAMP` | Microsecond-precision timestamp |
| `MESSAGE` | Log message |
| `PRIORITY` | 0=emerg … 7=debug |
| `SYSLOG_IDENTIFIER` | Process name |
| `_PID` | Process ID |

### 6.4 Error Handling & Fallback

| Error | Handling |
|---|---|
| Service fails to start | `journalctl -u modelprism -n 50 --no-pager` to diagnose |
| Exit code 0 (clean exit) | `Restart=on-failure` does NOT restart — use `always` if needed |
| Start limit burst | `systemctl reset-failed modelprism` after fixing the cause |
| Segfault / OOM signal | Caught by `Restart=on-failure`; log captured in journal |
| Config file missing | `EnvironmentFile=-/etc/modelprism/env` — `-` prefix means missing file is not fatal |

**Fallback:** If systemd is not available (container, dev), the agent can run standalone via `python -m modelprism.agent`. The service file is only provisioned in production environments.

---

## 7. PostgreSQL

PostgreSQL stores durable data: job history, user accounts, model metadata, billing records, and webhook idempotency keys.

### 7.1 Setup

```bash
pip install "asyncpg>=0.29.0" "psycopg[binary]>=3.1.0"
```

**Connection with asyncpg (async, recommended for ASGI):**

```python
import asyncpg

pool = await asyncpg.create_pool(
    dsn="postgresql://user:pass@localhost:5432/modelprism",
    min_size=5,
    max_size=20,
    command_timeout=30,
    max_inactive_connection_lifetime=300.0,  # 5 min
)

async with pool.acquire() as conn:
    rows = await conn.fetch("SELECT * FROM jobs WHERE status = $1", "running")
```

**Connection pool sizing:**

| Parameter | Default | Description |
|---|---|---|
| `min_size` | `5` | Minimum connections kept open |
| `max_size` | `20` | Maximum connections |
| `command_timeout` | `30` | Query timeout (seconds) |
| `max_inactive_connection_lifetime` | `300` | Close idle connections after (seconds) |

### 7.2 Connection Pooling

ModelPrism uses **built-in async pool** (asyncpg) by default. For higher throughput deployments, a **PgBouncer** sidecar is supported:

```ini
; pgbouncer.ini
[databases]
modelprism = host=127.0.0.1 port=5432 dbname=modelprism

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_db_connections = 50
default_pool_size = 25
```

**Connection string with PgBouncer:**

```
postgresql://user:pass@localhost:6432/modelprism?application_name=modelprism
```

**Pool mode trade-offs:**

| Mode | Behaviour | When to Use |
|---|---|---|
| `transaction` | Connection held for one transaction, then returned | **Default.** Best for web apps |
| `session` | Connection held for entire client session | Long-running queries, cursors |
| `statement` | Connection held for one statement | Low latency, no transactions |

### 7.3 Partitioned Tables

Large tables are partitioned to manage growth and enable efficient cleanup.

**Example: job logs partitioned by month**

```sql
-- Create partitioned table
CREATE TABLE job_logs (
    id          BIGSERIAL,
    job_id      UUID NOT NULL,
    level       TEXT NOT NULL DEFAULT 'info',
    message     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE job_logs_2026_06 PARTITION OF job_logs
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE TABLE job_logs_2026_07 PARTITION OF job_logs
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

-- Index on partition key + common query pattern
CREATE INDEX idx_job_logs_job_id ON job_logs (job_id, created_at DESC);
```

**Automated partition creation (via pg_cron or cron):**

```sql
-- Schedule monthly partition creation (requires pg_cron extension)
SELECT cron.schedule('create-next-partition', '0 0 1 * *',
    $$SELECT partition_manager.create_next_partition('job_logs')$$
);
```

**Partition strategy by table:**

| Table | Partition Key | Interval | Retention |
|---|---|---|---|
| `job_logs` | `created_at` | Monthly | 6 months |
| `model_downloads` | `created_at` | Monthly | 12 months |
| `api_requests` | `created_at` | Daily | 30 days |
| `billing_events` | `created_at` | Monthly | 36 months |

### 7.4 Scheduled Cleanup Jobs

Cleanup jobs run via `pg_cron` or an external scheduler (APScheduler in the agent).

```python
# Scheduled cleanup in agent (APScheduler)
from apscheduler.triggers.cron import CronTrigger

async def cleanup_old_partitions():
    """Drop partitions older than retention period."""
    async with pool.acquire() as conn:
        # Drop job_logs partitions older than 6 months
        await conn.execute("""
            SELECT partition_manager.drop_partitions_before(
                'job_logs', now() - interval '6 months'
            )
        """)

        # Clean orphaned sessions
        await conn.execute("""
            DELETE FROM sessions WHERE expires_at < now()
        """)

        # Archive completed jobs older than 90 days
        await conn.execute("""
            UPDATE jobs SET archived = true
            WHERE status IN ('completed', 'failed')
              AND updated_at < now() - interval '90 days'
        """)

scheduler.add_job(
    cleanup_old_partitions,
    CronTrigger(hour=3, minute=0),  # Daily at 03:00
    id="partition_cleanup",
)
```

**pg_cron alternative:**

```sql
-- Clean expired sessions every hour
SELECT cron.schedule('cleanup-sessions', '0 * * * *',
    $$DELETE FROM sessions WHERE expires_at < now()$$
);

-- Auto-vacuum tuning for partition tables
ALTER TABLE job_logs SET (autovacuum_vacuum_scale_factor = 0.01);
```

### 7.5 Schema Migrations

Use `alembic` for schema versioning:

```bash
alembic init migrations
alembic revision --autogenerate -m "add job_logs partition"
alembic upgrade head
```

```python
# alembic/env.py — configure async connection
from alembic import context
from app.db import get_async_engine

async def run_migrations():
    async with get_async_engine().connect() as conn:
        await conn.run_sync(context.run_async_migrations)
```

### 7.6 Error Handling & Fallback

| Error | Handling |
|---|---|
| Connection refused | Retry with backoff (1 s, 2 s, 4 s, max 30 s) |
| Auth failure | Surface misconfiguration; block startup |
| Query timeout | Log, return `503` |
| Deadlock | Retry transaction once; log warning |
| Serialisation failure | Retry transaction automatically |
| Connection pool exhausted | Queue; log warning; increase `max_size` if persistent |
| Disk full | Alert operator; switch to read-only mode |
| Replication lag (if replica) | Route reads to primary if lag > threshold |

**Fallback:** PostgreSQL is the system of record — there is no secondary store for its data. If the database is unavailable the agent enters a **degraded mode** where new jobs are queued (Redis) and persisted once the database recovers. The health endpoint includes `{"db": "unhealthy"}`.

---

## Cross-Cutting Concerns

### Credential Management

All credentials should be loaded from environment variables or a secrets manager (e.g., HashiCorp Vault, AWS Secrets Manager), never committed to the repository.

```python
import os

HF_TOKEN = os.environ.get("HF_TOKEN")
DOCKER_HOST = os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.environ.get("DATABASE_URL")
```

### Retry Strategy

| Integration | Policy |
|---|---|
| HuggingFace Hub | Exponential backoff: 2 s base, ×2, max 60 s, 3 retries |
| Docker Engine | Linear backoff: 2 s, 3 retries |
| Stripe | Exponential backoff: 1 s base, ×2, max 30 s, 3 retries (SDK default) |
| Redis | Immediate retry once; fall to in-memory |
| PostgreSQL | Exponential backoff: 1 s base, ×2, max 30 s, 5 retries |

### Health Endpoint Summary

```json
{
  "huggingface": "ok",
  "docker": "ok",
  "nvidia": {"gpus": 2, "driver": "535.154.05"},
  "stripe": "ok",
  "redis": "ok",
  "postgresql": "ok"
}
```

Each integration contributes a check to the `/health` endpoint. A non-critical failure (e.g., Stripe in self-hosted) returns the integration as `"disabled"` rather than `"unhealthy"`.

---

*End of integrations document.*
