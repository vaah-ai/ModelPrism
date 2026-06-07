# Glossary

## Access Token
A short-lived JWT (15-minute expiry) issued by the backend after authentication. The client includes it in the `Authorization: Bearer` header for all API requests. See also *Refresh Token*, *JWT*.

## Agent
A lightweight Python process installed on each GPU server in the cluster. It collects GPU and system metrics, manages model deployments, runs benchmarks, and maintains a persistent WebSocket connection back to the ModelPrism backend. See also *Agent Lifecycle*, *Agent Token*.

## Agent Lifecycle
The full lifecycle of an agent: registration (one-time token exchange), connection (persistent WebSocket), metric reporting, model management, possible pause/stop/deregister, and eventual teardown. The process is supervised by systemd on the GPU server.

## Agent Token
A single-use registration credential generated from the dashboard. The agent presents this token to the backend during initial registration to authenticate itself. Tokens expire after 24 hours.

## Apache 2.0
The permissive open-source license used for ModelPrism's core platform. It grants users the freedom to use, modify, and distribute the software, with the condition that any modified files carry prominent notices of changes.

## bcrypt
A password-hashing function used by the backend to store user passwords and API key hashes securely. ModelPrism uses a cost factor of 12, making brute-force attacks computationally expensive.

## Benchmark
A controlled performance test against a deployed model that measures metrics such as TTFT, TPOT, throughput, and latency under configurable concurrency and request patterns. See also *Benchmark Run*, *Benchmark Comparison*.

## Benchmark Comparison
A side-by-side view of two or more benchmark runs, allowing users to compare different model configurations, hardware setups, or model versions on metrics like latency and throughput.

## Benchmark Run
A single execution of a benchmark against a deployed model, saved with its full configuration (request count, concurrency, input distribution) and results. Runs are stored in PostgreSQL for historical review.

## CUDA
NVIDIA's parallel computing platform and programming model used by vLLM and the agent's GPU operations. ModelPrism requires CUDA 12.0+ on GPU servers.

## Data Retention
Configurable per-workspace time periods after which metrics, logs, and usage data are automatically deleted by a background cleanup job. Raw metrics (2s resolution) default to 24 hours; aggregated metrics default to 30 days; usage records are retained for 7 years for compliance.

## Docker Container
The isolation mechanism for running vLLM model instances. Each deployed model runs in its own Docker container with GPU device reservation via `--gpus`, memory limits, and health checking against `/v1/models`.

## Document
A top-level JSON:API response object (in `data`) that represents a single resource instance — for example, a GPU server, a model deployment, or a benchmark run. The top-level is a single object (not an array). See also *ResourceObject*.

## Downsampling
The process of reducing metric data fidelity over time: raw 2-second resolution is kept for short windows (default 24 hours), 1-minute aggregates for medium windows (default 30 days), and 5-minute aggregates for long-term storage (default 1 year). This keeps storage manageable while preserving trend visibility.

## GPU Server
A physical or virtual machine with one or more NVIDIA GPUs that runs the ModelPrism agent alongside vLLM for model inference.

## GPU Utilization
The percentage of GPU compute capacity in use over a sampling interval, reported by `nvidia-smi` and displayed in real-time dashboard charts. Distinct from VRAM usage — high utilization with low VRAM usage may indicate a bottleneck.

## Heartbeat
A periodic ping (every 15 seconds) sent from the agent to the backend over the WebSocket connection to confirm the agent is still alive. If no heartbeat arrives within a configurable timeout, the backend marks the agent as offline.

## HuggingFace Hub
A repository hosting thousands of pre-trained models. ModelPrism's model browser integrates with HuggingFace Hub's API for search, discovery, filtering, and one-click deployment of models.

## JSON:API
A specification (`application/vnd.api+json`) for building REST APIs. ModelPrism uses JSON:API for all dashboard REST endpoints, providing consistent document structure with `data`, `included`, `links`, and `meta` top-level members.

## JWT (JSON Web Token)
A compact, URL-safe token format used for authentication. ModelPrism issues access tokens (15-minute expiry) for API authorization and refresh tokens (7-day expiry) for obtaining new access tokens without re-authentication.

## Metric Batching
The agent's practice of collecting GPU and system metrics into batches (default 500ms interval) before sending them to the backend over WebSocket. This reduces overhead compared to sending one metric at a time.

## MODELPRISM_CLOUD flag
A boolean environment variable that switches ModelPrism between self-hosted mode (`false`) and cloud mode (`true`). When `false`, billing features are hidden; all other platform features remain fully functional.

## Model Deployment
The process of selecting a model from HuggingFace Hub (or custom), configuring vLLM parameters (quantization, tensor parallelism, context length), and launching it as a Docker container on a target GPU server via the agent.

## NVIDIA Container Toolkit
A toolchain that enables Docker containers to access NVIDIA GPUs. Required on GPU servers that run vLLM in Docker containers. It provides the `nvidia-container-runtime` and the `--gpus` Docker flag.

## nvidia-smi
The NVIDIA System Management Interface, a command-line utility that reports GPU metrics such as utilization, VRAM usage, temperature, and power draw. The ModelPrism agent invokes it via subprocess to collect GPU telemetry.

## Open Core
ModelPrism's business model: the core platform (agent, dashboard, model management, benchmarking, monitoring) is fully open source under Apache 2.0, while cloud-only features (multi-tenant API proxy, usage analytics, billing) are available in the hosted SaaS version.

## OpenAI-Compatible Proxy
A proxy endpoint at `/v1/chat/completions` and `/v1/completions` that accepts requests in the OpenAI API format and routes them to self-hosted vLLM instances, OpenAI, or Anthropic. Authenticated via `Authorization: Bearer sk-...` keys.

## Pagination
JSON:API-compliant pagination for list endpoints, using `page[number]` and `page[size]` query parameters. Responses include `links` (first, last, prev, next) and `meta` (total count) members.

## psutil
A Python library for system monitoring. The agent uses psutil to collect CPU utilization, RAM usage, disk I/O, and network metrics alongside GPU data from `nvidia-smi`.

## Rate Limiting
Per-key and per-IP request throttling enforced by the backend using Redis sliding-window counters. In self-hosted mode, rate limiting fails open (allows requests) if Redis is unavailable.

## RBAC (Role-Based Access Control)
The permission model governing what actions users can perform within a workspace. Built on four roles: Owner, Admin, Member, and Viewer. See also *Role*, *Workspace*.

## Refresh Token
A longer-lived JWT (7-day expiry) used to obtain new access tokens without requiring the user to re-authenticate. The backend rotates refresh tokens on each use, invalidating the previous one.

## Resumable Download
A download mechanism (typically using HTTP Range headers) that allows model weight downloads from HuggingFace Hub to be paused and resumed without restarting from scratch. Critical for large multi-gigabyte model files.

## ResourceObject
A single resource entity in a JSON:API response, containing `id`, `type`, `attributes`, and optionally `relationships` and `links`. For example, a GPU server resource object might have attributes for GPU count, VRAM, and status. A collection endpoint returns `data` as an array of resource objects; a single-resource endpoint returns `data` as a single resource object. See also *Document*.

## Role
A named permission level within a workspace: Owner (full access, billing, team management), Admin (manage models, API keys, users), Member (deploy models, create keys), or Viewer (read-only). See also *RBAC*, *Workspace*.

## Sparse Fieldset
A JSON:API feature allowing clients to request only specific fields of a resource via `fields[TYPE]=field1,field2` query parameters. For example, `fields[gpu_server]=name,status,gpu_count` reduces response payload size.

## Stripe Metered Billing
Usage-based billing integration where ModelPrism reports per-workspace token consumption to Stripe as meter events every hour. Stripe generates invoices automatically based on configured per-token pricing.

## Systemd
The Linux init system used to supervise the ModelPrism agent process on GPU servers. If the agent crashes, systemd automatically restarts it. The agent registers itself as a systemd service during installation.

## tiktoken
A fast open-source tokenizer library by OpenAI. ModelPrism uses tiktoken to count prompt and completion tokens for usage tracking and billing, intercepting requests and responses at the proxy layer.

## Token Counting
The process of measuring the number of tokens in each API request (prompt tokens) and response (completion tokens) using tiktoken. Used for usage tracking, rate limiting, and metered billing.

## vLLM
The high-performance LLM inference engine that ModelPrism manages. vLLM is launched per-model (typically in a Docker container), and ModelPrism configures its parameters, monitors its metrics, and proxies requests to its API.

## VRAM (Video Random Access Memory)
GPU memory used to hold model weights, KV cache, and intermediate tensors during inference. ModelPrism tracks VRAM usage per GPU and uses it for capacity calculations during model deployment.

## WebSocket
A persistent, full-duplex communication protocol used by the agent to stream real-time GPU metrics, logs, and deployment progress to the backend, and by the backend to push updates to the browser dashboard.

## Workspace
An isolated tenant within ModelPrism. Each workspace has its own GPU servers, models, API keys, users, roles, billing, and data retention settings. Users can belong to multiple workspaces. See also *RBAC*.
