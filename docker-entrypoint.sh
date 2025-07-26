#!/bin/bash
set -e

# Default values
DUCKSTATSD_HOST=${DUCKSTATSD_HOST:-0.0.0.0}
DUCKSTATSD_PORT=${DUCKSTATSD_PORT:-8125}
DUCKSTATSD_WEB_HOST=${DUCKSTATSD_WEB_HOST:-0.0.0.0}
DUCKSTATSD_WEB_PORT=${DUCKSTATSD_WEB_PORT:-5000}
DUCKSTATSD_DB_PATH=${DUCKSTATSD_DB_PATH:-/data/metrics.db}

echo "🦆 Starting DuckStatsD..."
echo "  StatsD Server: ${DUCKSTATSD_HOST}:${DUCKSTATSD_PORT}"
echo "  Web UI: http://${DUCKSTATSD_WEB_HOST}:${DUCKSTATSD_WEB_PORT}"
echo "  Database: ${DUCKSTATSD_DB_PATH}"
echo ""

# Function to handle shutdown
cleanup() {
    echo "Shutting down DuckStatsD..."
    kill $STATSD_PID $WEB_PID 2>/dev/null || true
    wait $STATSD_PID $WEB_PID 2>/dev/null || true
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Start StatsD server in background
echo "Starting StatsD server..."
duckstatsd \
    --host "$DUCKSTATSD_HOST" \
    --port "$DUCKSTATSD_PORT" \
    --db "$DUCKSTATSD_DB_PATH" &
STATSD_PID=$!

# Wait until database file is created
echo "Waiting for database to be available..."
while [ ! -f "$DUCKSTATSD_DB_PATH" ]; do
    sleep 1
done

# Start Web UI in background
echo "Starting Web UI..."
duckstatsd-web \
    --host "$DUCKSTATSD_WEB_HOST" \
    --port "$DUCKSTATSD_WEB_PORT" \
    --db "$DUCKSTATSD_DB_PATH" &
WEB_PID=$!


echo "✅ DuckStatsD is ready!"
echo "   Send StatsD metrics to: ${DUCKSTATSD_HOST}:${DUCKSTATSD_PORT}"
echo "   Open web UI at: http://localhost:${DUCKSTATSD_WEB_PORT}"

# Wait for both processes
wait $STATSD_PID $WEB_PID
