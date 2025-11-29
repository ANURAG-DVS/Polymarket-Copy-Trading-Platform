# DataDog Alert Configurations

## Critical Alerts (PagerDuty)

### Service Down
```json
{
  "name": "Service Down - Production",
  "type": "service check",
  "query": "\"http check\".over(\"env:production\",\"service:polymarket-backend\").by(\"*\").last(2).count_by_status()",
  "message": "🚨 **CRITICAL: Service is DOWN** @pagerduty-critical\n\nThe backend service has been down for 2 minutes.\n\n**Runbook:** https://wiki.company.com/runbook/service-down\n**Dashboard:** https://app.datadoghq.com/dashboard/polymarket-prod",
  "tags": ["env:production", "severity:critical"],
  "options": {
    "notify_no_data": true,
    "no_data_timeframe": 5,
    "notify_audit": true,
    "require_full_window": false,
    "thresholds": {
      "critical": 1,
      "ok": 0
    }
  }
}
```

### Trade Execution Failure Rate
```json
{
  "name": "High Trade Execution Failure Rate",
  "type": "metric alert",
  "query": "avg(last_5m):sum:trade.executed.error{env:production}.as_rate() / sum:trade.executed{env:production}.as_rate() * 100 > 30",
  "message": "🚨 **CRITICAL: Trade execution failure rate > 30%** @pagerduty-critical\n\nTrade execution is failing at an alarming rate.\n\n**Current Rate:** {{value}}%\n**Threshold:** 30%\n\n**Immediate Actions:**\n1. Check Polymarket API status\n2. Review recent deployments\n3. Check blockchain node connectivity\n\n**Runbook:** https://wiki.company.com/runbook/trade-failures",
  "tags": ["env:production", "severity:critical", "component:trading"],
  "options": {
    "thresholds": {
      "critical": 30,
      "warning": 15
    }
  }
}
```

### Database Connection Failure
```json
{
  "name": "Database Connection Failure",
  "type": "service check",
  "query": "\"postgres.can_connect\".over(\"env:production\").by(\"*\").last(2).count_by_status()",
  "message": "🚨 **CRITICAL: Cannot connect to database** @pagerduty-critical @slack-incidents\n\nDatabase connection has failed.\n\n**Immediate Actions:**\n1. Check RDS status in AWS console\n2. Verify security groups\n3. Check connection pool exhaustion\n\n**Runbook:** https://wiki.company.com/runbook/db-connection",
  "tags": ["env:production", "severity:critical", "component:database"]
}
```

## Warning Alerts (Slack)

### High API Error Rate
```json
{
  "name": "High API Error Rate",
  "type": "metric alert",
  "query": "avg(last_10m):sum:api.error{env:production}.as_rate() / sum:api.request{env:production}.as_rate() * 100 > 5",
  "message": "⚠️ **WARNING: API error rate > 5%** @slack-ops\n\nAPI is experiencing elevated error rates.\n\n**Current Rate:** {{value}}%\n**Threshold:** 5%\n\n**Check:**\n- Error logs: `kubectl logs -f deployment/backend`\n- Recent changes: Git commits\n- External dependencies: Polymarket API\n\n**Dashboard:** {{dashboard_link}}",
  "tags": ["env:production", "severity:warning", "component:api"],
  "options": {
    "thresholds": {
      "critical": 10,
      "warning": 5
    }
  }
}
```

### Queue Backlog
```json
{
  "name": "High Queue Backlog",
  "type": "metric alert",
  "query": "avg(last_5m):avg:queue.depth{env:production,queue_name:trades} > 1000",
  "message": "⚠️ **WARNING: Queue backlog > 1000 messages** @slack-ops\n\nQueue is backing up. Processing may be slow.\n\n**Current Depth:** {{value}}\n**Queue:** {{queue_name.name}}\n\n**Actions:**\n1. Check worker health\n2. Scale workers if needed\n3. Review error logs\n\n**Scale workers:**\n```\naws ecs update-service --cluster prod --service worker --desired-count 5\n```",
  "tags": ["env:production", "severity:warning", "component:queue"]
}
```

### High Disk Usage
```json
{
  "name": "High Disk Usage",
  "type": "metric alert",
  "query": "avg(last_10m):avg:system.disk.used{env:production} by {host} / avg:system.disk.total{env:production} by {host} * 100 > 80",
  "message": "⚠️ **WARNING: Disk usage > 80%** @slack-ops\n\n**Host:** {{host.name}}\n**Current Usage:** {{value}}%\n\n**Actions:**\n1. Check log files: `du -sh /var/log/*`\n2. Clean old logs: `find /var/log -mtime +7 -delete`\n3. Check Docker volumes: `docker system df`\n4. Clean Docker: `docker system prune -a`",
  "tags": ["env:production", "severity:warning", "component:infrastructure"]
}
```

## Info Alerts (Slack)

### Traffic Spike
```json
{
  "name": "Unusual Traffic Spike",
  "type": "anomaly",
  "query": "avg(last_15m):anomalies(avg:api.request{env:production}.as_rate(), 'basic', 2) >= 1",
  "message": "ℹ️ **INFO: Unusual traffic spike detected** @slack-analytics\n\nTraffic is significantly higher than normal.\n\n**Current Rate:** {{value}} req/s\n**Expected:** {{expected_value}} req/s\n\n**Monitor:**\n- User signups\n- Marketing campaigns\n- Potential DDoS\n\n**Dashboard:** {{dashboard_link}}",
  "tags": ["env:production", "severity:info", "component:traffic"]
}
```

### New User Signup Spike
```json
{
  "name": "User Signup Spike",
  "type": "anomaly",
  "query": "avg(last_1h):anomalies(sum:user.signup{env:production}.as_count(), 'basic', 3) >= 1",
  "message": "ℹ️ **INFO: Unusual signup activity** @slack-growth\n\nSignups are significantly higher than usual.\n\n**Current:** {{value}}\n**Expected:** {{expected_value}}\n\n**Possible Causes:**\n- Marketing campaign\n- Social media mention\n- Bot activity\n\n**Review:** User analytics dashboard",
  "tags": ["env:production", "severity:info", "component:growth"]
}
```

## Alert Configuration Best Practices

### Notification Channels
- **PagerDuty:** Critical production issues (24/7)
- **Slack #incidents:** All critical alerts
- **Slack #ops:** Warnings and operational issues
- **Slack #analytics:** Traffic and growth metrics
- **Email:** Non-urgent summaries

### Alert Fatigue Prevention
1. Use appropriate severity levels
2. Set realistic thresholds
3. Include runbook links
4. Provide actionable context
5. Review and tune regularly

### Escalation Policy
```
Critical Alert → PagerDuty
  ↓ (5 min no ack)
→ On-call engineer
  ↓ (10 min no resolution)
→ Secondary on-call
  ↓ (15 min no resolution)
→ Engineering manager
  ↓ (30 min no resolution)
→ CTO
```

### SLOs (Service Level Objectives)
- **Availability:** 99.9% uptime
- **API Latency:** p95 < 200ms
- **Trade Execution:** p99 < 500ms
- **Error Rate:** < 0.1%

### Muting Rules
```json
{
  "name": "Planned Maintenance Window",
  "scope": "env:production",
  "start": "2024-01-15T02:00:00Z",
  "end": "2024-01-15T04:00:00Z",
  "message": "Planned maintenance - database migration"
}
```
