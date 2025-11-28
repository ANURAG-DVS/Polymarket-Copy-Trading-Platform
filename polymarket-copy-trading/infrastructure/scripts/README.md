# Quick Start Scripts

This directory contains utility scripts for common operations.

## Available Scripts

### Database Management

```bash
# Initialize database
./scripts/init-db.sh

# Run migrations
./scripts/migrate.sh

# Backup database
./scripts/backup-db.sh
```

### Development

```bash
# Start all services
./scripts/dev-start.sh

# Stop all services
./scripts/dev-stop.sh

# Reset environment (WARNING: deletes all data)
./scripts/reset-env.sh
```

### Deployment

```bash
# Deploy to staging
./scripts/deploy-staging.sh

# Deploy to production
./scripts/deploy-production.sh
```

## Creating New Scripts

All scripts should:
1. Include proper error handling
2. Use shellcheck for linting
3. Include usage documentation
4. Be executable (`chmod +x script.sh`)
