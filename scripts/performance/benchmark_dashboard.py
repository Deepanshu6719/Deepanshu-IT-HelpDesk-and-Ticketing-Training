import json
from pathlib import Path
from statistics import mean, median, quantiles
from time import perf_counter

import httpx

from core.dashboard_cache import invalidate_dashboard_cache
from database.redis import redis_client

BASE_URL = "http://127.0.0.1:8002"
DASHBOARD_URL = f"{BASE_URL}/api/v1/dashboard/me"

TOKEN_FILE = Path("/tmp/helpdesk-perf-tokens.json")

ITERATIONS = 50
EXPECTED_TOTAL = 90_000
BENCHMARK_REDIS_DB = 13


def fetch_dashboard(client):
    started_at = perf_counter()

    response = client.get(DASHBOARD_URL)

    elapsed_ms = (perf_counter() - started_at) * 1000

    response.raise_for_status()

    payload = response.json()

    assert payload["success"] is True

    data = payload["data"]

    assert data["total_tickets"] == EXPECTED_TOTAL

    assert sum(data["by_status"].values()) == EXPECTED_TOTAL

    assert sum(data["by_priority"].values()) == EXPECTED_TOTAL

    assert data["assigned_tickets"] + data["unassigned_tickets"] == EXPECTED_TOTAL

    return elapsed_ms, data


def print_statistics(label, measurements):
    p95 = quantiles(
        measurements,
        n=100,
        method="inclusive",
    )[94]

    print(f"\n{label}")
    print("-" * 35)
    print(f"Requests: {len(measurements)}")
    print(f"Mean:     {mean(measurements):.3f} ms")
    print(f"Median:   {median(measurements):.3f} ms")
    print(f"P95:      {p95:.3f} ms")
    print(f"Minimum:  {min(measurements):.3f} ms")
    print(f"Maximum:  {max(measurements):.3f} ms")


def main():
    configured_db = redis_client.connection_pool.connection_kwargs["db"]

    if int(configured_db) != BENCHMARK_REDIS_DB:
        raise RuntimeError("Benchmark must use Redis database 13")

    tokens = json.loads(TOKEN_FILE.read_text())

    miss_times = []
    hit_times = []

    with httpx.Client(
        headers={"Authorization": f"Bearer {tokens['admin']}"},
        timeout=10,
    ) as client:
        # Warm up database connections and HTTP connection.
        for _ in range(5):
            invalidate_dashboard_cache()
            fetch_dashboard(client)

        for _ in range(ITERATIONS):
            # Force a cache MISS using a new generation.
            invalidate_dashboard_cache()

            miss_time, miss_data = fetch_dashboard(client)

            # Repeat without invalidation for a cache HIT.
            hit_time, hit_data = fetch_dashboard(client)

            assert miss_data == hit_data

            miss_times.append(miss_time)
            hit_times.append(hit_time)

    print("\nDashboard cache benchmark")
    print(f"Active tickets: {EXPECTED_TOTAL:,}")

    print_statistics("CACHE MISS", miss_times)
    print_statistics("CACHE HIT", hit_times)

    miss_median = median(miss_times)
    hit_median = median(hit_times)

    improvement = (miss_median - hit_median) / miss_median * 100

    speedup = miss_median / hit_median

    print("\nComparison")
    print("-" * 35)
    print(f"Median latency reduction: {improvement:.2f}%")
    print(f"Median speedup: {speedup:.2f}x")
    print("Response consistency: PASSED")


if __name__ == "__main__":
    main()
