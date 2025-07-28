# DuckStatsD 🦆

Lightweight StatsD stub for local development with web-based metrics visualization.

DuckStatsD provides a drop-in replacement for StatsD servers during
development, storing all metrics in SQLite for easy inspection and
visualization through a built-in web UI.

## Features

- **StatsD Protocol Support**: Compatible with standard StatsD and DogStatsD (tag support)
- **Metric Types**: Counters, gauges, timers, and sets
- **Web UI**: Interactive dashboard with charts and raw data exploration
- **SQLite Storage**: Persistent, inspectable metric storage
- **Docker Ready**: Easy deployment with Docker Compose

## Quick Start with Docker

The easiest way to use DuckStatsD is with Docker, using [the image available
in DockerHub](https://hub.docker.com/r/eliasdorneles/duckstatsd):

```bash
docker run -d -p 8125:8125/udp -p 5000:5000/tcp --name duckstatsd eliasdorneles/duckstatsd
```

Once running:
- Send StatsD metrics to `localhost:8125`
- View the web UI at `http://localhost:5000`

## Docker Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DUCKSTATSD_HOST` | `0.0.0.0` | StatsD server bind address |
| `DUCKSTATSD_PORT` | `8125` | StatsD server port |
| `DUCKSTATSD_WEB_HOST` | `0.0.0.0` | Web UI bind address |
| `DUCKSTATSD_WEB_PORT` | `5000` | Web UI port |
| `DUCKSTATSD_DB_PATH` | `/data/metrics.db` | SQLite database file path |

### Docker Compose Example

```yaml
version: '3.8'

services:
  duckstatsd:
    image: eliasdorneles/duckstatsd
    ports:
      - "8125:8125/udp"  # StatsD server
      - "5000:5000/tcp"  # Web UI
    volumes:
      - duckstatsd_data:/data
    environment:
      - DUCKSTATSD_DB_PATH=/data/metrics.db
    restart: unless-stopped

  # Your application that sends metrics
  myapp:
    build: .
    environment:
      - STATSD_HOST=duckstatsd
      - STATSD_PORT=8125
    depends_on:
      - duckstatsd

volumes:
  duckstatsd_data:
```

## Local Development

For development without Docker:

```bash
# Install dependencies
uv pip install -e .

# Start StatsD server
uv run duckstatsd --host 0.0.0.0 --port 8125 --db metrics.db

# Start web UI (in another terminal)
uv run duckstatsd-web --host 0.0.0.0 --port 5000 --db metrics.db
```

## Sending Metrics

### Standard StatsD Format

```bash
# Counter
echo "api.requests:1|c" | nc -u -w0 localhost 8125

# Gauge
echo "memory.usage:75|g" | nc -u -w0 localhost 8125

# Timer
echo "response.time:142|ms" | nc -u -w0 localhost 8125

# Set
echo "unique.users:user123|s" | nc -u -w0 localhost 8125
```

### With DogStatsD Tags

```bash
# Counter with tags
echo "api.requests:1|c|#env:prod,method:GET" | nc -u -w0 localhost 8125

# Gauge with tags
echo "memory.usage:75|g|#host:web01,region:us-east" | nc -u -w0 localhost 8125
```

### Using Python Datadog Library

```python
from datadog import statsd

# Configure to send to DuckStatsD
statsd.host = 'localhost'
statsd.port = 8125

# Send metrics with tags
statsd.increment('api.requests', tags=['env:dev', 'method:POST'])
statsd.gauge('memory.usage', 85.5, tags=['host:web01'])
statsd.timing('db.query', 45, tags=['table:users', 'op:select'])
```

### Using sample metrics generator script

```bash
# Generate sample metrics
python scripts/simulate_services.py
```


## Web UI Features

The web interface provides several views:

- **Dashboard**: Overview of recent metrics and activity
- **Counters**: Counter metrics with time series charts
- **Gauges**: Current gauge values and historical trends
- **Timers**: Timer statistics and distribution histograms
- **Sets**: Set metrics showing unique value counts
- **Tags**: Explore tag keys and values across all metrics
- **Raw Data**: Searchable table of all metric events

### Advanced Tag Filtering

The Raw Data view supports complex boolean tag expressions:

```
# Simple tag filter
env:prod

# Multiple conditions
env:prod AND method:GET

# Boolean logic with negation
env:prod OR (method:POST AND -status:error)

# Parentheses for grouping
(env:dev OR env:staging) AND method:GET
```

## Architecture

DuckStatsD consists of:

1. **UDP Server**: Listens for StatsD packets on port 8125
2. **Web UI**: Flask application for visualization and exploration
3. **Storage**: SQLite database with single table `raw_metrics`

## Similar projects

* [statsd-logger](https://github.com/zendesk/statsd-logger) by Zendesk
  * very simple logger, mainly for debugging metrics
  * highlights Datadog-style tags
* [statstee](https://github.com/rodaine/statstee)
  * captures the UDP packets with metrics using libpcap, needs root permissions
  * can be used to troubleshoot misbehaving applications in production environments that are sending too many metrics.
  * no support for Datadog-style tags

I created DuckStatsD because neither of these tools fit the bill for me, because I wanted something to be able to query and filter, notably to filter by Datadog-style tags.
