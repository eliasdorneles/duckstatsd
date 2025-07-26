import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


class MetricsDB:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _dict_factory(self, cursor, row):
        """Convert row to dictionary."""
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))

    def get_recent_metrics(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent metrics for dashboard."""
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT metric_name, metric_type, value, string_value, 
                       sample_rate, tags, timestamp
                FROM raw_metrics 
                ORDER BY timestamp DESC 
                LIMIT ?
            """,
                (limit,),
            )
            return cursor.fetchall()

    def get_metrics_summary(self, hours: int = 24) -> Dict[str, int]:
        """Get count of metrics by type."""
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT metric_type, COUNT(*) as count
                FROM raw_metrics 
                WHERE timestamp >= ?
                GROUP BY metric_type
            """,
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            )

            result = {"c": 0, "g": 0, "ms": 0, "s": 0}
            for row in cursor.fetchall():
                result[row[0]] = row[1]
            return result

    def get_active_metrics(
        self, hours: int = 1, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get most active metrics."""
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT metric_name, metric_type, COUNT(*) as event_count
                FROM raw_metrics 
                WHERE timestamp >= ?
                GROUP BY metric_name, metric_type
                ORDER BY event_count DESC
                LIMIT ?
            """,
                (since.strftime("%Y-%m-%d %H:%M:%S"), limit),
            )
            return cursor.fetchall()

    def get_counter_metrics(self) -> List[Dict[str, Any]]:
        """Get all counter metrics with totals."""
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute("""
                SELECT metric_name, 
                       SUM(value / sample_rate) as total_count,
                       COUNT(*) as event_count,
                       MAX(timestamp) as last_seen
                FROM raw_metrics 
                WHERE metric_type = 'c'
                GROUP BY metric_name
                ORDER BY total_count DESC
            """)
            return cursor.fetchall()

    def get_counter_timeseries(
        self, metric_name: str, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get counter events over time (per minute)."""
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT strftime('%Y-%m-%d %H:%M:00', timestamp) as minute,
                       SUM(value / sample_rate) as count
                FROM raw_metrics 
                WHERE metric_type = 'c' 
                  AND metric_name = ?
                  AND timestamp >= ?
                GROUP BY minute
                ORDER BY minute
            """,
                (metric_name, since.strftime("%Y-%m-%d %H:%M:%S")),
            )
            return cursor.fetchall()

    def get_gauge_metrics(self) -> List[Dict[str, Any]]:
        """Get current gauge values (latest for each metric)."""
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r1.metric_name, r1.value, r1.timestamp
                FROM raw_metrics r1
                INNER JOIN (
                    SELECT metric_name, MAX(timestamp) as max_timestamp
                    FROM raw_metrics 
                    WHERE metric_type = 'g'
                    GROUP BY metric_name
                ) r2 ON r1.metric_name = r2.metric_name 
                    AND r1.timestamp = r2.max_timestamp
                WHERE r1.metric_type = 'g'
                ORDER BY r1.metric_name
            """)
            return cursor.fetchall()

    def get_gauge_timeseries(
        self, metric_name: str, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get gauge values over time."""
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, value
                FROM raw_metrics 
                WHERE metric_type = 'g' 
                  AND metric_name = ?
                  AND timestamp >= ?
                ORDER BY timestamp
            """,
                (metric_name, since.strftime("%Y-%m-%d %H:%M:%S")),
            )
            return cursor.fetchall()

    def get_timer_metrics(self) -> List[Dict[str, Any]]:
        """Get timer metrics with basic stats."""
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute("""
                SELECT metric_name,
                       AVG(value) as avg_value,
                       MIN(value) as min_value,
                       MAX(value) as max_value,
                       COUNT(*) as event_count,
                       MAX(timestamp) as last_seen
                FROM raw_metrics 
                WHERE metric_type = 'ms'
                GROUP BY metric_name
                ORDER BY avg_value DESC
            """)
            return cursor.fetchall()

    def get_timer_values(self, metric_name: str, hours: int = 24) -> List[float]:
        """Get timer values for histogram."""
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT value
                FROM raw_metrics 
                WHERE metric_type = 'ms' 
                  AND metric_name = ?
                  AND timestamp >= ?
                ORDER BY timestamp
            """,
                (metric_name, since.strftime("%Y-%m-%d %H:%M:%S")),
            )
            return [row[0] for row in cursor.fetchall()]

    def get_set_metrics(self) -> List[Dict[str, Any]]:
        """Get set metrics with unique counts."""
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute("""
                SELECT metric_name,
                       COUNT(DISTINCT string_value) as unique_count,
                       COUNT(*) as event_count,
                       MAX(timestamp) as last_seen
                FROM raw_metrics 
                WHERE metric_type = 's'
                GROUP BY metric_name
                ORDER BY unique_count DESC
            """)
            return cursor.fetchall()

    def get_set_members(self, metric_name: str, limit: int = 20) -> List[str]:
        """Get recent unique set members."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT string_value
                FROM raw_metrics 
                WHERE metric_type = 's' 
                  AND metric_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (metric_name, limit),
            )
            return [row[0] for row in cursor.fetchall()]

    def get_raw_metrics(
        self,
        limit: int = 100,
        offset: int = 0,
        metric_name: Optional[str] = None,
        metric_type: Optional[str] = None,
        hours: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get raw metrics with filtering."""
        conditions = []
        params = []

        if metric_name:
            conditions.append("metric_name LIKE ?")
            params.append(f"%{metric_name}%")

        if metric_type:
            conditions.append("metric_type = ?")
            params.append(metric_type)

        if hours:
            since = datetime.utcnow() - timedelta(hours=hours)
            conditions.append("timestamp >= ?")
            params.append(since.strftime("%Y-%m-%d %H:%M:%S"))

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT metric_name, metric_type, value, string_value,
                       sample_rate, tags, timestamp
                FROM raw_metrics 
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """,
                params,
            )
            return cursor.fetchall()

