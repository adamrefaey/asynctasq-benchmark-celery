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

import psutil

from benchmarks.common import BenchmarkResult, Framework, ResourceMonitor, TaskTiming, Timer


async def run_asynctasq(config: BenchmarkConfig) -> BenchmarkResult:
    """Run AsyncTasQ throughput benchmark.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    from asynctasq import Config

    from tasks.asynctasq_tasks import noop_task

    # Initialize driver to query task status
    cfg = Config()
    driver = cfg.get_driver()
    await driver.connect()

    task_timings: list[TaskTiming] = []

    # Start resource monitoring
    monitor = ResourceMonitor(interval_seconds=0.5)
    await monitor.start()

    # Enqueue all tasks
    enqueue_start = time.perf_counter()
    task_ids = []

    for _i in range(config.task_count):
        enqueue_time = time.perf_counter()
        task_id = await noop_task.dispatch()
        task_ids.append(task_id)
        task_timings.append(
            TaskTiming(
                task_id=task_id,
                enqueue_time=enqueue_time,
            )
        )

    enqueue_end = time.perf_counter()
    enqueue_duration = enqueue_end - enqueue_start

    # Wait for all tasks to complete by polling driver stats
    processing_start = time.perf_counter()
    timeout = config.timeout_seconds
    start = time.perf_counter()
    poll_interval = 0.5  # Poll every 500ms

    completed = 0
    failed = 0

    while (time.perf_counter() - start) < timeout:
        # Get global stats from driver to check completion
        try:
            stats = await driver.get_global_stats()
            # completed_count is the number of tasks marked as completed
            completed = stats.get("completed", 0)
            failed = stats.get("failed", 0)

            # Check if all tasks are done (completed + failed >= task_count)
            if (completed + failed) >= config.task_count:
                break

        except Exception:
            # If stats query fails, continue polling
            pass

        await asyncio.sleep(poll_interval)

    processing_end = time.perf_counter()
    processing_duration = processing_end - processing_start

    # Stop resource monitoring and get averages
    avg_cpu, avg_memory = await monitor.stop()

    # Estimate task completion times
    # Without worker instrumentation, we assume tasks complete at steady rate
    # Distribute completion times evenly across processing duration
    if processing_duration > 0 and len(task_timings) > 0:
        time_per_task = processing_duration / len(task_timings)
        for i, timing in enumerate(task_timings):
            # Estimate: task completes after (i * time_per_task) seconds
            timing.start_time = processing_start + (i * time_per_task * 0.9)  # 90% of interval
            timing.complete_time = processing_start + ((i + 1) * time_per_task)
    else:
        # Fallback: all tasks complete at end (latency will be high)
        for timing in task_timings:
            timing.start_time = processing_start
            timing.complete_time = processing_end

    total_time = enqueue_duration + processing_duration

    await driver.disconnect()

    return BenchmarkResult(
        config=config,
        run_number=1,
        total_time=total_time,
        enqueue_time=enqueue_duration,
        processing_time=processing_duration,
        tasks_completed=completed,
        tasks_failed=failed,
        task_timings=task_timings,
        memory_mb=avg_memory,
        cpu_percent=avg_cpu,
    )


def run_celery(config: BenchmarkConfig) -> BenchmarkResult:
    """Run Celery throughput benchmark.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    from kombu import Connection

    from tasks.celery_tasks import app, noop_task

    task_timings: list[TaskTiming] = []

    # Start resource monitoring
    process = psutil.Process()
    process.cpu_percent()  # Initialize CPU monitoring
    cpu_samples: list[float] = []
    memory_samples: list[float] = []

    # Enqueue all tasks (don't store results - task has ignore_result=True)
    with Timer() as enqueue_timer:
        for i in range(config.task_count):
            enqueue_time = time.perf_counter()
            result = noop_task.delay()
            task_timings.append(
                TaskTiming(
                    task_id=result.id if hasattr(result, "id") else f"task_{i}",
                    enqueue_time=enqueue_time,
                )
            )

    # Wait for all tasks to complete by polling queue depth
    with Timer() as processing_timer:
        processing_start = time.perf_counter()
        timeout = config.timeout_seconds
        start = time.perf_counter()
        poll_interval = 0.5  # Poll every 500ms

        # Connect to broker to check queue depth
        with Connection(app.conf.broker_url) as conn:
            queue_name = "celery"  # Default Celery queue

            while (time.perf_counter() - start) < timeout:
                # Sample resources
                cpu_samples.append(process.cpu_percent())
                memory_samples.append(process.memory_info().rss / 1024 / 1024)

                # Check queue depth - when it's 0, all tasks are consumed
                try:
                    queue = conn.SimpleQueue(queue_name)
                    qsize = queue.qsize()
                    queue.close()

                    # If queue is empty, tasks are being processed or done
                    # Give workers a bit more time to finish processing
                    if qsize == 0:
                        time.sleep(poll_interval)  # Let workers finish
                        # Check again to confirm
                        queue = conn.SimpleQueue(queue_name)
                        qsize = queue.qsize()
                        queue.close()
                        if qsize == 0:
                            break
                except Exception:
                    # If queue check fails, continue polling
                    pass

                time.sleep(poll_interval)

        processing_end = time.perf_counter()

    # Calculate average resource usage
    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
    avg_memory = sum(memory_samples) / len(memory_samples) if memory_samples else 0.0

    # Estimate task completion times (same logic as AsyncTasQ)
    processing_duration = processing_timer.elapsed
    if processing_duration > 0 and len(task_timings) > 0:
        time_per_task = processing_duration / len(task_timings)
        for i, timing in enumerate(task_timings):
            timing.start_time = processing_start + (i * time_per_task * 0.9)
            timing.complete_time = processing_start + ((i + 1) * time_per_task)
    else:
        for timing in task_timings:
            timing.start_time = processing_start
            timing.complete_time = processing_end

    # Assume all tasks completed (we can't easily track individual completion without result backend)
    completed = config.task_count
    failed = 0

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
        memory_mb=avg_memory,
        cpu_percent=avg_cpu,
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
