I want to implement a StatsD stub tailored for local development.

The idea is to have a lightweight tool that the developer can use to inspect
metrics collected while running the app locally. Metrics will be stored in a
SQLite database.

This will be used for local development only, in production the apps will send
metrics to Datadog.

I will call it DuckStatsD, to poke fun at DogStatsD.

## Design

Let's design the data structures for a simple SQLite-based StatsD
implementation. The core idea is to store the raw metrics as they arrive,
perhaps with a timestamp, and then provide basic aggregation or retrieval for a
short time window.

StatsD handles four main metric types: **Counters**, **Gauges**, **Timers
(Histograms)**, and **Sets**. DogStatsD (Datadog's extension) also adds
**Tags**.

Here's a proposed SQLite schema, focusing on capturing the essential
information for each metric type.

-----

### Core Principles for Data Storage:

1.  **Raw Event Storage (Recommended):** Instead of pre-aggregating, store
    individual events. This offers maximum flexibility for querying and
    simulating different aggregation strategies later. Aggregation can be done
    via SQL queries at retrieval time.
2.  **Timestamp:** Essential for time-series data. Use UTC timestamps.
3.  **Metric Name:** The full name of the metric (e.g., `my_service.requests_total`).
4.  **Value:** The numeric value associated with the metric.
5.  **Tags:** Store tags as a JSON string or in a separate many-to-many table
    for flexibility. JSON is simpler for a dev-only stub.
6.  **Type:** Distinguish between counter, gauge, timer, set.

-----

### Proposed SQLite Schema

We'll use a single table to store all raw incoming StatsD metrics, making it
easy to query across types. Aggregation would then happen at query time.

#### Table: `raw_metrics`

This table will store every incoming StatsD packet's meaningful data point.

```sql
CREATE TABLE IF NOT EXISTS raw_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_type TEXT NOT NULL, -- 'counter', 'gauge', 'timer', 'set'
    value REAL,               -- Can be integer or float for counters, gauges, timers
    string_value TEXT,        -- For 'set' members (e.g., 'user_123'), or optional value for other types if needed
    sample_rate REAL DEFAULT 1.0, -- The sampling rate provided (e.g., @0.1)
    tags TEXT,                -- JSON string of key-value tags (e.g., '{"env": "dev", "status": "200"}')
    timestamp DATETIME NOT NULL -- UTC timestamp of when the metric was received
);

-- Indexing for performance on queries
CREATE INDEX IF NOT EXISTS idx_metric_name ON raw_metrics (metric_name);
CREATE INDEX IF NOT EXISTS idx_metric_type ON raw_metrics (metric_type);
CREATE INDEX IF NOT EXISTS idx_timestamp ON raw_metrics (timestamp);
```

**Field Explanations:**

  * **`id`**: Standard primary key.
  * **`metric_name`**: The full metric path (e.g., `service.api.requests`).
  * **`metric_type`**: A string indicating the StatsD type (`counter`, `gauge`, `timer`, `set`). This is crucial for interpreting the `value` and `string_value` fields.
  * **`value`**:
      * **Counters (`|c`)**: The increment amount (usually 1, unless explicitly `+N` or `-N`).
      * **Gauges (`|g`)**: The absolute value (can be `+N` or `-N` for delta,
        but stores the resulting gauge value after applying the delta).
      * **Timers (`|ms`)**: The duration in milliseconds.
      * **Sets (`|s`)**: Not applicable (use `string_value`).
      * *Note:* Using `REAL` allows for both integers and floating-point numbers.
  * **`string_value`**:
      * **Sets (`|s`)**: The unique member string (e.g., `user_123`).
      * *Optional for others*: Could be used for specific textual values if ever needed, but `value` covers numeric cases.
  * **`sample_rate`**: The `@` value (e.g., `0.1` for `@0.1`). This is
    important for correctly scaling counter increments if you want to later
    simulate full population.
  * **`tags`**: A JSON string representing the key-value tags associated with
    the metric (e.g., `#env:dev,status:ok`). Storing as JSON is flexible and
    SQLite's JSON functions make querying this easy.
  * **`timestamp`**: When the stub *received* the metric. Crucial for
    time-based aggregations. Always store in UTC (e.g., `YYYY-MM-DD
    HH:MM:SS.SSS` format).

-----

### How to Populate this Schema (Stub Logic Overview)

The StatsD stub would:

1.  Listen on a UDP port (default 8125).
2.  Receive a UDP packet (e.g., `my.metric:1|c|@0.5|#tag1:val1,tag2:val2`).
3.  Parse the packet:
      * Extract `metric_name` (`my.metric`)
      * Extract `value` (`1`)
      * Extract `metric_type` (`c`)
      * Extract `sample_rate` (`0.5`)
      * Parse `tags` into a dictionary/map and then serialize to JSON.
4.  Insert into `raw_metrics`:
      * For counters/timers/gauges: `INSERT INTO raw_metrics (metric_name, metric_type, value, sample_rate, tags, timestamp) VALUES (?, ?, ?, ?, ?, ?);`
      * For sets: `INSERT INTO raw_metrics (metric_name, metric_type, string_value, sample_rate, tags, timestamp) VALUES (?, ?, ?, ?, ?, ?);`
5.  Set `timestamp` to `CURRENT_TIMESTAMP` (or equivalent in your programming language, ensuring UTC).

-----

### Example SQL Queries for Retrieval and Aggregation

This is where the flexibility comes in. You can query your raw data for various insights.

Let's assume `strftime('%s', timestamp)` gives you Unix epoch seconds for time-based grouping.

#### 1\. Last 5 Minutes of All Metrics (Raw)

```sql
SELECT *
FROM raw_metrics
WHERE timestamp >= strftime('%Y-%m-%d %H:%M:%S', datetime('now', '-5 minutes'))
ORDER BY timestamp DESC;
```

#### 2\. Total Requests Counter for the Last Hour

(Assuming `my_service.requests_total` is a counter, and each value is `1` for an increment, adjusting for sample rate.)

```sql
SELECT
    metric_name,
    SUM(value / sample_rate) AS total_count
FROM raw_metrics
WHERE
    metric_type = 'counter' AND
    metric_name = 'my_service.requests_total' AND
    timestamp >= strftime('%Y-%m-%d %H:%M:%S', datetime('now', '-1 hour'))
GROUP BY metric_name;
```

#### 3\. Average Processing Time (Timer) for the Last 15 Minutes

```sql
SELECT
    metric_name,
    AVG(value) AS average_duration_ms,
    MIN(value) AS min_duration_ms,
    MAX(value) AS max_duration_ms,
    COUNT(*) AS event_count
FROM raw_metrics
WHERE
    metric_type = 'timer' AND
    metric_name = 'my_service.processing_duration_ms' AND
    timestamp >= strftime('%Y-%m-%d %H:%M:%S', datetime('now', '-15 minutes'))
GROUP BY metric_name;
```

#### 4\. Current Gauge Value (Last Known Value)

For gauges, you typically want the last reported value.

```sql
SELECT
    metric_name,
    value AS current_value,
    timestamp
FROM raw_metrics
WHERE
    metric_type = 'gauge' AND
    metric_name = 'my_service.current_temperature'
ORDER BY timestamp DESC
LIMIT 1;
```

#### 5\. Unique Users (Set) in the Last 24 Hours

```sql
SELECT
    metric_name,
    COUNT(DISTINCT string_value) AS unique_members_count
FROM raw_metrics
WHERE
    metric_type = 'set' AND
    metric_name = 'my_service.unique_users' AND
    timestamp >= strftime('%Y-%m-%d %H:%M:%S', datetime('now', '-24 hours'))
GROUP BY metric_name;
```

#### 6\. Counters Grouped by Tag and 1-Minute Intervals

```sql
SELECT
    metric_name,
    json_extract(tags, '$.status') AS status_tag,
    strftime('%Y-%m-%d %H:%M:00', timestamp) AS minute_interval,
    SUM(value / sample_rate) AS total_count
FROM raw_metrics
WHERE
    metric_type = 'counter' AND
    metric_name = 'my_service.api_calls' AND
    timestamp >= strftime('%Y-%m-%d %H:%M:%S', datetime('now', '-1 hour'))
GROUP BY metric_name, status_tag, minute_interval
ORDER BY minute_interval ASC, status_tag ASC;
```

-----

### Advantages of this SQLite approach:

  * **Lightweight:** SQLite is a single file database, no separate server process.
  * **Simple to Implement:** Straightforward parsing and `INSERT` statements.
  * **Flexible Querying:** You can ask almost any question of your raw data
    using SQL.
  * **Persistent:** Data is stored on disk and persists across restarts.
  * **No Aggregation Loss:** By storing raw events, you don't lose information
    due to pre-aggregation. You can define your aggregation windows and types
    at query time.
  * **Customizable:** You control exactly what's stored and how it's retrieved.

This schema provides a solid foundation for your custom StatsD stub. The key is
to write clear SQL queries for extracting the insights you need.
