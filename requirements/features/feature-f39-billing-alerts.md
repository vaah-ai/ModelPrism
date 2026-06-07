# Feature F39 — Billing Alerts & Budget Caps

System that monitors usage (from F29) against configurable thresholds and budget caps, issuing in-app (WebSocket via F16) and email (via F37) notifications before costs exceed limits. Supports hard caps that block API keys (via F27) and return 402 Payment Required (via F28).

---

## Acceptance Criteria

### ACF39-1: Absolute-Value Alert Fires When Threshold Crossed
**Given** an active workspace `ws-prod-01` has a billing alert set at `$500.00` absolute spend
**When** a usage record (F29) pushes the current billing period total for `ws-prod-01` past `$500.00`
**Then** a `billing_alert_events` record is created with `status = 'active'`
**And** a WebSocket message (F16) is pushed to `ws-prod-01` with `type: billing_alert`
**And** an email is sent to all workspace owners (F32) with subject "[ModelPrism] Spend Alert — $500.00 Threshold Reached"

### ACF39-2: Percentage-Based Alert Against Budget Cap
**Given** workspace `ws-prod-01` has a budget cap at `$2,000.00` **and** a billing alert at `80%` of the budget cap
**When** cumulative spend in the current billing period reaches `$1,600.00` (80 % of $2,000)
**Then** a `billing_alert_events` record is created with `status = 'active'`
**And** the WebSocket notification (F16) includes `threshold: "budget_percentage"`, `percentage: 80`, `budget_cap: 2000.00`, `spend: 1600.00`

### ACF39-3: Hard Budget Cap Blocks Over-Limit API Requests
**Given** workspace `ws-prod-01` has a hard budget cap at `$500.00` with `hard_cap = true`
**When** a new API request would cause cumulative spend in the current billing period to exceed `$500.00`
**Then** the proxy middleware (F28) checks the budget cap **before** forwarding the request to the model provider
**And** returns an HTTP `402 Payment Required` with JSON body `{"error": "budget_cap_reached", "message": "Monthly budget of $500.00 exceeded. Please upgrade your plan or adjust budget caps."}`
**And** any API keys (F27) associated with this workspace are NOT automatically blocked (the cap is billing-period-scoped)

### ACF39-4: Alert Resolves When Spend Falls Below Threshold (Next Period)
**Given** a `billing_alert_events` record exists with `status = 'active'` for a threshold
**When** a new billing period starts (monthly rollover)
**Then** all `billing_alert_events` with `status = 'active'` for the previous period are set to `status = 'resolved'`
**And** a WebSocket message (F16) is pushed with `type: billing_alert_resolved`
**And** an email notification is sent with subject "[ModelPrism] Spend Alert Resolved"

### ACF39-5: Owner Can Override or Delete an Alert
**Given** a workspace owner (F34, `role = 'owner'`) opens the billing dashboard (F38)
**When** they navigate to the Alerts section and select an existing alert
**Then** they can update the `threshold_value`, `threshold_type`, `budget_cap_id`, `hard_cap`, or `enabled` flag
**And** they can delete the alert entirely
**And** the audit log records the change as `billing_alert.update` or `billing_alert.delete` with the user's identity

---

## Concrete Examples

### Example 1: Creating an Absolute-Value Alert (POST /api/billing-alerts)

**Request:**
```
POST /api/billing-alerts
Content-Type: application/vnd.api+json
Authorization: Bearer <org_token>
```

```json
{
  "data": {
    "type": "billing-alerts",
    "attributes": {
      "workspace_id": "ws-prod-01",
      "name": "Production spend warning",
      "threshold_type": "absolute",
      "threshold_value": "500.00",
      "enabled": true,
      "notify_methods": ["in_app", "email"],
      "notify_user_ids": ["u-11111111-2222-3333-4444-555555555555"]
    }
  }
}
```

**Response (201 Created):**
```json
{
  "data": {
    "id": "ba-11111111-2222-3333-4444-555555555555",
    "type": "billing-alerts",
    "attributes": {
      "workspace_id": "ws-prod-01",
      "name": "Production spend warning",
      "threshold_type": "absolute",
      "threshold_value": "500.00",
      "enabled": true,
      "hard_cap": false,
      "budget_cap_id": null,
      "notify_methods": ["in_app", "email"],
      "notify_user_ids": ["u-11111111-2222-3333-4444-555555555555"],
      "created_at": "2026-06-01T08:00:00Z",
      "updated_at": "2026-06-01T08:00:00Z"
    }
  }
}
```

---

### Example 2: Alert Firing — WebSocket + Email Delivery

**Trigger:** Usage record processed at `2026-06-05T14:30:00Z` for workspace `ws-prod-01` pushes cumulative spend to `$523.47` (above the `$500.00` threshold).

**WebSocket message (F16 → workspace `ws-prod-01`):**
```json
{
  "type": "billing_alert",
  "payload": {
    "alert_id": "ba-11111111-2222-3333-4444-555555555555",
    "alert_name": "Production spend warning",
    "threshold_type": "absolute",
    "threshold_value": "500.00",
    "current_spend": "523.47",
    "currency": "USD",
    "workspace_id": "ws-prod-01",
    "billing_period_start": "2026-06-01T00:00:00Z",
    "billing_period_end": "2026-06-30T23:59:59Z",
    "event_id": "bae-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "fired_at": "2026-06-05T14:30:01Z"
  }
}
```

**Email sent (via F37):**
- **To:** workspace owners
- **Subject:** "[ModelPrism] Spend Alert — $500.00 Threshold Reached"
- **Body:**
```
Hi [Owner Name],

Workspace "ws-prod-01" has triggered a spend alert.

Alert: Production spend warning
Threshold: $500.00
Current spend: $523.47
Billing period: June 1 – June 30, 2026

Please review your usage at:
https://app.modelprism.com/billing/alerts/ba-11111111-2222-3333-4444-555555555555

— ModelPrism Billing
```

---

### Example 3: Percentage-Based Alert with Budget Cap

**Step 1 — Create budget cap:**
```
POST /api/budget-caps
Content-Type: application/vnd.api+json
Authorization: Bearer <org_token>
```

```json
{
  "data": {
    "type": "budget-caps",
    "attributes": {
      "workspace_id": "ws-prod-01",
      "amount": "2000.00",
      "currency": "USD",
      "period": "monthly",
      "hard_cap": false
    }
  }
}
```

**Response:**
```json
{
  "data": {
    "id": "bc-22222222-3333-4444-5555-666666666666",
    "type": "budget-caps",
    "attributes": {
      "workspace_id": "ws-prod-01",
      "amount": "2000.00",
      "currency": "USD",
      "period": "monthly",
      "hard_cap": false,
      "current_spend": "0.00",
      "created_at": "2026-06-01T08:00:00Z",
      "updated_at": "2026-06-01T08:00:00Z"
    }
  }
}
```

**Step 2 — Create percentage alert referencing the budget cap:**
```
POST /api/billing-alerts
Content-Type: application/vnd.api+json
```

```json
{
  "data": {
    "type": "billing-alerts",
    "attributes": {
      "workspace_id": "ws-prod-01",
      "name": "80% budget warning",
      "threshold_type": "budget_percentage",
      "threshold_value": "80.00",
      "budget_cap_id": "bc-22222222-3333-4444-5555-666666666666",
      "enabled": true,
      "notify_methods": ["in_app"],
      "notify_user_ids": ["u-11111111-2222-3333-4444-555555555555"]
    }
  }
}
```

**Step 3 — Spend reaches 80 % triggering alert:**

Spend recorded by F29 pushes cumulative to `$1,623.18`. The billing alert service evaluates `1623.18 / 2000.00 = 81.16 % > 80 %` and fires.

**WebSocket message:**
```json
{
  "type": "billing_alert",
  "payload": {
    "alert_id": "ba-33333333-4444-5555-6666-777777777777",
    "alert_name": "80% budget warning",
    "threshold_type": "budget_percentage",
    "threshold_value": "80.00",
    "percentage": 81.16,
    "budget_cap_id": "bc-22222222-3333-4444-5555-666666666666",
    "budget_cap": "2000.00",
    "current_spend": "1623.18",
    "currency": "USD",
    "workspace_id": "ws-prod-01",
    "billing_period_start": "2026-06-01T00:00:00Z",
    "billing_period_end": "2026-06-30T23:59:59Z",
    "event_id": "bae-bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "fired_at": "2026-06-12T09:15:33Z"
  }
}
```

---

### Example 4: Hard Cap Blocking an API Request

**Setup:** Workspace `ws-prod-01` has a hard budget cap of `$500.00`, and cumulative spend is already `$499.99`.

**Request (incoming via proxy, F28):**
```
POST /v1/chat/completions
Authorization: Bearer mp-key-abc123def456
Content-Type: application/json
```

```json
{
  "model": "Qwen2.5-72B-Instruct",
  "messages": [{"role": "user", "content": "Write a long analysis of quantum computing..."}]
}
```

**Proxy middleware evaluates:** Estimated cost of this request is `$0.15`. Adding `$0.15` to current spend `$499.99` would exceed the hard cap of `$500.00`.

**Response (402 Payment Required):**
```json
{
  "error": "budget_cap_reached",
  "message": "Monthly budget of $500.00 exceeded. Please upgrade your plan or adjust budget caps.",
  "workspace_id": "ws-prod-01",
  "budget_cap_id": "bc-22222222-3333-4444-5555-666666666666",
  "current_period_spend": "499.99",
  "estimated_request_cost": "0.15",
  "billing_period_start": "2026-06-01T00:00:00Z",
  "billing_period_end": "2026-06-30T23:59:59Z"
}
```

**Note:** The API keys for this workspace are NOT blocked across periods. Once the new billing period starts, requests are accepted again (ACF39-4).

---

### Example 5: Owner Override of Alert Settings

**Request (PATCH — owner updates alert threshold and adds an email notification):**
```
PATCH /api/billing-alerts/ba-11111111-2222-3333-4444-555555555555
Content-Type: application/vnd.api+json
Authorization: Bearer <owner_token>
```

```json
{
  "data": {
    "id": "ba-11111111-2222-3333-4444-555555555555",
    "type": "billing-alerts",
    "attributes": {
      "threshold_value": "1000.00",
      "notify_methods": ["in_app", "email"],
      "notify_user_ids": [
        "u-11111111-2222-3333-4444-555555555555",
        "u-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
      ]
    }
  }
}
```

**Response (200 OK):**
```json
{
  "data": {
    "id": "ba-11111111-2222-3333-4444-555555555555",
    "type": "billing-alerts",
    "attributes": {
      "workspace_id": "ws-prod-01",
      "name": "Production spend warning",
      "threshold_type": "absolute",
      "threshold_value": "1000.00",
      "enabled": true,
      "hard_cap": false,
      "budget_cap_id": null,
      "notify_methods": ["in_app", "email"],
      "notify_user_ids": [
        "u-11111111-2222-3333-4444-555555555555",
        "u-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
      ],
      "updated_at": "2026-06-06T10:30:00Z"
    }
  }
}
```

**Audit log entry (created by F38 backend):**
```json
{
  "action": "billing_alert.update",
  "resource_type": "billing-alert",
  "resource_id": "ba-11111111-2222-3333-4444-555555555555",
  "actor_id": "u-11111111-2222-3333-4444-555555555555",
  "actor_role": "owner",
  "workspace_id": "ws-prod-01",
  "changes": {
    "threshold_value": {"from": "500.00", "to": "1000.00"},
    "notify_methods": {"from": ["in_app"], "to": ["in_app", "email"]},
    "notify_user_ids": {"from": ["u-11111111-2222-3333-4444-555555555555"], "to": ["u-11111111-2222-3333-4444-555555555555", "u-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]}
  },
  "timestamp": "2026-06-06T10:30:00Z"
}
```

---

## Integration Points

| Feature | Relationship | Details |
|---|---|---|
| **F16** — WebSocket Gateway | **Used by** F39 | WebSocket messages for `billing_alert` and `billing_alert_resolved` types pushed to workspace channels |
| **F27** — API Key Management | **Consumed by** F39 | Hard caps do NOT auto-block API keys; alert context displayed in API key management UI |
| **F28** — Proxy (402 response) | **Used by** F39 | `402 Payment Required` returned by proxy middleware when hard cap is exceeded |
| **F29** — Usage Records | **Consumed by** F39 | `billing_alert_service.py` subscribes to `usage.recorded` events from F29 to evaluate thresholds |
| **F32** — Workspace | **Consumed by** F39 | Workspace ID is the scope for alerts and budget caps; owner list sourced from F32 |
| **F33** — RBAC | **Enforced by** F39 | Only `admin` and `owner` roles (via F34) can create/update/delete alerts and caps |
| **F34** — Team Membership | **Consumed by** F39 | `notify_user_ids` filtered to valid workspace members; email delivery uses member email |
| **F35** — Audit / Retention | **Consumed by** F39 | All alert/cap mutations are logged; `billing_alert_events` retained per F35 policy |
| **F37** — Notification / Email | **Used by** F39 | Email delivery via F37's `send_email()` with templates from `email_templates/billing_alert.html` |
| **F38** — Billing Dashboard | **Consumed by** F39 | Alerts and budget caps displayed and managed from the billing dashboard UI |

---

## Data Schema

### Table: `billing_alerts`

```sql
CREATE TABLE billing_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    VARCHAR(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    threshold_type  VARCHAR(32) NOT NULL CHECK (threshold_type IN ('absolute', 'budget_percentage')),
    threshold_value DECIMAL(12,2) NOT NULL CHECK (threshold_value > 0),
    budget_cap_id   UUID REFERENCES budget_caps(id) ON DELETE SET NULL,
    enabled         BOOLEAN NOT NULL DEFAULT true,
    hard_cap        BOOLEAN NOT NULL DEFAULT false,
    notify_methods  TEXT[] NOT NULL DEFAULT '{"in_app"}' CHECK (array_length(notify_methods, 1) > 0),
    notify_user_ids UUID[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_billing_alerts_workspace ON billing_alerts(workspace_id);
CREATE INDEX idx_billing_alerts_enabled ON billing_alerts(enabled) WHERE enabled = true;
```

### Table: `billing_alert_events`

```sql
CREATE TABLE billing_alert_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id        UUID NOT NULL REFERENCES billing_alerts(id) ON DELETE CASCADE,
    workspace_id    VARCHAR(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    status          VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'resolved')),
    threshold_type  VARCHAR(32) NOT NULL,
    threshold_value DECIMAL(12,2) NOT NULL,
    current_spend   DECIMAL(12,2) NOT NULL,
    budget_cap_id   UUID REFERENCES budget_caps(id) ON DELETE SET NULL,
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
    billing_period_start TIMESTAMPTZ NOT NULL,
    billing_period_end   TIMESTAMPTZ NOT NULL,
    fired_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX idx_billing_alert_events_active ON billing_alert_events(workspace_id, status)
    WHERE status = 'active';
CREATE INDEX idx_billing_alert_events_alert ON billing_alert_events(alert_id);
```

### Table: `budget_caps`

```sql
CREATE TABLE budget_caps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    VARCHAR(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    amount          DECIMAL(12,2) NOT NULL CHECK (amount > 0),
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
    period          VARCHAR(16) NOT NULL DEFAULT 'monthly' CHECK (period IN ('monthly', 'yearly')),
    hard_cap        BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(workspace_id, period)
);

CREATE INDEX idx_budget_caps_workspace ON budget_caps(workspace_id);
```

---

## Pydantic Schemas (backend/app/schemas/billing_alert.py)

```python
from decimal import Decimal
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import uuid


class BillingAlertCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    threshold_type: str = Field(...)  # "absolute" | "budget_percentage"
    threshold_value: Decimal = Field(..., gt=Decimal("0"))
    budget_cap_id: Optional[uuid.UUID] = None
    enabled: bool = True
    hard_cap: bool = False
    notify_methods: list[str] = Field(default=["in_app"])
    notify_user_ids: list[uuid.UUID] = Field(default=[])

    @field_validator("threshold_type")
    @classmethod
    def validate_threshold_type(cls, v: str) -> str:
        allowed = {"absolute", "budget_percentage"}
        if v not in allowed:
            raise ValueError(f"threshold_type must be one of {allowed}")
        return v

    @field_validator("notify_methods")
    @classmethod
    def validate_notify_methods(cls, v: list[str]) -> list[str]:
        allowed = {"in_app", "email", "webhook"}
        for m in v:
            if m not in allowed:
                raise ValueError(f"notify_method {m} not in {allowed}")
        if len(v) == 0:
            raise ValueError("at least one notify_method required")
        return v


class BillingAlertUpdate(BaseModel):
    threshold_value: Optional[Decimal] = None
    threshold_type: Optional[str] = None
    budget_cap_id: Optional[uuid.UUID] = None
    enabled: Optional[bool] = None
    hard_cap: Optional[bool] = None
    notify_methods: Optional[list[str]] = None
    notify_user_ids: Optional[list[uuid.UUID]] = None

    @field_validator("threshold_type")
    @classmethod
    def validate_threshold_type(cls, v: str) -> str:
        allowed = {"absolute", "budget_percentage"}
        if v not in allowed:
            raise ValueError(f"threshold_type must be one of {allowed}")
        return v


class BillingAlertResponse(BaseModel):
    id: uuid.UUID
    workspace_id: str
    name: str
    threshold_type: str
    threshold_value: Decimal
    budget_cap_id: Optional[uuid.UUID] = None
    enabled: bool
    hard_cap: bool
    notify_methods: list[str]
    notify_user_ids: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class BudgetCapCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=64)
    amount: Decimal = Field(..., gt=Decimal("0"))
    currency: str = "USD"
    period: str = "monthly"
    hard_cap: bool = False

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        allowed = {"monthly", "yearly"}
        if v not in allowed:
            raise ValueError(f"period must be one of {allowed}")
        return v


class BudgetCapResponse(BaseModel):
    id: uuid.UUID
    workspace_id: str
    amount: Decimal
    currency: str
    period: str
    hard_cap: bool
    current_spend: Decimal
    created_at: datetime
    updated_at: datetime


class BillingAlertEventResponse(BaseModel):
    id: uuid.UUID
    alert_id: uuid.UUID
    workspace_id: str
    status: str
    threshold_type: str
    threshold_value: Decimal
    current_spend: Decimal
    budget_cap_id: Optional[uuid.UUID] = None
    currency: str
    billing_period_start: datetime
    billing_period_end: datetime
    fired_at: datetime
    resolved_at: Optional[datetime] = None
```

---

## SQLAlchemy ORM Models (backend/app/models/billing_alert.py)

```python
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Boolean, Numeric, DateTime,
    ForeignKey, UniqueConstraint, Index, Text
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class BillingAlert(Base):
    __tablename__ = "billing_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    threshold_type = Column(String(32), nullable=False)
    threshold_value = Column(Numeric(12, 2), nullable=False)
    budget_cap_id = Column(UUID(as_uuid=True), ForeignKey("budget_caps.id", ondelete="SET NULL"), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    hard_cap = Column(Boolean, nullable=False, default=False)
    notify_methods = Column(ARRAY(Text), nullable=False, default=["in_app"])
    notify_user_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=[])
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_billing_alerts_workspace", "workspace_id"),
        Index("idx_billing_alerts_enabled", "enabled", postgresql_where=enabled.is_(True)),
    )


class BillingAlertEvent(Base):
    __tablename__ = "billing_alert_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("billing_alerts.id", ondelete="CASCADE"), nullable=False)
    workspace_id = Column(String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(16), nullable=False, default="active")
    threshold_type = Column(String(32), nullable=False)
    threshold_value = Column(Numeric(12, 2), nullable=False)
    current_spend = Column(Numeric(12, 2), nullable=False)
    budget_cap_id = Column(UUID(as_uuid=True), ForeignKey("budget_caps.id", ondelete="SET NULL"), nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    billing_period_start = Column(DateTime(timezone=True), nullable=False)
    billing_period_end = Column(DateTime(timezone=True), nullable=False)
    fired_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_billing_alert_events_active", "workspace_id", "status",
              postgresql_where=status == "active"),
        Index("idx_billing_alert_events_alert", "alert_id"),
    )


class BudgetCap(Base):
    __tablename__ = "budget_caps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    period = Column(String(16), nullable=False, default="monthly")
    hard_cap = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("workspace_id", "period", name="uq_budget_caps_workspace_period"),
        Index("idx_budget_caps_workspace", "workspace_id"),
    )
```

---

## Service Layer (backend/app/services/billing_alert_service.py)

```python
"""
Billing Alert Service — evaluates usage records against billing alerts and budget caps,
fires notifications via WebSocket (F16) and email (F37), and enforces hard caps in the proxy (F28).
"""

import uuid
import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_alert import BillingAlert, BillingAlertEvent, BudgetCap
from app.schemas.billing_alert import (
    BillingAlertCreate, BillingAlertUpdate,
    BudgetCapCreate, BillingAlertEventResponse,
)
from app.services.websocket_service import WebSocketService  # F16
from app.services.notification_service import NotificationService  # F37
from app.services.usage_service import UsageService  # F29

logger = logging.getLogger(__name__)


class BillingAlertService:

    def __init__(
        self,
        db: AsyncSession,
        ws_service: WebSocketService,
        notification_service: NotificationService,
        usage_service: UsageService,
    ):
        self.db = db
        self.ws = ws_service
        self.notify = notification_service
        self.usage = usage_service

    # ── CRUD: Billing Alerts ────────────────────────────────────────────

    async def create_alert(self, data: BillingAlertCreate) -> BillingAlert:
        """Create a new billing alert."""
        alert = BillingAlert(
            workspace_id=data.workspace_id,
            name=data.name,
            threshold_type=data.threshold_type,
            threshold_value=data.threshold_value,
            budget_cap_id=data.budget_cap_id,
            enabled=data.enabled,
            hard_cap=data.hard_cap,
            notify_methods=data.notify_methods,
            notify_user_ids=data.notify_user_ids,
        )
        self.db.add(alert)
        await self.db.commit()
        await self.db.refresh(alert)
        logger.info("Billing alert created: %s (workspace=%s)", alert.id, alert.workspace_id)
        return alert

    async def get_alert(self, alert_id: uuid.UUID) -> Optional[BillingAlert]:
        """Fetch a billing alert by ID."""
        result = await self.db.execute(
            select(BillingAlert).where(BillingAlert.id == alert_id)
        )
        return result.scalar_one_or_none()

    async def update_alert(self, alert_id: uuid.UUID, data: BillingAlertUpdate) -> Optional[BillingAlert]:
        """Update a billing alert (partial)."""
        alert = await self.get_alert(alert_id)
        if not alert:
            return None
        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return alert
        for key, value in update_dict.items():
            setattr(alert, key, value)
        alert.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(alert)
        logger.info("Billing alert updated: %s", alert.id)
        return alert

    async def delete_alert(self, alert_id: uuid.UUID) -> bool:
        """Delete a billing alert."""
        alert = await self.get_alert(alert_id)
        if not alert:
            return False
        await self.db.delete(alert)
        await self.db.commit()
        logger.info("Billing alert deleted: %s", alert_id)
        return True

    # ── CRUD: Budget Caps ──────────────────────────────────────────────

    async def create_budget_cap(self, data: BudgetCapCreate) -> BudgetCap:
        """Create a budget cap (upserts by workspace_id + period)."""
        existing = await self.db.execute(
            select(BudgetCap).where(
                BudgetCap.workspace_id == data.workspace_id,
                BudgetCap.period == data.period,
            )
        )
        cap = existing.scalar_one_or_none()
        if cap:
            cap.amount = data.amount
            cap.hard_cap = data.hard_cap
            cap.updated_at = datetime.utcnow()
        else:
            cap = BudgetCap(
                workspace_id=data.workspace_id,
                amount=data.amount,
                currency=data.currency,
                period=data.period,
                hard_cap=data.hard_cap,
            )
            self.db.add(cap)
        await self.db.commit()
        await self.db.refresh(cap)
        return cap

    # ── Threshold Evaluation ────────────────────────────────────────────

    async def evaluate_alerts(self, workspace_id: str):
        """
        Called when a usage record is processed (F29 event).
        Evaluates all enabled alerts for the workspace and fires if threshold crossed.
        """
        alerts = await self.db.execute(
            select(BillingAlert).where(
                BillingAlert.workspace_id == workspace_id,
                BillingAlert.enabled.is_(True),
            )
        )
        for alert in alerts.scalars().all():
            await self._evaluate_single_alert(alert)

    async def _evaluate_single_alert(self, alert: BillingAlert):
        """Evaluate one alert. Fires if threshold has been crossed and no active event exists."""
        current_spend = await self.usage.get_period_spend(alert.workspace_id)
        threshold_crossed = False
        percentage = None

        if alert.threshold_type == "absolute":
            if current_spend >= alert.threshold_value:
                threshold_crossed = True

        elif alert.threshold_type == "budget_percentage" and alert.budget_cap_id:
            cap = await self.db.get(BudgetCap, alert.budget_cap_id)
            if cap and cap.amount > 0:
                pct = (current_spend / cap.amount) * Decimal("100")
                percentage = float(round(pct, 2))
                if pct >= alert.threshold_value:
                    threshold_crossed = True

        if not threshold_crossed:
            return

        # Check if an active event already exists for this alert
        existing_event = await self.db.execute(
            select(BillingAlertEvent).where(
                BillingAlertEvent.alert_id == alert.id,
                BillingAlertEvent.status == "active",
            ).limit(1)
        )
        if existing_event.scalar_one_or_none():
            logger.debug("Active event already exists for alert %s, skipping", alert.id)
            return

        # Determine billing period bounds
        period_start, period_end = self._get_billing_period()

        event = BillingAlertEvent(
            alert_id=alert.id,
            workspace_id=alert.workspace_id,
            status="active",
            threshold_type=alert.threshold_type,
            threshold_value=alert.threshold_value,
            current_spend=current_spend,
            budget_cap_id=alert.budget_cap_id,
            currency="USD",
            billing_period_start=period_start,
            billing_period_end=period_end,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)

        # Push WebSocket notification (F16)
        await self._push_ws_alert(event, alert, float(current_spend), percentage)

        # Send email if configured (F37)
        if "email" in alert.notify_methods:
            await self._send_alert_email(event, alert, float(current_spend), percentage)

    async def _push_ws_alert(
        self, event: BillingAlertEvent, alert: BillingAlert,
        spend: float, percentage: float | None
    ):
        """Send a WebSocket billing_alert message to the workspace channel."""
        payload = {
            "type": "billing_alert",
            "payload": {
                "alert_id": str(alert.id),
                "alert_name": alert.name,
                "threshold_type": alert.threshold_type,
                "threshold_value": float(alert.threshold_value),
                "current_spend": spend,
                "currency": "USD",
                "workspace_id": alert.workspace_id,
                "billing_period_start": event.billing_period_start.isoformat(),
                "billing_period_end": event.billing_period_end.isoformat(),
                "event_id": str(event.id),
                "fired_at": event.fired_at.isoformat(),
            },
        }
        if percentage is not None:
            payload["payload"]["percentage"] = percentage
        await self.ws.send_to_workspace(alert.workspace_id, payload)

    async def _send_alert_email(
        self, event: BillingAlertEvent, alert: BillingAlert,
        spend: float, percentage: float | None
    ):
        """Send alert notification email."""
        subject = f"[ModelPrism] Spend Alert — ${float(alert.threshold_value):,.2f} Threshold Reached"
        context = {
            "alert_name": alert.name,
            "threshold_value": float(alert.threshold_value),
            "threshold_type": alert.threshold_type,
            "current_spend": spend,
            "percentage": percentage,
            "workspace_id": alert.workspace_id,
            "alert_id": str(alert.id),
        }
        await self.notify.send_email_to_users(
            user_ids=alert.notify_user_ids,
            subject=subject,
            template_name="billing_alert",
            context=context,
        )

    # ── Period Rollover (Resolve) ───────────────────────────────────────

    async def resolve_active_alerts(self, workspace_id: str):
        """
        Called at period rollover. Resolves all active alert events for the workspace.
        """
        active_events = await self.db.execute(
            select(BillingAlertEvent).where(
                BillingAlertEvent.workspace_id == workspace_id,
                BillingAlertEvent.status == "active",
            )
        )
        now = datetime.utcnow()
        for event in active_events.scalars().all():
            event.status = "resolved"
            event.resolved_at = now
        await self.db.commit()

        # Notify workspace
        await self.ws.send_to_workspace(workspace_id, {
            "type": "billing_alert_resolved",
            "payload": {
                "workspace_id": workspace_id,
                "resolved_at": now.isoformat(),
            },
        })

    # ── Hard Cap Check (for F28 proxy) ──────────────────────────────────

    async def check_hard_cap(
        self, workspace_id: str, estimated_cost: Decimal
    ) -> tuple[bool, Optional[dict]]:
        """
        Called by proxy middleware (F28) before forwarding a request.
        Returns (blocked: bool, error_payload: dict | None).

        If `blocked` is True, the proxy should return 402 Payment Required
        with the provided error payload.
        """
        result = await self.db.execute(
            select(BudgetCap).where(
                BudgetCap.workspace_id == workspace_id,
                BudgetCap.hard_cap.is_(True),
            )
        )
        cap = result.scalar_one_or_none()
        if not cap:
            return False, None  # no hard cap configured

        current_spend = await self.usage.get_period_spend(workspace_id)
        if current_spend + estimated_cost <= cap.amount:
            return False, None  # under cap

        period_start, period_end = self._get_billing_period()
        error_payload = {
            "error": "budget_cap_reached",
            "message": f"Monthly budget of ${float(cap.amount):,.2f} exceeded. "
                       "Please upgrade your plan or adjust budget caps.",
            "workspace_id": workspace_id,
            "budget_cap_id": str(cap.id),
            "current_period_spend": float(current_spend),
            "estimated_request_cost": float(estimated_cost),
            "billing_period_start": period_start.isoformat(),
            "billing_period_end": period_end.isoformat(),
        }
        return True, error_payload

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _get_billing_period() -> tuple[datetime, datetime]:
        """Return (start, end) for the current monthly billing period."""
        now = datetime.utcnow()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end = now.replace(year=now.year + 1, month=1, day=1,
                              hour=0, minute=0, second=0, microsecond=0)
        else:
            end = now.replace(month=now.month + 1, day=1,
                              hour=0, minute=0, second=0, microsecond=0)
        return start, end
```

---

## TypeScript Composable (frontend/app/composables/useBillingAlerts.ts)

```typescript
/**
 * Composable for billing alerts and budget caps in the billing dashboard (F38).
 * Consumes F39 API endpoints and renders WebSocket alert events (F16).
 */

import { ref, readonly, type Ref } from 'vue'
import { useWebSocket } from './useWebSocket'
import type { ApiResponse } from '~/types/api'

// ── Types ────────────────────────────────────────────────────────────────

export interface BillingAlert {
  id: string
  workspace_id: string
  name: string
  threshold_type: 'absolute' | 'budget_percentage'
  threshold_value: number
  budget_cap_id: string | null
  enabled: boolean
  hard_cap: boolean
  notify_methods: ('in_app' | 'email' | 'webhook')[]
  notify_user_ids: string[]
  created_at: string
  updated_at: string
}

export interface BudgetCap {
  id: string
  workspace_id: string
  amount: number
  currency: string
  period: 'monthly' | 'yearly'
  hard_cap: boolean
  current_spend: number
  created_at: string
  updated_at: string
}

export interface BillingAlertEvent {
  id: string
  alert_id: string
  workspace_id: string
  status: 'active' | 'resolved'
  threshold_type: string
  threshold_value: number
  current_spend: number
  budget_cap_id: string | null
  currency: string
  billing_period_start: string
  billing_period_end: string
  fired_at: string
  resolved_at: string | null
}

interface AlertCreatePayload {
  workspace_id: string
  name: string
  threshold_type: 'absolute' | 'budget_percentage'
  threshold_value: number
  budget_cap_id?: string | null
  enabled?: boolean
  hard_cap?: boolean
  notify_methods?: string[]
  notify_user_ids?: string[]
}

interface AlertUpdatePayload {
  threshold_value?: number
  threshold_type?: string
  budget_cap_id?: string | null
  enabled?: boolean
  hard_cap?: boolean
  notify_methods?: string[]
  notify_user_ids?: string[]
}

interface BudgetCapCreatePayload {
  workspace_id: string
  amount: number
  currency?: string
  period?: 'monthly' | 'yearly'
  hard_cap?: boolean
}

// ── Composable ───────────────────────────────────────────────────────────

export function useBillingAlerts() {
  const alerts = ref<BillingAlert[]>([])
  const budgetCaps = ref<BudgetCap[]>([])
  const activeEvents = ref<BillingAlertEvent[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Connect to WebSocket for live alert events (F16)
  const { onMessage } = useWebSocket()

  onMessage((msg) => {
    if (msg.type === 'billing_alert') {
      const event: BillingAlertEvent = {
        id: msg.payload.event_id,
        alert_id: msg.payload.alert_id,
        workspace_id: msg.payload.workspace_id,
        status: 'active',
        threshold_type: msg.payload.threshold_type,
        threshold_value: msg.payload.threshold_value,
        current_spend: msg.payload.current_spend,
        budget_cap_id: null,
        currency: msg.payload.currency,
        billing_period_start: msg.payload.billing_period_start,
        billing_period_end: msg.payload.billing_period_end,
        fired_at: msg.payload.fired_at,
        resolved_at: null,
      }
      activeEvents.value.unshift(event)
    }

    if (msg.type === 'billing_alert_resolved') {
      activeEvents.value = activeEvents.value.map((e) => {
        if (e.workspace_id === msg.payload.workspace_id && e.status === 'active') {
          return { ...e, status: 'resolved' as const, resolved_at: msg.payload.resolved_at }
        }
        return e
      })
    }
  })

  // ── Alerts CRUD ──────────────────────────────────────────────────────

  async function fetchAlerts(workspaceId: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/billing-alerts?workspace_id=${workspaceId}`, {
        headers: { Accept: 'application/vnd.api+json' },
      })
      if (!res.ok) throw new Error(`Fetch failed: ${res.status}`)
      const json: ApiResponse<BillingAlert[]> = await res.json()
      alerts.value = json.data
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createAlert(payload: AlertCreatePayload): Promise<BillingAlert | null> {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/billing-alerts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/vnd.api+json',
          Accept: 'application/vnd.api+json',
        },
        body: JSON.stringify({ data: { type: 'billing-alerts', attributes: payload } }),
      })
      if (!res.ok) throw new Error(`Create failed: ${res.status}`)
      const json: ApiResponse<BillingAlert> = await res.json()
      alerts.value.push(json.data)
      return json.data
    } catch (e: any) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateAlert(
    alertId: string,
    payload: AlertUpdatePayload,
  ): Promise<BillingAlert | null> {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/billing-alerts/${alertId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/vnd.api+json',
          Accept: 'application/vnd.api+json',
        },
        body: JSON.stringify({
          data: { id: alertId, type: 'billing-alerts', attributes: payload },
        }),
      })
      if (!res.ok) throw new Error(`Update failed: ${res.status}`)
      const json: ApiResponse<BillingAlert> = await res.json()
      const idx = alerts.value.findIndex((a) => a.id === alertId)
      if (idx !== -1) alerts.value[idx] = json.data
      return json.data
    } catch (e: any) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function deleteAlert(alertId: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/billing-alerts/${alertId}`, {
        method: 'DELETE',
        headers: { Accept: 'application/vnd.api+json' },
      })
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`)
      alerts.value = alerts.value.filter((a) => a.id !== alertId)
      return true
    } catch (e: any) {
      error.value = e.message
      return false
    } finally {
      loading.value = false
    }
  }

  // ── Budget Caps CRUD ─────────────────────────────────────────────────

  async function fetchBudgetCaps(workspaceId: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/budget-caps?workspace_id=${workspaceId}`, {
        headers: { Accept: 'application/vnd.api+json' },
      })
      if (!res.ok) throw new Error(`Fetch failed: ${res.status}`)
      const json: ApiResponse<BudgetCap[]> = await res.json()
      budgetCaps.value = json.data
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createBudgetCap(payload: BudgetCapCreatePayload): Promise<BudgetCap | null> {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/budget-caps', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/vnd.api+json',
          Accept: 'application/vnd.api+json',
        },
        body: JSON.stringify({ data: { type: 'budget-caps', attributes: payload } }),
      })
      if (!res.ok) throw new Error(`Create failed: ${res.status}`)
      const json: ApiResponse<BudgetCap> = await res.json()
      const idx = budgetCaps.value.findIndex(
        (c) => c.workspace_id === payload.workspace_id && c.period === (payload.period ?? 'monthly'),
      )
      if (idx !== -1) budgetCaps.value[idx] = json.data
      else budgetCaps.value.push(json.data)
      return json.data
    } catch (e: any) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  // ── Computed helpers ─────────────────────────────────────────────────

  function alertsForWorkspace(workspaceId: string): BillingAlert[] {
    return alerts.value.filter((a) => a.workspace_id === workspaceId)
  }

  function activeEventsForWorkspace(workspaceId: string): BillingAlertEvent[] {
    return activeEvents.value.filter(
      (e) => e.workspace_id === workspaceId && e.status === 'active',
    )
  }

  function budgetCapForWorkspace(workspaceId: string): BudgetCap | undefined {
    return budgetCaps.value.find((c) => c.workspace_id === workspaceId)
  }

  return {
    // State
    alerts: readonly(alerts),
    budgetCaps: readonly(budgetCaps),
    activeEvents: readonly(activeEvents),
    loading: readonly(loading),
    error: readonly(error),

    // Alerts
    fetchAlerts,
    createAlert,
    updateAlert,
    deleteAlert,

    // Budget Caps
    fetchBudgetCaps,
    createBudgetCap,

    // Helpers
    alertsForWorkspace,
    activeEventsForWorkspace,
    budgetCapForWorkspace,
  }
}
```
