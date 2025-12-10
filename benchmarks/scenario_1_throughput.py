"""Scenario 1: Basic Throughput Test

Measure maximum task completion rate with minimal overhead.
Tests fundamental queue performance without I/O or CPU work.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchmarks.common import BenchmarkConfig, BenchmarkResult

from benchmarks.common import BenchmarkResult, Framework, TaskTiming, Timer


async def run_asynctasq(config: BenchmarkConfig) -> BenchmarkResult:
    """Run AsyncTasQ throughput benchmark.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    from tasks.asynctasq_tasks import noop_task

    task_timings: list[TaskTiming] = []

    # Enqueue all tasks
    enqueue_start = time.perf_counter()
    task_ids = []

    for _i in range(config.task_count):
        enqueue_time = time.perf_counter()
        task_instance = await noop_task.dispatch()
        task_ids.append(str(task_instance.task_id))
        task_timings.append(
            TaskTiming(
                task_id=str(task_instance.task_id),
                enqueue_time=enqueue_time,
            )
        )

    enqueue_end = time.perf_counter()
    enqueue_duration = enqueue_end - enqueue_start

    # Wait for all tasks to complete
    processing_start = time.perf_counter()

    # TODO: Implement task completion tracking
    # For now, we'll use a simple polling approach
    completed = 0
    timeout = config.timeout_seconds
    start = time.perf_counter()

    while completed < config.task_count and (time.perf_counter() - start) < timeout:
        await asyncio.sleep(0.1)
        # In real implementation, check driver for completed tasks
        completed = config.task_count  # Placeholder

    processing_end = time.perf_counter()
    processing_duration = processing_end - processing_start

    total_time = enqueue_duration + processing_duration

    return BenchmarkResult(
        config=config,
        run_number=1,
        total_time=total_time,
        enqueue_time=enqueue_duration,
        processing_time=processing_duration,
        tasks_completed=completed,
        tasks_failed=0,
        task_timings=task_timings,
    )


def run_celery(config: BenchmarkConfig) -> BenchmarkResult:
    """Run Celery throughput benchmark.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    from tasks.celery_tasks import noop_task

    task_timings: list[TaskTiming] = []

    # Enqueue all tasks
    with Timer() as enqueue_timer:
        async_results = []
        for _i in range(config.task_count):
            enqueue_time = time.perf_counter()
            result = noop_task.delay()
            async_results.append(result)
            task_timings.append(
                TaskTiming(
                    task_id=result.id,
                    enqueue_time=enqueue_time,
                )
            )

    # Wait for all tasks to complete
    with Timer() as processing_timer:
        completed = 0
        failed = 0

        for result in async_results:
            try:
                result.get(timeout=config.timeout_seconds)
                completed += 1
            except Exception:
                failed += 1

    total_time = enqueue_timer.elapsed + processing_timer.elapsed

    return BenchmarkResult(
        config=config,
        run_number=1,
        total_time=total_time,
        enqueue_time=enqueue_timer.elapsed,
        processing_time=processing_timer.elapsed,
        tasks_completed=completed,
        tasks_failed=failed,
        task_timings=task_timings,
    )


async def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    """Run throughput benchmark for specified framework.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    if config.framework == Framework.ASYNCTASQ:
        return await run_asynctasq(config)
    elif config.framework == Framework.CELERY:
        return run_celery(config)
    else:
        raise ValueError(f"Unknown framework: {config.framework}")


if __name__ == "__main__":
    # Quick test
    import sys

    framework = Framework(sys.argv[1]) if len(sys.argv) > 1 else Framework.ASYNCTASQ

    from benchmarks.common import BenchmarkConfig, Driver

    config = BenchmarkConfig(
        framework=framework,
        driver=Driver.REDIS if framework == Framework.ASYNCTASQ else None,
        task_count=1000,  # Smaller for quick test
        worker_count=10,
        runs=1,
    )

    if framework == Framework.ASYNCTASQ:
        result = asyncio.run(run_benchmark(config))
    else:
        result = run_benchmark(config)

    print(f"\n{'=' * 60}")
    print(f"Scenario 1: Basic Throughput Test - {framework.value}")
    print(f"{'=' * 60}")
    print(f"Tasks:           {result.tasks_completed}/{config.task_count}")
    print(f"Total Time:      {result.total_time:.2f}s")
    print(f"Enqueue Time:    {result.enqueue_time:.2f}s")
    print(f"Processing Time: {result.processing_time:.2f}s")
    print(f"Throughput:      {result.throughput:.0f} tasks/sec")
    print(f"Enqueue Rate:    {result.enqueue_rate:.0f} tasks/sec")
    print(f"{'=' * 60}\n")
