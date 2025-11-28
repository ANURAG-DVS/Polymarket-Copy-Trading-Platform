"""
API Key Storage Service

Manages secure storage and retrieval of Polymarket API credentials with:
- Encrypted storage using AES-256-GCM
- Audit logging for all operations
- Rate limiting on decryption attempts
- Key expiration and rotation

Database schema:
- polymarket_api_keys table (see infrastructure/docker/schema.sql)
"""

import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.encryption_service import (
    get_encryption_service,
    EncryptionError,
    DecryptionError
)
from app.services.audit_service import get_audit_service, AuditAction
from app.services.rate_limit_service import get_rate_limit_service, RateLimitExceeded
from app.db.session import get_db
from loguru import logger


class APIKeyNotFoundError(Exception):
    """Raised when API key is not found for user"""
    pass


class APIKeyInactiveError(Exception):
    """Raised when attempting to use revoked/expired key"""
    pass


class APIKeyStorageService:
    """
    Manages secure storage and retrieval of Polymarket API credentials.
    
    Features:
    - Encrypted storage with per-user keys
    - Audit logging for all access
    - Rate limiting on decryption
    - Automatic key expiration
    """
    
    def __init__(self):
        self.encryption_service = get_encryption_service()
        self.audit_service = get_audit_service()
        self.rate_limit_service = get_rate_limit_service()
        logger.info("APIKeyStorageService initialized")
    
    async def store_api_key(
        self,
        db: AsyncSession,
        user_id: int,
        api_key: str,
        api_secret: str,
        private_key: Optional[str] = None,
        key_name: Optional[str] = None,
        daily_spend_limit_usd: float = 1000.00,
        expires_days: Optional[int] = None,
        is_primary: bool = False
    ) -> int:
        """
        Encrypt and store Polymarket API credentials.
        
        Args:
            db: Database session
            user_id: User's unique ID
            api_key: Polymarket API key (plaintext)
            api_secret: Polymarket API secret (plaintext)
            private_key: Optional Ethereum private key for direct contract interaction
            key_name: Optional user-defined name for this key set
            daily_spend_limit_usd: Daily spending limit (default: $1000)
            expires_days: Optional expiration in days
            is_primary: Whether this is the primary key for the user
            
        Returns:
            ID of created polymarket_api_keys record
            
        Raises:
            EncryptionError: If encryption fails
        """
        try:
            # Encrypt API key
            api_key_ciphertext, api_key_nonce, api_key_salt = self.encryption_service.encrypt(
                api_key, user_id
            )
            
            # Encrypt API secret
            api_secret_ciphertext, api_secret_nonce, api_secret_salt = self.encryption_service.encrypt(
                api_secret, user_id
            )
            
            # Optionally encrypt private key
            private_key_ciphertext = None
            private_key_nonce = None
            private_key_salt = None
            if private_key:
                private_key_ciphertext, private_key_nonce, private_key_salt = self.encryption_service.encrypt(
                    private_key, user_id
                )
            
            # Compute hash for lookup
            key_hash = self.encryption_service.compute_key_hash(api_key)
            
            # Calculate expiration
            expires_at = None
            if expires_days:
                expires_at = datetime.utcnow() + timedelta(days=expires_days)
            
            # Store encrypted data
            # Combined storage: ciphertext || nonce || salt (for compact storage)
            encrypted_api_key = api_key_ciphertext + api_key_nonce + api_key_salt
            encrypted_api_secret = api_secret_ciphertext + api_secret_nonce + api_secret_salt
            
            encrypted_private_key = None
            if private_key:
                encrypted_private_key = private_key_ciphertext + private_key_nonce + private_key_salt
            
            # Insert into database
            from app.models.api_key import APIKey
            
            api_key_record = APIKey(
                user_id=user_id,
                encrypted_api_key=encrypted_api_key,
                encrypted_api_secret=encrypted_api_secret,
                encrypted_private_key=encrypted_private_key,
                key_name=key_name,
                key_hash=key_hash,
                daily_spend_limit_usd=daily_spend_limit_usd,
                is_primary=is_primary,
                expires_at=expires_at,
                status='active'
            )
            
            db.add(api_key_record)
            await db.flush()
            
            # Audit log
            await self.audit_service.log(
                db=db,
                user_id=user_id,
                action=AuditAction.API_KEY_STORED,
                resource_type='api_key',
                resource_id=str(api_key_record.id),
                details={
                    'key_name': key_name,
                    'is_primary': is_primary,
                    'expires_at': expires_at.isoformat() if expires_at else None
                }
            )
            
            logger.info(f"Stored API key for user {user_id} (key_id: {api_key_record.id})")
            return api_key_record.id
            
        except Exception as e:
            logger.error(f"Failed to store API key for user {user_id}: {e}")
            raise
    
    async def retrieve_api_key(
        self,
        db: AsyncSession,
        user_id: int,
        key_id: Optional[int] = None
    ) -> Dict[str, str]:
        """
        Decrypt and retrieve Polymarket API credentials.
        
        Args:
            db: Database session
            user_id: User's unique ID
            key_id: Optional specific key ID (defaults to primary key)
            
        Returns:
            Dictionary with 'api_key', 'api_secret', and optionally 'private_key'
            
        Raises:
            APIKeyNotFoundError: If no key found
            APIKeyInactiveError: If key is revoked/expired
            DecryptionError: If decryption fails
            RateLimitExceeded: If too many decryption attempts
        """
        try:
            # Rate limiting: max 100 decryptions per user per minute
            rate_limit_key = f"api_key_decrypt:{user_id}"
            await self.rate_limit_service.check_rate_limit(
                key=rate_limit_key,
                max_requests=100,
                window_seconds=60
            )
            
            # Fetch key record
            from app.models.api_key import APIKey
            
            query = select(APIKey).where(APIKey.user_id == user_id)
            
            if key_id:
                query = query.where(APIKey.id == key_id)
            else:
                # Get primary key, or most recent active key
                query = query.where(APIKey.status == 'active')
                query = query.order_by(
                    APIKey.is_primary.desc(),
                    APIKey.created_at.desc()
                )
            
            result = await db.execute(query)
            api_key_record = result.scalar_one_or_none()
            
            if not api_key_record:
                raise APIKeyNotFoundError(f"No API key found for user {user_id}")
            
            # Check if key is active
            if api_key_record.status != 'active':
                raise APIKeyInactiveError(f"API key is {api_key_record.status}")
            
            # Check expiration
            if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
                # Mark as expired
                api_key_record.status = 'expired'
                await db.flush()
                raise APIKeyInactiveError("API key has expired")
            
            # Decrypt credentials
            # Extract components from combined storage
            api_key_data = api_key_record.encrypted_api_key
            api_secret_data = api_key_record.encrypted_api_secret
            
            # Split: last 32 bytes = salt, previous 12 bytes = nonce, rest = ciphertext
            api_key = self._decrypt_combined(api_key_data, user_id)
            api_secret = self._decrypt_combined(api_secret_data, user_id)
            
            result = {
                'api_key': api_key,
                'api_secret': api_secret,
                'key_id': api_key_record.id
            }
            
            # Optionally decrypt private key
            if api_key_record.encrypted_private_key:
                private_key = self._decrypt_combined(
                    api_key_record.encrypted_private_key, 
                    user_id
                )
                result['private_key'] = private_key
            
            # Update last_used_at
            api_key_record.last_used_at = datetime.utcnow()
            await db.flush()
            
            # Audit log
            await self.audit_service.log(
                db=db,
                user_id=user_id,
                action=AuditAction.API_KEY_RETRIEVED,
                resource_type='api_key',
                resource_id=str(api_key_record.id),
                details={'key_name': api_key_record.key_name}
            )
            
            logger.info(f"Retrieved API key for user {user_id} (key_id: {api_key_record.id})")
            return result
            
        except (APIKeyNotFoundError, APIKeyInactiveError, RateLimitExceeded):
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve API key for user {user_id}: {e}")
            raise
    
    def _decrypt_combined(self, combined_data: bytes, user_id: int) -> str:
        """
        Decrypt from combined storage format (ciphertext || nonce || salt).
        
        Args:
            combined_data: Combined encrypted data
            user_id: User ID for key derivation
            
        Returns:
            Decrypted plaintext
        """
        # Extract components
        salt = combined_data[-32:]  # Last 32 bytes
        nonce = combined_data[-44:-32]  # 12 bytes before salt
        ciphertext = combined_data[:-44]  # Everything else
        
        return self.encryption_service.decrypt(ciphertext, nonce, salt, user_id)
    
    async def revoke_api_key(
        self,
        db: AsyncSession,
        user_id: int,
        key_id: int,
        reason: Optional[str] = None
    ) -> None:
        """
        Mark API key as revoked (inactive).
        
        Args:
            db: Database session
            user_id: User's unique ID
            key_id: Key ID to revoke
            reason: Optional revocation reason
            
        Raises:
            APIKeyNotFoundError: If key not found
        """
        from app.models.api_key import APIKey
        
        # Fetch and update key
        result = await db.execute(
            select(APIKey).where(
                and_(APIKey.id == key_id, APIKey.user_id == user_id)
            )
        )
        api_key_record = result.scalar_one_or_none()
        
        if not api_key_record:
            raise APIKeyNotFoundError(f"API key {key_id} not found for user {user_id}")
        
        # Update status
        api_key_record.status = 'revoked'
        api_key_record.revoked_at = datetime.utcnow()
        api_key_record.revoked_reason = reason
        await db.flush()
        
        # Audit log
        await self.audit_service.log(
            db=db,
            user_id=user_id,
            action=AuditAction.API_KEY_REVOKED,
            resource_type='api_key',
            resource_id=str(key_id),
            details={'reason': reason}
        )
        
        logger.info(f"Revoked API key {key_id} for user {user_id}")
    
    async def rotate_encryption_keys(
        self,
        db: AsyncSession,
        user_id: int,
        key_id: Optional[int] = None
    ) -> None:
        """
        Rotate encryption keys by re-encrypting with new salts.
        
        This should be done periodically (e.g., every 90 days) or after
        a suspected security incident.
        
        Args:
            db: Database session
            user_id: User's unique ID
            key_id: Optional specific key (defaults to all user's keys)
            
        Raises:
            APIKeyNotFoundError: If no keys found
        """
        from app.models.api_key import APIKey
        
        # Fetch keys to rotate
        query = select(APIKey).where(
            and_(
                APIKey.user_id == user_id,
                APIKey.status == 'active'
            )
        )
        
        if key_id:
            query = query.where(APIKey.id == key_id)
        
        result = await db.execute(query)
        api_keys = result.scalars().all()
        
        if not api_keys:
            raise APIKeyNotFoundError(f"No active keys found for user {user_id}")
        
        rotated_count = 0
        for api_key_record in api_keys:
            try:
                # Decrypt current data
                api_key = self._decrypt_combined(api_key_record.encrypted_api_key, user_id)
                api_secret = self._decrypt_combined(api_key_record.encrypted_api_secret, user_id)
                
                private_key = None
                if api_key_record.encrypted_private_key:
                    private_key = self._decrypt_combined(
                        api_key_record.encrypted_private_key, 
                        user_id
                    )
                
                # Re-encrypt with new salts
                api_key_ct, api_key_nonce, api_key_salt = self.encryption_service.encrypt(api_key, user_id)
                api_secret_ct, api_secret_nonce, api_secret_salt = self.encryption_service.encrypt(api_secret, user_id)
                
                # Update record
                api_key_record.encrypted_api_key = api_key_ct + api_key_nonce + api_key_salt
                api_key_record.encrypted_api_secret = api_secret_ct + api_secret_nonce + api_secret_salt
                
                if private_key:
                    pk_ct, pk_nonce, pk_salt = self.encryption_service.encrypt(private_key, user_id)
                    api_key_record.encrypted_private_key = pk_ct + pk_nonce + pk_salt
                
                rotated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to rotate key {api_key_record.id}: {e}")
                continue
        
        await db.flush()
        
        # Audit log
        await self.audit_service.log(
            db=db,
            user_id=user_id,
            action=AuditAction.API_KEY_ROTATED,
            resource_type='api_key',
            resource_id=str(user_id),
            details={'rotated_count': rotated_count}
        )
        
        logger.info(f"Rotated {rotated_count} encryption keys for user {user_id}")


# Singleton instance
_api_key_storage_service: Optional[APIKeyStorageService] = None


def get_api_key_storage_service() -> APIKeyStorageService:
    """Get singleton instance of APIKeyStorageService"""
    global _api_key_storage_service
    if _api_key_storage_service is None:
        _api_key_storage_service = APIKeyStorageService()
    return _api_key_storage_service
