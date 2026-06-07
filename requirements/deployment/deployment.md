# ModelPrism Deployment Guide

> Self-hosted deployment of the ModelPrism GPU inference management platform on
> VPS / dedicated hardware. This guide covers every component: the Nuxt 4
> frontend, the FastAPI backend, PostgreSQL 15+, Redis 7+, and the
> `modelprism-agent` that runs on GPU servers.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Docker Compose Setup](#3-docker-compose-setup)
4. [Environment Variables Reference](#4-environment-variables-reference)
5. [GPU Server Agent Installation](#5-gpu-server-agent-installation)
6. [TLS / SSL with Caddy](#6-tls--ssl-with-caddy)
   - [Alternative: Nginx + Let's Encrypt](#alternative-nginx--lets-encrypt)
7. [Backup and Restore](#7-backup-and-restore)
8. [Upgrade Procedures](#8-upgrade-procedures)
9. [Monitoring and Alerting](#9-monitoring-and-alerting)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Architecture Overview

```
┌─────────────────────────┐
│        Internet         │
└────┬────────────────┬───┘
     │                │
     ▼                ▼
┌────────────┐  ┌────────────┐
│  Frontend  │  │  Backend   │
│  VPS       │  │  VPS       │
│            │  │            │
│  Nuxt 4    │  │  FastAPI   │
│  (SSR)     │  │  (uvicorn) │
│            │  │            │
│  Caddy     │  │  Caddy     │
└────────────┘  └─────┬──────┘
                       │
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
      ┌──────────────┐  ┌──────────────┐
      │  PostgreSQL  │  │    Redis     │
      │  15+         │  │  7+          │
      │  (persistent)│  │  (cache/queue)│
      └──────────────┘  └──────────────┘
              │
              │  (control plane — HTTPS)
              ▼
   ┌─────────────────────┐
   │   GPU Server Pool   │
   │                     │
   │  ┌───────────────┐  │
   │  │ modelprism-   │  │
   │  │ agent (Docker)│  │
   │  └───────────────┘  │
   │  │  NVIDIA GPUs  │  │
   │  └───────────────┘  │
   └─────────────────────┘
```

| Machine           | Recommended Spec                | Services                                      |
| ----------------- | ------------------------------- | --------------------------------------------- |
| **Frontend VPS**  | 2 vCPU, 4 GB RAM, 80 GB SSD    | Nuxt 4 (SSR), Caddy                           |
| **Backend VPS**   | 4 vCPU, 8 GB RAM, 100 GB SSD   | FastAPI, PostgreSQL, Redis, Caddy             |
| **GPU Server(s)** | 8+ vCPU, 32+ GB RAM, GPU       | `modelprism-agent`, NVIDIA Container Toolkit  |

You may colocate frontend and backend on a single VPS for smaller deployments (8
vCPU, 16 GB RAM recommended).

---

## 2. Prerequisites

### All Machines

- **Ubuntu 22.04 LTS** or **Debian 12** (recommended)
- **Docker** ≥ 24.x + **Docker Compose** v2
- **Caddy** (or Nginx) for TLS termination
- **curl**, **jq**, **git**
- Firewall open ports:
  - `22/tcp` — SSH (restrict to trusted IPs)
  - `80/tcp`, `443/tcp` — HTTP / HTTPS
  - `3000/tcp` — (internal) Nuxt SSR
  - `8000/tcp` — (internal) FastAPI
  - `2376/tcp` — (optional, internal) Docker TCP for agent orchestration

### GPU Servers Only

- **NVIDIA GPU** with compute capability ≥ 7.0
- **NVIDIA drivers** ≥ 545
- **NVIDIA Container Toolkit** (`nvidia-ctk`)

---

## 3. Docker Compose Setup

Create the project directory and configuration on the **backend VPS**.

### 3.1 Directory Layout

```
/opt/modelprism/
├── .env                      # Environment variables (secret)
├── docker-compose.yml
├── caddy/
│   └── Caddyfile
├── postgres/
│   └── init/
│       └── 01-init.sql       # Initial schema (optional)
├── redis/
│   └── redis.conf
├── backups/                  # Backup destination
├── data/
│   ├── postgres/
│   └── redis/
└── modelprism/
    └── .env.production       # FastAPI env overrides
```

### 3.2 docker-compose.yml

```yaml
# /opt/modelprism/docker-compose.yml
name: modelprism

x-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"

services:
  # ── PostgreSQL ──────────────────────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
      - ./postgres/init:/docker-entrypoint-initdb.d:ro
    environment:
      POSTGRES_USER: ${MODELPRISM_DB_USER:-modelprism}
      POSTGRES_PASSWORD: ${MODELPRISM_DB_PASSWORD:?err}
      POSTGRES_DB: modelprism
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${MODELPRISM_DB_USER:-modelprism}"]
      interval: 10s
      timeout: 5s
      retries: 5
    logging: *default-logging

  # ── Redis ───────────────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: >
      redis-server
      --requirepass ${MODELPRISM_REDIS_PASSWORD:?err}
      --appendonly yes
      --auto-aof-rewrite-percentage 100
      --auto-aof-rewrite-min-size 64mb
    volumes:
      - ./data/redis:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    logging: *default-logging

  # ── FastAPI Backend ─────────────────────────────────────────────────────────
  backend:
    image: ghcr.io/modelprism/modelprism-backend:${MODELPRISM_VERSION:-latest}
    pull_policy: always
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./modelprism/.env.production:/app/.env:ro
      - modelprism_data:/app/data
    environment:
      # Database
      MODELPRISM_DB_HOST: postgres
      MODELPRISM_DB_PORT: 5432
      MODELPRISM_DB_USER: ${MODELPRISM_DB_USER:-modelprism}
      MODELPRISM_DB_PASSWORD: ${MODELPRISM_DB_PASSWORD:?err}
      MODELPRISM_DB_NAME: modelprism

      # Redis
      MODELPRISM_REDIS_HOST: redis
      MODELPRISM_REDIS_PORT: 6379
      MODELPRISM_REDIS_PASSWORD: ${MODELPRISM_REDIS_PASSWORD:?err}

      # Security
      MODELPRISM_SECRET_KEY: ${MODELPRISM_SECRET_KEY:?err}
      MODELPRISM_ENCRYPTION_KEY: ${MODELPRISM_ENCRYPTION_KEY:?err}
      MODELPRISM_JWT_SECRET: ${MODELPRISM_JWT_SECRET:?err}

      # Admin
      MODELPRISM_ADMIN_EMAIL: ${MODELPRISM_ADMIN_EMAIL:-admin@example.com}
      MODELPRISM_ADMIN_PASSWORD: ${MODELPRISM_ADMIN_PASSWORD:?err}

      # URL
      MODELPRISM_BACKEND_URL: https://api.modelprism.example.com
      MODELPRISM_FRONTEND_URL: https://modelprism.example.com

      # GPU Orchestration
      MODELPRISM_AGENT_REGISTRATION_KEY: ${MODELPRISM_AGENT_REGISTRATION_KEY:?err}

      # Logging
      MODELPRISM_LOG_LEVEL: ${MODELPRISM_LOG_LEVEL:-info}
      MODELPRISM_JSON_LOGS: "true"
    ports:
      - "127.0.0.1:8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging: *default-logging

  # ── Nuxt 4 Frontend ─────────────────────────────────────────────────────────
  frontend:
    image: ghcr.io/modelprism/modelprism-frontend:${MODELPRISM_VERSION:-latest}
    pull_policy: always
    restart: unless-stopped
    environment:
      NUXT_PUBLIC_API_BASE: https://api.modelprism.example.com
      NUXT_PUBLIC_SITE_URL: https://modelprism.example.com
      MODELPRISM_BACKEND_URL: http://backend:8000
      NUXT_SESSION_PASSWORD: ${NUXT_SESSION_PASSWORD:?err}
    ports:
      - "127.0.0.1:3000:3000"
    healthcheck:
      test: ["CMD", "node", "-e", "fetch('http://127.0.0.1:3000/api/health').then(r => process.exit(r.ok ? 0 : 1))"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    logging: *default-logging

volumes:
  modelprism_data:
```

### 3.3 Deploy

```bash
# Clone once (or just copy docker-compose.yml)
mkdir -p /opt/modelprism && cd /opt/modelprism

# Create the .env file (see section 4)
cp .env.example .env

# Pull images and start
docker compose pull
docker compose up -d

# Check health
docker compose ps
docker compose logs --tail=50
```

---

## 4. Environment Variables Reference

Create `/opt/modelprism/.env`:

```bash
# ── Required ──────────────────────────────────────────────────────────────────

# Database
MODELPRISM_DB_PASSWORD="<generate: openssl rand -base64 32>"

# Redis
MODELPRISM_REDIS_PASSWORD="<generate: openssl rand -base64 32>"

# Security
MODELPRISM_SECRET_KEY="<generate: openssl rand -base64 64>"
MODELPRISM_ENCRYPTION_KEY="<generate: openssl rand -hex 32>"
MODELPRISM_JWT_SECRET="<generate: openssl rand -base64 64>"

# Admin bootstrap
MODELPRISM_ADMIN_EMAIL="admin@example.com"
MODELPRISM_ADMIN_PASSWORD="<generate a strong password>"

# Agent registration
MODELPRISM_AGENT_REGISTRATION_KEY="<generate: openssl rand -base64 32>"

# Frontend session encryption
NUXT_SESSION_PASSWORD="<generate: openssl rand -base64 32>"

# ── Optional ──────────────────────────────────────────────────────────────────

MODELPRISM_DB_USER="modelprism"
MODELPRISM_DB_NAME="modelprism"
MODELPRISM_LOG_LEVEL="info"
MODELPRISM_VERSION="latest"
```

### Complete Variable Table

| Variable                             | Required | Default          | Description                                 |
| ------------------------------------ | -------- | ---------------- | ------------------------------------------- |
| `MODELPRISM_DB_HOST`                 | No       | `localhost`      | PostgreSQL hostname                         |
| `MODELPRISM_DB_PORT`                 | No       | `5432`           | PostgreSQL port                             |
| `MODELPRISM_DB_USER`                 | No       | `modelprism`     | PostgreSQL user                             |
| `MODELPRISM_DB_PASSWORD`             | **Yes**  | —                | PostgreSQL password                          |
| `MODELPRISM_DB_NAME`                 | No       | `modelprism`     | PostgreSQL database name                    |
| `MODELPRISM_DB_POOL_SIZE`            | No       | `20`             | Connection pool size                        |
| `MODELPRISM_DB_MAX_OVERFLOW`         | No       | `10`             | Max overflow connections                    |
| `MODELPRISM_REDIS_HOST`              | No       | `localhost`      | Redis hostname                              |
| `MODELPRISM_REDIS_PORT`              | No       | `6379`           | Redis port                                  |
| `MODELPRISM_REDIS_PASSWORD`          | **Yes**  | —                | Redis password (AUTH)                       |
| `MODELPRISM_REDIS_DB`               | No       | `0`              | Redis database index                        |
| `MODELPRISM_SECRET_KEY`              | **Yes**  | —                | Django-style app secret key (session signing)|
| `MODELPRISM_ENCRYPTION_KEY`          | **Yes**  | —                | Fernet key for model API key encryption     |
| `MODELPRISM_JWT_SECRET`              | **Yes**  | —                | JWT signing secret                          |
| `MODELPRISM_JWT_ALGORITHM`           | No       | `HS256`          | JWT algorithm                               |
| `MODELPRISM_JWT_EXPIRY_MINUTES`      | No       | `60`             | Access token expiry                         |
| `MODELPRISM_BACKEND_URL`             | No       | `http://localhost:8000` | Public backend URL                    |
| `MODELPRISM_FRONTEND_URL`            | No       | `http://localhost:3000` | Public frontend URL                   |
| `MODELPRISM_ADMIN_EMAIL`             | No       | —                | Bootstrap admin email                       |
| `MODELPRISM_ADMIN_PASSWORD`          | **Yes**  | —                | Bootstrap admin password                    |
| `MODELPRISM_AGENT_REGISTRATION_KEY`  | **Yes**  | —                | Shared secret for GPU agent registration    |
| `MODELPRISM_AGENT_HEARTBEAT_SECONDS` | No       | `30`             | Agent heartbeat interval                    |
| `MODELPRISM_AGENT_TIMEOUT_SECONDS`   | No       | `90`             | Agent timeout before marking offline        |
| `MODELPRISM_LOG_LEVEL`               | No       | `info`           | One of: `debug`, `info`, `warning`, `error` |
| `MODELPRISM_JSON_LOGS`               | No       | `true`           | Enable structured JSON logging              |
| `MODELPRISM_CORS_ORIGINS`            | No       | `["*"]`          | Allowed CORS origins (JSON array)           |
| `MODELPRISM_RATE_LIMIT_PER_MINUTE`   | No       | `60`             | API rate limit per user, per minute         |
| `MODELPRISM_STORAGE_BACKEND`         | No       | `local`          | Model storage backend (`local` or `s3`)    |
| `MODELPRISM_STORAGE_S3_BUCKET`       | No       | —                | S3 bucket name (if `s3` backend)           |
| `MODELPRISM_STORAGE_S3_REGION`       | No       | —                | S3 region                                   |
| `MODELPRISM_STORAGE_S3_ENDPOINT`     | No       | —                | S3-compatible endpoint URL                  |
| `MODELPRISM_STORAGE_S3_ACCESS_KEY`   | No       | —                | S3 access key                               |
| `MODELPRISM_STORAGE_S3_SECRET_KEY`   | No       | —                | S3 secret key                               |
| `NUXT_SESSION_PASSWORD`              | **Yes**  | —                | 32-char encryption key for Nuxt sessions    |
| `NUXT_PUBLIC_API_BASE`               | No       | —                | Public API URL for client-side calls        |
| `NUXT_PUBLIC_SITE_URL`               | No       | —                | Public site URL for sitemap / SEO           |

> **Security note:** Never commit `.env` to version control. Rotate `SECRET_KEY`,
> `ENCRYPTION_KEY`, `JWT_SECRET`, and `AGENT_REGISTRATION_KEY` on a regular
> schedule or after any suspected compromise.

---

## 5. GPU Server Agent Installation

The `modelprism-agent` is a container that registers with the backend, pulls
model images, and serves inference requests.

### 5.1 Prerequisites (GPU Server)

```bash
# 1. NVIDIA drivers
nvidia-smi  # Verify — should show driver + CUDA version

# 2. NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL "https://nvidia.github.io/libnvidia-container/stable/${distribution}/libnvidia-container.list" | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 3. Docker (if not already installed)
# See https://docs.docker.com/engine/install/ubuntu/
```

### 5.2 One-Line Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/modelprism/modelprism/main/scripts/install-agent.sh | \
  sudo bash -s -- \
    --backend https://api.modelprism.example.com \
    --register-key "YOUR_AGENT_REGISTRATION_KEY"
```

The script will:

1. Pull the `ghcr.io/modelprism/modelprism-agent` image
2. Create a systemd service for automatic restart
3. Register with the backend
4. Start the heartbeat loop

### 5.3 Manual Docker Run

```bash
docker run -d \
  --name modelprism-agent \
  --restart unless-stopped \
  --gpus all \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v modelprism_models:/models \
  -e MODELPRISM_BACKEND_URL="https://api.modelprism.example.com" \
  -e MODELPRISM_REGISTRATION_KEY="<key>" \
  -e MODELPRISM_AGENT_ID="gpu-01" \
  -e MODELPRISM_GPU_MEMORY_RESERVE_GB=2 \
  -e MODELPRISM_LOG_LEVEL=info \
  ghcr.io/modelprism/modelprism-agent:latest
```

### 5.4 Verify Agent Registration

```bash
# From any machine with access to the API:
curl -s https://api.modelprism.example.com/api/v1/agents \
  -H "Authorization: Bearer $(mp login --token)" | jq '.'
```

Expected output:

```json
{
  "agents": [
    {
      "id": "gpu-01",
      "status": "online",
      "gpu_count": 1,
      "gpu_model": "NVIDIA A100 80GB",
      "vram_total_mb": 81920,
      "vram_free_mb": 81000,
      "last_heartbeat": "2026-06-07T10:30:00Z"
    }
  ]
}
```

---

## 6. TLS / SSL with Caddy

### 6.1 Caddyfile

Place this on both the **frontend VPS** and **backend VPS** (or a single Caddy
instance that reverse-proxies both).

```caddy
# /opt/modelprism/caddy/Caddyfile

modelprism.example.com {
    reverse_proxy 127.0.0.1:3000

    header /api/* {
        Access-Control-Allow-Origin "https://modelprism.example.com"
        Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS"
        Access-Control-Allow-Headers "Content-Type, Authorization"
    }

    # Security headers
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "geolocation=(), microphone=(), camera=()"
    }

    # Rate limiting
    rate_limit {
        zone dynamic {
            key {remote_host}
            events 100
            window 1m
        }
    }

    # Compression
    encode gzip

    # Logs
    log {
        output file /var/log/caddy/frontend.log
        format json
    }
}

api.modelprism.example.com {
    reverse_proxy 127.0.0.1:8000

    header /health {
        Access-Control-Allow-Origin "*"
    }

    header /api/* {
        Access-Control-Allow-Origin "https://modelprism.example.com"
        Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS"
        Access-Control-Allow-Headers "Content-Type, Authorization"
    }

    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
    }

    rate_limit {
        zone api {
            key {remote_host}
            events 200
            window 1m
        }
    }

    encode gzip

    log {
        output file /var/log/caddy/backend.log
        format json
    }
}
```

### 6.2 Run Caddy

```bash
# Using Docker (recommended for colocation)
docker run -d \
  --name caddy \
  --restart unless-stopped \
  -p 80:80 \
  -p 443:443 \
  -p 443:443/udp \
  -v /opt/modelprism/caddy/Caddyfile:/etc/caddy/Caddyfile:ro \
  -v caddy_data:/data \
  -v caddy_config:/config \
  -v /var/log/caddy:/var/log/caddy \
  caddy:2-alpine

# Or install Caddy directly:
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
sudo systemctl enable --now caddy
```

### Alternative: Nginx + Let's Encrypt

```nginx
# /etc/nginx/sites-available/modelprism

server {
    listen 80;
    server_name modelprism.example.com api.modelprism.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name modelprism.example.com;

    ssl_certificate     /etc/letsencrypt/live/modelprism.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/modelprism.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 443 ssl http2;
    server_name api.modelprism.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.modelprism.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.modelprism.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Obtain certificates
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d modelprism.example.com -d api.modelprism.example.com
sudo systemctl enable --now nginx
```

---

## 7. Backup and Restore

### 7.1 Automated Backup Script

Save as `/opt/modelprism/scripts/backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/modelprism/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

mkdir -p "$BACKUP_DIR"

# ── PostgreSQL ────────────────────────────────────────────────────────────────
echo "Backing up PostgreSQL..."
docker compose exec -T postgres pg_dump \
  --username="${MODELPRISM_DB_USER:-modelprism}" \
  --format=custom \
  --compress=9 \
  --file=/tmp/modelprism_db.dump \
  modelprism

docker compose cp postgres:/tmp/modelprism_db.dump \
  "${BACKUP_DIR}/modelprism_db_${TIMESTAMP}.dump"

echo "  → ${BACKUP_DIR}/modelprism_db_${TIMESTAMP}.dump"

# ── Redis ─────────────────────────────────────────────────────────────────────
echo "Backing up Redis..."
docker compose exec -T redis redis-cli \
  -a "${MODELPRISM_REDIS_PASSWORD}" \
  --rdb /tmp/dump.rdb

docker compose cp redis:/tmp/dump.rdb \
  "${BACKUP_DIR}/redis_${TIMESTAMP}.rdb"

echo "  → ${BACKUP_DIR}/redis_${TIMESTAMP}.rdb"

# ── Configuration ─────────────────────────────────────────────────────────────
echo "Backing up configuration..."
tar czf "${BACKUP_DIR}/config_${TIMESTAMP}.tar.gz" \
  -C /opt/modelprism \
  --exclude=backups \
  --exclude=data/postgres \
  --exclude=data/redis \
  "./.env" "./docker-compose.yml" "./caddy/"

echo "  → ${BACKUP_DIR}/config_${TIMESTAMP}.tar.gz"

# ── Cleanup ───────────────────────────────────────────────────────────────────
find "$BACKUP_DIR" -name "modelprism_db_*.dump" -mtime "+${RETENTION_DAYS}" -delete
find "$BACKUP_DIR" -name "redis_*.rdb" -mtime "+${RETENTION_DAYS}" -delete
find "$BACKUP_DIR" -name "config_*.tar.gz" -mtime "+${RETENTION_DAYS}" -delete

echo "Done. Retention: ${RETENTION_DAYS} days."
```

### 7.2 Cron Job

```bash
# /etc/cron.d/modelprism-backup
MAILTO="admin@example.com"
0 3 * * * root MODELPRISM_DB_USER=modelprism MODELPRISM_REDIS_PASSWORD="<redacted>" /opt/modelprism/scripts/backup.sh
```

### 7.3 Restore

```bash
# PostgreSQL restore
docker compose exec -T postgres pg_restore \
  --username="${MODELPRISM_DB_USER:-modelprism}" \
  --dbname=modelprism \
  --clean \
  --if-exists \
  < /opt/modelprism/backups/modelprism_db_20260607_030000.dump

# Redis restore (requires restart)
docker compose stop redis
cp /opt/modelprism/backups/redis_20260607_030000.rdb /opt/modelprism/data/redis/dump.rdb
docker compose start redis
```

---

## 8. Upgrade Procedures

### 8.1 Standard Upgrade

```bash
cd /opt/modelprism

# 1. Pull new images
docker compose pull

# 2. Apply any new migration files
#    (postgres/init scripts are idempotent)

# 3. Restart services
docker compose up -d --remove-orphans

# 4. Run database migrations (handled by backend on startup,
#    but can be run manually for pinned versions):
docker compose exec backend alembic upgrade head

# 5. Verify
docker compose ps
curl -s https://api.modelprism.example.com/health | jq .
```

### 8.2 Pinned Version Upgrade

```bash
# Set the version in .env
export MODELPRISM_VERSION="v1.2.3"

docker compose pull
docker compose up -d
```

### 8.3 Rollback

```bash
# Revert to previous image tag
export MODELPRISM_VERSION="v1.2.2"
docker compose pull
docker compose up -d

# If database migration needs rollback:
docker compose exec backend alembic downgrade -1
```

---

## 9. Monitoring and Alerting

### 9.1 Health Endpoint

The backend exposes a health check at `/health`:

```bash
curl -s https://api.modelprism.example.com/health
```

```json
{
  "status": "healthy",
  "version": "1.2.3",
  "uptime_seconds": 86400,
  "postgres": {
    "status": "connected",
    "pool_size": 8,
    "active_connections": 2
  },
  "redis": {
    "status": "connected",
    "used_memory_mb": 45
  },
  "agents_online": 3,
  "agents_offline": 0,
  "active_inferences": 12
}
```

### 9.2 Prometheus + Node Exporter

```yaml
# /opt/modelprism/docker-compose.monitoring.yml
name: modelprism-monitoring

services:
  prometheus:
    image: prom/prometheus:latest
    restart: unless-stopped
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "127.0.0.1:9090:9090"

  node-exporter:
    image: prom/node-exporter:latest
    restart: unless-stopped
    network_mode: host
    pid: host

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    restart: unless-stopped
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    ports:
      - "127.0.0.1:8080:8080"
    privileged: true

volumes:
  prometheus_data:
```

```yaml
# /opt/modelprism/monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "node"
    static_configs:
      - targets: ["localhost:9100"]

  - job_name: "docker"
    static_configs:
      - targets: ["localhost:8080"]

  - job_name: "modelprism-api"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["127.0.0.1:8000"]
```

### 9.3 Grafana Dashboard

```bash
docker run -d \
  --name grafana \
  --restart unless-stopped \
  -p 127.0.0.1:3001:3000 \
  -v grafana_data:/var/lib/grafana \
  -e GF_SECURITY_ADMIN_PASSWORD="<password>" \
  grafana/grafana:latest
```

### 9.4 Alerting Rules

Save as `/opt/modelprism/monitoring/alerts.yml`:

```yaml
groups:
  - name: modelprism
    rules:
      - alert: AgentOffline
        expr: modelprism_agents_online < 1
        for: 2m
        annotations:
          summary: "No GPU agents online"

      - alert: AgentHighMemory
        expr: modelprism_agent_memory_pct > 90
        for: 5m
        annotations:
          summary: "GPU agent memory > 90%"

      - alert: QueueBacklog
        expr: modelprism_inference_queue_depth > 50
        for: 1m
        annotations:
          summary: "Inference queue backlog > 50"

      - alert: HighErrorRate
        expr: rate(modelprism_http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "API error rate > 5%"
```

### 9.5 Log Aggregation with Loki

```yaml
  # Append to docker-compose.monitoring.yml
  loki:
    image: grafana/loki:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:3100:3100"
    volumes:
      - ./monitoring/loki.yml:/etc/loki/loki.yml:ro
      - loki_data:/loki

  promtail:
    image: grafana/promtail:latest
    restart: unless-stopped
    volumes:
      - /var/log/caddy:/var/log/caddy:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./monitoring/promtail.yml:/etc/promtail/promtail.yml:ro

volumes:
  loki_data:
```

### 9.6 Uptime Monitoring (External)

Configure external monitoring against the health endpoint:

| Check          | URL                                                | Expected                        |
| -------------- | -------------------------------------------------- | ------------------------------- |
| Frontend       | `https://modelprism.example.com`                   | HTTP 200                        |
| API Health     | `https://api.modelprism.example.com/health`        | JSON `{"status": "healthy"}`   |
| GPU Heartbeat  | `https://api.modelprism.example.com/api/v1/agents` | JSON array with `status: online`|

Recommended providers: Checkly, Better Uptime, or Uptime Kuma (self-hosted).

---

## 10. Troubleshooting

| Symptom                              | Likely Cause                    | Check / Fix                                   |
| ------------------------------------ | ------------------------------- | --------------------------------------------- |
| Frontend shows "API unreachable"     | Backend down or CORS misconfig  | `docker compose logs backend`                 |
|                                      |                                 | Verify `MODELPRISM_CORS_ORIGINS`              |
| Agent shows "offline"                | Registration key mismatch       | Re-run install with correct `--register-key`  |
|                                      | Network blocked (port 443)      | `curl -s https://api.example.com/health`     |
| Database connection refused          | Postgres not healthy            | `docker compose logs postgres`                |
|                                      | Password mismatch               | Verify `.env` values match                    |
| Redis connection refused             | Redis password mismatch         | `docker compose exec redis redis-cli AUTH <pw>`|
| GPU not detected in agent            | NVIDIA CTK not configured       | `docker run --rm --gpus all nvidia/cuda:12-base nvidia-smi` |
| SSL certificate not issued           | DNS not propagated              | `dig +short modelprism.example.com`           |
|                                      | Port 80 not reachable           | `ss -tlnp \| grep ':80'`                     |
| `docker compose` command not found   | Docker Compose v2 not installed | `sudo apt install docker-compose-plugin`      |
| Out of disk space                    | Logs or old backups             | `docker system prune -af`                     |
|                                      |                                 | Increase backup retention or move to volume   |

### Quick Health Check Script

```bash
#!/usr/bin/env bash
# /opt/modelprism/scripts/healthcheck.sh

echo "=== ModelPrism Health Check ==="
echo ""

# Services
docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null || echo "Docker Compose not running"

echo ""

# API health
if curl -sf https://api.modelprism.example.com/health > /dev/null 2>&1; then
  echo "✅ API Health: OK"
  curl -s https://api.modelprism.example.com/health | jq '{status, agents_online, active_inferences}'
else
  echo "❌ API Health: UNREACHABLE"
fi

echo ""

# Frontend
if curl -sf https://modelprism.example.com > /dev/null 2>&1; then
  echo "✅ Frontend: OK"
else
  echo "❌ Frontend: UNREACHABLE"
fi

echo ""

# Agents
if curl -sf https://api.modelprism.example.com/api/v1/agents \
  -H "Authorization: Bearer $(mp login --token 2>/dev/null)" | jq '.agents[] | {id, status}' 2>/dev/null; then
  echo "✅ Agents: OK (see above)"
else
  echo "❌ Agents: Could not fetch agent list"
fi

echo ""
df -h /opt/modelprism | tail -1 | awk '{print "Disk usage:", $5, "("$3" used of "$2")"}'
```

---

> **Next steps:** After deploying, run the health check script to validate the
> setup, then add GPU servers one at a time. For production use, configure
> external monitoring and set up weekly backup cron jobs. See the
> [Operations Guide](../operations/operations.md) for day-to-day management
> tasks.
