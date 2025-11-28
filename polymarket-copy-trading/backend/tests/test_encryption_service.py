"""
Unit Tests for Encryption Service

Tests for AES-256-GCM encryption with Argon2id key derivation.
"""

import pytest
import os
from unittest.mock import Mock, patch

from app.services.encryption_service import (
    EncryptionService,
    EncryptionError,
    DecryptionError,
    get_encryption_service
)


class TestEncryptionService:
    """Test suite for EncryptionService"""
    
    @pytest.fixture
    def encryption_service(self):
        """Create encryption service with test master key"""
        with patch('app.services.encryption_service.settings') as mock_settings:
            # Generate test master key (base64 encoded)
            import base64
            test_key = os.urandom(32)
            mock_settings.MASTER_ENCRYPTION_KEY = base64.b64encode(test_key).decode()
            
            service = EncryptionService()
            return service
    
    def test_generate_salt(self, encryption_service):
        """Test salt generation"""
        salt1 = encryption_service.generate_salt()
        salt2 = encryption_service.generate_salt()
        
        assert len(salt1) == encryption_service.SALT_LENGTH
        assert len(salt2) == encryption_service.SALT_LENGTH
        assert salt1 != salt2  # Should be random
    
    def test_derive_user_key(self, encryption_service):
        """Test Argon2id key derivation"""
        user_id = 123
        salt = encryption_service.generate_salt()
        
        key1 = encryption_service.derive_user_key(user_id, salt)
        key2 = encryption_service.derive_user_key(user_id, salt)
        
        # Same user + same salt = same key
        assert key1 == key2
        assert len(key1) == encryption_service.KEY_LENGTH
    
    def test_derive_user_key_different_users(self, encryption_service):
        """Test that different users get different keys"""
        salt = encryption_service.generate_salt()
        
        key1 = encryption_service.derive_user_key(123, salt)
        key2 = encryption_service.derive_user_key(456, salt)
        
        # Different users = different keys
        assert key1 != key2
    
    def test_derive_user_key_different_salts(self, encryption_service):
        """Test that different salts produce different keys"""
        user_id = 123
        salt1 = encryption_service.generate_salt()
        salt2 = encryption_service.generate_salt()
        
        key1 = encryption_service.derive_user_key(user_id, salt1)
        key2 = encryption_service.derive_user_key(user_id, salt2)
        
        # Different salts = different keys
        assert key1 != key2
    
    def test_encrypt_decrypt_roundtrip(self, encryption_service):
        """Test encryption and decryption roundtrip"""
        plaintext = "my_super_secret_api_key"
        user_id = 123
        
        # Encrypt
        ciphertext, nonce, salt = encryption_service.encrypt(plaintext, user_id)
        
        # Verify components have correct lengths
        assert len(nonce) == encryption_service.NONCE_LENGTH
        assert len(salt) == encryption_service.SALT_LENGTH
        assert len(ciphertext) > 0
        assert ciphertext != plaintext.encode()  # Should be encrypted
        
        # Decrypt
        decrypted = encryption_service.decrypt(ciphertext, nonce, salt, user_id)
        
        # Should match original
        assert decrypted == plaintext
    
    def test_encrypt_different_nonces(self, encryption_service):
        """Test that encrypting same plaintext produces different ciphertexts"""
        plaintext = "my_api_key"
        user_id = 123
        
        ct1, nonce1, salt1 = encryption_service.encrypt(plaintext, user_id)
        ct2, nonce2, salt2 = encryption_service.encrypt(plaintext, user_id)
        
        # Different salts and nonces
        assert nonce1 != nonce2
        assert salt1 != salt2
        assert ct1 != ct2  # Different ciphertexts
    
    def test_decrypt_wrong_user(self, encryption_service):
        """Test that decryption fails with wrong user ID"""
        plaintext = "secret"
        user_id = 123
        wrong_user_id = 456
        
        ciphertext, nonce, salt = encryption_service.encrypt(plaintext, user_id)
        
        # Try to decrypt with wrong user ID
        with pytest.raises(DecryptionError):
            encryption_service.decrypt(ciphertext, nonce, salt, wrong_user_id)
    
    def test_decrypt_tampered_ciphertext(self, encryption_service):
        """Test that decryption detects tampering"""
        plaintext = "secret"
        user_id = 123
        
        ciphertext, nonce, salt = encryption_service.encrypt(plaintext, user_id)
        
        # Tamper with ciphertext
        tampered_ciphertext = bytearray(ciphertext)
        tampered_ciphertext[0] ^= 1  # Flip one bit
        
        # Should fail authentication
        with pytest.raises(DecryptionError, match="authentication"):
            encryption_service.decrypt(bytes(tampered_ciphertext), nonce, salt, user_id)
    
    def test_compute_key_hash(self, encryption_service):
        """Test key hash computation"""
        api_key = "my_api_key_12345"
        
        hash1 = encryption_service.compute_key_hash(api_key)
        hash2 = encryption_service.compute_key_hash(api_key)
        
        # Should be deterministic
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex is 64 chars
        
        # Different keys should have different hashes
        hash3 = encryption_service.compute_key_hash("different_key")
        assert hash1 != hash3
    
    def test_rotate_user_key(self, encryption_service):
        """Test key rotation (re-encryption with new salt)"""
        plaintext = "api_key_to_rotate"
        user_id = 123
        
        # Initial encryption
        old_ct, old_nonce, old_salt = encryption_service.encrypt(plaintext, user_id)
        
        # Rotate (re-encrypt)
        new_ct, new_nonce, new_salt = encryption_service.rotate_user_key(
            old_ct, old_nonce, old_salt, user_id
        )
        
        # New encryption should have different salt and nonce
        assert new_salt != old_salt
        assert new_nonce != old_nonce
        assert new_ct != old_ct
        
        # But should decrypt to same plaintext
        decrypted = encryption_service.decrypt(new_ct, new_nonce, new_salt, user_id)
        assert decrypted == plaintext
    
    def test_encryption_service_singleton(self):
        """Test that get_encryption_service returns singleton"""
        with patch('app.services.encryption_service.settings') as mock_settings:
            import base64
            mock_settings.MASTER_ENCRYPTION_KEY = base64.b64encode(os.urandom(32)).decode()
            
            service1 = get_encryption_service()
            service2 = get_encryption_service()
            
            assert service1 is service2
    
    def test_missing_master_key(self):
        """Test that service fails without master key"""
        with patch('app.services.encryption_service.settings') as mock_settings:
            mock_settings.MASTER_ENCRYPTION_KEY = None
            
            with pytest.raises(EncryptionError, match="not configured"):
                EncryptionService()
    
    def test_encrypt_empty_string(self, encryption_service):
        """Test encryption of empty string"""
        plaintext = ""
        user_id = 123
        
        ciphertext, nonce, salt = encryption_service.encrypt(plaintext, user_id)
        decrypted = encryption_service.decrypt(ciphertext, nonce, salt, user_id)
        
        assert decrypted == plaintext
    
    def test_encrypt_unicode(self, encryption_service):
        """Test encryption of Unicode characters"""
        plaintext = "🔐 Secret key with émojis 中文"
        user_id = 123
        
        ciphertext, nonce, salt = encryption_service.encrypt(plaintext, user_id)
        decrypted = encryption_service.decrypt(ciphertext, nonce, salt, user_id)
        
        assert decrypted == plaintext
    
    def test_encrypt_long_text(self, encryption_service):
        """Test encryption of long text"""
        plaintext = "A" * 10000  # 10KB of text
        user_id = 123
        
        ciphertext, nonce, salt = encryption_service.encrypt(plaintext, user_id)
        decrypted = encryption_service.decrypt(ciphertext, nonce, salt, user_id)
        
        assert decrypted == plaintext
        assert len(ciphertext) > len(plaintext)  # GCM adds tag


@pytest.mark.asyncio
class TestEncryptionServicePerformance:
    """Performance tests for encryption service"""
    
    @pytest.fixture
    def encryption_service(self):
        with patch('app.services.encryption_service.settings') as mock_settings:
            import base64
            mock_settings.MASTER_ENCRYPTION_KEY = base64.b64encode(os.urandom(32)).decode()
            return EncryptionService()
    
    def test_key_derivation_performance(self, encryption_service, benchmark):
        """Benchmark key derivation (should be slow for security)"""
        salt = encryption_service.generate_salt()
        
        # Argon2id should take ~50-100ms for security
        result = benchmark(encryption_service.derive_user_key, 123, salt)
        assert len(result) == encryption_service.KEY_LENGTH
    
    def test_encryption_performance(self, encryption_service, benchmark):
        """Benchmark encryption speed"""
        plaintext = "test_api_key_12345"
        
        result = benchmark(encryption_service.encrypt, plaintext, 123)
        assert len(result) == 3  # ciphertext, nonce, salt
