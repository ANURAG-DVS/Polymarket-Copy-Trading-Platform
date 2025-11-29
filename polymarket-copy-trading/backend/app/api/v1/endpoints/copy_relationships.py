from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.copy_relationship import RelationshipStatus
from app.schemas.trader import CopyRelationshipCreate, CopyRelationshipResponse
from app.services.copy_relationship_service import CopyRelationshipService

router = APIRouter()

@router.post("", response_model=CopyRelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_copy_relationship(
    relationship_data: CopyRelationshipCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a copy trading relationship
    
    Start copying a trader's positions with specified percentage and max investment
    """
    copy_service = CopyRelationshipService(db)
    
    relationship = await copy_service.create_relationship(
        user_id=current_user.id,
        relationship_data=relationship_data
    )
    
    return CopyRelationshipResponse.from_orm(relationship)

@router.get("", response_model=List[CopyRelationshipResponse])
async def get_my_copy_relationships(
    include_stopped: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all copy relationships for the current user
    """
    copy_service = CopyRelationshipService(db)
    
    relationships = await copy_service.get_user_relationships(
        user_id=current_user.id,
        include_stopped=include_stopped
    )
    
    return [CopyRelationshipResponse.from_orm(r) for r in relationships]

@router.patch("/{relationship_id}/status", response_model=CopyRelationshipResponse)
async def update_relationship_status(
    relationship_id: int,
    new_status: RelationshipStatus,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update copy relationship status (pause/resume/stop)
    """
    copy_service = CopyRelationshipService(db)
    
    relationship = await copy_service.update_relationship_status(
        relationship_id=relationship_id,
        user_id=current_user.id,
        new_status=new_status
    )
    
    return CopyRelationshipResponse.from_orm(relationship)

@router.patch("/{relationship_id}/settings", response_model=CopyRelationshipResponse)
async def update_relationship_settings(
    relationship_id: int,
    copy_percentage: float = None,
    max_investment_usd: float = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update copy relationship settings
    """
    copy_service = CopyRelationshipService(db)
    
    relationship = await copy_service.update_relationship_settings(
        relationship_id=relationship_id,
        user_id=current_user.id,
        copy_percentage=copy_percentage,
        max_investment_usd=max_investment_usd
    )
    
    return CopyRelationshipResponse.from_orm(relationship)

@router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def stop_copying_trader(
    relationship_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Stop copying a trader (same as setting status to STOPPED)
    """
    copy_service = CopyRelationshipService(db)
    
    await copy_service.update_relationship_status(
        relationship_id=relationship_id,
        user_id=current_user.id,
        new_status=RelationshipStatus.STOPPED
    )
    
    return None
