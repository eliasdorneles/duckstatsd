import sqlite3
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple


class MetricsDB:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _dict_factory(self, cursor, row):
        """Convert row to dictionary."""
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))

    def _parse_tag_filter_expression(self, expression: str) -> Tuple[str, List[str]]:
        """
        Parse complex tag filter expressions like:
        - tag1:value1
        - tag1:value1 OR tag2:value2
        - tag1:value1 AND tag2:value2
        - (tag1:value1 OR tag2:value2) AND -tag3:value3
        - -tag1:value1

        Returns (sql_condition, params_list)
        """
        if not expression or not expression.strip():
            return "1=1", []

        # Clean up the expression
        expression = expression.strip()

        # Simple tokenizer
        tokens = self._tokenize_tag_expression(expression)
        if not tokens:
            return "1=1", []

        # Parse the expression into SQL
        sql_condition, params = self._parse_tag_tokens(tokens)
        return sql_condition, params

    def _tokenize_tag_expression(self, expression: str) -> List[str]:
        """Tokenize the tag filter expression."""
        # Pattern to match: tag:value, operators, parentheses, negation
        # Updated to handle more characters in tag names and values
        pattern = r"(\(|\)|AND|OR|-?[a-zA-Z_][a-zA-Z0-9_.-]*:[^()\s]+|-?[a-zA-Z_][a-zA-Z0-9_.-]*)"
        tokens = re.findall(pattern, expression, re.IGNORECASE)
        return [token.strip() for token in tokens if token.strip()]

    def _parse_tag_tokens(self, tokens: List[str]) -> Tuple[str, List[str]]:
        """Parse tokenized expression into SQL condition."""
        if not tokens:
            return "1=1", []

        # Convert to postfix notation and then to SQL
        try:
            postfix = self._infix_to_postfix(tokens)
            return self._postfix_to_sql(postfix)
        except Exception:
            # If parsing fails, fall back to simple single tag parsing
            if len(tokens) == 1:
                return self._parse_single_tag(tokens[0])
            return "1=1", []

    def _infix_to_postfix(self, tokens: List[str]) -> List[str]:
        """Convert infix notation to postfix using Shunting Yard algorithm."""
        precedence = {"OR": 1, "AND": 2}
        stack = []
        output = []

        for token in tokens:
            if self._is_tag_token(token):
                output.append(token)
            elif token.upper() in ["AND", "OR"]:
                while (
                    stack
                    and stack[-1] != "("
                    and stack[-1].upper() in precedence
                    and precedence[stack[-1].upper()] >= precedence[token.upper()]
                ):
                    output.append(stack.pop())
                stack.append(token.upper())
            elif token == "(":
                stack.append(token)
            elif token == ")":
                while stack and stack[-1] != "(":
                    output.append(stack.pop())
                if stack:
                    stack.pop()  # Remove the '('

        while stack:
            output.append(stack.pop())

        return output

    def _postfix_to_sql(self, postfix: List[str]) -> Tuple[str, List[str]]:
        """Convert postfix notation to SQL condition."""
        stack = []
        all_params = []

        for token in postfix:
            if self._is_tag_token(token):
                condition, params = self._parse_single_tag(token)
                stack.append(condition)
                all_params.extend(params)
            elif token.upper() == "AND":
                if len(stack) >= 2:
                    right = stack.pop()
                    left = stack.pop()
                    stack.append(f"({left} AND {right})")
                elif len(stack) == 1:
                    # If only one operand, just use it
                    pass
            elif token.upper() == "OR":
                if len(stack) >= 2:
                    right = stack.pop()
                    left = stack.pop()
                    stack.append(f"({left} OR {right})")
                elif len(stack) == 1:
                    # If only one operand, just use it
                    pass

        if stack:
            return stack[0], all_params
        return "1=1", []

    def _is_tag_token(self, token: str) -> bool:
        """Check if token is a tag (not an operator or parenthesis)."""
        return token.upper() not in ["AND", "OR", "(", ")"] and (
            ":" in token or token.startswith("-")
        )

    def _parse_single_tag(self, tag_token: str) -> Tuple[str, List[str]]:
        """Parse a single tag token into SQL condition."""
        # Handle negation
        negated = tag_token.startswith("-")
        if negated:
            tag_token = tag_token[1:]

        if ":" in tag_token:
            # tag:value format
            tag_key, tag_value = tag_token.split(":", 1)
            condition = "json_extract(tags, '$.' || ?) = ?"
            params = [tag_key, tag_value]
        else:
            # just tag key existence
            tag_key = tag_token
            condition = "json_extract(tags, '$.' || ?) IS NOT NULL"
            params = [tag_key]

        if negated:
            if ":" in tag_token:
                condition = f"NOT ({condition})"
            else:
                condition = "json_extract(tags, '$.' || ?) IS NULL"

        return condition, params

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
        tag_filter: Optional[str] = None,
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

        if tag_filter:
            # Parse complex tag filter expression
            tag_condition, tag_params = self._parse_tag_filter_expression(tag_filter)
            if tag_condition != "1=1":  # Only add if it's not a no-op
                conditions.append(tag_condition)
                params.extend(tag_params)

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

    # Tag-related queries
    def get_all_tag_keys(self) -> List[str]:
        """Get all unique tag keys across all metrics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Use SQLite JSON functions to extract all keys
            cursor.execute("""
                SELECT DISTINCT json_each.key
                FROM raw_metrics, json_each(raw_metrics.tags)
                WHERE tags IS NOT NULL AND tags != 'null'
                ORDER BY json_each.key
            """)
            return [row[0] for row in cursor.fetchall()]

    def get_tag_values(self, tag_key: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all values for a specific tag key with counts."""
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT json_extract(tags, '$.' || ?) as tag_value,
                       COUNT(*) as count,
                       MAX(timestamp) as last_seen
                FROM raw_metrics
                WHERE tags IS NOT NULL 
                  AND json_extract(tags, '$.' || ?) IS NOT NULL
                GROUP BY tag_value
                ORDER BY count DESC
                LIMIT ?
            """,
                (tag_key, tag_key, limit),
            )
            return cursor.fetchall()

    def get_top_tag_combinations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most common tag combinations."""
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT tags,
                       COUNT(*) as count,
                       MAX(timestamp) as last_seen
                FROM raw_metrics
                WHERE tags IS NOT NULL AND tags != 'null' AND tags != '{}'
                GROUP BY tags
                ORDER BY count DESC
                LIMIT ?
            """,
                (limit,),
            )
            return cursor.fetchall()

    def get_recent_tagged_metrics(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent metrics that have tags."""
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT metric_name, metric_type, value, string_value,
                       sample_rate, tags, timestamp
                FROM raw_metrics
                WHERE tags IS NOT NULL AND tags != 'null' AND tags != '{}'
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )
            return cursor.fetchall()

    def get_counter_timeseries_by_tag(
        self, metric_name: str, tag_key: str, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get counter time series grouped by tag value."""
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT strftime('%Y-%m-%d %H:%M:00', timestamp) as minute,
                       json_extract(tags, '$.' || ?) as tag_value,
                       SUM(value / sample_rate) as count
                FROM raw_metrics 
                WHERE metric_type = 'c' 
                  AND metric_name = ?
                  AND timestamp >= ?
                  AND json_extract(tags, '$.' || ?) IS NOT NULL
                GROUP BY minute, tag_value
                ORDER BY minute, tag_value
            """,
                (tag_key, metric_name, since.strftime("%Y-%m-%d %H:%M:%S"), tag_key),
            )
            return cursor.fetchall()

    def get_gauge_timeseries_by_tag(
        self, metric_name: str, tag_key: str, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get gauge time series grouped by tag value."""
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp,
                       json_extract(tags, '$.' || ?) as tag_value,
                       value
                FROM raw_metrics 
                WHERE metric_type = 'g' 
                  AND metric_name = ?
                  AND timestamp >= ?
                  AND json_extract(tags, '$.' || ?) IS NOT NULL
                ORDER BY timestamp, tag_value
            """,
                (tag_key, metric_name, since.strftime("%Y-%m-%d %H:%M:%S"), tag_key),
            )
            return cursor.fetchall()

    def get_timer_values_by_tag(
        self, metric_name: str, tag_key: str, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get timer values grouped by tag value."""
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT json_extract(tags, '$.' || ?) as tag_value,
                       value
                FROM raw_metrics 
                WHERE metric_type = 'ms' 
                  AND metric_name = ?
                  AND timestamp >= ?
                  AND json_extract(tags, '$.' || ?) IS NOT NULL
                ORDER BY timestamp
            """,
                (tag_key, metric_name, since.strftime("%Y-%m-%d %H:%M:%S"), tag_key),
            )
            return cursor.fetchall()

    def get_metrics_by_tag_filter(
        self,
        tag_key: str,
        tag_value: str,
        metric_type: Optional[str] = None,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get metrics filtered by specific tag key=value."""
        since = datetime.utcnow() - timedelta(hours=hours)
        conditions = ["timestamp >= ?", "json_extract(tags, '$.' || ?) = ?"]
        params = [since.strftime("%Y-%m-%d %H:%M:%S"), tag_key, tag_value]

        if metric_type:
            conditions.append("metric_type = ?")
            params.append(metric_type)

        where_clause = " AND ".join(conditions)

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
                LIMIT 1000
            """,
                params,
            )
            return cursor.fetchall()

    def get_tag_summary(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get summary of tag usage."""
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT json_each.key as tag_key,
                       COUNT(*) as usage_count,
                       COUNT(DISTINCT json_each.value) as unique_values,
                       MAX(timestamp) as last_seen
                FROM raw_metrics, json_each(raw_metrics.tags)
                WHERE timestamp >= ?
                  AND tags IS NOT NULL AND tags != 'null'
                GROUP BY json_each.key
                ORDER BY usage_count DESC
            """,
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            )
            return cursor.fetchall()
