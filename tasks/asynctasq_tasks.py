"""AsyncTasQ task definitions for benchmarking.

All task types used in the benchmark scenarios with proper type hints.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from asynctasq.tasks import BaseTask, ProcessTask, SyncTask, task
import httpx

# ============================================================================
# Scenario 1: Basic Throughput - Minimal Tasks
# ============================================================================


@task
def noop_task() -> None:
    """Minimal task with no processing (baseline throughput test).

    Note: @task decorator auto-detects sync function and uses SyncTask.
    """
    pass


@task
def simple_logging_task(message: str) -> str:
    """Simple task that returns the message (minimal processing).

    Note: @task decorator auto-detects sync function and uses SyncTask.
    """
    return f"Processed: {message}"


# ============================================================================
# Scenario 2: I/O-Bound Tasks
# ============================================================================


@task
async def fetch_user_http(user_id: int, base_url: str = "http://localhost:8080") -> dict[str, Any]:
    """Fetch user data from mock API (async HTTP I/O).

    Args:
        user_id: User ID to fetch
        base_url: Base URL of mock API server

    Returns:
        User data from API
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/users/{user_id}?latency=100")
        response.raise_for_status()
        return response.json()


@task
async def fetch_order_http(
    order_id: int, base_url: str = "http://localhost:8080"
) -> dict[str, Any]:
    """Fetch order data from mock API (async HTTP I/O).

    Args:
        order_id: Order ID to fetch
        base_url: Base URL of mock API server

    Returns:
        Order data from API
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/orders/{order_id}?latency=150")
        response.raise_for_status()
        return response.json()


@task
async def concurrent_http_requests(num_requests: int = 10) -> list[dict[str, Any]]:
    """Make multiple concurrent HTTP requests (tests async concurrency).

    Args:
        num_requests: Number of concurrent requests to make

    Returns:
        List of responses
    """
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get(f"http://localhost:8080/users/{i}?latency=50") for i in range(num_requests)
        ]
        responses = await asyncio.gather(*tasks)
        return [r.json() for r in responses]


# ============================================================================
# Scenario 3: CPU-Bound Tasks
# ============================================================================


@task
def parse_json_sync(json_string: str) -> dict[str, Any]:
    """Parse JSON in thread pool (light CPU work via SyncTask).

    Note: @task decorator auto-detects sync function and uses SyncTask.

    Args:
        json_string: JSON string to parse

    Returns:
        Parsed dictionary
    """
    return json.loads(json_string)


class ComputeFactorialSync(SyncTask[int]):
    """Compute factorial in thread pool (moderate CPU work).

    Uses ThreadPoolExecutor via asyncio.run_in_executor.
    Good for 50-80% CPU utilization, 10-100ms tasks.
    """

    number: int

    def handle_sync(self) -> int:
        """Compute factorial synchronously in thread pool."""
        result = 1
        for i in range(1, self.number + 1):
            result *= i
        return result


class ComputeHashProcess(ProcessTask[str]):
    """Compute hash in separate process (heavy CPU work).

    Uses ProcessPoolExecutor with independent GIL.
    Best for >80% CPU utilization, >100ms tasks.
    Matches Celery prefork performance.
    """

    data: bytes
    iterations: int = 100000

    def handle_process(self) -> str:
        """Compute PBKDF2 hash in separate process (bypasses GIL)."""
        result = hashlib.pbkdf2_hmac("sha256", self.data, b"salt", self.iterations)
        return result.hex()


class HashDataHeavyProcess(ProcessTask[str]):
    """Hash 10MB of data (heavy CPU-bound work in process).

    This is the recommended approach for heavy CPU work in AsyncTasQ.
    Achieves parity with Celery prefork workers.
    """

    data: bytes

    def handle_process(self) -> str:
        """Hash data using SHA256 in separate process."""
        return hashlib.sha256(self.data).hexdigest()


# Anti-pattern example (for documentation purposes)
class BlockingCPUTask(BaseTask[int]):
    """ANTI-PATTERN: CPU-bound work in BaseTask blocks event loop.

    This is intentionally slow and should NEVER be used in production.
    Included only to demonstrate the performance difference.
    """

    number: int

    async def handle(self) -> int:
        """Compute factorial synchronously (BLOCKS EVENT LOOP)."""
        result = 1
        for i in range(1, self.number + 1):
            result *= i
        return result


# ============================================================================
# Scenario 4: Mixed Workload
# ============================================================================


@task
async def mixed_io_task(task_id: int) -> str:
    """Light I/O task (60% of mixed workload)."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8080/users/{task_id}?latency=50")
        return response.json()["name"]


@task
def mixed_cpu_light(data: str) -> dict[str, Any]:
    """Light CPU task (30% of mixed workload) - JSON parsing."""
    return json.loads(data)


class MixedCPUHeavy(ProcessTask[str]):
    """Heavy CPU task (10% of mixed workload) - hashing in process."""

    data: bytes

    def handle_process(self) -> str:
        """Hash data in separate process."""
        return hashlib.sha256(self.data).hexdigest()


# ============================================================================
# Scenario 5: Serialization Efficiency
# ============================================================================


@task
async def small_payload_task(data: dict[str, Any]) -> dict[str, Any]:
    """Task with small JSON-friendly payload."""
    return {"processed": True, **data}


@task
async def large_payload_task(data: dict[str, Any]) -> int:
    """Task with large nested payload (tests serialization efficiency)."""

    # Count total items in nested structure
    def count_items(obj: Any) -> int:
        if isinstance(obj, dict):
            return sum(count_items(v) for v in obj.values())
        elif isinstance(obj, list):
            return sum(count_items(v) for v in obj)
        return 1

    return count_items(data)


@task
async def binary_payload_task(data: bytes) -> str:
    """Task with binary payload (tests msgpack binary efficiency)."""
    return hashlib.md5(data).hexdigest()


# ============================================================================
# Scenario 7: Real-World Order Processing
# ============================================================================


@task
async def validate_order(order_id: int) -> dict[str, Any]:
    """Step 1: Validate order data."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8080/orders/{order_id}")
        order = response.json()

        # Simple validation
        if order["total"] <= 0:
            raise ValueError("Invalid order total")

        return order


@task
async def charge_payment(order_id: int, amount: float, error_rate: float = 0.05) -> dict[str, str]:
    """Step 2: Charge payment (with configurable error rate for retry testing)."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8080/error-simulation?error_rate={error_rate}&latency=200"
        )
        response.raise_for_status()  # Will raise on simulated errors

        return {
            "order_id": str(order_id),
            "amount": str(amount),
            "status": "charged",
            "transaction_id": f"txn_{order_id}",
        }


@task
async def send_confirmation_email(order_id: int, user_email: str) -> dict[str, str]:
    """Step 3: Send order confirmation email."""
    await asyncio.sleep(0.1)  # Simulate email service latency
    return {
        "order_id": str(order_id),
        "email": user_email,
        "status": "sent",
    }


@task
async def update_inventory(order_id: int, items: list[dict[str, Any]]) -> dict[str, int]:
    """Step 4: Update inventory counts."""
    await asyncio.sleep(0.05)  # Simulate database write
    updated_count = len(items)
    return {
        "order_id": order_id,
        "items_updated": updated_count,
    }


# ============================================================================
# Scenario 8: Cold Start Testing
# ============================================================================


@task
async def first_task() -> str:
    """First task to execute after worker startup (cold start test)."""
    return "Worker initialized successfully"


# ============================================================================
# Utility Tasks
# ============================================================================


@task
async def sleep_task(duration: float) -> float:
    """Task that sleeps for specified duration (for timing tests)."""
    await asyncio.sleep(duration)
    return duration


@task
async def error_task(message: str = "Intentional error") -> None:
    """Task that always fails (for error handling tests)."""
    raise ValueError(message)


@task
async def retry_task(attempt: int, max_attempts: int = 3) -> dict[str, int | str]:
    """Task that fails until max attempts (for retry testing)."""
    if attempt < max_attempts:
        raise ValueError(f"Attempt {attempt}/{max_attempts} failed")

    return {
        "attempt": attempt,
        "status": "success",
    }
