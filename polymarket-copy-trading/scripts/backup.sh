#!/bin/bash

# Backup script for Polymarket Copy Trading Platform
# Run daily via cron: 0 2 * * * /path/to/backup.sh

set -e

# Configuration
BACKUP_DIR="/backups/polymarket"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
S3_BUCKET="s3://polymarket-backups"

# Create backup directory
mkdir -p $BACKUP_DIR

echo "🗄️  Starting backup at $(date)"

# Backup PostgreSQL database
echo "Backing up database..."
pg_dump $DATABASE_URL | gzip > $BACKUP_DIR/database_$TIMESTAMP.sql.gz

# Backup Redis (if needed)
if [ -n "$REDIS_URL" ]; then
    echo "Backing up Redis..."
    redis-cli --rdb $BACKUP_DIR/redis_$TIMESTAMP.rdb
    gzip $BACKUP_DIR/redis_$TIMESTAMP.rdb
fi

# Backup environment files
echo "Backing up configuration..."
tar -czf $BACKUP_DIR/config_$TIMESTAMP.tar.gz \
    .env.production \
    nginx/nginx.conf \
    .aws/

# Upload to S3
echo "Uploading to S3..."
aws s3 sync $BACKUP_DIR $S3_BUCKET/$(date +%Y/%m/%d)/ \
    --storage-class STANDARD_IA \
    --sse AES256

# Clean up old backups
echo "Cleaning up old backups..."
find $BACKUP_DIR -type f -mtime +$RETENTION_DAYS -delete

# Verify backup
echo "Verifying backup..."
latest_backup=$(ls -t $BACKUP_DIR/database_*.sql.gz | head -1)
if [ -f "$latest_backup" ] && [ -s "$latest_backup" ]; then
    echo "✅ Backup successful: $latest_backup"
    
    # Test restore (dry run)
    gunzip -c $latest_backup | head -n 100 > /dev/null
    echo "✅ Backup file is valid"
else
    echo "❌ Backup failed or file is empty"
    exit 1
fi

# Log to monitoring
curl -X POST "https://api.datadoghq.com/api/v1/events" \
    -H "DD-API-KEY: $DATADOG_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"title\": \"Database Backup Complete\",
        \"text\": \"Backup completed successfully at $(date)\",
        \"priority\": \"normal\",
        \"tags\": [\"environment:production\", \"backup:database\"],
        \"alert_type\": \"success\"
    }"

echo "✅ Backup completed at $(date)"
