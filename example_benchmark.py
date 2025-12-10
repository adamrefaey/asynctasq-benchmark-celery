"""Example: Running a Custom Benchmark

This script demonstrates how to run a custom benchmark scenario programmatically.
"""

import asyncio
from pathlib import Path

from benchmarks.common import BenchmarkConfig, BenchmarkSummary, Driver, Framework
from benchmarks.scenario_1_throughput import run_benchmark


async def main() -> None:
    """Run example benchmark."""

    # Configure AsyncTasQ benchmark
    asynctasq_config = BenchmarkConfig(
        framework=Framework.ASYNCTASQ,
        driver=Driver.REDIS,
        task_count=5000,
        worker_count=10,
        runs=5,
        warmup_seconds=10,
        timeout_seconds=120,
    )

    print("=" * 70)
    print("Running AsyncTasQ Benchmark (Scenario 1: Basic Throughput)")
    print("=" * 70)
    print(f"Tasks: {asynctasq_config.task_count}")
    print(f"Workers: {asynctasq_config.worker_count}")
    print(f"Runs: {asynctasq_config.runs}")
    print()

    # Run multiple iterations
    asynctasq_results = []
    for run in range(1, asynctasq_config.runs + 1):
        print(f"Run {run}/{asynctasq_config.runs}...", end=" ")

        asynctasq_config.runs = run
        result = await run_benchmark(asynctasq_config)
        asynctasq_results.append(result)

        print(f"✓ {result.throughput:.0f} tasks/sec, {result.mean_latency:.2f}ms mean latency")

    # Create summary
    asynctasq_summary = BenchmarkSummary(
        config=asynctasq_config,
        results=asynctasq_results,
    )

    # Display results
    print()
    print("=" * 70)
    print("AsyncTasQ Results Summary")
    print("=" * 70)
    print(
        f"Throughput:      {asynctasq_summary.throughput_stats['mean']:.0f} ± "
        f"{asynctasq_summary.throughput_stats['stdev']:.0f} tasks/sec"
    )
    print(
        f"Mean Latency:    {asynctasq_summary.mean_latency_stats['mean']:.2f} ± "
        f"{asynctasq_summary.mean_latency_stats['stdev']:.2f} ms"
    )
    print(f"P95 Latency:     {asynctasq_summary.p95_latency_stats['mean']:.2f} ms")
    print(f"P99 Latency:     {asynctasq_summary.p99_latency_stats['mean']:.2f} ms")
    print()

    # Save results
    output_dir = Path("results/example")
    output_dir.mkdir(parents=True, exist_ok=True)

    import json

    output_file = output_dir / "asynctasq_redis_example.json"
    with open(output_file, "w") as f:
        json.dump(asynctasq_summary.to_dict(), f, indent=2)

    print(f"✓ Results saved to {output_file}")
    print()

    # Now run Celery for comparison
    celery_config = BenchmarkConfig(
        framework=Framework.CELERY,
        driver=None,
        task_count=5000,
        worker_count=10,
        runs=5,
        warmup_seconds=10,
        timeout_seconds=120,
    )

    print("=" * 70)
    print("Running Celery Benchmark (Scenario 1: Basic Throughput)")
    print("=" * 70)
    print("Note: Make sure Celery workers are running!")
    print("Start workers with: celery -A tasks.celery_tasks worker --loglevel=info")
    print()

    celery_results = []
    for run in range(1, celery_config.runs + 1):
        print(f"Run {run}/{celery_config.runs}...", end=" ")

        celery_config.runs = run
        result = await run_benchmark(celery_config)
        celery_results.append(result)

        print(f"✓ {result.throughput:.0f} tasks/sec, {result.mean_latency:.2f}ms mean latency")

    celery_summary = BenchmarkSummary(
        config=celery_config,
        results=celery_results,
    )

    print()
    print("=" * 70)
    print("Celery Results Summary")
    print("=" * 70)
    print(
        f"Throughput:      {celery_summary.throughput_stats['mean']:.0f} ± "
        f"{celery_summary.throughput_stats['stdev']:.0f} tasks/sec"
    )
    print(
        f"Mean Latency:    {celery_summary.mean_latency_stats['mean']:.2f} ± "
        f"{celery_summary.mean_latency_stats['stdev']:.2f} ms"
    )
    print(f"P95 Latency:     {celery_summary.p95_latency_stats['mean']:.2f} ms")
    print(f"P99 Latency:     {celery_summary.p99_latency_stats['mean']:.2f} ms")
    print()

    # Comparison
    speedup = asynctasq_summary.throughput_stats["mean"] / celery_summary.throughput_stats["mean"]
    latency_reduction = (
        1 - asynctasq_summary.mean_latency_stats["mean"] / celery_summary.mean_latency_stats["mean"]
    ) * 100

    print("=" * 70)
    print("Comparison: AsyncTasQ vs Celery")
    print("=" * 70)
    print(f"Throughput Speedup:    {speedup:.2f}x")
    print(f"Latency Reduction:     {latency_reduction:.1f}%")
    print()
    print(f"AsyncTasQ is {speedup:.2f}x faster than Celery for this workload!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
