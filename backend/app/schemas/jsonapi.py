"""JSON:API 1.0 base serializers.

Provides Pydantic models for the JSON:API document structure:
``ResourceObject``, ``Document``, ``Error``, and a helper function
``resource_from_orm`` to convert SQLAlchemy ORM instances into
JSON:API resource objects.

Use for all Dashboard REST endpoints (``application/vnd.api+json``).
Auth, agent registration, and proxy endpoints use plain JSON instead.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.utils.crypto import generate_agent_id


class JSONAPIResource(BaseModel):
    """A single JSON:API resource object.

    See https://jsonapi.org/format/#document-resource-objects
    """

    type: str
    id: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    relationships: dict[str, Any] | None = None
    links: dict[str, Any] | None = None


class JSONAPIDocument(BaseModel):
    """A JSON:API top-level document.

    See https://jsonapi.org/format/#document-top-level
    """

    data: JSONAPIResource | list[JSONAPIResource] | None = None
    meta: dict[str, Any] | None = None
    links: dict[str, Any] | None = None
    included: list[JSONAPIResource] | None = None
    errors: list[JSONAPIError] | None = None


class JSONAPIError(BaseModel):
    """A JSON:API error object.

    See https://jsonapi.org/format/#error-objects
    """

    status: str
    code: str
    title: str
    detail: str
    source: dict[str, Any] | None = None


def _to_kebab(name: str) -> str:
    """Convert a snake_case string to kebab-case."""
    return name.replace("_", "-")


_ATTRIBUTE_MAP: dict[str, dict[str, str]] = {
    "Agent": {
        "name": "name",
        "hostname": "hostname",
        "agent_version": "agent-version",
        "vllm_version": "vllm-version",
        "status": "status",
        "gpu_info": "gpu-info",
        "cpu_info": "cpu-info",
        "disk_info": "disk-info",
        "os_info": "os-info",
        "last_seen_at": "last-seen-at",
        "created_at": "created-at",
        "updated_at": "updated-at",
    },
}


def resource_from_orm(
    obj: Any,
    type_name: str | None = None,
    attr_map: dict[str, str] | None = None,
) -> JSONAPIResource:
    """Convert an SQLAlchemy ORM instance to a JSON:API resource object.

    The resource ``type`` defaults to the ORM class name lowercased
    (e.g. ``Agent`` → ``"agent"``).  Attribute names are converted to
    kebab-case automatically unless an explicit ``attr_map`` is provided.

    Args:
        obj: An SQLAlchemy ORM instance with a ``.id`` attribute.
        type_name: Optional explicit resource type string.  If omitted,
            the class name (lowercased) is used.
        attr_map: Optional dict mapping ORM attribute names to JSON:API
            attribute names (kebab-case).  If omitted, all public
            attributes are included with automatic kebab-case conversion.

    Returns:
        A ``JSONAPIResource`` instance.
    """
    if type_name is None:
        type_name = obj.__class__.__name__.lower()

    if attr_map is None:
        attr_map = _ATTRIBUTE_MAP.get(obj.__class__.__name__, {})

    # Build attributes from the attr_map or from all public fields
    attributes: dict[str, Any] = {}
    if attr_map:
        for orm_attr, json_key in attr_map.items():
            value = getattr(obj, orm_attr, None)
            if value is not None:
                # Serialize datetime objects to ISO strings
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                # Serialize UUID to string
                if hasattr(value, "hex") and hasattr(value, "version"):
                    value = str(value)
                attributes[json_key] = value
    else:
        table = getattr(obj, "__table__", None)
        if table is not None:
            for column in table.columns:
                field_name = column.name
                value = getattr(obj, field_name, None)
                if value is not None:
                    if hasattr(value, "isoformat"):
                        value = value.isoformat()
                    attributes[_to_kebab(field_name)] = value

    # Build self-link and ID using the human-friendly agent_id
    raw_id = obj.id
    if isinstance(raw_id, UUID):
        agent_id_str = generate_agent_id(raw_id)
    else:
        agent_id_str = str(raw_id)

    links = {"self": f"/api/agents/{agent_id_str}"}

    return JSONAPIResource(
        type=type_name,
        id=agent_id_str,
        attributes=attributes,
        links=links,
    )
