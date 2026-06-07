The file has been written to `/Users/pk/Projects/ModelPrism/requirements/features/feature-f12-agent-log-streaming.md`.

The specification covers:

- **4 acceptance criteria** (AC1–AC4) — log ingestion validation, real-time WebSocket broadcast, historical JSON:API retrieval with filtering/pagination, and retention enforcement
- **4 concrete examples** with full JSON payloads — single error entry, batch of deployment progress, historical retrieval with level filter, and reconnection replay after network outage
- **Integration points** referencing F1 (backend scaffolding), F3 (database schema), F7 (agent WebSocket connection), F15 (dashboard log viewer), F16 (WS broadcast), F19 (deployment log viewer), F32/F35 (workspace data retention)
- **Real file paths** across all four layers: agent (`log_streamer.py`), backend route (`agent_logs.py`), service (`log_service.py`, `retention_service.py`), WS broadcast (`dashboard_ws.py`), frontend components (`LiveLog.vue`, `DeploymentLogViewer.vue`)
- **SQL schema** with indexed columns, **agent-side buffering** with backoff and bounded circular buffer, **log truncation for display**, **UI behavior** for the log viewer