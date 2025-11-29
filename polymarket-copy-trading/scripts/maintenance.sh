#!/bin/bash

# Database maintenance script
# Run weekly via cron: 0 3 * * 0 /path/to/maintenance.sh

set -e

echo "🔧 Starting database maintenance at $(date)"

# Reindex databases
echo "Reindexing databases..."
psql $DATABASE_URL -c "REINDEX DATABASE polymarket_copy;"

# Update statistics
echo "Updating query planner statistics..."
psql $DATABASE_URL -c "ANALYZE;"

# Vacuum full (during maintenance window only)
echo "Vacuuming database..."
psql $DATABASE_URL -c "VACUUM ANALYZE;"

# Check for bloat
echo "Checking for table bloat..."
psql $DATABASE_URL <<EOF
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    n_live_tup,
    n_dead_tup,
    ROUND(n_dead_tup * 100.0 / NULLIF(n_live_tup, 0), 2) as dead_percentage
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC
LIMIT 10;
EOF

# Optimize indexes
echo "Checking for missing indexes..."
psql $DATABASE_URL <<EOF
SELECT
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    seq_tup_read / seq_scan as avg_seq_read
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_scan DESC
LIMIT 10;
EOF

# Clean up old data (if applicable)
echo "Cleaning up old data..."
psql $DATABASE_URL <<EOF
-- Delete old notifications (> 90 days)
DELETE FROM notifications WHERE created_at < NOW() - INTERVAL '90 days';

-- Delete old trade history (> 1 year)
DELETE FROM trades WHERE created_at < NOW() - INTERVAL '1 year' AND status = 'closed';
EOF

echo "✅ Maintenance completed at $(date)"

# Log to monitoring
curl -X POST "https://api.datadoghq.com/api/v1/events" \
    -H "DD-API-KEY: $DATADOG_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"title\": \"Database Maintenance Complete\",
        \"text\": \"Weekly maintenance completed successfully\",
        \"priority\": \"normal\",
        \"tags\": [\"environment:production\", \"maintenance:database\"],
        \"alert_type\": \"success\"
    }"
