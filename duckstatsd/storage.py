import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any


class MetricsStorage:
    def __init__(self, db_path: str = "metrics.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize the SQLite database with the raw_metrics table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create the raw_metrics table as specified in the design
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raw_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    value REAL,
                    string_value TEXT,
                    sample_rate REAL DEFAULT 1.0,
                    tags TEXT,
                    timestamp DATETIME NOT NULL
                );
            """)

            # Create indexes for performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_metric_name ON raw_metrics (metric_name);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_metric_type ON raw_metrics (metric_type);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON raw_metrics (timestamp);"
            )

            conn.commit()

    def store_metric(
        self,
        metric_name: str,
        metric_type: str,
        value: Optional[float] = None,
        string_value: Optional[str] = None,
        sample_rate: float = 1.0,
        tags: Optional[Dict[str, str]] = None,
    ):
        """Store a metric in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Convert tags dict to JSON string
            tags_json = json.dumps(tags) if tags else None

            # Get current UTC timestamp
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            cursor.execute(
                """
                INSERT INTO raw_metrics 
                (metric_name, metric_type, value, string_value, sample_rate, tags, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metric_name,
                    metric_type,
                    value,
                    string_value,
                    sample_rate,
                    tags_json,
                    timestamp,
                ),
            )

            conn.commit()
