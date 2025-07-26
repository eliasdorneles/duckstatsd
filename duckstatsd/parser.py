from typing import Dict, Optional, Tuple, Any


class StatsDParser:
    """Parser for StatsD UDP packets in the format: metric:value|type|@rate|#tags"""

    @staticmethod
    def parse_packet(packet: str) -> Optional[Dict[str, Any]]:
        """
        Parse a StatsD packet string into components.

        Format: metric_name:value|type|@sample_rate|#tag1:val1,tag2:val2

        Returns:
            Dict with parsed components or None if invalid
        """
        packet = packet.strip()
        if not packet:
            return None

        # Split by | to get main components
        parts = packet.split("|")
        if len(parts) < 2:
            return None

        # Parse metric name and value
        metric_part = parts[0]
        if ":" not in metric_part:
            return None

        metric_name, value_str = metric_part.rsplit(":", 1)
        metric_type = parts[1]

        # Initialize result
        result = {
            "metric_name": metric_name,
            "metric_type": metric_type,
            "value": None,
            "string_value": None,
            "sample_rate": 1.0,
            "tags": {},
        }

        # Parse value based on metric type
        if metric_type == "s":  # set
            result["string_value"] = value_str
        else:
            try:
                result["value"] = float(value_str)
            except ValueError:
                return None

        # Parse optional components (sample rate and tags)
        for part in parts[2:]:
            if part.startswith("@"):
                # Sample rate
                try:
                    result["sample_rate"] = float(part[1:])
                except ValueError:
                    continue
            elif part.startswith("#"):
                # Tags
                result["tags"] = StatsDParser._parse_tags(part[1:])

        return result

    @staticmethod
    def _parse_tags(tags_str: str) -> Dict[str, str]:
        """Parse tag string into a dictionary."""
        tags = {}
        if not tags_str:
            return tags

        # Split by comma and parse key:value pairs
        for tag in tags_str.split(","):
            tag = tag.strip()
            if ":" in tag:
                key, value = tag.split(":", 1)
                tags[key.strip()] = value.strip()
            else:
                # Tag without value (DogStatsD allows this)
                tags[tag.strip()] = ""

        return tags
