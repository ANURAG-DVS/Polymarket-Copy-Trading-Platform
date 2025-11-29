# On-Call Runbook

## Overview

This runbook provides step-by-step procedures for common production issues.

## Table of Contents

1. [Common Issues](#common-issues)
2. [Escalation Procedures](#escalation-procedures)
3. [Emergency Contacts](#emergency-contacts)
4. [Tools &Access](#tools--access)

## Common Issues

### Issue: Trade Execution Queue Stuck

**Symptoms:**
- Queue depth increasing
- No trades executing
- `queue.depth` metric rising

**Diagnosis:**
```bash
# Check queue depth
redis-cli LLEN trade_execution_queue

# Check worker status
aws ecs describe-services --cluster prod --service worker

# Check worker logs
aws logs tail /ecs/polymarket-worker --follow
```

**Resolution:**
```bash
# Option 1: Restart workers
aws ecs update-service \
  --cluster polymarket-production-cluster \
  --service worker \
  --force-new-deployment

# Option 2: Scale workers
aws ecs update-service \
  --cluster polymarket-production-cluster \
  --service worker \
  --desired-count 5

# Option 3: Clear stuck jobs (CAUTION)
redis-cli DEL trade_execution_queue
# Then manually requeue from database
```

**Prevention:**
- Monitor queue depth alerts
- Set up worker auto-scaling
- Implement dead letter queue

---

### Issue: Database Connection Pool Exhausted

**Symptoms:**
- `too many connections` errors
- API slow/timing out
- Health check failures

**Diagnosis:**
```bash
# Check connection count
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"

# Check idle connections
psql $DATABASE_URL -c "
  SELECT state, count(*) 
  FROM pg_stat_activity 
  GROUP BY state;
"

# Find long-running queries
psql $DATABASE_URL -c "
  SELECT pid, now() - query_start AS duration, query 
  FROM pg_stat_activity 
  WHERE state = 'active' 
  ORDER BY duration DESC 
  LIMIT 10;
"
```

**Resolution:**
```bash
# Kill idle connections
psql $DATABASE_URL -c "
  SELECT pg_terminate_backend(pid) 
  FROM pg_stat_activity 
  WHERE state = 'idle' 
  AND state_change < now() - interval '5 minutes';
"

# Restart application (resets pool)
aws ecs update-service \
  --cluster polymarket-production-cluster \
  --service backend \
  --force-new-deployment

# Increase max connections (emergency)
aws rds modify-db-parameter-group \
  --db-parameter-group-name polymarket-prod \
  --parameters "ParameterName=max_connections,ParameterValue=200,ApplyMethod=immediate"
```

**Prevention:**
- Tune connection pool size
- Implement connection timeouts
- Add connection pool monitoring

---

### Issue: Polymarket API Down/Slow

**Symptoms:**
- `polymarket_api` health check failing
- Trade execution failures
- API timeouts

**Diagnosis:**
```bash
# Test Polymarket API
curl -I https://clob.polymarket.com/markets

# Check API latency
curl -w "@curl-format.txt" -o /dev/null -s https://clob.polymarket.com/markets

# Check error logs
aws logs filter-pattern "Polymarket API" \
  --log-group-name /ecs/polymarket-backend \
  --start-time $(date -u -d '10 minutes ago' +%s)000
```

**Resolution:**
```bash
# Option 1: Enable circuit breaker
# (Requires implementation)

# Option 2: Pause auto-trading
psql $DATABASE_URL -c "
  UPDATE copy_relationships 
  SET status = 'paused', 
  auto_resume_at = NOW() + INTERVAL '1 hour';
"

# Option 3: Switch to backup RPC (if available)
# Update POLYGON_RPC_URL environment variable

# Notify users
# Send notification via Telegram bot
```

**Prevention:**
- Implement circuit breaker pattern
- Set up Polymarket API monitoring
- Have backup RPC providers

---

### Issue: High Memory Usage / OOM Kills

**Symptoms:**
- Containers restarting
- `OOMKilled` in container logs
- Slow response times

**Diagnosis:**
```bash
# Check memory usage
docker stats

# Check container restarts
docker ps -a | grep Restart

# Check OOM kills
journalctl -k | grep -i "killed process"

# Profile application (if running)
py-spy top --pid <PID>
```

**Resolution:**
```bash
# Immediate: Restart service
docker-compose restart backend

# Increase memory limits
# Edit docker-compose.prod.yml
# Then redeploy

# Find memory leak (if persistent)
# 1. Enable memory profiling
# 2. Capture heap dump
# 3. Analyze with memory_profiler
```

**Prevention:**
- Set appropriate memory limits
- Profile application regularly
- Monitor memory trends

---

### Issue: SSL Certificate Expiring/Expired

**Symptoms:**
- Browser SSL warnings
- API calls failing with SSL errors
- Certificate expiry alerts

**Diagnosis:**
```bash
# Check certificate expiry
echo | openssl s_client -servername polymarket-copy.com \
  -connect polymarket-copy.com:443 2>/dev/null | \
  openssl x509 -noout -dates

# Check in 30 days
openssl x509 -checkend 2592000 -noout -in /path/to/cert.pem
```

**Resolution:**
```bash
# Renew Let's Encrypt certificate
certbot renew --nginx

# Or manually
certbot certonly --nginx -d polymarket-copy.com -d www.polymarket-copy.com

# Reload Nginx
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

# Verify
curl -vI https://polymarket-copy.com
```

**Prevention:**
- Set up auto-renewal with certbot
- Monitor certificate expiry (30 days warning)
- Test renewal in staging

---

### Issue: Deployment Rollback Needed

**Symptoms:**
- Critical bugs in production
- Service degradation after deployment
- Data corruption

**Diagnosis:**
```bash
# Check deployment history
aws ecs describe-services \
  --cluster polymarket-production-cluster \
  --services backend

# Check recent commits
git log --oneline -10

# Check error spike
# Review DataDog dashboard
```

**Resolution:**
```bash
# Trigger rollback workflow
gh workflow run rollback.yml \
  -f task_definition_revision=polymarket-production:PREVIOUS_REV \
  -f snapshot_id=pre-deploy-YYYYMMDD-HHMMSS

# Or manual rollback
aws ecs update-service \
  --cluster polymarket-production-cluster \
  --service backend \
  --task-definition polymarket-production:PREVIOUS_REV \
  --force-new-deployment

# Watch deployment
aws ecs wait services-stable \
  --cluster polymarket-production-cluster \
  --services backend
```

**Prevention:**
- Comprehensive testing
- Gradual rollout
- Feature flags
- Automated rollback on health check failures

---

## Escalation Procedures

### Level 1: On-Call Engineer (You)
**Response Time:** Immediate  
**Actions:**
1. Acknowledge alert
2. Assess severity
3. Follow runbook
4. Attempt resolution
5. Escalate if needed (15 min)

### Level 2: Secondary On-Call
**Response Time:** 5 minutes  
**Contact:** Via PagerDuty  
**When:** Primary can't resolve in 15 min

### Level 3: Engineering Manager
**Response Time:** 10 minutes  
**Contact:** +1-XXX-XXX-XXXX  
**When:** Issue persists > 30 min

### Level 4: CTO
**Response Time:** 15 minutes  
**Contact:** +1-XXX-XXX-XXXX  
**When:** Major outage > 1 hour

## Emergency Contacts

### On-Call Rotation
- **Week 1:** Alice (+1-555-0001)
- **Week 2:** Bob (+1-555-0002)
- **Week 3:** Charlie (+1-555-0003)

### Management
- **Engineering Manager:** Dave (+1-555-0100)
- **CTO:** Eve (+1-555-0200)

### External
- **AWS Support:** Enterprise Support Portal
- **DataDog Support:** support@datadoghq.com
- **PagerDuty:** Support in app

## Tools & Access

### Required Access
- [ ] AWS Console (Production account)
- [ ] GitHub (polymarket-copy-trading repo)
- [ ] DataDog (Production workspace)
- [ ] PagerDuty (On-call schedule)
- [ ] Slack (#incidents, #ops)
- [ ] Database (Read/Write access)

### Useful Commands

**Check Service Status:**
```bash
# ECS services
aws ecs list-services --cluster polymarket-production-cluster

# Service health
curl https://polymarket-copy.com/health/detailed
```

**View Logs:**
```bash
# Backend logs
aws logs tail /ecs/polymarket-backend --follow

# Worker logs
aws logs tail /ecs/polymarket-worker --follow

# Nginx logs
aws logs tail /ecs/polymarket-nginx --follow
```

**Database Access:**
```bash
# Connect to database
psql $PRODUCTION_DATABASE_URL

# Read-only queries recommended
```

**Scale Services:**
```bash
# Scale workers
aws ecs update-service \
  --cluster polymarket-production-cluster \
  --service worker \
  --desired-count 5

# Scale backend
aws ecs update-service \
  --cluster polymarket-production-cluster \
  --service backend \
  --desired-count 3
```

## Communication Templates

### Incident Notification
```
🚨 INCIDENT: [Brief description]

Status: Investigating / Identified / Monitoring / Resolved
Severity: Critical / High / Medium / Low
Impact: [Who/what is affected]
Started: [Time]
ETA: [Expected resolution time]

Updates will be posted in #incidents
Status page: status.polymarket-copy.com
```

### Resolution Notification
```
✅ RESOLVED: [Brief description]

Duration: [Total time]
Root Cause: [What went wrong]
Fix: [What was done]
Prevention: [How we'll prevent this]

Post-mortem: [Link to document]
```

## Post-Incident Actions

1. **Immediate (< 1 hour):**
   - [ ] Service restored
   - [ ] Alert acknowledged/resolved
   - [ ] Team notified

2. **Same Day:**
   - [ ] Incident timeline documented
   - [ ] Initial root cause identified
   - [ ] Temporary fixes applied

3. **Within 48 hours:**
   - [ ] Post-mortem scheduled
   - [ ] Root cause analysis complete
   - [ ] Action items identified

4. **Within 1 week:**
   - [ ] Preventive measures implemented
   - [ ] Runbook updated
   - [ ] Monitoring improved

## Additional Resources

- **Status Page:** https://status.polymarket-copy.com
- **Documentation:** https://docs.polymarket-copy.com
- **Monitoring:** https://app.datadoghq.com/dashboard/polymarket-prod
- **AWS Console:** https://console.aws.amazon.com
- **GitHub:** https://github.com/company/polymarket-copy-trading
