# F32: Workspace Management

## Metadata
- **ID:** F32
- **Phase:** Scale
- **Effort:** Medium
- **Dependencies:** F3, F5
- **Acceptance Criteria Count:** 7

## Description

Feature F32 implements full workspace lifecycle management — creation, configuration, member management, settings, and deletion — giving each workspace tenant a self-contained operational unit within ModelPrism. A workspace is the top-level organisational boundary in the platform: every resource (agents, model deployments, API keys, usage records, benchmarks) belongs to exactly one workspace, and all queries enforce workspace-scoped data isolation via the `workspace_id` foreign key column defined in F3.

The feature covers four functional areas. First, **workspace settings** exposes a JSONB `settings` column on the `workspaces` table (F3) and a dedicated JSON:API endpoint for reading and updating workspace-level preferences: data retention period (how long agent metrics and logs are kept before cleanup), theme default (light/dark/system), time zone for dashboard display, notification preferences, rate limit defaults for API keys (RPM, TPM), and model deployment default parameters (default quantization, default `max_model_len`). Second, **member management** provides a complete CRUD interface for `workspace_members` (F3): inviting users by email (creating pending membership rows), accepting invitations, listing members with their roles, changing roles (`owner` / `admin` / `member` / `viewer`), and removing members. Third, the **workspace dashboard** surfaces a summary view showing total active agents, running model deployments, active API keys, workspace-wide usage statistics aggregated for the current billing period (F29), and a member activity feed. Fourth, **workspace deletion** handles the full teardown cascade: confirming via a secondary verification prompt (user must type the workspace name), performing a soft-delete by setting a `deleted_at` timestamp, initiating a background cleanup job that reaps all associated resources asynchronously (F3 `ON DELETE CASCADE` handles the database side), and offering a grace-period undo within 7 days.

The feature integrates with F5 (auth) by deriving the caller's workspace from their JWT session context — every endpoint in F32 is workspace-scoped. It integrates with F3 (database schema) by reading and writing the `workspaces` and `workspace_members` tables with their existing column structure. It integrates with F6 (agent registration) for generating one-click workspace-level registration tokens, and with F27 (API keys) and F29 (usage tracking) for workspace-level aggregate statistics on the dashboard. Future features F33 (RBAC refinement) and F37 (Stripe billing) will build on top of this workspace management foundation.

## Concrete Examples (Specification by Example)

### Example 1: Workspace Settings Update — Retention and Defaults

- **Input:** A workspace admin navigates to Dashboard → Settings, modifies the data retention period from 30 to 90 days, changes the default theme to `dark`, and sets a default RPM limit of 120 for new API keys. They click "Save".

- **Action:** The frontend calls `PATCH /api/workspace/settings` with a JSON:API request body:

  ```json
  {
    "data": {
      "type": "workspaceSettings",
      "id": "ws-11111111-2222-3333-4444-555555555555",
      "attributes": {
        "retentionDays": 90,
        "themeDefault": "dark",
        "timezone": "UTC",
        "defaults": {
          "rateLimits": { "rpmMax": 120, "tpmMax": null },
          "deploymentDefaults": {
            "quantization": "fp8",
            "maxModelLen": 16384,
            "gpuMemoryUtilization": 0.85
          }
        },
        "notifications": {
          "agentOffline": true,
          "deploymentFailed": true,
          "usageThresholdPercent": 80
        }
      }
    }
  }
  ```

- **Expected Output:** HTTP 200 OK. Response body (JSON:API):

  ```json
  {
    "data": {
      "type": "workspaceSettings",
      "id": "ws-11111111-2222-3333-4444-555555555555",
      "attributes": {
        "name": "Alice's Workspace",
        "slug": "alices-workspace",
        "retentionDays": 90,
        "themeDefault": "dark",
        "timezone": "UTC",
        "defaults": {
          "rateLimits": { "rpmMax": 120, "tpmMax": null },
          "deploymentDefaults": {
            "quantization": "fp8",
            "maxModelLen": 16384,
            "gpuMemoryUtilization": 0.85
          }
        },
        "notifications": {
          "agentOffline": true,
          "deploymentFailed": true,
          "usageThresholdPercent": 80
        },
        "createdAt": "2026-04-01T12:00:00+00:00",
        "updatedAt": "2026-06-07T15:30:00+00:00"
      },
      "links": {
        "self": "/api/workspace/settings"
      }
    }
  }
  ```

- **Side effect:** The `workspaces` row is updated: `settings` JSONB column now contains the full settings object. The retention cleanup job (F35) reads `retentionDays` from this column on its next run to determine which `agent_metrics` and `agent_logs` rows to purge. New API keys created after this update will inherit `rate_limits.rpmMax = 120` as their default scope unless overridden during creation (F27).

### Example 2: Invite Member by Email

- **Input:** An admin navigates to Dashboard → Workspace → Members, clicks "Invite Member", enters `bob@example.com`, selects role `member`, and clicks "Send Invitation".

- **Action:** The frontend calls `POST /api/workspace/members/invite` with a JSON:API request body:

  ```json
  {
    "data": {
      "type": "workspaceInvitations",
      "attributes": {
        "email": "bob@example.com",
        "role": "member"
      }
    }
  }
  ```

- **Action (backend):** The backend checks that the caller has role `owner` or `admin` (403 if not). It looks up the user by email in the `users` table:

  - **If user exists:** Creates a `workspace_members` row with `user_id` set (immediate activation), `role = "member"`, `invited_by = caller_id`, and sends an email notification (or console log in development) with the message: `"You've been added to Alice's Workspace on ModelPrism. Log in at https://dashboard.modelprism.io to get started."`
  - **If user does not exist:** Creates a `workspace_members` row with `user_id = NULL`, `role = "member"`, `invited_by = caller_id`, and sends an email invitation (or console log in development): `"Alice has invited you to join their ModelPrism workspace. Create an account at https://dashboard.modelprism.io/register?invite=ws-11111111-2222-3333-4444-555555555555 to accept."` The row has the `member` role reserved but inactive until the user registers and claims it.

- **Expected Output:** HTTP 201 Created. Response body:

  ```json
  {
    "data": {
      "type": "workspaceMembers",
      "id": "wm-aabbccdd-eeee-ffff-gggg-hhhhiiiijjjj",
      "attributes": {
        "userId": "b1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "email": "bob@example.com",
        "displayName": null,
        "role": "member",
        "status": "active",
        "invitedBy": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "createdAt": "2026-06-07T16:00:00+00:00"
      },
      "links": {
        "self": "/api/workspace/members/wm-aabbccdd-eeee-ffff-gggg-hhhhiiiijjjj"
      }
    },
    "included": [
      {
        "type": "users",
        "id": "b1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "attributes": {
          "email": "bob@example.com",
          "displayName": null
        }
      }
    ]
  }
  ```

  If the user does not yet exist, the response is:
  ```json
  {
    "data": {
      "type": "workspaceMembers",
      "id": "wm-aabbccdd-eeee-ffff-gggg-hhhhiiiijjjj",
      "attributes": {
        "userId": null,
        "email": "bob@example.com",
        "displayName": null,
        "role": "member",
        "status": "pending",
        "invitedBy": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "createdAt": "2026-06-07T16:00:00+00:00"
      },
      "links": {
        "self": "/api/workspace/members/wm-aabbccdd-eeee-ffff-gggg-hhhhiiiijjjj"
      }
    }
  }
  ```

### Example 3: Change Member Role and Remove Member

- **Input A (Change Role):** An `owner` promotes an existing `member` to `admin` in their workspace.

- **Action A:** The frontend calls `PATCH /api/workspace/members/wm-aabbccdd-eeee-ffff-gggg-hhhhiiiijjjj` with:
  ```json
  {
    "data": {
      "type": "workspaceMembers",
      "id": "wm-aabbccdd-eeee-ffff-gggg-hhhhiiiijjjj",
      "attributes": {
        "role": "admin"
      }
    }
  }
  ```

- **Expected Output A:** HTTP 200 OK. The `workspace_members` row has `role = "admin"` updated, `updated_at` timestamp refreshed. Response returns the updated member resource.

- **Input B (Remove Member):** The `owner` clicks "Remove" next to a `viewer`-role member in the members list. A confirmation dialog appears: `"Remove Charlie from this workspace? They will lose access to all workspace resources."`

- **Action B:** The frontend calls `DELETE /api/workspace/members/wm-cccceeee-ffff-aaaa-bbbb-ccccddddeeee`. The backend deletes the `workspace_members` row (or sets `user_id = NULL` and `role = NULL` to preserve the invitation record, depending on the status). The F3 `ON DELETE CASCADE` is not used here — the row is intentionally removed by application code, cascading effects on user-scoped resources (usage records, API keys associated with that user within the workspace) are handled by setting `user_id` references to `NULL` (per F3 `ON DELETE SET NULL` on those FKs).

- **Expected Output B:** HTTP 204 No Content. The member is removed. If the removed user has an active JWT session, their next request to any workspace endpoint returns HTTP 403 with `code: "NOT_A_MEMBER"`. The frontend's auth middleware (F5) checks `workspace_members` membership on every authenticated request, so the access cut-off is immediate.

### Example 4: Workspace Deletion with Grace Period

- **Input:** A workspace `owner` navigates to Dashboard → Workspace → Settings, scrolls to the "Delete Workspace" danger zone, clicks "Delete Workspace". A modal prompts them to type the workspace name (`"Alice's Workspace"`) as confirmation. They type the name and click "Confirm Delete".

- **Action:** The frontend calls `POST /api/workspace/delete` with:
  ```json
  {
    "data": {
      "type": "workspaceDeletion",
      "attributes": {
        "confirmation": "Alice's Workspace",
        "reason": "Migrating to on-premise deployment"
      }
    }
  }
  ```

- **Action (backend):** The backend verifies:
  1. The caller has role `owner` (only owner can delete a workspace).
  2. The `confirmation` string matches `workspaces.name` (case-sensitive match).
  3. No running model deployments exist with status `running` or `healthy` — if they do, the endpoint returns HTTP 409 with `code: "ACTIVE_DEPLOYMENTS"` and a list of deployment names that must be stopped first.
  
  On success, the backend sets `workspaces.deleted_at = now()` (soft-delete), records a `deleted_by` reference (`user_id` of the caller), and initiates an async background task that:
  - Stops all running agents by sending `stop_agent` WebSocket commands (F11)
  - Stops all running model deployments by sending `stop_deployment` commands (F19)
  - After all agents are confirmed stopped, purges associated rows from all scoped tables (the `ON DELETE CASCADE` FKs on the database handle this automatically)
  - Sets `workspaces.cloud_mode = false`

- **Expected Output:** HTTP 202 Accepted. Response body:
  ```json
  {
    "data": {
      "type": "workspaceDeletion",
      "id": "ws-11111111-2222-3333-4444-555555555555",
      "attributes": {
        "status": "pending",
        "deletedAt": "2026-06-07T17:00:00+00:00",
        "deletedBy": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "gracePeriodEndsAt": "2026-06-14T17:00:00+00:00",
        "recoveryToken": "ws-recovery-abc123def456..."
      },
      "meta": {
        "warning": "Your workspace has been scheduled for deletion. You have 7 days to undo this action using the recovery token sent to your email. After the grace period, all data will be permanently removed."
      }
    }
  }
  ```

- **Side effect:** All authenticated users in the workspace are redirected to a "Workspace Pending Deletion" page. New login attempts for this workspace return HTTP 403 with `code: "WORKSPACE_DELETED"`. The recovery token `ws-recovery-abc123def456...` is stored as a SHA-256 hash in a new `workspace_deletion_recovery` column or table (or as a field within `workspaces.settings` JSONB). The owner can use this token within 7 days to `POST /api/workspace/restore` and undo the deletion. After 7 days, a background sweep hard-deletes the workspace row (cascading to all child rows via the database FKs).

- **Input (Restore within grace period):** The owner copies the recovery token from their email and navigates to `/restore-workspace`, entering the token.

- **Action (Restore):** The frontend calls `POST /api/workspace/restore` with:
  ```json
  {
    "data": {
      "type": "workspaceRestore",
      "attributes": {
        "workspaceId": "ws-11111111-2222-3333-4444-555555555555",
        "recoveryToken": "ws-recovery-abc123def456..."
      }
    }
  }
  ```

- **Expected Output (Restore):** HTTP 200 OK. The `deleted_at` and `deleted_by` columns are set to `NULL`. The background deletion task is cancelled. The workspace and all its resources are fully accessible again. All members regain access.

### Example 5: Workspace Dashboard Summary Statistics

- **Input:** A workspace member navigates to the dashboard home page (`/dashboard`). The page should display a high-level summary of workspace health and usage.

- **Action:** The frontend calls `GET /api/workspace/summary` with the authenticated JWT session. The backend aggregates data across several scoped tables for the current workspace:
  - Agent count: `SELECT status, COUNT(*) FROM agents WHERE workspace_id = :ws_id GROUP BY status`
  - Model deployments: `SELECT status, COUNT(*) FROM model_deployments WHERE workspace_id = :ws_id GROUP BY status`
  - Active API keys: `SELECT COUNT(*) FROM api_keys WHERE workspace_id = :ws_id AND status = 'active'`
  - Usage (current month): `SELECT SUM(input_tokens), SUM(output_tokens), SUM(cost_cents) FROM usage_records WHERE workspace_id = :ws_id AND created_at >= date_trunc('month', now())`
  - Active members: `SELECT COUNT(*) FROM workspace_members WHERE workspace_id = :ws_id AND user_id IS NOT NULL`

- **Expected Output:** HTTP 200 OK. Response body (JSON:API):
  ```json
  {
    "data": {
      "type": "workspaceSummary",
      "id": "ws-11111111-2222-3333-4444-555555555555",
      "attributes": {
        "agents": {
          "total": 4,
          "online": 2,
          "offline": 1,
          "paused": 1
        },
        "deployments": {
          "total": 6,
          "healthy": 3,
          "running": 1,
          "stopped": 1,
          "failed": 1
        },
        "activeApiKeys": 3,
        "members": 5,
        "usage": {
          "inputTokens": 14200000,
          "outputTokens": 3800000,
          "totalTokens": 18000000,
          "costCents": 1420,
          "periodStart": "2026-06-01T00:00:00+00:00",
          "periodEnd": "2026-06-30T23:59:59+00:00"
        },
        "recentActivity": [
          {
            "type": "member_joined",
            "description": "Bob joined the workspace",
            "timestamp": "2026-06-07T16:00:00+00:00"
          },
          {
            "type": "deployment_completed",
            "description": "mistral-7b deployed on cyan-koala-42",
            "timestamp": "2026-06-07T14:30:00+00:00"
          },
          {
            "type": "key_created",
            "description": "New API key 'CI/CD pipeline key' created",
            "timestamp": "2026-06-06T10:00:00+00:00"
          }
        ]
      },
      "links": {
        "self": "/api/workspace/summary"
      }
    }
  }
  ```

## Acceptance Criteria

- **ACF32-1: Workspace settings are stored in and retrieved from the JSONB `settings` column** — A `PATCH /api/workspace/settings` request with a partial or full settings payload updates the `workspaces.settings` JSONB column. The `GET /api/workspace/settings` endpoint returns the current settings object merged with defaults. The serializer flattens top-level keys (`retentionDays`, `themeDefault`, `timezone`) and nests `defaults` and `notifications` objects as sub-keys within the JSONB column. Invalid keys (e.g., unknown settings like `"foo": "bar"`) are silently ignored — the backend validates against a known schema. The `updated_at` timestamp on the `workspaces` row is refreshed. The retention cleanup job (F35) reads `settings->>'retentionDays'` on its next cycle and prunes `agent_metrics` and `agent_logs` rows older than that many days.

- **ACF32-2: Member invitation handles both existing and non-existing users** — A `POST /api/workspace/members/invite` with a registered user's email creates a `workspace_members` row with `user_id` set (non-null), `role` as specified, and `status` implicitly `active` (the `user_id` column being non-null indicates the member has a linked account). An invitation to an unregistered email creates a row with `user_id = NULL` and `status = "pending"` (stored in the F3 `workspace_members` structure — the `user_id` FK uses `ON DELETE SET NULL`, making this safe). The `role` column is populated in both cases. Inviting an email address that already has a membership in the workspace (either active or pending) returns HTTP 409 with `code: "ALREADY_MEMBER"`. Only users with role `owner` or `admin` can send invitations; role `member` and `viewer` receive HTTP 403.

- **ACF32-3: Role changes and member removal enforce ownership rules** — A `PATCH /api/workspace/members/{id}` with a new `role` value updates the `workspace_members.role` column. A workspace must always have at least one `owner` — attempting to change the last `owner`'s role to a non-owner role returns HTTP 422 with `code: "LAST_OWNER"`. A `DELETE /api/workspace/members/{id}` removes the membership row. A removed `owner` immediately loses owner access; if they were the only owner, the workspace becomes ownerless and a warning is logged (this scenario is prevented by the `LAST_OWNER` check). The caller must have role `owner` or `admin` to change roles or remove members. An `admin` can remove `member` and `viewer` roles but cannot remove another `admin` or the `owner`. Only the `owner` can remove or demote another `admin`.

- **ACF32-4: Workspace deletion requires typed confirmation and checks active resources** — A `POST /api/workspace/delete` request must include a `confirmation` attribute that matches `workspaces.name` exactly (case-sensitive). If the workspace has any `model_deployments` with status `running` or `healthy`, the endpoint returns HTTP 409 with `code: "ACTIVE_DEPLOYMENTS"` and a `details` array listing the deployment names and IDs. The caller must have role `owner`. On success, the endpoint sets `workspaces.deleted_at` and `workspaces.deleted_by`, returns HTTP 202 with a `recoveryToken` and a `gracePeriodEndsAt` timestamp exactly 7 days in the future. The workspace is immediately inaccessible to all members (the JWT middleware checks `deleted_at IS NULL` before allowing any request). Active WebSocket connections to agents in the workspace are gracefully closed with a `workspace_deleted` close reason.

- **ACF32-5: Deletion recovery is possible within a 7-day grace period** — A `POST /api/workspace/restore` request with a valid `workspaceId` (UUID) and `recoveryToken` (the raw token string returned at deletion time, hashed for storage) restores the workspace: `deleted_at` and `deleted_by` are set to `NULL` and the background sweep task for that workspace is cancelled. The recovery token is SHA-256 hashed before storage and compared against the hash on restoration. A single-use token is consumed on first successful restore — subsequent attempts with the same token return HTTP 400 with `code: "TOKEN_CONSUMED"`. After the 7-day grace period expires, a background Celery Beat or APScheduler task (running daily at 02:00 UTC) hard-deletes all workspaces where `deleted_at + 7 days < now()`, cascading through all F3 foreign keys. The restore endpoint returns HTTP 410 Gone with `code: "GRACE_PERIOD_EXPIRED"` if the grace period has passed.

- **ACF32-6: Workspace summary endpoint aggregates cross-table statistics** — A `GET /api/workspace/summary` request returns a composite JSON:API resource with agent counts grouped by status, deployment counts grouped by status, active API key count, member count, current-month usage totals (input tokens, output tokens, cost in cents), and a `recentActivity` array (last 10 events). The activity array is assembled from the 10 most recent rows across the `workspace_members` (new members), `model_deployments` (status transitions), `api_keys` (creations and revocations), and `agent_logs` (error events) tables for the current workspace, ordered by timestamp descending and limited to 10 entries. The endpoint returns within 500ms for workspaces with up to 50 agents and 100,000 usage records per month. Query performance relies on the composite indexes defined in F3: `ix_agents_workspace_status`, `ix_model_deployments_workspace_status`, `ix_api_keys_workspace_id`, `ix_workspace_members_user_id`, `ix_usage_records_workspace_created`.

- **ACF32-7: Workspace name and slug are unique and immutable after creation** — The `workspaces.slug` column has a UNIQUE constraint at the database level (F3). On workspace creation (F5 registration flow, which is the only creation path), the slug is auto-generated from the workspace name: lowercased, non-alphanumeric characters replaced with hyphens, consecutive hyphens collapsed, trailing hyphens stripped. If the generated slug conflicts with an existing slug, a numeric suffix is appended (e.g., `alices-workspace-1`). The `workspaces.name` can be updated via `PATCH /api/workspace/settings` with a `name` attribute, but the `slug` is never automatically regenerated — it remains frozen at creation time. The slug change requires a separate `PATCH /api/workspace/settings` with an explicit `slug` attribute, which must pass the UNIQUE constraint validation. Attempting to set a slug that matches an existing workspace returns HTTP 422 with `code: "SLUG_TAKEN"`.

## Technical Notes

### File Paths

| Layer | File | Purpose |
|-------|------|---------|
| ORM model | `backend/app/models/workspace.py` | SQLAlchemy `Workspace` model — `id`, `name`, `slug`, `cloud_mode`, `settings` (JSONB), `deleted_at`, `deleted_by`, `created_at`, `updated_at`. Defined in F3, extended with deletion fields. |
| ORM model | `backend/app/models/workspace_member.py` | SQLAlchemy `WorkspaceMember` model — `id`, `workspace_id`, `user_id`, `role` (enum `UserRole`), `invited_by`, `created_at`. Defined in F3. |
| Pydantic schema | `backend/app/schemas/workspace.py` | JSON:API request/response schemas: `WorkspaceSettingsSchema`, `WorkspaceMemberSchema`, `WorkspaceInvitationSchema`, `WorkspaceSummarySchema`, `WorkspaceDeletionSchema`, `WorkspaceRestoreSchema`. Each extends the JSON:API resource object pattern from F4. |
| Route handler | `backend/app/api/workspace.py` | FastAPI router — `GET /api/workspace/settings`, `PATCH /api/workspace/settings`, `GET /api/workspace/summary`, `GET /api/workspace/members`, `POST /api/workspace/members/invite`, `PATCH /api/workspace/members/{id}`, `DELETE /api/workspace/members/{id}`, `POST /api/workspace/delete`, `POST /api/workspace/restore`. |
| Service layer | `backend/app/services/workspace_service.py` | Business logic: settings merge with defaults, member invitation flow, role validation, deletion lifecycle (soft-delete, recovery token generation/hashing, grace period checks, background cleanup dispatch). |
| Frontend page | `frontend/app/pages/dashboard/workspace/settings.vue` | Workspace settings page — retention, theme, timezone, defaults, notification preferences, danger zone (delete). |
| Frontend page | `frontend/app/pages/dashboard/workspace/members.vue` | Member management page — member list table, invite dialog, role change controls, remove member with confirmation. |
| Frontend page | `frontend/app/pages/dashboard/workspace/summary.vue` | Workspace summary / dashboard overview — stats cards, activity feed. |
| Frontend composable | `frontend/app/composables/useWorkspace.ts` | Pinia composable for workspace state: `fetchSettings()`, `updateSettings()`, `fetchSummary()`, `fetchMembers()`, `inviteMember()`, `updateMemberRole()`, `removeMember()`, `deleteWorkspace()`, `restoreWorkspace()`. |
| Frontend page | `frontend/app/pages/restore-workspace.vue` | Unauthenticated page for recovery token entry and workspace restoration. |
| Frontend page | `frontend/app/pages/workspace-deleted.vue` | Page shown to users whose workspace is pending deletion. Displays grace period countdown and contact-support message. |

### WebSocket Integration for Agent Shutdown on Workspace Deletion

When a workspace is soft-deleted, the backend must gracefully shut down any agents connected via WebSocket (F6/F7). The flow is:

```python
# backend/app/services/workspace_service.py (conceptual)
async def soft_delete_workspace(workspace_id: UUID, deleted_by: UUID) -> dict:
    async with db_session.begin():
        ws = await db_session.get(Workspace, workspace_id)
        ws.deleted_at = datetime.now(timezone.utc)
        ws.deleted_by = deleted_by
        # Generate recovery token
        raw_token = secrets.token_urlsafe(32)
        token_hash = sha256(f"ws-recovery-{raw_token}".encode()).hexdigest()
        ws.settings = {
            **(ws.settings or {}),
            "deletion": {
                "token_hash": token_hash,
                "grace_period_ends": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "deleted_by": str(deleted_by)
            }
        }
    # Notify connected agents outside the transaction
    agent_ids = await get_workspace_agent_ids(workspace_id)
    for agent_id in agent_ids:
        ws_manager = get_agent_ws_manager()
        await ws_manager.send(agent_id, {
            "type": "command",
            "command": "stop_agent",
            "params": {"reason": "workspace_deleted", "graceful": True}
        })
    return {"recovery_token": f"ws-recovery-{raw_token}", "grace_period_ends": ...}
```

### Settings JSONB Schema (Validated Keys)

The `workspaces.settings` JSONB column accepts and stores the following keys. All other keys written by a `PATCH /api/workspace/settings` request are silently dropped.

```json
{
  "retentionDays": 90,
  "themeDefault": "dark",
  "timezone": "UTC",
  "defaults": {
    "rateLimits": {
      "rpmMax": 120,
      "tpmMax": null
    },
    "deploymentDefaults": {
      "quantization": "fp8",
      "maxModelLen": 16384,
      "gpuMemoryUtilization": 0.85
    }
  },
  "notifications": {
    "agentOffline": true,
    "deploymentFailed": true,
    "usageThresholdPercent": 80
  },
  "deletion": {
    "token_hash": "sha256_hex_string",
    "grace_period_ends": "2026-06-14T17:00:00+00:00",
    "deleted_by": "uuid-string"
  }
}
```

- `deletion` is a system-managed key written only by the delete/restore endpoints and is not exposed in `GET /api/workspace/settings` responses. User-initiated settings writes cannot modify the `deletion` sub-object.
- `retentionDays` ranges from 7 to 365. Values outside this range are clamped. Default: 30.
- `themeDefault` accepts `"light"`, `"dark"`, or `"system"`. Default: `"system"`.
- `timezone` must be a valid IANA timezone identifier (e.g., `"America/New_York"`, `"Europe/Berlin"`). Validated against `pytz.all_timezones`. Default: `"UTC"`.
- `defaults.rateLimits.rpmMax` and `tpmMax` are nullable integers. Null means "use the platform default" (defined in F30).
- `defaults.deploymentDefaults` keys are used by the deployment wizard (F19) as pre-filled values in Step 3 (Configure Parameters). They are nullable — null means the wizard uses its own defaults.
- `notifications.usageThresholdPercent` ranges from 0 to 100. When set, the workspace receives a notification (email/in-app banner) when monthly usage exceeds this percentage of the plan's token limit.

### Background Cleanup Job

A scheduled task (Celery Beat schedule, running daily at 02:00 UTC) hard-deletes workspaces past their 7-day grace period:

```python
# backend/app/tasks/workspace_cleanup.py
from celery import Celery
from datetime import datetime, timezone, timedelta

app = Celery("modelprism")

@app.task
def purge_expired_workspaces():
    """Hard-delete workspaces whose grace period has expired."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    # Find workspaces soft-deleted more than 7 days ago
    expired = select(Workspace).where(
        Workspace.deleted_at.isnot(None),
        Workspace.deleted_at < cutoff
    )
    for ws in expired:
        # CASCADE handles all child tables
        db_session.delete(ws)
    db_session.commit()
```

### Slug Generation Algorithm

```python
# backend/app/services/workspace_service.py
import re, secrets

def generate_slug(name: str, existing_slugs: set[str]) -> str:
    """Generate a unique URL-safe slug from a workspace name."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    slug = slug.strip('-')
    if not slug:
        slug = f"workspace-{secrets.token_hex(4)}"
    base = slug
    counter = 1
    while slug in existing_slugs:
        slug = f"{base}-{counter}"
        counter += 1
    return slug
```

### Edge Cases

- **Last owner removal:** The `PATCH` and `DELETE` endpoints for members check that the workspace will still have at least one member with role `owner` after the operation. This is enforced with a `SELECT COUNT(*) FROM workspace_members WHERE workspace_id = :wid AND role = 'owner'` before the mutation. The check counts rows, not users — a single user with `owner` on multiple rows counts as one owner. If the count would drop to zero, the operation is rejected.

- **Invitation expiry:** Pending invitations (rows with `user_id IS NULL`) expire after 30 days. A background sweep (same Celery Beat schedule as the purge job) sets `role = NULL` and deletes the row or marks it as `expired` in a future `invitation_status` column. Expired invitations are not shown in the member list by default (a filter can show them).

- **Invitation claim at registration:** When a new user registers (F5 `POST /api/auth/register`), the registration handler checks if any `workspace_members` rows exist with a matching email and `user_id IS NULL`. If found, it claims all of them by setting `user_id = new_user.id`. The workspace slug is included as a query parameter in the registration URL from the invitation email. If no invitation exists, a default workspace is created as usual.

- **Workspace with no name set:** The F5 registration handler always generates a default workspace name (`"{display_name}'s Workspace"` or `"My Workspace"` as fallback). The F32 spec does not alter this — it only provides the `PATCH` endpoint for changing the name later.

- **Concurrent settings writes:** The `PATCH /api/workspace/settings` endpoint uses optimistic concurrency control: it compares the request's `updatedAt` (if provided) against the database row's `updated_at`. A mismatch returns HTTP 409 with `code: "CONFLICT"` and the current state. This prevents last-writer-wins data loss from concurrent settings edits.

- **Recovery token storage:** The recovery token hash is stored inside the `settings` JSONB column under `deletion.token_hash`. This avoids adding a new column to the F3 schema. On restore, the raw token input is SHA-256 hashed and compared against the stored hash. After successful restore, the `deletion` key is removed from the JSONB column.

- **Deletion with active auto-scaling:** If agents belong to an auto-scaling group (future feature), the deletion handler gracefully de-registers each agent from the scaling group before sending the `stop_agent` command. This prevents orphaned cloud instances. For MVP, all agents are stopped with `stop_agent` commands and the scaling group state is not tracked.

### Performance Considerations

- **Summary endpoint caching:** The `GET /api/workspace/summary` response is cached in Redis (TTL 60 seconds) with the workspace ID as the cache key. Invalidated when any of the underlying tables (agents, model_deployments, api_keys, workspace_members, usage_records) change for that workspace. The Pinia store on the frontend refetches every 30 seconds while the dashboard page is active, or on explicit navigation to the page.

- **Large member lists:** The `GET /api/workspace/members` endpoint supports JSON:API pagination (`page[offset]`, `page[limit]`), sorting by `createdAt` or `role`, and filtering by `status` (`active` / `pending`). Default limit is 20, max is 100.

- **Usage aggregation window:** The summary endpoint's usage query runs against the `usage_records` table with the `ix_usage_records_workspace_created` index (F3), scoped to `WHERE workspace_id = :ws_id AND created_at >= date_trunc('month', now())`. For workspaces with heavy usage (>1M records/month), the query executes a materialised summary that is updated hourly by a background task, falling back to a direct query with a 10-second timeout.

### Integration Points

- **F3 (Database schema):** Reads and writes the `workspaces` table (columns: `id`, `name`, `slug`, `cloud_mode`, `settings` JSONB, `created_at`, `updated_at`) and the `workspace_members` table (`id`, `workspace_id`, `user_id`, `role` as `user_role` enum, `invited_by`, `created_at`). The `settings` JSONB column stores workspace preferences and the deletion recovery token hash. All workspace-scoped queries use the `workspace_id` FK and the composite indexes defined in F3 for performance.

- **F5 (Email/password auth):** The JWT auth middleware provides `request.state.workspace_id` which F32 endpoints use for all queries. Registration (F5) is the sole workspace creation path — there is no standalone "create workspace" endpoint in F32. The F5 `register` handler generates the default workspace and membership; F32 provides the management UI post-creation. The JWT middleware's membership check on every request (F5 ACF5-7) is extended to also deny requests for workspaces where `deleted_at IS NOT NULL`.

- **F6 (Agent registration):** The workspace member list page includes a "Registration Tokens" section (reusing the F6 agent registration token flow) that displays active tokens for the workspace and allows creating new ones. The token creation button is moved into this workspace settings page for the F32/Scale phase. The `agent_registration_tokens` table is workspace-scoped via its `workspace_id` FK (F3).

- **F11 (Agent command handler):** Workspace deletion sends `stop_agent` commands over WebSocket (F11) to all connected agents in the workspace, with a `reason: "workspace_deleted"` parameter. The agent-side command handler (F11) interprets this as a terminal shutdown — it stops all running model deployments, removes Docker containers, and exits the agent process.

- **F16 (WebSocket broadcast):** The workspace summary's `recentActivity` list includes events broadcast via the WebSocket (F16) — deployment completions (F19), agent status changes (F6/F7), and key creations (F27). These events are captured by a database trigger or an application-level event bus that writes to an `activity_log` or queries the existing entity tables for recent changes.

- **F19 (Model deployment wizard):** Reads `workspaces.settings.defaults.deploymentDefaults` to pre-fill vLLM parameter fields in Step 3 of the deployment wizard. If no defaults are set, the wizard uses its own hardcoded defaults. The `GET /api/workspace/settings` endpoint is called on mount of the deploy wizard page.

- **F27 (API key management):** Reads `workspaces.settings.defaults.rateLimits` as the default scope when creating new API keys. If `rateLimits` defaults are set at the workspace level, new keys inherit them unless explicitly overridden at creation time. The workspace summary endpoint counts active API keys and includes the count.

- **F29 (Usage tracking):** The workspace summary endpoint aggregates usage statistics for the current month (`usage_records` table). The per-workspace usage data is also consumed by the billing system (F37) for invoice generation.

- **F30 (Rate limiting):** Reads `workspaces.settings.defaults.rateLimits` to set workspace-level rate limit defaults applied when no per-key or per-deployment rate limits are configured. The actual enforcement is in F30's middleware.

- **F33 (RBAC refinement — future):** The role-based permissions established in F32 (owner, admin, member, viewer) are the foundation for F33, which will add resource-level permissions (e.g., "Bob can only access models with tag `dev`").

- **F35 (Data retention — future):** The retention cleanup job reads `workspaces.settings.retentionDays` to determine the pruning window for `agent_metrics` and `agent_logs`. The job is described in F32's settings section but implemented in F35.

- **F37 (Stripe billing — future):** The workspace plan tier (free vs paid) and Stripe customer ID are stored in a future `billing_plans` table scoped by `workspace_id`. The F37 implementation will add plan-related fields to the workspace settings UI.

### Dependency Graph

```
F3 (workspaces + workspace_members schema) ──→ F32 (This feature)
                                                      │
F5 (JWT auth + registration creates workspace) ──────┤
                                                      │
├── ACF32-1 settings ──→ F35 (Data retention)         │
├── ACF32-2 members ──→ F33 (RBAC refinement)         │
├── ACF32-4 deletion ──→ F11 (Agent shutdown)         │
├── ACF32-6 summary ──→ F16 (Activity broadcast)      │
├── Settings defaults ──→ F19 (Deployment defaults)   │
├── Settings defaults ──→ F27 (Key defaults)           │
└── Summary usage ──→ F29 (Usage tracking)            │
                                                      │
F32 ──→ F37 (Stripe billing builds on workspace org)  │
```

## Depends on: F3 (Database schema — workspaces and workspace_members tables), F5 (Email/password auth — JWT sessions, workspace context, registration creates initial workspace)
