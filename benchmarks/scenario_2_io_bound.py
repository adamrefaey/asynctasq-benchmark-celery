"""Scenario 2: I/O-Bound Workload

Simulate real-world HTTP API calls with AsyncTasQ's async advantages.
Tests async concurrency vs Celery's threading/prefork models.
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
    """Run AsyncTasQ I/O-bound benchmark.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    from asynctasq.config import get_global_config
    from asynctasq.core.driver_factory import DriverFactory

    from tasks.asynctasq_tasks import fetch_user_http

    # Get global config (set by runner for database isolation)
    cfg = get_global_config()
    driver = DriverFactory.create_from_config(cfg)
    await driver.connect()

    # Purge queue to ensure clean state (critical for multi-run benchmarks)
    try:
        # Manually delete Redis keys since driver doesn't have purge_queue
        # This ensures no leftover tasks from previous runs affect results
        if hasattr(driver, "client") and driver.client:
            await driver.client.delete(
                "queue:default",
                "queue:default:processing",
                "queue:default:delayed",
                "queue:default:dead",
            )
        else:
            pass
    except Exception as e:
        print(f"[AsyncTasQ] Warning: Could not purge queue: {e}")
        # Continue anyway - workers should handle existing tasks

    # NOTE: Warmup is handled by workers being pre-started.
    # The benchmark assumes workers are already running and ready to process tasks.
    # This avoids the benchmark script needing to manage worker lifecycle.

    task_timings: list[TaskTiming] = []

    # Start resource monitoring
    # NOTE: This monitors the benchmark script process, NOT the worker processes.
    # For true worker resource usage, monitor worker PIDs separately.
    # This gives us the overhead of enqueueing and monitoring.
    monitor = ResourceMonitor(interval_seconds=0.5)
    await monitor.start()

    # Enqueue all tasks
    enqueue_start = time.perf_counter()
    task_ids = []

    for i in range(config.task_count):
        enqueue_time = time.perf_counter()
        task_id = await fetch_user_http.dispatch(user_id=i % 1000)
        task_ids.append(task_id)
        task_timings.append(
            TaskTiming(
                task_id=task_id,
                enqueue_time=enqueue_time,
            )
        )

    enqueue_end = time.perf_counter()
    enqueue_duration = enqueue_end - enqueue_start

    # Wait for all tasks to complete by polling queue depth
    processing_start = time.perf_counter()
    timeout = config.timeout_seconds
    start = time.perf_counter()
    poll_interval = 0.5  # Poll every 500ms

    completed = 0
    failed = 0
    queue_depth_samples: list[tuple[float, int]] = []

    last_pending = None
    same_pending_count = 0

    while (time.perf_counter() - start) < timeout:
        # Get global stats from driver to check completion
        try:
            stats = await driver.get_global_stats()
            pending = stats.get("pending", 0)
            running = stats.get("running", 0)

            # Track queue depth (pending + running tasks)
            timestamp = time.perf_counter()
            queue_depth_samples.append((timestamp, pending + running))

            # Check if all tasks are done (pending + running == 0)
            if pending == 0 and running == 0:
                # All tasks processed - calculate completed/failed
                # Since we don't track individual task outcomes, assume all completed
                completed = config.task_count
                failed = 0
                break

            # Detect if we're stuck (pending count hasn't changed in 30 seconds)
            if pending == last_pending:
                same_pending_count += 1
                if same_pending_count > 60:  # 60 polls * 0.5s = 30s
                    completed = config.task_count - pending
                    failed = pending
                    break
            else:
                same_pending_count = 0
                last_pending = pending

        except Exception:
            # If stats query fails, continue polling
            pass

        await asyncio.sleep(poll_interval)
    else:
        # Timeout occurred - calculate partial completion
        try:
            stats = await driver.get_global_stats()
            pending = stats.get("pending", 0)
            running = stats.get("running", 0)
            completed = config.task_count - (pending + running)
            failed = pending + running
        except Exception:
            # If stats query fails, mark all as failed
            completed = 0
            failed = config.task_count

    processing_end = time.perf_counter()
    processing_duration = processing_end - processing_start

    # Stop resource monitoring and get averages
    avg_cpu, avg_memory = await monitor.stop()

    # Estimate task completion times
    # NOTE: Without worker instrumentation, we use queue depth samples to estimate
    # when tasks completed. This is more accurate than linear distribution.
    if processing_duration > 0 and len(task_timings) > 0 and len(queue_depth_samples) > 2:
        # Use queue depth samples to estimate completion times
        # Tasks complete as queue drains, not linearly
        total_tasks = len(task_timings)

        for i, timing in enumerate(task_timings):
            # Find the queue depth sample when this task likely completed
            # Assumes FIFO order: task i completes when queue drained to (total - i)
            target_depth = total_tasks - i - 1

            # Find closest queue depth sample
            closest_sample = queue_depth_samples[0]
            for timestamp, depth in queue_depth_samples:
                if depth <= target_depth:
                    closest_sample = (timestamp, depth)
                    break

            # Estimate: task started slightly before completion (assume 100ms execution for HTTP)
            timing.complete_time = closest_sample[0]
            timing.start_time = max(processing_start, timing.complete_time - 0.1)
    elif processing_duration > 0 and len(task_timings) > 0:
        # Fallback: distribute evenly if no queue depth data
        # This is less accurate but better than nothing
        time_per_task = processing_duration / len(task_timings)
        for i, timing in enumerate(task_timings):
            timing.start_time = processing_start + (i * time_per_task * 0.9)
            timing.complete_time = processing_start + ((i + 1) * time_per_task)
    else:
        # Worst case fallback: all tasks complete at end (latency will be high)
        for timing in task_timings:
            timing.start_time = processing_start
            timing.complete_time = processing_end

    total_time = enqueue_duration + processing_duration

    # Clean up before disconnect
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
        queue_depth_samples=queue_depth_samples,
        memory_mb=avg_memory,
        cpu_percent=avg_cpu,
    )


def run_celery(config: BenchmarkConfig) -> BenchmarkResult:
    """Run Celery I/O-bound benchmark.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    from kombu import Connection

    from tasks.celery_tasks import app, fetch_user_http

    task_timings: list[TaskTiming] = []

    # Start resource monitoring
    # NOTE: This monitors the benchmark script process, NOT the Celery worker processes.
    # For true worker resource usage, monitor worker PIDs separately.
    # This gives us the overhead of enqueueing and monitoring.
    process = psutil.Process()
    process.cpu_percent()  # Initialize CPU monitoring
    cpu_samples: list[float] = []
    memory_samples: list[float] = []

    # Enqueue all tasks (tasks store results in backend)
    with Timer() as enqueue_timer:
        for i in range(config.task_count):
            enqueue_time = time.perf_counter()
            result = fetch_user_http.delay(user_id=i % 1000)
            task_timings.append(
                TaskTiming(
                    task_id=result.id if hasattr(result, "id") else f"task_{i}",
                    enqueue_time=enqueue_time,
                )
            )

    # Wait for all tasks to complete by polling queue depth
    queue_depth_samples: list[tuple[float, int]] = []

    with Timer() as processing_timer:
        processing_start = time.perf_counter()
        timeout = config.timeout_seconds
        start = time.perf_counter()
        poll_interval = 0.5  # Poll every 500ms

        # Connect to broker to check queue depth
        with Connection(app.conf.broker_url) as conn:
            queue_name = "celery"  # Default Celery queue
            consecutive_empty = 0  # Count consecutive empty checks

            while (time.perf_counter() - start) < timeout:
                # Sample resources
                cpu_samples.append(process.cpu_percent())
                memory_samples.append(process.memory_info().rss / 1024 / 1024)

                # Check queue depth - when it's 0, all tasks are consumed
                try:
                    queue = conn.SimpleQueue(queue_name)
                    qsize = queue.qsize()
                    queue.close()

                    # Track queue depth over time
                    timestamp = time.perf_counter()
                    queue_depth_samples.append((timestamp, qsize))

                    # If queue is empty, tasks are being processed or done
                    # Need multiple consecutive empty checks to confirm completion
                    if qsize == 0:
                        consecutive_empty += 1
                        # After 3 consecutive empty checks (1.5 seconds), assume done
                        if consecutive_empty >= 3:
                            break
                    else:
                        consecutive_empty = 0  # Reset counter if queue has tasks

                except Exception as e:
                    # If queue doesn't exist (404 NOT_FOUND), all tasks are consumed
                    # This happens when Redis queue is completely drained
                    if "NOT_FOUND" in str(e) or "404" in str(e):
                        break
                    # For other errors, continue polling
                    pass

                time.sleep(poll_interval)

        processing_end = time.perf_counter()
        processing_duration = processing_timer.elapsed

    # Calculate average resource usage
    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
    avg_memory = sum(memory_samples) / len(memory_samples) if memory_samples else 0.0

    # Assume all tasks completed (we can't easily track individual completion without result backend)
    completed = config.task_count
    failed = 0

    # Estimate task completion times using queue depth samples
    # NOTE: Without worker instrumentation, we use queue depth to estimate completion
    if processing_duration > 0 and len(task_timings) > 0 and len(queue_depth_samples) > 2:
        # Use queue depth samples to estimate completion times
        total_tasks = len(task_timings)

        for i, timing in enumerate(task_timings):
            # Find queue depth sample when this task likely completed
            target_depth = total_tasks - i - 1

            closest_sample = queue_depth_samples[0]
            for timestamp, depth in queue_depth_samples:
                if depth <= target_depth:
                    closest_sample = (timestamp, depth)
                    break

            timing.complete_time = closest_sample[0]
            timing.start_time = max(processing_start, timing.complete_time - 0.1)
    elif processing_duration > 0 and len(task_timings) > 0:
        # Fallback: distribute evenly
        time_per_task = processing_duration / len(task_timings)
        for i, timing in enumerate(task_timings):
            timing.start_time = processing_start + (i * time_per_task * 0.9)
            timing.complete_time = processing_start + ((i + 1) * time_per_task)
    else:
        for timing in task_timings:
            timing.start_time = processing_start
            timing.complete_time = processing_end

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
        queue_depth_samples=queue_depth_samples,
        memory_mb=avg_memory,
        cpu_percent=avg_cpu,
    )


async def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    """Run I/O-bound benchmark for specified framework.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    if config.framework == Framework.ASYNCTASQ:
        return await run_asynctasq(config)
    elif config.framework == Framework.CELERY:
        # Run synchronous Celery code in thread to avoid blocking event loop
        return await asyncio.to_thread(run_celery, config)
    else:
        raise ValueError(f"Unknown framework: {config.framework}")
