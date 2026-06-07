"""Agent registration and management API routes.

Provides endpoints for the two-phase agent registration flow and
agent listing/detail.  Token generation and registration endpoints use
plain JSON; list and detail endpoints return JSON:API format.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.agent import (
    AgentCompleteRequest,
    AgentRegisterRequest,
    ClaimResponse,
    CompleteResponse,
    TokenResponse,
)
from app.schemas.jsonapi import JSONAPIDocument, resource_from_orm
from app.services import agent_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("/tokens", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_token(db: DbDep) -> dict[str, object]:
    """Generate a new agent registration token.

    The returned token is shown once — it is hashed before storage
    and cannot be retrieved again.  The prefix is safe to display in UIs.
    """
    return await agent_manager.create_registration_token(db)


@router.post("/register", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def claim_agent(
    db: DbDep,
    payload: AgentRegisterRequest,
) -> dict[str, object]:
    """Phase 1 of two-phase agent registration: claim with a token.

    Validates the registration token, reserves a friendly agent name,
    and creates the agent record in ``offline`` status.  The agent must
    call the complete endpoint within the claim timeout window.
    """
    return await agent_manager.claim_agent(
        db,
        token_str=payload.token,
        hostname=payload.hostname,
    )


@router.put(
    "/{agent_id}/register",
    response_model=CompleteResponse,
    status_code=status.HTTP_200_OK,
)
async def complete_registration(
    db: DbDep,
    agent_id: Annotated[UUID, Path(description="Agent UUID from the claim phase")],
    payload: AgentCompleteRequest,
) -> dict[str, object]:
    """Phase 2 of two-phase agent registration: submit hardware details.

    Updates the agent with GPU, CPU, disk, and OS information and sets
    the status to ``online``.  Must be called within the claim timeout
    window (default 5 minutes).
    """
    hardware = payload.model_dump(exclude_none=True)
    return await agent_manager.complete_registration_v2(db, agent_id, hardware)


@router.get("", response_model=JSONAPIDocument)
async def list_agents(db: DbDep) -> dict[str, Any]:
    """List all registered agents in JSON:API format.

    Returns basic agent info: id, name, hostname, status,
    agent-version, last-seen-at, created-at, updated-at.
    """
    agents = await agent_manager.list_agents(db)
    resources = [resource_from_orm(a) for a in agents]
    return JSONAPIDocument(
        data=resources,
        meta={"total": len(agents)},
    ).model_dump(exclude_none=True)


@router.get("/{agent_id}", response_model=JSONAPIDocument)
async def get_agent(
    db: DbDep,
    agent_id: Annotated[UUID, Path(description="Agent UUID")],
) -> dict[str, Any]:
    """Get a single agent's full details in JSON:API format.

    Returns all agent attributes including hardware specs.
    """
    agent = await agent_manager.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return JSONAPIDocument(
        data=resource_from_orm(agent),
    ).model_dump(exclude_none=True)
