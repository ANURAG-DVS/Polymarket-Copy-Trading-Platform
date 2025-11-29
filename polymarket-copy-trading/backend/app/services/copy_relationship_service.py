from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, status
from app.models.copy_relationship import CopyRelationship, RelationshipStatus
from app.models.user import User
from app.models.trader import Trader
from app.schemas.trader import CopyRelationshipCreate
import logging

logger = logging.getLogger(__name__)

class CopyRelationshipService:
    """Service for managing copy trading relationships"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_relationship(
        self,
        user_id: int,
        relationship_data: CopyRelationshipCreate
    ) -> CopyRelationship:
        """Create a new copy relationship"""
        
        # Check if trader exists
        trader_result = await self.db.execute(
            select(Trader).where(Trader.id == relationship_data.trader_id)
        )
        trader = trader_result.scalars().first()
        
        if not trader:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trader not found"
            )
        
        # Check if relationship already exists
        existing = await self.db.execute(
            select(CopyRelationship).where(
                and_(
                    CopyRelationship.user_id == user_id,
                    CopyRelationship.trader_id == relationship_data.trader_id,
                    CopyRelationship.status != RelationshipStatus.STOPPED
                )
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already copying this trader"
            )
        
        # Create relationship
        relationship = CopyRelationship(
            user_id=user_id,
            trader_id=relationship_data.trader_id,
            copy_percentage=relationship_data.copy_percentage,
            max_investment_usd=relationship_data.max_investment_usd,
            status=RelationshipStatus.ACTIVE
        )
        
        self.db.add(relationship)
        await self.db.commit()
        await self.db.refresh(relationship)
        
        logger.info(f"Created copy relationship: user {user_id} -> trader {relationship_data.trader_id}")
        return relationship
    
    async def get_user_relationships(
        self,
        user_id: int,
        include_stopped: bool = False
    ) -> List[CopyRelationship]:
        """Get all copy relationships for a user"""
        query = select(CopyRelationship).where(
            CopyRelationship.user_id == user_id
        )
        
        if not include_stopped:
            query = query.where(
                CopyRelationship.status != RelationshipStatus.STOPPED
            )
        
        query = query.order_by(CopyRelationship.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_relationship_status(
        self,
        relationship_id: int,
        user_id: int,
        new_status: RelationshipStatus
    ) -> CopyRelationship:
        """Update relationship status (pause/resume/stop)"""
        result = await self.db.execute(
            select(CopyRelationship).where(
                and_(
                    CopyRelationship.id == relationship_id,
                    CopyRelationship.user_id == user_id
                )
            )
        )
        relationship = result.scalars().first()
        
        if not relationship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Copy relationship not found"
            )
        
        relationship.status = new_status
        
        if new_status == RelationshipStatus.PAUSED:
            from datetime import datetime
            relationship.paused_at = datetime.utcnow()
        elif new_status == RelationshipStatus.STOPPED:
            from datetime import datetime
            relationship.stopped_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(relationship)
        
        logger.info(f"Updated relationship {relationship_id} status to {new_status}")
        return relationship
    
    async def update_relationship_settings(
        self,
        relationship_id: int,
        user_id: int,
        copy_percentage: Optional[float] = None,
        max_investment_usd: Optional[float] = None
    ) -> CopyRelationship:
        """Update relationship settings"""
        result = await self.db.execute(
            select(CopyRelationship).where(
                and_(
                    CopyRelationship.id == relationship_id,
                    CopyRelationship.user_id == user_id
                )
            )
        )
        relationship = result.scalars().first()
        
        if not relationship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Copy relationship not found"
            )
        
        if copy_percentage is not None:
            relationship.copy_percentage = copy_percentage
        
        if max_investment_usd is not None:
            relationship.max_investment_usd = max_investment_usd
        
        await self.db.commit()
        await self.db.refresh(relationship)
        
        logger.info(f"Updated relationship {relationship_id} settings")
        return relationship
