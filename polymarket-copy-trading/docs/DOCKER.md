# Docker Deployment Guide

## Overview

This guide covers deploying the Polymarket Copy Trading Platform using Docker.

## Quick Start

### Development

```bash
# Start all services
make dev

# View logs
make logs

# Stop services
make down
```

### Production

```bash
# Build images
make build

# Start production stack
make prod

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                    Nginx (80/443)                │
│              Reverse Proxy + SSL                 │
└────────────────────┬────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
┌─────────▼────────┐   ┌───────▼────────┐
│   Backend API    │   │   WebSocket    │
│   (Port 8000)    │   │                │
└─────────┬────────┘   └────────────────┘
          │
    ┌─────┴─────┬──────────┬──────────┐
    │           │          │          │
┌───▼───┐  ┌───▼───┐  ┌──▼───┐  ┌───▼────┐
│Worker │  │ Beat  │  │ Bot  │  │ Redis  │
└───┬───┘  └───────┘  └──────┘  └────────┘
    │
┌───▼─────────┐
│  PostgreSQL │
└─────────────┘
```

## Services

### Backend API
- **Image:** `polymarket-backend:latest`
- **Port:** 8000
- **Health Check:** `/health`
- **Resources:** 2 CPU, 2GB RAM

### Celery Worker
- **Image:** `polymarket-worker:latest`
- **Replicas:** 3 (production)
- **Resources:** 2 CPU, 2GB RAM

### Celery Beat
- **Image:** `polymarket-beat:latest`
- **Replicas:** 1
- **Resources:** 1 CPU, 512MB RAM

### Telegram Bot
- **Image:** `polymarket-telegram:latest`
- **Resources:** 1 CPU, 512MB RAM

### PostgreSQL
- **Image:** `postgres:15-alpine`
- **Port:** 5432
- **Persistent:** Yes

### Redis
- **Image:** `redis:7-alpine`
- **Port:** 6379
- **Persistent:** Yes

## Makefile Commands

### Development
```bash
make dev              # Start development environment
make dev-build        # Build and start development
make dev-stop         # Stop development environment
make dev-restart      # Restart development
```

### Production
```bash
make prod             # Start production environment
make prod-build       # Build and start production
make prod-stop        # Stop production
make prod-scale       # Scale workers to 5
```

### Building
```bash
make build            # Build all images
make build-backend    # Build backend only
make build-worker     # Build worker only
make build-telegram   # Build telegram bot only
```

### Testing
```bash
make test             # Run tests
make test-cov         # Run tests with coverage
```

### Database
```bash
make migrate          # Run migrations
make migrate-create   # Create new migration
make db-shell         # Open database shell
```

### Logs
```bash
make logs             # All services
make logs-backend     # Backend only
make logs-worker      # Worker only
make logs-telegram    # Telegram bot only
```

### Shell Access
```bash
make shell-backend    # Shell into backend
make shell-worker     # Shell into worker
make shell-postgres   # Shell into postgres
```

### Cleanup
```bash
make clean            # Remove all containers/volumes/images
make clean-volumes    # Remove volumes only
```

### Validation
```bash
make validate-env     # Validate environment config
make validate-docker  # Validate Docker config
```

### Security
```bash
make scan             # Scan images for vulnerabilities
```

### Monitoring
```bash
make stats            # Container stats
make ps               # Running containers
```

## Environment Configuration

### Development
```bash
cp .env.example .env.development
# Edit .env.development
make validate-env
make dev
```

### Production
```bash
# Fetch from AWS Secrets Manager
python scripts/fetch_secrets.py \
  --secret-name polymarket-copy-trading-secrets \
  --output .env.production

# Or create manually
cp .env.example .env.production
# Edit .env.production

make prod
```

## Docker Compose Files

### docker-compose.dev.yml
- Hot reload enabled
- Mounted volumes for code
- Development tools (MailHog, PGAdmin, Redis Commander)
- Exposed ports for debugging

### docker-compose.prod.yml
- No mounted volumes
- Resource limits
- Replicas for scaling
- Nginx reverse proxy
- SSL/TLS support
- Restart policies

## Building Images

### Multi-stage Backend
```dockerfile
Stage 1: Base dependencies
Stage 2: Install Python packages
Stage 3: Production with non-root user
```

### Optimization
- Layer caching
- .dockerignore files
- Alpine base images
- Multi-stage builds
- Non-root users

## Networking

### Development
- Network: `polymarket_network` (bridge)
- Service discovery by name
- All ports exposed

### Production
- Network: External load balancer
- Internal service mesh
- Only Nginx exposed (80/443)

## Volumes

### Development
```
postgres_dev_data   - Database data
redis_dev_data      - Redis persistence
```

### Production
```
postgres_prod_data  - Database data (backup daily)
redis_prod_data     - Redis persistence
```

## Health Checks

### Backend
```yaml
healthcheck:
  test: curl -f http://localhost:8000/health
  interval: 30s
  timeout: 10s
  retries: 3
```

### PostgreSQL
```yaml
healthcheck:
  test: pg_isready -U postgres
  interval: 10s
  timeout: 5s
  retries: 5
```

### Redis
```yaml
healthcheck:
  test: redis-cli ping
  interval: 10s
  timeout: 5s
  retries: 5
```

## Resource Limits

### Production
```yaml
backend:
  limits:
    cpus: '2'
    memory: 2G
  reservations:
    cpus: '1'
    memory: 1G

worker:
  limits:
    cpus: '2'
    memory: 2G
```

## Scaling

### Horizontal Scaling
```bash
# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale celery_worker=5

# Or use Makefile
make prod-scale
```

### Vertical Scaling
Edit resource limits in `docker-compose.prod.yml`

## Security

### Image Scanning
```bash
# Install Trivy
brew install trivy

# Scan images
make scan

# Or manually
trivy image polymarket-backend:latest
```

### Best Practices
✅ Non-root users in containers
✅ Multi-stage builds
✅ Minimal base images (Alpine)
✅ No secrets in images
✅ Regular security scans
✅ Updated dependencies

## Monitoring

### Container Stats
```bash
docker stats
# Or
make stats
```

### Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# With grep
docker-compose logs -f backend | grep ERROR
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs backend

# Check health
docker ps

# Shell into container
docker-compose exec backend /bin/bash
```

### Database connection failed
```bash
# Check PostgreSQL
docker-compose exec postgres pg_isready

# Check connection string
docker-compose exec backend env | grep DATABASE

# Check network
docker-compose exec backend ping postgres
```

### Out of memory
```bash
# Check stats
docker stats

# Increase limits in compose file
# Or reduce worker concurrency
```

## CI/CD Integration

### GitHub Actions
```yaml
- name: Build Docker images
  run: make build

- name: Run tests
  run: make test

- name: Push to registry
  run: |
    docker tag polymarket-backend:latest registry.com/backend:${{ github.sha }}
    docker push registry.com/backend:${{ github.sha }}
```

## Production Deployment

### AWS ECS
1. Push images to ECR
2. Create task definitions
3. Create ECS service
4. Configure load balancer
5. Set up auto-scaling

### Kubernetes
1. Create deployments
2. Create services
3. Set up ingress
4. Configure HPA

### Docker Swarm
```bash
docker swarm init
docker stack deploy -c docker-compose.prod.yml polymarket
```

## Backup & Recovery

### Database Backup
```bash
docker-compose exec postgres pg_dump -U postgres polymarket_copy > backup.sql
```

### Restore
```bash
docker-compose exec -T postgres psql -U postgres polymarket_copy < backup.sql
```

## Performance Tuning

### PostgreSQL
- Adjust `shared_buffers`
- Tune `work_mem`
- Configure connection pooling

### Redis
- Enable persistence (AOF)
- Configure maxmemory
- Set eviction policy

### Workers
- Adjust concurrency
- Configure prefetch
- Set max tasks per worker

## Support

**Issues?**
1. Check logs: `make logs`
2. Validate config: `make validate-env`
3. Check health: `make ps`
4. Review this guide
5. Contact DevOps
