import socket
import threading
import logging
from typing import Optional

from .storage import MetricsStorage
from .parser import StatsDParser


class DuckStatsDServer:
    """UDP server that receives StatsD metrics and stores them in SQLite."""

    def __init__(
        self, host: str = "localhost", port: int = 8125, db_path: str = "metrics.db"
    ):
        self.host = host
        self.port = port
        self.storage = MetricsStorage(db_path)
        self.parser = StatsDParser()
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None

        # Setup logging
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    def start(self):
        """Start the UDP server in a background thread."""
        if self.running:
            self.logger.warning("Server is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info(f"DuckStatsD server started on {self.host}:{self.port}")

    def stop(self):
        """Stop the UDP server."""
        if not self.running:
            return

        self.running = False
        if self.socket:
            self.socket.close()
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("DuckStatsD server stopped")

    def _run_server(self):
        """Main server loop."""
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))

            self.logger.info(f"Listening for StatsD packets on {self.host}:{self.port}")

            while self.running:
                try:
                    # Receive UDP packet (max 1024 bytes should be enough for StatsD)
                    data, addr = self.socket.recvfrom(1024)
                    packet = data.decode("utf-8", errors="ignore")

                    # Parse and store the metric
                    self._process_packet(packet)

                except socket.error as e:
                    if self.running:
                        self.logger.error(f"Socket error: {e}")
                except Exception as e:
                    self.logger.error(f"Error processing packet: {e}")

        except Exception as e:
            self.logger.error(f"Server error: {e}")
        finally:
            if self.socket:
                self.socket.close()

    def _process_packet(self, packet: str):
        """Process a single StatsD packet."""
        # Handle multiple metrics in one packet (separated by newlines)
        for line in packet.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                parsed = self.parser.parse_packet(line)
                if parsed:
                    self.storage.store_metric(
                        metric_name=parsed["metric_name"],
                        metric_type=parsed["metric_type"],
                        value=parsed["value"],
                        string_value=parsed["string_value"],
                        sample_rate=parsed["sample_rate"],
                        tags=parsed["tags"],
                    )
                    self.logger.debug(
                        f"Stored metric: {parsed['metric_name']} ({parsed['metric_type']})"
                    )
                else:
                    self.logger.warning(f"Failed to parse packet: {line}")
            except Exception as e:
                self.logger.error(f"Error processing metric '{line}': {e}")
