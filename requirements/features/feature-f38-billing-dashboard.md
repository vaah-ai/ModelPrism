The file has been written. Here's a summary of what's in the completed feature spec:

**F38: Billing Dashboard** — 7 acceptance criteria, 6 concrete examples with full JSON payloads, and comprehensive technical notes.

Key design decisions reflected in the spec:

- **Three backend aggregate endpoints** (`/api/billing/summary`, `/api/billing/breakdown`, `/api/billing/per-key`) plus one Stripe-proxying endpoint (`/api/billing/subscription`)
- **Self-hosted mode** handled gracefully: `billing_model` flag from `workspaces.cloud_mode`, subscription card replaced with info banner, server-hourly cost gated on F36 rate configuration
- **Stacked-bar chart** with blue (per-token inference from F29) and green (server-hourly from F36) segments
- **Per-key drill-down** via `GET /api/billing/per-key`, linking to F27 key management pages
- **Stripe integration** proxied through the backend (not direct frontend Stripe calls), with Redis caching to avoid rate limits
- **Cents-based precision** throughout with `_display` computed strings
- **Role-based access**: billing data visible to all roles, subscription endpoint restricted to `owner`
- **Integrations**: F5 (auth), F14 (MetricCard), F17 (time range), F27 (API keys), F29 (usage records), F32 (cloud_mode), F33 (RBAC), F34 (isolation), F35 (retention warning), F36 (hourly rates), F37 (Stripe)
