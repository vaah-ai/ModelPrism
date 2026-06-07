---
id: F23
title: "Model Optimization Recommendations"
phase: "Enhancement"
effort: "Medium"
dependsOn:
  - F10
  - F22
acceptanceCriteria:
  - AC23-1: "The system shall generate a 'low GPU utilisation' recommendation when a model's GPU utilisation across all running replicas is below 60 % for a sustained period of at least 10 consecutive collection cycles."
  - AC23-2: "The system shall generate a 'high queue depth' recommendation when the average waiting-request queue depth exceeds 16 for more than 5 consecutive collection cycles and KV-cache pressure is simultaneously above 80 %."
  - AC23-3: "The system shall generate a 'high error rate' recommendation when the request error rate (4xx or 5xx) exceeds 5 % or the request truncation rate exceeds 10 % over any 60-second rolling window."
  - AC23-4: "The system shall generate a 'throughput imbalance' recommendation when the standard deviation of throughput across TP-grouped GPUs exceeds 3 × the mean throughput of that group."
  - AC23-5: "The system shall run the recommendation evaluator every 30 seconds via a background Celery beat task and use a Redis set to prevent duplicate in-flight recommendations for the same (model_id, rule) tuple."
  - AC23-6: "The system shall expose a JSON:API resource at /api/v1/recommendations supporting list, show, and PATCH (to dismiss, snooze, or apply) operations, backed by a 'recommendations' database table."
---

## Description

The Model Optimization Recommendations feature provides a rule-based recommendation engine that continuously monitors telemetry collected by the metric-ingestion pipeline (F10) and the running-model registry maintained by the Manage Running Models feature (F22). By evaluating a small set of deterministic rules against the latest metrics for every active model replica, the engine surfaces actionable, prioritised suggestions that help operators reduce cost, improve throughput, and preempt capacity bottlenecks before they degrade serving quality.

Each recommendation is classified with a severity level (**info**, **warning**, **critical**), a human-readable summary, a detailed explanation, and a reference to the specific model(s) and metric values that triggered it. The engine uses a Redis-backed deduplication guard to prevent flooding the database with identical in-flight recommendations for the same (model_id, rule) pair; once a recommendation is dismissed, snoozed, or applied, a new one for the same rule and model may be generated on the next evaluation cycle. The frontend surfaces these recommendations in a dedicated panel where operators can triage them quickly, optionally navigating to the corresponding model detail view or triggering a scaling action (F14, F34) directly from the recommendation card.

Operators can interact with each recommendation via a JSON:API-compliant endpoint:
  - **Dismiss** – permanently remove the recommendation.
  - **Snooze** – suppress the recommendation for a configurable duration (default 7 days).
  - **Apply** – mark the recommendation as accepted and trigger the suggested remediation if an automated action is available (e.g., scale up a model group, adjust concurrency limits).
  - **Acknowledge** – leave the recommendation visible but mark it as seen, so the operator can review it later without it counting as "unaddressed".

The recommendation engine is deliberately kept as a stateless, deterministic evaluator so that its behaviour is fully auditable and can be tested with static metric snapshots. It runs as a periodic Celery beat task every 30 seconds, reads the latest metrics from the time-series database (via F10's aggregated views), and writes new recommendations to the `recommendations` relational table. The frontend polls or subscribes to the endpoint to keep the recommendation panel up to date without requiring a page refresh.

---

## Examples

### Example 1: Low GPU utilisation (info)

```json
POST /api/v1/recommendations/evaluate  (internal – triggered by Celery beat)

[
  {
    "id": "rec_01JABCDEFGHIJKLMNOPQRSTUV",
    "model_id": "mod_llama_3_1_8b_instruct",
    "replica_id": "rep_gpu_0a1b2c3d",
    "rule": "low_gpu_util",
    "severity": "info",
    "title": "Low GPU utilisation – llama-3.1-8b-instruct",
    "detail": "GPU utilisation on host worker-4 (GPU 3) has averaged 34 % over the last 10 collection cycles (threshold: < 60 % for ≥ 10 cycles). Consider consolidating this replica or reducing the instance count to improve cost efficiency.",
    "metrics": {
      "avg_gpu_util_pct": 34.2,
      "collection_cycles": 10,
      "threshold": 60,
      "gpu_ids": ["worker-4:GPU:3"],
      "host": "worker-4"
    },
    "severity_score": 25,
    "state": "active",
    "created_at": "2026-05-14T10:32:00Z"
  }
]
```

### Example 2: High queue depth + KV cache pressure (critical)

```json
[
  {
    "id": "rec_02KLMNOPQRSTUVWXYZ0123456",
    "model_id": "mod_llama_3_1_8b_instruct",
    "replica_id": "rep_gpu_7e8f9a0b",
    "rule": "high_queue_depth",
    "severity": "critical",
    "title": "Queue depth critical – llama-3.1-8b-instruct (replica rep_gpu_7e8f9a0b)",
    "detail": "Average waiting-request queue depth over the last 5 collection cycles is 43 (threshold: > 16) and KV-cache utilisation is at 91 % (threshold: > 80 %). The replica is at high risk of saturation. Consider scaling up the model group or increasing the max-concurrent-requests setting.",
    "metrics": {
      "avg_queue_depth": 43.0,
      "queue_collection_cycles": 5,
      "queue_threshold": 16,
      "kv_cache_util_pct": 91.0,
      "kv_cache_threshold": 80,
      "gpu_ids": ["worker-2:GPU:0", "worker-2:GPU:1"],
      "host": "worker-2"
    },
    "severity_score": 90,
    "state": "active",
    "created_at": "2026-05-14T10:32:05Z"
  }
]
```

### Example 3: High error / truncation rate (warning)

```json
[
  {
    "id": "rec_03PQRSTUVWXYZ0123456789A",
    "model_id": "mod_mixtral_8x7b_instruct",
    "rule": "high_error_rate",
    "severity": "warning",
    "title": "Elevated error / truncation rate – mixtral-8x7b-instruct",
    "detail": "Over the last 60-second window the request error rate (4xx / 5xx) is 7.2 % (threshold: > 5 %) and the truncation rate is 14.5 % (threshold: > 10 %). The model may be receiving malformed requests or the context window may be too small for the current workload. Investigate recent client traffic patterns and review the model's max-context-length configuration.",
    "metrics": {
      "error_rate_pct": 7.2,
      "error_rate_threshold": 5.0,
      "truncation_rate_pct": 14.5,
      "truncation_rate_threshold": 10.0,
      "window_seconds": 60,
      "total_requests": 1520
    },
    "severity_score": 60,
    "state": "active",
    "created_at": "2026-05-14T10:35:00Z"
  }
]
```

### Example 4: Throughput imbalance across TP GPUs (warning)

```json
[
  {
    "id": "rec_04BCDEFGHIJKLMNOPQRSTUVW",
    "model_id": "mod_llama_3_1_70b_instruct",
    "rule": "throughput_imbalance",
    "severity": "warning",
    "title": "Throughput imbalance detected – llama-3.1-70b-instruct (TP group tp-group-3)",
    "detail": "Across the 4 GPUs in tensor-parallel group tp-group-3, the standard deviation of throughput-per-GPU over the last 10 collection cycles is 142 req/s, which exceeds 3 × the group mean (38 req/s). This imbalance indicates possible network or memory-bandwidth skew between the GPUs. Investigate NCCL topology and NUMA affinity for the affected hosts.",
    "metrics": {
      "tp_group": "tp-group-3",
      "gpu_count": 4,
      "per_gpu_throughput": { "worker-1:GPU:0": 85, "worker-1:GPU:1": 312, "worker-1:GPU:2": 91, "worker-1:GPU:3": 298 },
      "group_mean_throughput": 196.5,
      "group_stddev_throughput": 114.1,
      "stddev_threshold_multiplier": 3.0,
      "collection_cycles": 10
    },
    "severity_score": 55,
    "state": "active",
    "created_at": "2026-05-14T10:38:00Z"
  }
]
```

### Example 5: User dismisses a recommendation via API (PATCH)

```json
PATCH /api/v1/recommendations/rec_01JABCDEFGHIJKLMNOPQRSTUV
Content-Type: application/vnd.api+json

{
  "data": {
    "type": "recommendations",
    "id": "rec_01JABCDEFGHIJKLMNOPQRSTUV",
    "attributes": {
      "action": "dismiss"
    }
  }
}

→ 200 OK

Response:
{
  "data": {
    "type": "recommendations",
    "id": "rec_01JABCDEFGHIJKLMNOPQRSTUV",
    "attributes": {
      "model_id": "mod_llama_3_1_8b_instruct",
      "rule": "low_gpu_util",
      "state": "dismissed",
      "dismissed_at": "2026-05-25T09:15:00Z",
      "suppress_until": "2026-06-01T09:15:00Z"
    }
  }
}
```

---

## Acceptance Criteria

**AC23-1 — Low GPU utilisation rule evaluation**

Given a model with at least one running replica, when the GPU utilisation across all GPUs of that replica is below 60 % for 10 or more consecutive metric collection cycles, then the system shall generate an "info"-severity recommendation with rule `low_gpu_util` and a `severity_score` between 20 and 40.

**AC23-2 — High queue depth rule evaluation**

Given a model with at least one running replica, when the average waiting-request queue depth exceeds 16 for more than 5 consecutive collection cycles **and** the KV-cache utilisation on that replica is simultaneously above 80 %, then the system shall generate a "critical"-severity recommendation with rule `high_queue_depth` and a `severity_score` between 80 and 100.

**AC23-3 — High error / truncation rate rule evaluation**

Given a model with at least one running replica, when the request error rate (4xx or 5xx) exceeds 5 % or the request truncation rate exceeds 10 % over any 60-second rolling window, then the system shall generate a "warning"-severity recommendation with rule `high_error_rate` and a `severity_score` between 50 and 70.

**AC23-4 — Throughput imbalance rule evaluation**

Given a model whose replicas are deployed across a tensor-parallel GPU group of size ≥ 2, when the standard deviation of throughput across the GPUs in that group exceeds 3 × the group mean throughput, then the system shall generate a "warning"-severity recommendation with rule `throughput_imbalance` and a `severity_score` between 40 and 65.

**AC23-5 — Periodic evaluator with deduplication**

The system shall run the recommendation evaluator every 30 seconds via a Celery beat task. Before inserting a new recommendation, the evaluator SHALL check a Redis set keyed by `(model_id, rule)` and skip insertion if an active, non-dismissed, non-snoozed entry already exists for that tuple. Entries SHALL be removed from the Redis guard set when the recommendation transitions out of the `active` state.

**AC23-6 — JSON:API resource and database migration**

The system shall expose a JSON:API-compliant endpoint at `/api/v1/recommendations` supporting `GET` (list with pagination and filtering by model_id, rule, state, and severity), `GET /{id}` (show single recommendation), and `PATCH /{id}` (transition state: dismiss, snooze, apply, acknowledge). A database migration SHALL create the `recommendations` table with at least the columns: `id (UUID PK)`, `model_id (FK → models.id)`, `replica_id (nullable)`, `rule (VARCHAR)`, `severity (ENUM: info/warning/critical)`, `title (TEXT)`, `detail (TEXT)`, `metrics (JSONB)`, `severity_score (INT)`, `state (ENUM: active/dismissed/snoozed/applied/acknowledged)`, `suppress_until (TIMESTAMPTZ, nullable)`, `created_at`, `updated_at`, and `dismissed_at (nullable)`.

---

## Technical Notes

**File layout (new service):**
```
backend/
  recommendations/
    __init__.py
    models.py              # SQLAlchemy model (Recommendation)
    schema.py              # Marshmallow / Pydantic schemas for JSON:API
    rules.py               # Rule evaluator functions (low_gpu_util, high_queue_depth, …)
    evaluator.py           # Celery task orchestration + Redis dedup
    resources.py           # Flask-RESTful / FastAPI route definitions
    cli.py                 # Management commands (re-evaluate, purge old)
    migrations/
      XXXX_create_recommendations.py
    tests/
      test_rules.py
      test_evaluator.py
      test_api.py
```

**Service architecture (Celery beat + FastAPI):**
```python
# evaluator.py  (conceptual skeleton)
from celery import Celery
from redis import Redis
from models import Recommendation, db
from rules import evaluate_low_gpu_util, evaluate_high_queue_depth, …

celery_app = Celery("recommendations")
redis_client = Redis.from_url("redis://...")

RULES = [
    ("low_gpu_util",      evaluate_low_gpu_util,      30),
    ("high_queue_depth",  evaluate_high_queue_depth,   30),
    ("high_error_rate",   evaluate_high_error_rate,    30),
    ("throughput_imbalance", evaluate_throughput_imbalance, 30),
]

@celery_app.task(name="recommendations.evaluate")
def evaluate_all_rules():
    for rule_name, evaluator_fn, _ in RULES:
        results = evaluator_fn()   # queries metric views, returns list of candidate dicts
        for rec in results:
            dedup_key = f"rec_guard:{rec['model_id']}:{rule_name}"
            if redis_client.sismember("rec_guard_set", dedup_key):
                continue
            recommendation = Recommendation(**rec, state="active")
            db.session.add(recommendation)
            redis_client.sadd("rec_guard_set", dedup_key)
        db.session.commit()
```

**Thresholds reference:**
| Rule                   | Metric(s)                        | Condition                                    | Severity |
|------------------------|----------------------------------|----------------------------------------------|----------|
| `low_gpu_util`         | avg GPU utilisation %            | < 60 % for ≥ 10 consecutive cycles           | info     |
| `high_queue_depth`     | avg queue depth + KV-cache util  | queue > 16 for ≥ 5 cycles AND KV > 80 %      | critical |
| `high_error_rate`      | error rate % + truncation rate % | error > 5 % OR truncation > 10 % in 60 s     | warning  |
| `throughput_imbalance` | per-GPU throughput (stddev/mean) | stddev > 3 × mean across TP group (≥ 2 GPUs) | warning  |

**Frontend component (Vue / Nuxt):**
- `RecommendationPanel.vue` – slide-out panel listing recommendations ordered by `severity_score DESC`, grouped by state (`active` at top).
- `RecommendationCard.vue` – individual card displaying severity badge, title, detail, timestamp, and action buttons (Dismiss, Snooze, Acknowledge, Apply).
- Auto-polls `GET /api/v1/recommendations?filter[state]=active` every 15 seconds; transitions to WebSocket subscription when available.

**Edge cases:**
- Model is stopped / removed between evaluation cycles – the evaluator should skip models that no longer have running replicas (F22 integration) to avoid stale recommendations.
- A replica transitions from "running" to "stopping" during evaluation – the evaluator should tolerate partial metric sets and skip the replica gracefully.
- Redis is unavailable – the evaluator should degrade to a local in-memory dedup set and log a warning, rather than failing the entire evaluation cycle.
- Burst of recommendations for the same model across different rules – each rule evaluated independently; a single model could appear in multiple active recommendations simultaneously.
- Snoozed recommendations that expire – a periodic Celery task (every 5 minutes) should re-`touch` the Redis guard set for recommendations whose `suppress_until` has passed, allowing re-evaluation to produce a fresh recommendation.

**Integration points:**
- **F10** (Metric Ingestion) – consumes pre-aggregated metric views (avg GPU util, queue depth, KV-cache, error rate, truncation rate, per-GPU throughput).
- **F14** (Autoscaling) – "Apply" action on a `high_queue_depth` recommendation may trigger a scale-up via F14's API.
- **F15** (Alerting) – `critical`-severity recommendations should emit an alert via the alerting pipeline for immediate operator notification.
- **F16** (Model Dashboard) – recommendation detail view should deep-link to the model-dashboard page for that model/replica.
- **F22** (Manage Running Models) – queries the running-models registry to determine which models and replicas are active on each evaluation cycle.
- **F34** (Scaling) – "Apply" on `low_gpu_util` may trigger a scale-down recommendation to reduce instance count.
