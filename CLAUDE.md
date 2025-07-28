# Claude Development Notes

This file contains information to help Claude understand the project structure
and development workflows.

## Project Overview

DuckStatsD is a StatsD-compatible metrics collection server with a web UI for
visualizing metrics. It uses Python/Flask for the backend and SQLite for
storage.

## Development Commands

```bash
# Format Python code (ruff) and Jinja2 template files (djlint)
make format

# Run the web application
uv run duckstatsd-web --debug

# Run the StatsD server
uv run duckstatsd
```

## Architecture Notes

### Key Components

#### Core StatsD Server (`duckstatsd/`)
- **`main.py`**: Entry point for the StatsD server (`duckstatsd` command)
- **`server.py`**: UDP server implementation (`DuckStatsDServer` class) that listens for StatsD packets
- **`parser.py`**: StatsD packet parser (`StatsDParser` class) supporting standard StatsD and DogStatsD formats
- **`storage.py`**: SQLite storage layer (`MetricsStorage` class) for persisting raw metrics

#### Web UI (`duckstatsd/web/`)
- **`app.py`**: Flask web application (`duckstatsd-web` command) with metric visualization pages
- **`database.py`**: Database query layer (`MetricsDB` class) with aggregation and filtering methods
- **`templates/`**: Jinja2 templates for dashboard, counters, gauges, timers, sets, tags, and raw data pages
- **`static/`**: CSS styles for the web interface

#### Database Schema
- **`raw_metrics` table**: Stores all incoming StatsD events with columns:
  - `metric_name`, `metric_type` (c/g/ms/s), `value`, `string_value`
  - `sample_rate`, `tags` (JSON), `timestamp`
  - Indexed on metric_name, metric_type, and timestamp for performance

#### Supported Metric Types
- **Counters** (`c`): Increment/decrement values with rate calculations
- **Gauges** (`g`): Point-in-time values with trend visualization  
- **Timers** (`ms`): Duration measurements with histogram distribution
- **Sets** (`s`): Unique value tracking with cardinality metrics
- **Tags**: DogStatsD-compatible key-value metadata stored as JSON

#### Entry Points
- **`duckstatsd`**: Starts UDP server on port 8125 (configurable)
- **`duckstatsd-web`**: Starts Flask web UI on port 5000 (configurable)
- Both commands support SQLite database path configuration

#### Deployment
- **Docker**: Multi-service container with both StatsD server and web UI
- **Environment variables**: Configurable host, port, and database path settings
- **Docker Compose**: Ready-to-use setup for local development environments
