The file has been written to `/Users/pk/Projects/ModelPrism/requirements/features/feature-f33-role-based-access.md`. Here's a summary of what's in the document:

**6 Acceptance Criteria:**
1. Every dashboard API endpoint enforces a minimum role via `@requires_role` decorator (40+ endpoint×role combinations tested)
2. Frontend conditionally renders UI elements based on role using `useAuthorization` composable with `v-if` guards
3. Service-layer guard clauses re-verify role from database on sensitive operations (defence against stale JWT)
4. WebSocket command dispatch enforces role-based authorization with real-time DB re-verification
5. Role changes take effect immediately via Redis pub/sub + WebSocket `role_changed` events
6. The permission matrix is verifiable from a single source of truth (`rbac_matrix.py`)

**5 Concrete Examples with JSON payloads:**
1. Viewer attempts model deployment → HTTP 403 with JSON:API error showing `insufficient_role`
2. Admin invites a member, fails to promote to admin (owner-only), with `LAST_OWNER` protection
3. Viewer dashboard renders all read-only content, hides all mutating controls
4. Owner deletes workspace — service-layer DB re-verification catches stale JWT demotion
5. Member sends `deploy_model` WebSocket command → error returned, agent never contacted

**Technical notes** cover the complete 30+ row permission matrix, `@requires_role` decorator implementation, WebSocket command role mapping, the frontend `useAuthorization` composable, service-layer guard pattern, Redis pub/sub event broadcast, middleware ordering (Auth → RBAC → Workspace Scope), and integration points with F5, F11, F16, F27, F28, F30, F32, F34, and F40.