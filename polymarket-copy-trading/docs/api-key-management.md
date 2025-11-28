# API Key Management System - Setup & Usage Guide

## Overview

Secure API key management system for storing Polymarket credentials with:
- **AES-256-GCM** encryption with authenticated encryption
- **Argon2id** key derivation (memory-hard, GPU-resistant)
- **Per-user encryption keys** for isolation
- **Spend limit enforcement** (daily, per-trade, total exposure)
- **Audit logging** for all operations
- **Rate limiting** on decryption attempts
- **Key rotation** capabilities

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Application Layer                      │
│  (FastAPI endpoints, Celery workers)            │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│      API Key Storage Service                    │
│  • store_api_key()                              │
│  • retrieve_api_key()                           │
│  • revoke_api_key()                             │
│  • rotate_encryption_keys()                     │
└──────────┬──────────────────────┬───────────────┘
           │                      │
           ▼                      ▼
  ┌────────────────┐    ┌──────────────────┐
  │ Encryption     │    │ Spend Limit      │
  │ Service        │    │ Enforcer         │
  │ (AES + Argon2) │    │ (Multi-level)    │
  └────────┬───────┘    └────────┬─────────┘
           │                     │
           ▼                     ▼
  ┌────────────────────────────────────┐
  │         PostgreSQL Database         │
  │  • polymarket_api_keys (encrypted)  │
  │  • users (limits)                   │
  │  • trades (spend tracking)          │
  │  • audit_logs (security)            │
  └────────────────────────────────────┘
```

## Quick Setup

### 1. Generate Master Encryption Key

```bash
# Generate a secure master key (store in environment, NEVER commit!)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Add to `.env`:
```bash
MASTER_ENCRYPTION_KEY=<generated_key_here>
```

### 2. Install Dependencies

```bash
pip install -r backend/requirements.txt
pip install -r backend/requirements-security.txt
```

### 3. Run Database Migrations

```bash
cd backend
alembic upgrade head
```

### 4. Start Redis (for rate limiting)

```bash
# Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or via docker-compose
docker-compose up -d redis
```

## Usage Examples

### Store API Key

```python
from app.services.api_key_storage_service import get_api_key_storage_service
from app.db.session import get_db

storage_service = get_api_key_storage_service()

async with get_db() as db:
    key_id = await storage_service.store_api_key(
        db=db,
        user_id=123,
        api_key="your_polymarket_api_key",
        api_secret="your_polymarket_api_secret",
        private_key="optional_ethereum_private_key",  # Optional
        key_name="Main Trading Key",
        daily_spend_limit_usd=1000.00,
        expires_days=90,  # Optional expiration
        is_primary=True
    )
    
    await db.commit()
    print(f"Stored API key with ID: {key_id}")
```

### Retrieve API Key

```python
async with get_db() as db:
    credentials = await storage_service.retrieve_api_key(
        db=db,
        user_id=123
        # key_id=... optional, defaults to primary key
    )
    
    print(f"API Key: {credentials['api_key']}")
    print(f"API Secret: {credentials['api_secret']}")
    # credentials['private_key'] if stored
```

### Check Spend Limits Before Trade

```python
from app.services.spend_limit_service import get_spend_limit_service
from decimal import Decimal

spend_service = get_spend_limit_service()

async with get_db() as db:
    try:
        await spend_service.check_spend_limit(
            db=db,
            user_id=123,
            key_id=1,
            trade_amount_usd=Decimal('250.00')
        )
        print("✓ Spend limit check passed")
    except SpendLimitExceededError as e:
        print(f"✗ Spend limit exceeded: {e}")
```

### Update Spend After Trade

```python
async with get_db() as db:
    await spend_service.update_spend_tracking(
        db=db,
        user_id=123,
        key_id=1,
        trade_amount_usd=Decimal('250.00'),
        trade_id=456  # Optional
    )
    await db.commit()
```

### Revoke API Key

```python
async with get_db() as db:
    await storage_service.revoke_api_key(
        db=db,
        user_id=123,
        key_id=1,
        reason="User requested revocation"
    )
    await db.commit()
```

### Rotate Encryption Keys

```python
# Rotate all keys for a user (recommended every 90 days)
async with get_db() as db:
    await storage_service.rotate_encryption_keys(
        db=db,
        user_id=123
        # key_id=... optional, defaults to all active keys
    )
    await db.commit()
```

## Security Features

### 1. Encryption

**AES-256-GCM** (Galois/Counter Mode):
- 256-bit key length
- Authenticated encryption (prevents tampering)
- Unique nonce per encryption
- Automatic authentication tag verification

**Argon2id** Key Derivation:
- Memory-hard (19 MiB)
- Resistant to GPU attacks
- Resistant to side-channel attacks
- Per-user salt for key isolation

### 2. Rate Limiting

Prevents brute-force decryption attempts:
- **100 decryptions per user per minute**
- Uses Redis sorted sets (sliding window)
- Distributed rate limiting (works across multiple servers)

```python
# Automatically enforced in retrieve_api_key()
# Raises RateLimitExceeded if limit exceeded
```

### 3. Audit Logging

All operations logged to `audit_logs` table:
- API key stored/retrieved/revoked/rotated
- Spend limit updates
- Includes user_id, timestamp, IP address, user agent

Query audit logs:
```sql
SELECT * FROM audit_logs
WHERE user_id = 123
  AND action LIKE 'api_key_%'
ORDER BY created_at DESC
LIMIT 100;
```

### 4. Automatic Expiration

Keys can have expiration dates:
```python
await storage_service.store_api_key(
    ...,
    expires_days=90  # Expires after 90 days
)
```

Expired keys automatically rejected during retrieval.

## Spend Limit Enforcement

### Three Levels of Protection

1. **API Key Daily Limit**
   - Resets every 24 hours
   - Configurable per key

2. **User Per-Trade Limit**
   - Based on subscription tier
   - Free: $100, Pro: $2,000, Premium: $10,000

3. **Total Exposure Limit**
   - Sum of all open positions
   - Prevents over-leveraging

### Subscription Tier Limits

| Tier | Max Trade Size | Daily Limit | Total Exposure |
|------|---------------|-------------|----------------|
| Free | $100 | $500 | $500 |
| Basic | $500 | $2,500 | $2,500 |
| Pro | $2,000 | $10,000 | $10,000 |
| Premium | $10,000 | $50,000 | $100,000 |

## Production Deployment

### Environment Variables

Required in production `.env`:
```bash
# CRITICAL: Never commit this file!
MASTER_ENCRYPTION_KEY=<your_secure_key>
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://redis-host:6379/0
```

### AWS KMS Integration (Optional)

For enhanced security, use AWS KMS to manage the master encryption key:

```python
# app/services/kms_service.py
import boto3
from botocore.exceptions import ClientError

class KMSService:
    def __init__(self):
        self.kms = boto3.client('kms', region_name='us-east-1')
        self.key_id = os.getenv('AWS_KMS_KEY_ID')
    
    def get_master_key(self) -> bytes:
        """Retrieve master key from KMS"""
        try:
            response = self.kms.decrypt(
                CiphertextBlob=base64.b64decode(os.getenv('ENCRYPTED_MASTER_KEY'))
            )
            return response['Plaintext']
        except ClientError as e:
            raise EncryptionError(f"KMS decryption failed: {e}")
```

Setup:
1. Create KMS key in AWS Console
2. Encrypt your master key with KMS
3. Store encrypted result in `ENCRYPTED_MASTER_KEY` env var
4. Update `encryption_service.py` to use KMSService

### HashiCorp Vault Integration (Optional)

For dynamic secrets management:

```python
# app/services/vault_service.py
import hvac

class VaultService:
    def __init__(self):
        self.client = hvac.Client(
            url=os.getenv('VAULT_ADDR'),
            token=os.getenv('VAULT_TOKEN')
        )
    
    def get_master_key(self) -> bytes:
        """Retrieve master key from Vault"""
        secret = self.client.secrets.kv.v2.read_secret_version(
            path='polymarket/master_encryption_key'
        )
        return base64.b64decode(secret['data']['data']['key'])
```

Setup:
1. Install Vault
2. Store master key: `vault kv put secret/polymarket/master_encryption_key key=<base64_key>`
3. Configure access policies
4. Update `encryption_service.py` to use VaultService

## Testing

### Run Unit Tests

```bash
cd backend
pytest tests/test_encryption_service.py -v
pytest tests/test_api_key_storage_service.py -v
pytest tests/test_spend_limit_service.py -v
```

###  Test Coverage

```bash
pytest tests/ --cov=app/services --cov-report=html
open htmlcov/index.html
```

## Monitoring & Maintenance

### Daily Tasks

1. **Monitor Failed Decryptions**
```sql
SELECT COUNT(*) as failed_attempts, user_id
FROM audit_logs
WHERE action = 'api_key_retrieved'
  AND details->>'error' IS NOT NULL
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY user_id
HAVING COUNT(*) > 10;
```

2. **Check Spend Limit Usage**
```sql
SELECT 
    u.email,
    ak.daily_spent_usd,
    ak.daily_spend_limit_usd,
    (ak.daily_spent_usd / ak.daily_spend_limit_usd * 100) as usage_percent
FROM polymarket_api_keys ak
JOIN users u ON ak.user_id = u.id
WHERE ak.status = 'active'
  AND ak.daily_spent_usd > 0
ORDER BY usage_percent DESC;
```

### Weekly Tasks

1. **Rotate High-Value User Keys** (every 90 days)
2. **Review Audit Logs** for suspicious activity
3. **Check Key Expiration** and notify users

### Security Checklist

- [ ] Master encryption key stored in secure secret manager (AWS KMS/Vault)
- [ ] Database encrypted at rest
- [ ] TLS connections enforced
- [ ] Audit logs reviewed regularly
- [ ] Rate limiting enabled
- [ ] Key rotation policy established (90 days)
- [ ] Backup encryption keys securely stored
- [ ] Access logs monitored for anomalies

## Troubleshooting

### Error: "MASTER_ENCRYPTION_KEY not configured"

Generate and set the master key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add to .env: MASTER_ENCRYPTION_KEY=<output>
```

### Error: "Rate limit exceeded"

User has exceeded decryption rate limit (100/min). Wait 60 seconds or clear Redis:
```bash
redis-cli DEL "rate_limit:api_key_decrypt:123"
```

### Error: "API key has expired"

Key expiration date passed. Store a new key or remove expiration:
```sql
UPDATE polymarket_api_keys
SET expires_at = NULL
WHERE id = <key_id>;
```

## API Reference

### EncryptionService

- `encrypt(plaintext, user_id) → (ciphertext, nonce, salt)`
- `decrypt(ciphertext, nonce, salt, user_id) → plaintext`
- `compute_key_hash(plaintext_key) → hash`
- `rotate_user_key(old_ct, old_nonce, old_salt, user_id) → (new_ct, new_nonce, new_salt)`

### APIKeyStorageService

- `store_api_key(db, user_id, api_key, api_secret, **kwargs) → key_id`
- `retrieve_api_key(db, user_id, key_id=None) → dict`
- `revoke_api_key(db, user_id, key_id, reason=None) → None`
- `rotate_encryption_keys(db, user_id, key_id=None) → None`

### SpendLimitEnforcerService

- `check_spend_limit(db, user_id, key_id, trade_amount_usd) → None` (raises on exceeded)
- `update_spend_tracking(db, user_id, key_id, trade_amount_usd, trade_id=None) → None`
- `get_spend_limits_status(db, user_id, key_id=None) → dict`

## Performance

- **Encryption**: ~0.5ms per operation
- **Key Derivation**: ~50-100ms (intentionally slow for security)
- **Database Query**: ~5-10ms (indexed lookups)
- **Total Retrieval Time**: ~60-120ms

For high-throughput scenarios, consider caching decrypted keys in memory for 5 minutes with proper access controls.

## License

This implementation follows security best practices from:
- OWASP Cryptographic Storage Cheat Sheet
- NIST SP 800-132 (Password-Based Key Derivation)
- NIST SP 800-38D (AES-GCM)
