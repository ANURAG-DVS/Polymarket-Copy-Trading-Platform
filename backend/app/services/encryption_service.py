"""
Encryption Service for API Key Management

Provides AES-256-GCM encryption with Argon2 key derivation for secure storage
of Polymarket API credentials. Each user gets a unique encryption key derived
from the master key and a per-user salt.

Security Features:
- AES-256-GCM authenticated encryption
- Argon2id key derivation (memory-hard, resistant to GPU attacks)
- Per-user salts for key isolation
- Cryptographically secure random nonce generation
"""

import os
import secrets
import hashlib
from typing import Tuple, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag
import argon2
from loguru import logger

from app.core.config import settings


class EncryptionError(Exception):
    """Raised when encryption operations fail"""
    pass


class DecryptionError(Exception):
    """Raised when decryption operations fail"""
    pass


class EncryptionService:
    """
    Handles encryption and decryption of sensitive data using AES-256-GCM.
    
    Uses Argon2id for key derivation to provide strong protection against
    brute-force attacks, even with powerful GPUs.
    """
    
    # AES-256 requires 32 bytes (256 bits)
    KEY_LENGTH = 32
    
    # GCM nonce should be 12 bytes (96 bits) for optimal security
    NONCE_LENGTH = 12
    
    # Salt length for key derivation (16 bytes minimum recommended)
    SALT_LENGTH = 32
    
    # Argon2id parameters (OWASP recommended values for 2023)
    ARGON2_TIME_COST = 2  # iterations
    ARGON2_MEMORY_COST = 19456  # KiB (19 MiB)
    ARGON2_PARALLELISM = 1  # number of threads
    
    def __init__(self):
        """Initialize encryption service with master key from environment"""
        self.master_key = self._get_master_key()
        logger.info("EncryptionService initialized")
    
    def _get_master_key(self) -> bytes:
        """
        Retrieve master encryption key from environment.
        
        Returns:
            Master key as bytes
            
        Raises:
            EncryptionError: If master key is not configured
        """
        master_key_b64 = settings.MASTER_ENCRYPTION_KEY
        
        if not master_key_b64:
            raise EncryptionError(
                "MASTER_ENCRYPTION_KEY not configured in environment. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        
        try:
            # Master key should be base64 encoded
            import base64
            master_key = base64.b64decode(master_key_b64)
            
            # Ensure it's the correct length
            if len(master_key) != self.KEY_LENGTH:
                # If not, hash it to get correct length
                master_key = hashlib.sha256(master_key).digest()
            
            return master_key
        except Exception as e:
            raise EncryptionError(f"Invalid MASTER_ENCRYPTION_KEY format: {e}")
    
    def generate_salt(self) -> bytes:
        """
        Generate a cryptographically secure random salt.
        
        Returns:
            Random salt bytes
        """
        return secrets.token_bytes(self.SALT_LENGTH)
    
    def derive_user_key(self, user_id: int, salt: bytes) -> bytes:
        """
        Derive a unique encryption key for a specific user using Argon2id.
        
        This ensures that even if one user's key is compromised, other users'
        data remains secure.
        
        Args:
            user_id: User's unique identifier
            salt: Per-user salt (should be stored with encrypted data)
            
        Returns:
            Derived encryption key (32 bytes)
            
        Raises:
            EncryptionError: If key derivation fails
        """
        try:
            # Use Argon2id (hybrid mode - resistant to both GPU and side-channel attacks)
            hasher = argon2.PasswordHasher(
                time_cost=self.ARGON2_TIME_COST,
                memory_cost=self.ARGON2_MEMORY_COST,
                parallelism=self.ARGON2_PARALLELISM,
                hash_len=self.KEY_LENGTH,
                salt_len=self.SALT_LENGTH,
                type=argon2.Type.ID,  # Argon2id
            )
            
            # Combine master key with user ID for input material
            input_material = self.master_key + str(user_id).encode('utf-8')
            
            # Derive key using Argon2id
            # Note: argon2.PasswordHasher returns a full hash string, we need to extract the key
            # So we'll use low-level argon2 API instead
            from argon2.low_level import hash_secret_raw
            
            derived_key = hash_secret_raw(
                secret=input_material,
                salt=salt,
                time_cost=self.ARGON2_TIME_COST,
                memory_cost=self.ARGON2_MEMORY_COST,
                parallelism=self.ARGON2_PARALLELISM,
                hash_len=self.KEY_LENGTH,
                type=argon2.Type.ID,
            )
            
            return derived_key
            
        except Exception as e:
            logger.error(f"Key derivation failed for user {user_id}: {e}")
            raise EncryptionError(f"Failed to derive user key: {e}")
    
    def encrypt(self, plaintext: str, user_id: int, salt: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypt plaintext using AES-256-GCM.
        
        Args:
            plaintext: Data to encrypt
            user_id: User ID for key derivation
            salt: Optional salt (will generate new one if not provided)
            
        Returns:
            Tuple of (ciphertext, nonce, salt) - all as bytes
            Store all three for decryption
            
        Raises:
            EncryptionError: If encryption fails
        """
        try:
            # Generate salt if not provided
            if salt is None:
                salt = self.generate_salt()
            
            # Derive user-specific key
            key = self.derive_user_key(user_id, salt)
            
            # Create AES-GCM cipher
            aesgcm = AESGCM(key)
            
            # Generate random nonce (MUST be unique for each encryption)
            nonce = secrets.token_bytes(self.NONCE_LENGTH)
            
            # Encrypt plaintext
            # GCM provides both confidentiality and authenticity
            ciphertext = aesgcm.encrypt(
                nonce=nonce,
                data=plaintext.encode('utf-8'),
                associated_data=None  # Can add user_id here for additional binding
            )
            
            logger.debug(f"Successfully encrypted data for user {user_id}")
            return ciphertext, nonce, salt
            
        except Exception as e:
            logger.error(f"Encryption failed for user {user_id}: {e}")
            raise EncryptionError(f"Encryption failed: {e}")
    
    def decrypt(self, ciphertext: bytes, nonce: bytes, salt: bytes, user_id: int) -> str:
        """
        Decrypt ciphertext using AES-256-GCM.
        
        Args:
            ciphertext: Encrypted data
            nonce: Nonce used during encryption
            salt: Salt used for key derivation
            user_id: User ID for key derivation
            
        Returns:
            Decrypted plaintext as string
            
        Raises:
            DecryptionError: If decryption fails or authentication tag is invalid
        """
        try:
            # Derive the same user-specific key
            key = self.derive_user_key(user_id, salt)
            
            # Create AES-GCM cipher
            aesgcm = AESGCM(key)
            
            # Decrypt and verify
            plaintext_bytes = aesgcm.decrypt(
                nonce=nonce,
                data=ciphertext,
                associated_data=None
            )
            
            plaintext = plaintext_bytes.decode('utf-8')
            logger.debug(f"Successfully decrypted data for user {user_id}")
            return plaintext
            
        except InvalidTag:
            logger.error(f"Authentication tag verification failed for user {user_id} - data may be tampered")
            raise DecryptionError("Decryption failed: Data authentication failed (possible tampering)")
        except Exception as e:
            logger.error(f"Decryption failed for user {user_id}: {e}")
            raise DecryptionError(f"Decryption failed: {e}")
    
    def compute_key_hash(self, plaintext_key: str) -> str:
        """
        Compute SHA-256 hash of API key for lookup without decryption.
        
        Args:
            plaintext_key: API key in plaintext
            
        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(plaintext_key.encode('utf-8')).hexdigest()
    
    def rotate_user_key(
        self, 
        old_ciphertext: bytes, 
        old_nonce: bytes, 
        old_salt: bytes, 
        user_id: int
    ) -> Tuple[bytes, bytes, bytes]:
        """
        Re-encrypt data with a new salt (key rotation).
        
        Args:
            old_ciphertext: Previously encrypted data
            old_nonce: Previous nonce
            old_salt: Previous salt
            user_id: User ID
            
        Returns:
            Tuple of (new_ciphertext, new_nonce, new_salt)
            
        Raises:
            DecryptionError: If old data cannot be decrypted
            EncryptionError: If re-encryption fails
        """
        # Decrypt with old key
        plaintext = self.decrypt(old_ciphertext, old_nonce, old_salt, user_id)
        
        # Re-encrypt with new salt
        return self.encrypt(plaintext, user_id, salt=None)


# Singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get singleton instance of EncryptionService.
    
    Returns:
        EncryptionService instance
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
