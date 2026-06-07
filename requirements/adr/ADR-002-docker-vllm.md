# ADR-002: Docker for vLLM

## Status
Accepted

## Context
Initial requirements listed Docker as "optional, recommended for production" but allowed direct subprocess-based vLLM management. Subprocess management has critical failure modes:

1. vLLM crash leaves orphan process consuming 80GB+ VRAM
2. Port conflicts between concurrent model deployments
3. No GPU memory limits — model can OOM the GPU
4. No filesystem isolation — model code accesses agent data
5. Security risk: malicious model can execute arbitrary code on host

## Decision
Docker is **mandatory** for all vLLM model deployments from day one:

- Each model gets an isolated Docker container
- GPU device reservation via `--gpus device=X` flag
- Memory limits via Docker
- Atomic port allocation from a reservation table
- Health checking via `/v1/models` every 10s
- Container lifecycle managed by agent via Docker SDK (not subprocess)

## Consequences
- Requires Docker Engine on all GPU servers
- Slightly more overhead than bare subprocess (negligible for inference workloads)
- Clean isolation: agent crash does not orphan vLLM
- Port conflicts eliminated
- GPU memory oversubscription prevented
- Security sandboxing: read-only rootfs, dropped capabilities, restricted network
