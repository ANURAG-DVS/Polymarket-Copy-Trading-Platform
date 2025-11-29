# CI/CD & Deployment Runbook

## Overview

This runbook provides operational procedures for the Polymarket Copy Trading Platform's CI/CD pipeline and deployment processes.

## Table of Contents

1. [GitHub Actions Workflows](#github-actions-workflows)
2. [Deployment Procedures](#deployment-procedures)
3. [Rollback Procedures](#rollback-procedures)
4. [Troubleshooting](#troubleshooting)
5. [Emergency Procedures](#emergency-procedures)

## GitHub Actions Workflows

### Test & Build Workflow

**Triggers:**
- Push to any branch
- Pull request to `main` or `develop`

**Jobs:**
1. **Lint** - Code quality checks
2. **Unit Tests** - Backend unit tests with coverage
3. **Integration Tests** - API integration tests
4. **Build** - Docker image builds
5. **Security Scan** - Vulnerability scanning

**Required Secrets:**
- None (uses test credentials)

**What to Watch:**
- Coverage must be >80%
- All lint checks must pass
- Docker builds must succeed
- Security scan should have no CRITICAL vulnerabilities

### Deploy Staging Workflow

**Triggers:**
- Push to `develop` branch

**Jobs:**
1. **Build and Push** - Build and push to ECR
2. **Migrate Database** - Run Alembic migrations
3. **Deploy** - Deploy to ECS staging
4. **Smoke Tests** - Basic functionality tests
5. **Notify** - Slack notification

**Required Secrets:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `STAGING_DATABASE_URL`
- `STAGING_URL`
- `SLACK_WEBHOOK`

**What to Watch:**
- Migration success
- Health check response
- Smoke test results

### Deploy Production Workflow

**Triggers:**
- Push to `main` branch
- Manual workflow dispatch

**Jobs:**
1. **Approve** - Manual approval (2 approvers)
2. **Build and Push** - Build production images
3. **Backup Database** - Create RDS snapshot
4. **Migrate Database** - Run migrations
5. **Deploy** - Blue-green deployment
6. **Health Check** - Comprehensive health checks
7. **Monitor** - Send deployment event
8. **Notify** - Team notification

**Required Secrets:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `PRODUCTION_DATABASE_URL`
- `PRODUCTION_URL`
- `RDS_INSTANCE_ID`
- `PRODUCTION_APPROVERS`
- `DATADOG_API_KEY`
- `SLACK_WEBHOOK`

**What to Watch:**
- Approval process
- Database backup completion
- Migration success
- Health check pass rate
- Service stability

## Deployment Procedures

### Staging Deployment

**Prerequisites:**
1. All tests passing on `develop`
2. Code review approved
3. No breaking changes

**Steps:**
1. Merge to `develop` branch:
   ```bash
   git checkout develop
   git pull origin develop
   git merge feature/your-branch
   git push origin develop
   ```

2. Monitor workflow:
   - Go to Actions tab
   - Watch "Deploy to Staging"
   - Check each job

3. Verify deployment:
   ```bash
   curl https://staging.polymarket-copy.com/health
   ```

4. Test critical paths:
   - User registration
   - Login
   - Browse traders
   - Create copy relationship

**Rollback if needed:**
```bash
# Via GitHub Actions
gh workflow run rollback.yml -f task_definition_revision=previous-revision

# Or manual ECS update
aws ecs update-service \
  --cluster polymarket-staging-cluster \
  --service polymarket-staging \
  --task-definition polymarket-staging:PREVIOUS_REVISION
```

### Production Deployment

**Prerequisites:**
1. Successfully deployed to staging
2. Staging tests passed
3. 2 approvers ready
4. Off-peak hours (if possible)
5. Incident response team on standby

**Steps:**

1. **Pre-deployment Checklist:**
   - [ ] All tests passing
   - [ ] Staging verified
   - [ ] Database migration tested
   - [ ] Rollback plan ready
   - [ ] Team notified
   - [ ] Monitoring dashboards open

2. **Initiate Deployment:**
   ```bash
   git checkout main
   git pull origin main
   git merge develop
   git push origin main
   ```

3. **Approve Deployment:**
   - Go to GitHub Actions
   - Find approval issue
   - 2 team members approve

4. **Monitor Deployment:**
   - Watch workflow progress
   - Monitor CloudWatch logs
   - Check DataDog dashboard
   - Watch error rates

5. **Post-Deployment Verification:**
   ```bash
   # Health check
   curl https://polymarket-copy.com/health
   
   # API test
   curl https://polymarket-copy.com/api/v1/traders/leaderboard
   
   # Check logs
   aws logs tail /ecs/polymarket-production --follow
   ```

6. **Verify Critical Paths:**
   - [ ] User can register
   - [ ] User can login
   - [ ] User can browse traders
   - [ ] User can create copy
   - [ ] Trades are executing
   - [ ] Notifications working
   - [ ] WebSocket connections stable

7. **Monitor for 30 minutes:**
   - Error rates
   - Response times
   - CPU/Memory usage
   - Database connections
   - Active users

8. **Mark Complete:**
   - Update deployment log
   - Close incident channel
   - Document any issues

## Rollback Procedures

### Automatic Rollback

**Triggers:**
- Health check failures after deployment
- Automatic rollback via workflow

**What Happens:**
1. Failed health checks detected
2. Rollback workflow triggered
3. Previous task definition deployed
4. Team notified

### Manual Rollback

**When to Rollback:**
- Critical bugs in production
- Service degradation
- Data corruption
- Security incident

**Procedure:**

1. **Assess Situation:**
   - Severity?
   - User impact?
   - Data at risk?

2. **Decide:**
   - Hotfix or rollback?
   - Database rollback needed?

3. **Execute Rollback:**

   **Application Only:**
   ```bash
   gh workflow run rollback.yml \
     -f task_definition_revision=polymarket-production:PREVIOUS_REVISION
   ```

   **Application + Database:**
   ```bash
   # Find snapshot
   aws rds describe-db-snapshots \
     --db-instance-identifier polymarket-production
   
   # Rollback
   gh workflow run rollback.yml \
     -f task_definition_revision=polymarket-production:PREVIOUS_REVISION \
     -f snapshot_id=pre-deploy-YYYYMMDD-HHMMSS
   ```

4. **Verify Rollback:**
   ```bash
   # Check health
   curl https://polymarket-copy.com/health
   
   # Check version (if endpoint exists)
   curl https://polymarket-copy.com/api/v1/version
   
   # Check logs
   aws logs tail /ecs/polymarket-production --follow
   ```

5. **Communicate:**
   - Update status page
   - Notify team
   - Post-mortem schedule

## Troubleshooting

### Build Failures

**Lint Failures:**
```bash
# Local check
cd backend
black --check app/
flake8 app/

# Fix
black app/
```

**Test Failures:**
```bash
# Run locally
cd backend
pytest tests/ -v

# Check specific test
pytest tests/unit/test_auth.py::TestLogin -v
```

**Docker Build Failures:**
```bash
# Build locally
docker build -t test ./backend

# Check logs
docker build --progress=plain -t test ./backend
```

### Deployment Failures

**ECS Deployment Stuck:**
```bash
# Check service events
aws ecs describe-services \
  --cluster polymarket-production-cluster \
  --services polymarket-production

# Check tasks
aws ecs list-tasks \
  --cluster polymarket-production-cluster \
  --service-name polymarket-production

# Describe task
aws ecs describe-tasks \
  --cluster polymarket-production-cluster \
  --tasks TASK_ARN
```

**Migration Failures:**
```bash
# Check migration status
alembic current

# Check migration history
alembic history

# Rollback one revision
alembic downgrade -1

# Try again
alembic upgrade head
```

**Health Check Failures:**
```bash
# Check application logs
aws logs tail /ecs/polymarket-production --follow

# SSH into container (if needed)
aws ecs execute-command \
  --cluster polymarket-production-cluster \
  --task TASK_ID \
  --container backend \
  --interactive \
  --command "/bin/bash"

# Check database connectivity
psql $DATABASE_URL -c "SELECT 1"
```

### Performance Issues

**High CPU:**
- Check worker concurrency
- Review recent code changes
- Check for infinite loops
- Profile application

**High Memory:**
- Check for memory leaks
- Review caching strategy
- Check connection pooling
- Reduce worker count

**Slow Responses:**
- Check database queries
- Review N+1 queries
- Check external API calls
- Review caching

## Emergency Procedures

### Service Down

**Immediate Actions:**
1. Check status page
2. Review monitoring dashboards
3. Check recent deployments
4. Review error logs

**Resolution:**
```bash
# Quick health check
curl https://polymarket-copy.com/health

# Check ECS service
aws ecs describe-services \
  --cluster polymarket-production-cluster \
  --services polymarket-production

# Force new deployment (if stuck)
aws ecs update-service \
  --cluster polymarket-production-cluster \
  --service polymarket-production \
  --force-new-deployment

# Scale up (if capacity issue)
aws ecs update-service \
  --cluster polymarket-production-cluster \
  --service polymarket-production \
  --desired-count 4
```

### Database Issues

**High Connections:**
```bash
# Check connections
SELECT count(*) FROM pg_stat_activity;

# Kill idle connections
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' 
AND state_change < current_timestamp - INTERVAL '5 minutes';
```

**Slow Queries:**
```bash
# Find slow queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query 
FROM pg_stat_activity 
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';

# Kill slow query
SELECT pg_terminate_backend(PID);
```

### Security Incident

**Immediate Actions:**
1. Assess severity
2. Contain threat
3. Preserve evidence
4. Notify security team

**Steps:**
```bash
# Rotate secrets immediately
python scripts/fetch_secrets.py --rotate

# Force logout all users
# (requires implementation)

# Enable additional logging
aws logs put-retention-policy \
  --log-group-name /ecs/polymarket-production \
  --retention-in-days 90

# Review access logs
aws logs tail /ecs/polymarket-production --since 1h
```

## Required Secrets Setup

### GitHub Secrets

**AWS:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`

**Database:**
- `STAGING_DATABASE_URL`
- `PRODUCTION_DATABASE_URL`
- `RDS_INSTANCE_ID`

**URLs:**
- `STAGING_URL`
- `PRODUCTION_URL`

**Monitoring:**
- `DATADOG_API_KEY`
- `SLACK_WEBHOOK`

**Approvers:**
- `PRODUCTION_APPROVERS` (comma-separated GitHub usernames)

### Adding Secrets

```bash
# Via GitHub CLI
gh secret set AWS_ACCESS_KEY_ID

# Via GitHub UI
# Settings → Secrets and variables → Actions → New repository secret
```

## Monitoring & Alerts

### Key Metrics

**Application:**
- Request rate
- Error rate
- Response time (p50, p95, p99)
- Active users

**Infrastructure:**
- CPU usage
- Memory usage
- Network I/O
- Disk usage

**Database:**
- Connection count
- Query time
- Cache hit rate
- Replication lag

### Alert Thresholds

**Critical:**
- Error rate > 5%
- Response time p95 > 2s
- CPU > 90%
- Memory > 95%
- Database connections > 90%

**Warning:**
- Error rate > 1%
- Response time p95 > 1s
- CPU > 75%
- Memory > 80%

## Contact Information

**On-Call Rotation:**
- Primary: [Name]
- Secondary: [Name]
- Manager: [Name]

**Escalation:**
1. On-call engineer (PagerDuty)
2. Team lead
3. Engineering manager
4. CTO

**External:**
- AWS Support: [Case Portal]
- DataD og: [Support]
- Slack: #incidents channel

## Post-Deployment Checklist

- [ ] Deployment successful
- [ ] Health checks passing
- [ ] Migrations applied
- [ ] Monitoring active
- [ ] No error spikes
- [ ] Performance normal
- [ ] Team notified
- [ ] Documentation updated
- [ ] Deployment log updated

## References

- [AWS ECS Documentation](https://d ocs.aws.amazon.com/ecs/)
- [GitHub Actions Documentation](https://docs.github.com/actions)
- [Alembic Migration Guide](https://alembic.sqlalchemy.org/)
- [Internal Wiki](https://wiki.company.com)
