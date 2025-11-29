# Environment Configuration Guide

## Quick Start

### 1. Development Setup

```bash
# Copy example environment file
cp .env.example .env.development

# Edit with your local values
nano .env.development

# Validate configuration
python scripts/validate_env.py --env-file .env.development

# Start services
docker-compose up -d
```

### 2. Required Environment Variables

All variables marked with ⚠️ **must** be set before running the application.

#### Application
- ⚠️ `NODE_ENV` - Environment (development/staging/production)
- ⚠️ `PORT` - API server port (default: 8000)
- ⚠️ `FRONTEND_URL` - Frontend application URL
- ⚠️ `API_URL` - Backend API URL

#### Database
- ⚠️ `DATABASE_URL` - Full PostgreSQL connection string
- ⚠️ `DB_HOST` - Database host
- ⚠️ `DB_PORT` - Database port
- ⚠️ `DB_NAME` - Database name
- ⚠️ `DB_USER` - Database user
- ⚠️ `DB_PASSWORD` - Database password (min 8 chars)

#### Authentication
- ⚠️ `JWT_SECRET` - JWT signing secret (**min 32 chars**)
- ⚠️ `JWT_REFRESH_SECRET` - Refresh token secret (**min 32 chars**)
- ⚠️ `MASTER_ENCRYPTION_KEY` - Fernet encryption key

#### Blockchain
- ⚠️ `POLYGON_RPC_URL` - Polygon RPC endpoint
- `POLYGON_CHAIN_ID` - Chain ID (137 for mainnet, 80001 for Mumbai testnet)

### 3. Generating Secrets

#### JWT Secrets
```bash
# Generate random 32+ character string
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### Encryption Key
```bash
# Generate Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### Database Password
```bash
# Generate strong password
python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(32)))"
```

## Environment-Specific Setup

### Development (.env.development)
- Uses local PostgreSQL and Redis
- Debug logging enabled
- CORS allows localhost origins
- Test Stripe keys
- MailHog for email testing

### Staging (.env.staging)
- Separate staging database
- Warning logs
- Limited CORS origins
- Test payment gateway
- Real email (but flagged as staging)

### Production (.env.production)
- **Never commit this file!**
- Fetch from AWS Secrets Manager
- Error-level logging only
- Strict CORS
- Production payment gateway
- Real email service

## Secrets Management

### AWS Secrets Manager (Production)

**1. Create Secret:**
```bash
aws secretsmanager create-secret \
  --name polymarket-copy-trading-secrets \
  --description "Production secrets for Polymarket Copy Trading" \
  --secret-string file://secrets.json \
  --region us-east-1
```

**2. Fetch on Startup:**
```bash
python scripts/fetch_secrets.py \
  --secret-name polymarket-copy-trading-secrets \
  --region us-east-1 \
  --output .env.production
```

**3. Rotate Secrets:**
```bash
aws secretsmanager rotate-secret \
  --secret-id polymarket-copy-trading-secrets \
  --rotation-lambda-arn arn:aws:lambda:...
```

### HashiCorp Vault (Alternative)

```bash
# Write secret
vault kv put secret/polymarket/config \
  JWT_SECRET="..." \
  DB_PASSWORD="..."

# Read secret
vault kv get -format=json secret/polymarket/config
```

## Configuration Validation

### Validate Before Startup
```bash
# Validate configuration
python scripts/validate_env.py --env-file .env.development

# Show configuration summary
python scripts/validate_env.py --summary
```

### Automated Validation
Add to startup script:
```bash
#!/bin/bash
set -e

# Validate environment
python scripts/validate_env.py || {
  echo "❌ Environment validation failed!"
  exit 1
}

# Start application
python -m app.main
```

## Docker Compose

### Start All Services
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs -f backend
```

### Stop All Services
```bash
docker-compose down
```

### Rebuild After Changes
```bash
docker-compose build
docker-compose up -d
```

## Service URLs (Development)

- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Frontend:** http://localhost:3000
- **PGAdmin:** http://localhost:5050
- **MailHog:** http://localhost:8025
- **Redis:** localhost:6379
- **PostgreSQL:** localhost:5432

## Security Best Practices

### ✅ DO:
- Use environment variables for all secrets
- Generate strong random secrets (32+ characters)
- Rotate secrets regularly (every 90 days)
- Use AWS Secrets Manager or Vault in production
- Validate configuration before startup
- Use different secrets per environment
- Add .env.* to .gitignore

### ❌ DON'T:
- Commit .env files to git
- Use same secrets across environments
- Log secret values
- Share secrets in Slack/email
- Use weak/predictable secrets
- Hardcode secrets in source code

## Troubleshooting

### Missing Environment Variable
```
❌ JWT_SECRET: MISSING (required)
```
**Solution:** Add the variable to your .env file

### Invalid Value
```
❌ PORT: Value 99999 above maximum 65535
```
**Solution:** Use a valid port number (1000-65535)

### Database Connection Failed
```
sqlalchemy.exc.OperationalError: could not connect to server
```
**Solution:**
1. Check DATABASE_URL is correct
2. Ensure PostgreSQL is running
3. Verify DB credentials

### Redis Connection Failed
```
redis.exceptions.ConnectionError: Error connecting to Redis
```
**Solution:**
1. Check REDIS_URL is correct
2. Ensure Redis is running
3. Check firewall settings

## Secrets Rotation Checklist

### Every 90 Days:
- [ ] Generate new JWT_SECRET
- [ ] Generate new JWT_REFRESH_SECRET
- [ ] Generate new MASTER_ENCRYPTION_KEY
- [ ] Update database password
- [ ] Update in AWS Secrets Manager
- [ ] Deploy with zero downtime
- [ ] Verify no auth errors
- [ ] Update backup encryption

### After Security Incident:
- [ ] Rotate ALL secrets immediately
- [ ] Review access logs
- [ ] Audit who had access
- [ ] Update secrets in all environments
- [ ] Force user re-authentication
- [ ] Document incident

## Environment Variables Reference

See [.env.example](.env.example) for complete list with descriptions.

## Support

**Issues with configuration?**
1. Run validation: `python scripts/validate_env.py`
2. Check Docker logs: `docker-compose logs`
3. Review this guide
4. Contact DevOps team
