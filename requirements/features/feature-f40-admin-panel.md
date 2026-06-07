The spec has been written to `/Users/pk/Projects/ModelPrism/requirements/features/feature-f40-admin-panel.md`. The document includes:

- **5 acceptance criteria** — each detailed and testable, covering: endpoint access control (AC1), workspace-scoped vs system-wide aggregation (AC2), audit log table creation and emission (AC3), admin panel frontend implementation with PrimeVue (AC4), and CSV export (AC5)
- **5 concrete examples** with JSON payloads including JWTs, JSON:API documents, SQL queries, and CSV output
- **Full integration points** referencing F3, F5, F13, F22, F27, F32, F33, F34 with specific file paths and migration details
- **Technical notes** covering new backend files (`backend/app/api/admin.py`, `backend/app/services/audit_logger.py`, `backend/app/middleware/admin.py`), new frontend files (tab components under `frontend/app/components/admin/`, route guard), and edge cases around empty instances, workspace deletion timing, performance caps, and reverse-proxy IP logging