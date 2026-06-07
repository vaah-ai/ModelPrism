# F4: JSON:API serialization layer

## Metadata
- **ID:** F4
- **Phase:** Foundation
- **Effort:** Medium
- **Dependencies:** F3
- **Acceptance Criteria Count:** 6

## Description
Build a reusable JSON:API 1.0 serialization layer in `backend/app/schemas/` that converts SQLAlchemy ORM models into standard-compliant `ResourceObject`, `Document`, and `Error` payloads (`application/vnd.api+json`). This layer provides base Pydantic schemas for resource serialization with automatic `type` and `id` fields, a pagination envelope (offset/limit + `total` + links), structured error formatting (status/code/title/detail/source), and utility parsers for query-string filter, sort, and sparse-fieldset parameters that route handlers inject into service-layer queries.

## Concrete Examples (Specification by Example)

### Example 1: Single Resource Response
- **Input:** The frontend requests `GET /api/agents/550e8400-e29b-41d4-a716-446655440000` and the route handler fetches the agent ORM row from the database.
- **Action:** The handler calls `AgentSchema.from_orm(agent_row)` which produces a JSON:API `Document` with a single `ResourceObject` in the `data` key. The schema reads the ORM model's `id` (UUID as string), `type: "agents"`, and maps specified ORM columns to an `attributes` dictionary with camelCase keys.
- **Expected Output:**
  ```json
  {
    "data": {
      "type": "agents",
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "attributes": {
        "friendlyName": "cyan-koala-42",
        "customName": null,
        "status": "online",
        "agentVersion": "0.1.0",
        "lastSeenAt": "2026-06-07T12:00:02+00:00",
        "registeredAt": "2026-06-01T08:00:00+00:00",
        "hardwareInfo": {
          "gpu_models": ["NVIDIA A100-SXM4-80GB"],
          "gpu_count": 1,
          "total_vram_gb": 80,
          "total_ram_gb": 512,
          "total_disk_gb": 2048
        },
        "hourlyRateCents": 150
      },
      "relationships": {
        "modelDeployments": {
          "links": {
            "related": "/api/agents/550e8400-e29b-41d4-a716-446655440000/models"
          }
        }
      },
      "links": {
        "self": "/api/agents/550e8400-e29b-41d4-a716-446655440000"
      }
    }
  }
  ```

### Example 2: Paginated Collection Response
- **Input:** The frontend requests `GET /api/agents?page[offset]=0&page[limit]=20&sort=-status,createdAt` to list all agents in the workspace, sorted by status descending then creation date ascending.
- **Action:** The route handler passes the parsed `SortParam` and `PaginationParams` to the service layer, which queries the database with `ORDER BY status DESC, created_at ASC` and `LIMIT 20 OFFSET 0`. The handler wraps the resulting rows in `AgentSchema.from_orm_list(agents, count=total)`.
- **Expected Output:**
  ```json
  {
    "data": [
      {
        "type": "agents",
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "attributes": { "friendlyName": "cyan-koala-42", "status": "online", ... },
        "links": { "self": "/api/agents/..." }
      }
    ],
    "meta": {
      "total": 14,
      "count": 20,
      "offset": 0,
      "limit": 20
    },
    "links": {
      "self": "/api/agents?page%5Boffset%5D=0&page%5Blimit%5D=20&sort=-status,createdAt",
      "first": "/api/agents?page%5Boffset%5D=0&page%5Blimit%5D=20&sort=-status,createdAt",
      "last": "/api/agents?page%5Boffset%5D=0&page%5Blimit%5D=20&sort=-status,createdAt",
      "next": null,
      "prev": null
    }
  }
  ```

### Example 3: Validation Error Response
- **Input:** The frontend sends `POST /api/models/deploy` with an invalid body — missing `modelName` and an invalid `port` value of `999999`.
- **Action:** FastAPI's Pydantic request validation catches the errors before the handler executes. The JSON:API error formatter converts each Pydantic `ValidationError` item into a JSON:API error object with `status`, `code`, `title`, `detail`, and `source.pointer`.
- **Expected Output:**
  ```json
  {
    "errors": [
      {
        "status": "422",
        "code": "VALIDATION_ERROR",
        "title": "Missing required field",
        "detail": "The 'modelName' field is required.",
        "source": { "pointer": "/data/attributes/modelName" }
      },
      {
        "status": "422",
        "code": "VALIDATION_ERROR",
        "title": "Invalid field value",
        "detail": "Port must be between 1024 and 65535.",
        "source": { "pointer": "/data/attributes/port" }
      }
    ]
  }
  ```

### Example 4: Resource Not Found with JSON:API Error
- **Input:** The frontend requests `GET /api/models/00000000-0000-0000-0000-000000000000` (a UUID that does not exist in the database).
- **Action:** The service layer returns `None`. The route handler calls `jsonapi_error(404, "RESOURCE_NOT_FOUND", "Model not found", detail="No model exists with the specified ID.")`.
- **Expected Output:**
  ```json
  {
    "errors": [
      {
        "status": "404",
        "code": "RESOURCE_NOT_FOUND",
        "title": "Model not found",
        "detail": "No model exists with the specified ID."
      }
    ]
  }
  ```

### Example 5: Sparse Fieldsets (Client-Side Field Selection)
- **Input:** The frontend requests `GET /api/agents?fields[agents]=friendlyName,status,hardwareInfo` to reduce payload size for a large agent list.
- **Action:** The `FieldSetParser` extracts the `fields[agents]` query parameter and passes the allowlist to `AgentSchema.from_orm_list()`. The schema only serializes the requested attributes.
- **Expected Output:**
  ```json
  {
    "data": [
      {
        "type": "agents",
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "attributes": {
          "friendlyName": "cyan-koala-42",
          "status": "online",
          "hardwareInfo": { ... }
        },
        "links": { "self": "/api/agents/..." }
      }
    ],
    "meta": { "total": 14, "count": 20, "offset": 0, "limit": 20 },
    "links": { ... }
  }
  ```

### Example 6: Filtered Collection with Multiple Filters
- **Input:** The frontend requests `GET /api/agents?filter[status]=online&filter[search]=koala` to list only online agents whose friendly name or custom name contains "koala".
- **Action:** The `FilterParser` extracts `filter[status]=online` and `filter[search]=koala`, converting them into a structured dict. The service layer applies `WHERE agents.status = 'online' AND (agents.friendly_name ILIKE '%koala%' OR agents.custom_name ILIKE '%koala%')` and returns only the matching agents.
- **Expected Output:**
  ```json
  {
    "data": [
      {
        "type": "agents",
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "attributes": { "friendlyName": "cyan-koala-42", "status": "online", ... },
        "links": { "self": "/api/agents/..." }
      }
    ],
    "meta": { "total": 1, "count": 20, "offset": 0, "limit": 20 },
    "links": { ... }
  }
  ```

## Acceptance Criteria

- **ACF4-1: Base `ResourceObject` schema enforces JSON:API structure** — Every resource response payload serializes into a JSON:API `ResourceObject` containing `type` (derived from the model class, e.g., `"agents"`), `id` (UUID as string), `attributes` (mapped ORM columns with `snake_case` to `camelCase` key conversion), `relationships` (link objects for related resources), and `links.self` (canonical resource URL). The `data` key at the document root wraps single resources as an object and collections as an array, per JSON:API 1.0 specification.

- **ACF4-2: Pagination envelope supports offset/limit with `total`, `count`, and `links`** — The `PaginatedDocument` wrapper includes a `meta` object with `total` (total matching records), `count` (number in this page), `offset`, and `limit`. The `links` object contains `self`, `first`, `last`, `next`, and `prev` URLs with properly encoded query parameters. When `total` fits in a single page (total <= limit), `next` and `prev` are `null` and `first == last == self`.

- **ACF4-3: Structured error formatter produces JSON:API `errors` array** — The `jsonapi_error(status, code, title, detail, source_pointer)` utility returns a JSON:API-compliant error document. Every error response is wrapped in `{"errors": [...]}`. HTTP 4xx and 5xx responses use this format exclusively for all dashboard REST endpoints. The formatter supports one error or a list of errors (for batch validation). FastAPI exception handlers (`RequestValidationError`, `HTTPException`) are registered to convert their native format into JSON:API errors.

- **ACF4-4: Filter, sort, and fieldset query-string parsers produce structured output** — Query-string parameters are parsed into typed Python objects:
  - `SortParser`: Accepts comma-separated sort fields with optional `-` prefix for descending (e.g., `sort=-status,createdAt`). Returns a list of `SortParam(field, direction)` tuples. Rejects unknown sort fields with a 400 error.
  - `FilterParser`: Accepts `filter[key]=value` and `filter[key]=val1,val2` (IN-style). Returns `dict[str, FilterValue]`. Supports operator suffixes: `filter[status][neq]=offline`, `filter[createdAt][gte]=2026-06-01` (range queries).
  - `FieldSetParser`: Accepts `fields[resourceType]=field1,field2` per the JSON:API sparse fieldsets spec. Returns `dict[str, set[str]]` keyed by resource type. Unknown fields within an allowlist are silently ignored.
  - `PaginationParser`: Accepts `page[offset]` and `page[limit]` with defaults (offset=0, limit=20) and maximums (limit max=100).

- **ACF4-5: All resource schemas inherit from a single `BaseSchema` with `from_orm` and `from_orm_list` class methods** — Concrete schemas (e.g., `AgentSchema`, `ModelDeploymentSchema`, `UserSchema`, `ApiKeySchema`, `BenchmarkRunSchema`, `UsageRecordSchema`) extend `BaseSchema[ModelType]` and declare an `AttributesModel` inner Pydantic model that defines which ORM columns are exposed and their serialized types (including `camelCase` aliases). `from_orm(orm_instance)` produces a single-resource `Document`. `from_orm_list(orm_instances, total)` produces a paginated `PaginatedDocument`. Nested JSONB columns (e.g., `agent.hardware_info`, `model_deployment.config`) are serialized as-is into the attributes dict without flattening. Enum fields are serialized as their string values (e.g., `"online"`, not `AgentStatus.ONLINE`).

- **ACF4-6: FastAPI exception handlers convert built-in errors to JSON:API format** — Three exception handlers are registered on the FastAPI app instance:
  1. `RequestValidationError` (Pydantic validation failure) → HTTP 422 with one JSON:API error per validation error, including `source.pointer` pointing to the JSON path of the invalid field.
  2. `HTTPException` (raised by route handlers, e.g., 401, 403, 404, 409) → JSON:API error using the exception's `status_code` and `detail`. The `code` field is derived from the exception's "reason" or a default mapping (404 → `"RESOURCE_NOT_FOUND"`, 401 → `"UNAUTHORIZED"`, 403 → `"FORBIDDEN"`, 409 → `"CONFLICT"`, 422 → `"VALIDATION_ERROR"`, 429 → `"RATE_LIMITED"`, 500 → `"INTERNAL_ERROR"`).
  3. `Exception` (unhandled) → HTTP 500 JSON:API error with `"INTERNAL_ERROR"` code. The server logs the full traceback server-side but returns only a generic message in the response to avoid leaking internals.

## Technical Notes

### File Structure

```
backend/app/schemas/
├── __init__.py          # Re-exports all schemas for convenient imports
├── jsonapi.py           # BaseSchema, ResourceObject, Document, PaginatedDocument, jsonapi_error
├── filters.py           # SortParser, FilterParser, FieldSetParser, PaginationParser
├── agent.py             # AgentSchema, AgentRegistrationSchema
├── model.py             # ModelDeploymentSchema
├── benchmark.py         # BenchmarkRunSchema, BenchmarkResultSchema
├── user.py              # UserSchema (limited fields — no password_hash), WorkspaceMemberSchema
├── key.py               # ApiKeySchema (excludes key_hash, includes key prefix)
└── usage.py             # UsageRecordSchema
```

### `jsonapi.py` — Core Serialization

```python
# Core pattern: BaseSchema[ModelT] generic with from_orm class methods
#
# Each concrete schema defines an inner AttributesModel:
#
# class AgentSchema(BaseSchema["Agent"]):
#     TYPE = "agents"
#
#     class AttributesModel(BaseAttributesModel):
#         friendly_name: str = Field(alias="friendlyName")
#         custom_name: str | None = Field(alias="customName")
#         status: str
#         ...
#
# Single resource:
#     doc = AgentSchema.from_orm(agent_row)
#
# Paginated collection:
#     doc = AgentSchema.from_orm_list(agent_rows, total=42)
```

### Key Serialization Rules

| ORM → JSON | Rule |
|-----------|------|
| Column names | `snake_case` → `camelCase` via Pydantic `alias` |
| UUIDs | Serialized as lowercase strings per JSON:API spec |
| `datetime` | ISO 8601 with timezone (`2026-06-07T12:00:02+00:00`) |
| `Enum` fields | `.value` string (e.g., `"online"`, `"healthy"`) |
| `JSONB` columns | Serialized as-is (nested object inside attributes) |
| `None`/`NULL` | Omitted from attributes unless explicitly nullable with `Field(default=None)` |
| `Decimal`/`int` cents | Serialized as integer (e.g., `hourlyRateCents: 150`) |

### Query Parameter Parsing (filters.py)

```python
@dataclass
class SortParam:
    field: str       # snake_case field name
    direction: Literal["asc", "desc"]

@dataclass
class FilterValue:
    eq: str | list[str] | None = None
    neq: str | None = None
    gte: str | None = None   # ISO datetime or numeric
    lte: str | None = None
    like: str | None = None  # ILIKE pattern

class PaginationParams:
    offset: int = 0
    limit: int = 20           # max 100

class SortParser:
    ALLOWED_FIELDS: dict[str, str]   # {"friendlyName": "friendly_name", ...}

class FilterParser:
    ALLOWED_FILTERS: dict[str, str]  # {"status": "status", "search": None, ...}
```

### Integration Points

- **F3 (Database schema):** Each ORM model in `backend/app/models/` gets a corresponding schema in `backend/app/schemas/`. The schema maps ORM columns to JSON:API attributes. Relationship links reference the route paths defined in the API surface.

- **F5 (Auth):** The `UserSchema` is used for `GET /api/auth/me` and `PUT /api/auth/me` responses. It explicitly excludes `password_hash`, `failed_login_attempts`, and `locked_until` from the serialized attributes.

- **F6 (Agent registration):** `AgentSchema` serializes the newly created agent row for the registration response. The `AgentRegistrationSchema` handles the request/response for token generation and the two-phase claim flow.

- **F7-F13 (Agent system):** All agent-related CRUD endpoints use `AgentSchema`, `ModelDeploymentSchema`, and `UsageRecordSchema` for their response bodies.

- **F14-F17 (Dashboard):** The frontend consumes JSON:API responses via Nuxt's `useFetch` or a small JSON:API deserializer composable. The pagination envelope powers infinite-scroll and page-based list views in the dashboard UI.

- **F18-F23 (Model management):** `ModelDeploymentSchema` and related schemas serialize model deployment data for the deploy wizard and running model views.

- **F25 (Benchmark storage):** `BenchmarkRunSchema` and `BenchmarkResultSchema` handle benchmark data serialization with nested results within a run.

- **F27 (API keys):** `ApiKeySchema` serializes key metadata but never exposes the raw key or `key_hash`. The full key is returned only once at creation time via a dedicated response field outside the JSON:API `attributes` (as a top-level `meta.key`).

- **F32 (Workspace management):** `UserSchema` and `WorkspaceMemberSchema` handle workspace membership listing and role management.

- **F37 (Billing):** Billing-related schemas handle invoice and plan data serialization.

### Error Handling Requirements

- **Validation errors:** Pydantic's `RequestValidationError` is caught by a custom FastAPI exception handler and converted to JSON:API error format. Each validation error in the list generates one error entry with a JSON Pointer `source.pointer` (e.g., `/data/attributes/modelName`).

- **Database errors:** `IntegrityError` and similar SQLAlchemy exceptions are caught at the service layer and re-raised as `HTTPException` (409 Conflict for unique violations, 422 for constraint violations). The JSON:API error handler then formats them correctly.

- **Authorization errors:** 401 and 403 errors use the JSON:API format with codes `"UNAUTHORIZED"` and `"FORBIDDEN"` respectively. The `detail` field provides a human-readable message.

- **Rate limiting:** 429 responses use `"RATE_LIMITED"` code with an optional `Retry-After` header. The error body includes `meta.retryAfter` with the seconds until the rate limit resets.

- **Unhandled exceptions:** Caught by a catch-all handler, logged with full traceback, and returned as HTTP 500 with `"INTERNAL_ERROR"` code. The `detail` field contains only a generic "An unexpected error occurred" message to avoid information leakage.

- **Content-Type enforcement:** All JSON:API responses use `Content-Type: application/vnd.api+json`. The frontend sends `Accept: application/vnd.api+json` on all dashboard API requests. A middleware rejects requests with unsupported media types with a 415 JSON:API error.

### Dependencies on F3

F4 directly depends on F3 because the schema layer imports ORM model types for generic type hints and knows the column structure for attribute mapping. Concrete schemas are developed alongside or immediately after their corresponding ORM models. The `BaseSchema` generic is parameterized with the ORM model class (`Schema[ModelT]`) to enable type-safe attribute serialization.

### Depends on: F3
