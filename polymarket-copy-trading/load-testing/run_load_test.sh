#!/bin/bash

# Load testing script for Polymarket Copy Trading Platform

set -e

echo "🚀 Starting load tests..."

# Configuration
TARGET_URL=${1:-"http://localhost:8000"}
USERS=${2:-10000}
SPAWN_RATE=${3:-100}
DURATION=${4:-"10m"}

echo "Target: $TARGET_URL"
echo "Users: $USERS"
echo "Spawn Rate: $SPAWN_RATE/s"
echo "Duration: $DURATION"

# Start Locust in headless mode
locust \
  -f locustfile.py \
  --host=$TARGET_URL \
  --users=$USERS \
  --spawn-rate=$SPAWN_RATE \
  --run-time=$DURATION \
  --html=report.html \
  --csv=results \
  --headless

echo ""
echo "✅ Load test completed!"
echo ""
echo "📊 Results:"
echo "  HTML Report: report.html"
echo "  CSV Results: results_stats.csv"
echo ""

# Display summary
echo "📈 Performance Summary:"
cat results_stats.csv | column -t -s,

# Generate simple benchmark report
cat > benchmark_report.md << EOF
# Load Test Report

**Date:** $(date)
**Target:** $TARGET_URL
**Configuration:**
- Concurrent Users: $USERS
- Spawn Rate: $SPAWN_RATE/s
- Duration: $DURATION

## Results

\`\`\`
$(cat results_stats.csv | column -t -s,)
\`\`\`

## Response Time Distribution

See \`results_stats_history.csv\` for detailed response time distribution.

## Recommendations

Based on the test results:

1. **If p95 < 200ms:** ✅ Performance is excellent
2. **If p95 < 500ms:** ⚠️ Performance is acceptable but could be improved
3. **If p95 > 500ms:** ❌ Performance optimization needed

Refer to PERFORMANCE.md for optimization strategies.
EOF

echo "📝 Benchmark report: benchmark_report.md"
