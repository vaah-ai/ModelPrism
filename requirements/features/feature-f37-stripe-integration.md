The feature specification has been written to `/Users/pk/Projects/ModelPrism/requirements/features/feature-f37-stripe-integration.md`. The document includes:

- **8 acceptance criteria** (exceeding the 6 minimum), each detailed and testable with clear Given/When/Then and measurable thresholds
- **5 concrete examples** with full JSON payloads showing the Stripe Checkout flow, webhook processing, meter event batching, invoice handling, and subscription cancellation
- **Integration points** referencing F3, F5, F29, F30, F32, F33, F34, F35, F38, and F39 with specific file paths and column names
- **Actual file paths** from the ModelPrism directory structure (new files under `backend/app/models/billing.py`, `backend/app/services/billing_worker.py`, etc.)
- **JSON:API format** for all dashboard REST endpoints, including the checkout, subscription, invoice, and cancel resource types
- **UUIDv7**, ISO 8601 timestamps, and real-world model names throughout
- **Full table schemas** (`billing_webhook_events`, `billing_invoices`, `billing_meter_errors`) with constraints and indexes
- **Migrations** reference (`0007_stripe_billing.py`) for the Alembic migration
- **Edge cases** including historical record push, webhook race conditions, zero-dollar records, and network partitions