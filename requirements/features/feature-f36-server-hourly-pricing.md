# F36 — Server Hourly Pricing

## Description

Allow operators to assign an **hourly rate** (in USD) to each GPU server. This rate is used exclusively for **internal cost tracking and display** — it is **never sent to Stripe** and does not affect customer billing. The value is purely informational, helping operators estimate server-level running costs and compare them against what the same workload would cost via a cloud API.

The feature is available in both **self-hosted** and **cloud** mode, subject to the same RBAC gates defined in F33.

---

## Examples

### Example 1 — Setting an hourly rate on a server

An operator configures a 4×A100 HGX server at $32.77/hr.

**Request** (JSON:API `PATCH /api/servers/<uuid>`):

```json
{
  "data": {
    "type": "servers",
    "id": "4a1f2c3e-8b7d-4e9f-a012-3456789abcde",
    "attributes": {
      "hourly_rate_usd": 32.77
    }
  }
}
```

**Response** (200):

```json
{
  "data": {
    "type": "servers",
    "id": "4a1f2c3e-8b7d-4e9f-a012-3456789abcde",
    "attributes": {
      "label": "HGX-4xA100",
      "hourly_rate_usd": 32.77,
      "gpu_count": 4,
      "gpu_model": "A100-SXM-80GB",
      "status": "online"
    }
  }
}
```

---

### Example 2 — Fleet cost summary on the overview page

The overview DataTable (F10) now includes two new column groups after the existing GPU/GHB columns:

| Server | GPUs | vRAM | GHB/s | $/hr | Est. Daily | Est. Monthly |
|--------|------|------|-------|------|------------|--------------|
| HGX-4xA100  | 4× A100 80 GB | 2 560 GB | 12 800 | **$32.77** | $786.48 | $23 594.40 |
| DGX-B200    | 8× B200 141 GB | 4 512 GB | 36 000 | **$21.50** | $516.00 | $15 480.00 |
| HGX-8×H100  | 8× H100 80 GB | 2 560 GB | 28 000 | **$41.93** | $1 006.32 | $30 189.60 |

**Response** — `GET /api/servers?include=cost-summary`:

The endpoint appends a `cost-summary` included resource with pre-computed daily (24 h) and monthly (730 h) projections.

---

### Example 3 — Cost comparison chart on single-server dashboard

The server dashboard (F17) gains a new **Cost Comparison** card that contrasts the server's hourly rate against equivalent cloud API pricing.

The chart uses the hourly rate multiplied by actual uptime hours over a selectable period (7 d / 30 d / 90 d) and overlays a hypothetical cloud cost for the same number of inference tokens generated.

**Data source** — `GET /api/servers/<uuid>/cost-comparison?range=30d`:

```json
{
  "data": {
    "type": "cost-comparisons",
    "attributes": {
      "server_hourly_rate": 32.77,
      "server_uptime_hours": 672.0,
      "server_total_cost": 22021.44,
      "tokens_generated": 840000000,
      "cloud_rate_per_1m_tokens": 0.15,
      "cloud_equivalent_cost": 126.00,
      "savings_vs_cloud_pct": 99.43
    }
  }
}
```

The card displays two bars — **Server Cost** vs **Cloud Equivalent** — making the value proposition of self-hosting immediately visible.

---

### Example 4 — Clearing a rate (decommissioning a server)

When a server is marked as `offline` or decommissioned, the operator may optionally clear its hourly rate.

**Request** — `PATCH /api/servers/<uuid>`:

```json
{
  "data": {
    "type": "servers",
    "id": "4a1f2c3e-8b7d-4e9f-a012-3456789abcde",
    "attributes": {
      "hourly_rate_usd": null,
      "status": "offline"
    }
  }
}
```

**Response** (200): the `hourly_rate_usd` field is now `null`.

---

### Example 5 — Bulk inline editing from the overview DataTable

The overview DataTable exposes the `$ / hr` column as an **inline-editable number field** (F10 inline-edit pattern). The user clicks the value and types a new number; pressing Enter fires a bulk `PATCH /api/servers` with only the changed field.

**Request** — `PATCH /api/servers`:

```json
{
  "data": [
    {
      "type": "servers",
      "id": "4a1f2c3e-8b7d-4e9f-a012-3456789abcde",
      "attributes": { "hourly_rate_usd": 35.00 }
    },
    {
      "type": "servers",
      "id": "b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
      "attributes": { "hourly_rate_usd": 22.75 }
    }
  ]
}
```

**Response** — `207 Multi-Status` with per-resource results.

---

## Acceptance Criteria

| ID | Criterion | Verification |
|----|-----------|-------------|
| **ACF36-1** | Rate can be set, updated, and cleared via JSON:API `PATCH /api/servers/<uuid>`. Value is persisted in `servers.hourly_rate_usd`. Validation rejects negative values and values > 999.99. | Unit test + curl |
| **ACF36-2** | Fleet‑level endpoint (`GET /api/servers?include=cost-summary`) returns aggregate daily and monthly projections for all servers with a non‑null hourly rate. Projections are computed server‑side. | Integration test |
| **ACF36-3** | Single‑server cost‑comparison endpoint (`GET /api/servers/<uuid>/cost-comparison?range=30d`) returns server cost, cloud equivalent, and savings percentage. Cloud rate per million tokens is configurable via a new `CLOUD_INFERENCE_RATE_PER_1M` env var (default: $0.15). | E2E test + visual inspection of dashboard chart |

---

## Technical Notes

### Data Model

- **Migration** — Add column `hourly_rate_usd NUMERIC(7,2)` to `servers` table (nullable, default `NULL`).
- **Pydantic** — Add `hourly_rate_usd: Optional[Decimal]` to `ServerUpdate` schema. Field-level validator: `Field(ge=0, le=999.99)`.

### Backend

- **Route** — The existing `PATCH /api/servers/<uuid>` handler (F14) already supports partial updates; only the new field needs wiring.
- **Bulk route** — A new `PATCH /api/servers` (plural) endpoint handles inline‑edit batches. Returns `207 Multi-Status`.
- **Cost-summary include** — Add a `cost-summary` relationship/calculator in `backend/app/services/server_cost.py`. Logic:
  - daily = hourly_rate × 24
  - monthly = hourly_rate × 730 (365 ÷ 12 × 24)
- **Cost-comparison endpoint** — New route in `backend/app/routes/servers.py`. Reads uptime from `server_uptime_events` (F34), multiplies by hourly rate, loads `CLOUD_INFERENCE_RATE_PER_1M`, computes cloud equivalent from tokens generated (F15 metric).

### Frontend

- **Overview DataTable** (`frontend/app/pages/dashboard/index.vue`):
  - Add columns: `$ / hr`, `Est. Daily`, `Est. Monthly`
  - `$ / hr` column uses inline‑edit component (F10 inline‑edit pattern)
  - Estimated columns are read‑only; computed from `cost-summary` include
- **Server Dashboard** (`frontend/app/pages/dashboard/[id].vue`):
  - New **Cost Comparison** card below the existing GPU utilisation chart
  - Two‑bar chart (server cost vs cloud equivalent) using the same charting lib as F34 (Chart.js or ApexCharts)
  - Period selector (7 d / 30 d / 90 d) that refetches the cost-comparison endpoint
- **Empty state**: when `hourly_rate_usd` is `null`, the dashboard hides the cost card and shows a "Set hourly rate to see cost estimates" prompt with a link to the overview DataTable.

### Permissions (F33)

| Action | Permission Slug | Grants |
|--------|----------------|--------|
| View hourly rate | `servers:read` | `admin`, `operator`, `viewer` |
| Set / edit / clear hourly rate | `servers:update` | `admin`, `operator` |

### Dependencies

| Feature | Relationship |
|---------|-------------|
| **F10** — Overview DataTable | Inline‑edit pattern reused for `$ / hr` column |
| **F14** — Server CRUD | Single‑server `PATCH` handler extended |
| **F15** — Per‑server telemetry | Token‑count metric consumed by cost‑comparison |
| **F17** — Server Dashboard | Hosts the new Cost Comparison card |
| **F29** — Cloud / Self‑Hosted mode toggle | Feature available in both modes |
| **F33** — RBAC & Permissions | Gates as shown above |
| **F34** — Server uptime tracking | Uptime hours consumed by cost‑comparison |