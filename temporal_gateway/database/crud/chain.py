"""
CRUD operations for Chain model
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..models import Chain


def create_chain(
    session: Session,
    name: str,
    status: str = "initializing",
    temporal_workflow_id: Optional[str] = None,
    temporal_run_id: Optional[str] = None,
    chain_definition: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
) -> Chain:
    """Create a new chain execution record"""
    chain = Chain(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        temporal_workflow_id=temporal_workflow_id,
        temporal_run_id=temporal_run_id,
        status=status,
        chain_definition=chain_definition,
        started_at=datetime.utcnow(),
    )
    session.add(chain)
    session.commit()
    session.refresh(chain)
    return chain


def get_chain(session: Session, chain_id: str) -> Optional[Chain]:
    """Get chain by ID"""
    return session.query(Chain).filter(Chain.id == chain_id).first()


def get_chain_by_temporal_id(session: Session, temporal_workflow_id: str) -> Optional[Chain]:
    """Get chain by Temporal workflow ID"""
    return session.query(Chain).filter(Chain.temporal_workflow_id == temporal_workflow_id).first()


def update_chain_status(
    session: Session,
    chain_id: str,
    status: str,
    current_level: Optional[int] = None,
    error_message: Optional[str] = None,
) -> Optional[Chain]:
    """Update chain status"""
    chain = get_chain(session, chain_id)
    if not chain:
        return None

    chain.status = status
    if current_level is not None:
        chain.current_level = current_level
    if error_message:
        chain.error_message = error_message
    if status in ["completed", "failed", "cancelled"]:
        chain.completed_at = datetime.utcnow()

    session.commit()
    session.refresh(chain)
    return chain


def list_chains(
    session: Session,
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
) -> List[Chain]:
    """List chains with optional filtering"""
    query = session.query(Chain)
    if status:
        query = query.filter(Chain.status == status)
    return query.order_by(desc(Chain.started_at)).limit(limit).offset(offset).all()


def delete_chain(session: Session, chain_id: str) -> bool:
    """Delete a chain and all associated workflows/artifacts (cascade)"""
    chain = get_chain(session, chain_id)
    if not chain:
        return False

    session.delete(chain)
    session.commit()
    return True
