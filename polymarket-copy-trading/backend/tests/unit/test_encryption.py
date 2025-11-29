import pytest
from cryptography.fernet import Fernet
from app.core.config import settings

class TestAPIKeyEncryption:
    """Test API key encryption and decryption"""
    
    def test_encrypt_decrypt_cycle(self):
        """Test encryption and decryption produce original value"""
        # Generate key
        key = Fernet.generate_key()
        fernet = Fernet(key)
        
        # Original data
        api_key = "test_api_key_123456"
        
        # Encrypt
        encrypted = fernet.encrypt(api_key.encode())
        
        # Decrypt
        decrypted = fernet.decrypt(encrypted).decode()
        
        assert decrypted == api_key
    
    def test_encrypted_is_different(self):
        """Test that encrypted value is different from original"""
        key = Fernet.generate_key()
        fernet = Fernet(key)
        
        api_key = "test_api_key_123456"
        encrypted = fernet.encrypt(api_key.encode())
        
        assert encrypted != api_key.encode()
    
    def test_same_input_different_output(self):
        """Test that same input produces different encrypted output"""
        key = Fernet.generate_key()
        fernet = Fernet(key)
        
        api_key = "test_api_key_123456"
        encrypted1 = fernet.encrypt(api_key.encode())
        encrypted2 = fernet.encrypt(api_key.encode())
        
        # Fernet includes timestamp, so outputs differ
        assert encrypted1 != encrypted2
    
    def test_wrong_key_fails_decryption(self):
        """Test that wrong key fails decryption"""
        key1 = Fernet.generate_key()
        key2 = Fernet.generate_key()
        
        fernet1 = Fernet(key1)
        fernet2 = Fernet(key2)
        
        api_key = "test_api_key_123456"
        encrypted = fernet1.encrypt(api_key.encode())
        
        with pytest.raises(Exception):
            fernet2.decrypt(encrypted)
