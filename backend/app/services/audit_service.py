"""
Audit Logging Service

Tracks all security-sensitive operations for compliance and security monitoring.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger


class AuditAction(str, Enum):
    """Enumeration of auditable actions"""
    API_KEY_STORED = "api_key_stored"
    API_KEY_RETRIEVED = "api_key_retrieved"
    API_KEY_REVOKED = "api_key_revoked"
    API_KEY_ROTATED = "api_key_rotated"
    SPEND_UPDATED = "spend_updated"
    TRADE_EXECUTED = "trade_executed"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"


class AuditService:
    """
    Logs security-sensitive operations to audit_logs table.
    """
    
    async def log(
        self,
        db: AsyncSession,
        user_id: Optional[int],
        action: AuditAction,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Log an auditable action.
        
        Args:
            db: Database session
            user_id: User performing the action (None for system actions)
            action: Type of action performed
            resource_type: Type of resource affected (e.g., 'api_key', 'trade')
            resource_id: ID of affected resource
            details: Additional details as JSON
            ip_address: Optional IP address
            user_agent: Optional user agent string
        """
        from app.models.audit_log import AuditLog
        
        audit_log = AuditLog(
            user_id=user_id,
            action=action.value,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow()
        )
        
        db.add(audit_log)
        # Don't flush - let the caller manage transaction
        
        logger.info(f"Audit log: {action.value} by user {user_id} on {resource_type}:{resource_id}")


# Singleton instance
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """Get singleton instance of AuditService"""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
