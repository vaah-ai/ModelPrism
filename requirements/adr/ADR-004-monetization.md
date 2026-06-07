# ADR-004: Monetization Model

## Status
Accepted

## Context
ModelPrism needs a clear monetization strategy before building billing infrastructure. Options considered:

1. **Fully open source** — all code OSS, revenue from hosting only
2. **Open core** — core platform OSS, advanced features paid
3. **Source available** — code visible but license restricts commercial use

Initial requirements described Stripe metered billing but were ambiguous about whether billing code ships in the OSS repository.

## Decision
**Open core model:**

- **Core platform** (OSS, Apache 2.0): agent, dashboard, model management, benchmarking, monitoring, basic user management, server hourly pricing cost comparison
- **Cloud-only features** (SaaS): multi-tenant API proxy with key management, usage analytics across workspaces, SSO, Stripe billing integration
- `MODELPRISM_CLOUD` env var controls mode (default `false` for self-hosted)
- Billing code lives in the open-source repo behind the feature flag — users can see and audit it, but it only activates with Stripe API keys

## Consequences
- Clear monetization path without restricting OSS users
- Core platform is valuable standalone
- Billing infrastructure investment justified by cloud revenue
- No surprise for self-hosted users — documented in README from day one
