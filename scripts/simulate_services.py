#!/usr/bin/env python3
"""
Realistic service metrics simulator for DuckStatsD testing.

This script simulates multiple microservices sending metrics continuously:
- API services with request counts, response times, error rates
- Background workers with job processing metrics
- Database metrics with connection pools and query times
- Cache metrics with hit/miss rates
- System metrics like memory and CPU usage

Run with: python scripts/simulate_services.py
Stop with: Ctrl+C
"""

import time
import random
import signal
import sys
import math
from datadog import statsd
from datetime import datetime


class ServiceSimulator:
    def __init__(self):
        # Configure statsd client for DuckStatsD
        statsd.host = "localhost"
        statsd.port = 8125

        # Service definitions
        self.services = {
            "auth-service": {
                "endpoints": ["/login", "/logout", "/register", "/profile", "/verify"],
                "base_rps": 50,  # requests per second
                "error_rate": 0.02,  # 2% error rate
                "response_time_base": 120,  # ms
            },
            "orders-service": {
                "endpoints": ["/orders", "/orders/{id}", "/checkout", "/cart"],
                "base_rps": 30,
                "error_rate": 0.05,  # 5% error rate
                "response_time_base": 200,
            },
            "payments-service": {
                "endpoints": ["/charge", "/refund", "/webhooks"],
                "base_rps": 15,
                "error_rate": 0.01,  # 1% error rate (critical service)
                "response_time_base": 300,
            },
            "inventory-service": {
                "endpoints": ["/products", "/stock", "/availability"],
                "base_rps": 40,
                "error_rate": 0.03,
                "response_time_base": 150,
            },
        }

        self.workers = ["email-worker", "image-processor", "analytics-worker"]
        self.databases = ["users-db", "orders-db", "analytics-db"]
        self.cache_services = ["redis-main", "redis-sessions"]

        self.running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _tags_to_list(self, tags_dict):
        """Convert a dictionary of tags to datadog format list."""
        return [f"{key}:{value}" for key, value in tags_dict.items()]

    def _poisson(self, lam):
        """Simple Poisson distribution using standard library."""
        if lam <= 0:
            return 0
        # Use Knuth's algorithm for small lambda
        if lam < 30:
            L = math.exp(-lam)
            k = 0
            p = 1.0
            while p > L:
                k += 1
                p *= random.random()
            return k - 1
        else:
            # For large lambda, use normal approximation
            return max(0, int(random.gauss(lam, math.sqrt(lam))))

    def _signal_handler(self, signum, frame):
        print("\nShutting down service simulator...")
        self.running = False
        sys.exit(0)

    def _get_status_code(self, error_rate):
        """Generate realistic HTTP status codes."""
        if random.random() < error_rate:
            # Error scenarios
            return random.choices(
                [400, 401, 403, 404, 429, 500, 502, 503],
                weights=[10, 15, 5, 20, 5, 25, 10, 10],
            )[0]
        else:
            # Success scenarios
            return random.choices([200, 201, 204], weights=[85, 10, 5])[0]

    def _get_response_time(self, base_time, status_code):
        """Generate realistic response times based on status."""
        if status_code >= 500:
            # Server errors are often slower
            multiplier = random.uniform(1.5, 3.0)
        elif status_code == 429:
            # Rate limiting is very fast
            multiplier = random.uniform(0.1, 0.3)
        elif status_code in [401, 403]:
            # Auth failures are fast
            multiplier = random.uniform(0.2, 0.5)
        else:
            # Normal variation
            multiplier = random.uniform(0.5, 1.5)

        return max(1, int(base_time * multiplier + random.gauss(0, base_time * 0.2)))

    def simulate_api_services(self):
        """Simulate API service metrics."""
        for service_name, config in self.services.items():
            # Simulate some requests this second
            request_count = self._poisson(config["base_rps"] / 60)  # per-second rate

            for _ in range(request_count):
                endpoint = random.choice(config["endpoints"])
                status_code = self._get_status_code(config["error_rate"])
                response_time = self._get_response_time(
                    config["response_time_base"], status_code
                )

                tags = {
                    "service": service_name,
                    "endpoint": endpoint,
                    "status": str(status_code),
                    "env": "local",
                }

                # Request count
                statsd.increment("api.requests.hits", tags=self._tags_to_list(tags))

                # Response time
                statsd.timing(
                    "api.response_time", response_time, tags=self._tags_to_list(tags)
                )

                # Error count (only for errors)
                if status_code >= 400:
                    statsd.increment(
                        "api.requests.errors", tags=self._tags_to_list(tags)
                    )

                # Success rate gauge
                success_rate = (1 - config["error_rate"]) * 100
                noise = random.gauss(0, 2)  # Add some noise
                statsd.gauge(
                    f"{service_name}.health.success_rate",
                    max(0, min(100, success_rate + noise)),
                    tags=self._tags_to_list({"service": service_name}),
                )

    def simulate_worker_services(self):
        """Simulate background worker metrics."""
        for worker in self.workers:
            # Job processing
            jobs_processed = self._poisson(5)  # ~5 jobs per second

            for _ in range(jobs_processed):
                job_type = random.choice(
                    ["email", "image_resize", "data_export", "report_gen"]
                )
                processing_time = random.expovariate(
                    1 / 2000
                )  # exponential distribution, avg 2s

                tags = {"worker": worker, "job_type": job_type, "env": "local"}

                statsd.increment("worker.jobs.processed", tags=self._tags_to_list(tags))
                statsd.timing(
                    "worker.job.duration",
                    int(processing_time * 1000),
                    tags=self._tags_to_list(tags),
                )

                # Occasional job failures
                if random.random() < 0.02:  # 2% failure rate
                    statsd.increment(
                        "worker.jobs.failed", tags=self._tags_to_list(tags)
                    )

            # Queue depth (gauge)
            queue_depth = max(0, random.gauss(20, 8))
            statsd.gauge(
                "worker.queue.depth",
                int(queue_depth),
                tags=self._tags_to_list({"worker": worker}),
            )

    def simulate_database_metrics(self):
        """Simulate database metrics."""
        for db in self.databases:
            tags = {"database": db, "env": "local"}

            # Query metrics
            query_count = self._poisson(30)  # ~30 queries per second
            for _ in range(query_count):
                query_type = random.choice(["SELECT", "INSERT", "UPDATE", "DELETE"])
                query_time = random.lognormvariate(2.5, 0.8)  # log-normal distribution

                statsd.increment(
                    "db.queries.total",
                    tags=self._tags_to_list({**tags, "query_type": query_type}),
                )
                statsd.timing(
                    "db.query.duration",
                    int(query_time),
                    tags=self._tags_to_list({**tags, "query_type": query_type}),
                )

            # Connection pool
            pool_size = 20
            active_connections = random.randint(5, 18)
            statsd.gauge(
                "db.connections.active",
                active_connections,
                tags=self._tags_to_list(tags),
            )
            statsd.gauge(
                "db.connections.pool_size", pool_size, tags=self._tags_to_list(tags)
            )
            statsd.gauge(
                "db.connections.utilization",
                (active_connections / pool_size) * 100,
                tags=self._tags_to_list(tags),
            )

            # Slow query detection
            if random.random() < 0.1:  # 10% chance of slow query
                slow_query_time = random.uniform(5000, 15000)  # 5-15 seconds
                statsd.timing(
                    "db.query.slow", int(slow_query_time), tags=self._tags_to_list(tags)
                )

    def simulate_cache_metrics(self):
        """Simulate cache (Redis) metrics."""
        for cache in self.cache_services:
            tags = {"cache": cache, "env": "local"}

            # Cache operations
            total_ops = self._poisson(100)  # ~100 ops per second
            hit_rate = random.uniform(0.75, 0.95)  # 75-95% hit rate
            hits = int(total_ops * hit_rate)
            misses = total_ops - hits

            statsd.increment(
                "cache.operations.hits", hits, tags=self._tags_to_list(tags)
            )
            statsd.increment(
                "cache.operations.misses", misses, tags=self._tags_to_list(tags)
            )
            statsd.gauge(
                "cache.hit_rate", hit_rate * 100, tags=self._tags_to_list(tags)
            )

            # Memory usage
            memory_used_mb = random.gauss(512, 50)  # ~512MB with variation
            memory_total_mb = 1024
            statsd.gauge(
                "cache.memory.used_mb",
                max(0, memory_used_mb),
                tags=self._tags_to_list(tags),
            )
            statsd.gauge(
                "cache.memory.utilization",
                (memory_used_mb / memory_total_mb) * 100,
                tags=self._tags_to_list(tags),
            )

            # Key count
            key_count = random.randint(10000, 50000)
            statsd.gauge("cache.keys.total", key_count, tags=self._tags_to_list(tags))

    def simulate_system_metrics(self):
        """Simulate system-level metrics."""
        services = list(self.services.keys()) + self.workers

        for service in services:
            tags = {"service": service, "env": "local"}

            # CPU usage (percentage)
            cpu_usage = max(0, min(100, random.gauss(25, 10)))
            statsd.gauge(
                "system.cpu.usage_percent", cpu_usage, tags=self._tags_to_list(tags)
            )

            # Memory usage
            memory_mb = max(100, random.gauss(256, 64))
            statsd.gauge(
                "system.memory.used_mb", memory_mb, tags=self._tags_to_list(tags)
            )

            # Disk I/O
            if random.random() < 0.3:  # 30% chance of disk activity
                disk_read_mb = random.expovariate(1 / 10)  # avg 10MB
                disk_write_mb = random.expovariate(1 / 5)  # avg 5MB
                statsd.gauge(
                    "system.disk.read_mb", disk_read_mb, tags=self._tags_to_list(tags)
                )
                statsd.gauge(
                    "system.disk.write_mb", disk_write_mb, tags=self._tags_to_list(tags)
                )

    def simulate_custom_business_metrics(self):
        """Simulate business-specific metrics."""
        # User activity
        if random.random() < 0.8:  # 80% chance per second
            user_id = f"user_{random.randint(1, 1000)}"
            statsd.set(
                "users.active", user_id, tags=self._tags_to_list({"env": "local"})
            )

        # Orders
        if random.random() < 0.1:  # ~6 orders per minute
            order_value = random.uniform(10, 500)
            payment_method = random.choice(
                ["credit_card", "paypal", "apple_pay", "bank_transfer"]
            )

            statsd.increment(
                "business.orders.total",
                tags=self._tags_to_list(
                    {"payment_method": payment_method, "env": "local"}
                ),
            )
            statsd.gauge(
                "business.orders.value",
                order_value,
                tags=self._tags_to_list(
                    {"payment_method": payment_method, "env": "local"}
                ),
            )

        # Revenue tracking
        if random.random() < 0.05:  # Revenue updates less frequently
            revenue = random.uniform(1000, 5000)
            statsd.gauge(
                "business.revenue.daily",
                revenue,
                tags=self._tags_to_list({"env": "local"}),
            )

    def run(self):
        """Main simulation loop."""
        print("🦆 Starting DuckStatsD service simulator...")
        print("Simulating:")
        print(f"  - {len(self.services)} API services")
        print(f"  - {len(self.workers)} background workers")
        print(f"  - {len(self.databases)} databases")
        print(f"  - {len(self.cache_services)} cache services")
        print("  - System metrics")
        print("  - Business metrics")
        print("\nPress Ctrl+C to stop\n")

        cycle_count = 0

        while self.running:
            start_time = time.time()

            try:
                # Run all simulations
                self.simulate_api_services()
                self.simulate_worker_services()
                self.simulate_database_metrics()
                self.simulate_cache_metrics()
                self.simulate_system_metrics()
                self.simulate_custom_business_metrics()

                cycle_count += 1
                if cycle_count % 10 == 0:  # Every 10 seconds
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Generated {cycle_count} seconds of metrics"
                    )

            except Exception as e:
                print(f"Error in simulation: {e}")

            # Sleep to maintain ~1 second intervals
            elapsed = time.time() - start_time
            sleep_time = max(0, 1.0 - elapsed)
            time.sleep(sleep_time)


if __name__ == "__main__":
    simulator = ServiceSimulator()
    simulator.run()
