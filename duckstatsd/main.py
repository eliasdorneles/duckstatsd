import argparse
import signal
import sys
import time

from .server import DuckStatsDServer


def main():
    parser = argparse.ArgumentParser(
        description="DuckStatsD - A lightweight StatsD stub for local development"
    )
    parser.add_argument(
        "--host", default="localhost", help="Host to bind to (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=8125, help="Port to bind to (default: 8125)"
    )
    parser.add_argument(
        "--db", default="metrics.db", help="SQLite database file (default: metrics.db)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Create and start server
    server = DuckStatsDServer(host=args.host, port=args.port, db_path=args.db)

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\nShutting down DuckStatsD...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        server.start()
        print(f"DuckStatsD running on {args.host}:{args.port}")
        print(f"Database: {args.db}")
        print("Press Ctrl+C to stop")

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down DuckStatsD...")
        server.stop()


if __name__ == "__main__":
    main()
