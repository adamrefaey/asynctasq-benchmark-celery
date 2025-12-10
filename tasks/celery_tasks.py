"""Celery task definitions for benchmarking.

Equivalent implementations of AsyncTasQ tasks for fair comparison.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from celery import Celery
import requests
import os

# Initialize Celery app with explicit Redis database separation
# IMPORTANT: Celery uses DB 1 (broker) and DB 2 (backend) to avoid conflicts with AsyncTasQ (DB 0)
app = Celery(
    "celery_tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
)

# Configure Celery
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


# ============================================================================
# Scenario 1: Basic Throughput - Minimal Tasks
# ============================================================================


@app.task(ignore_result=True)  # Disable result backend for throughput test
def noop_task() -> None:
    """Minimal task with no processing (baseline throughput test)."""
    pass


@app.task
def simple_logging_task(message: str) -> str:
    """Simple task that returns the message (minimal processing)."""
    return f"Processed: {message}"


# ============================================================================
# Scenario 2: I/O-Bound Tasks
# ============================================================================


@app.task
def fetch_user_http(user_id: int, base_url: str = "http://localhost:8080") -> dict[str, Any]:
    """Fetch user data from mock API (sync HTTP I/O).

    Note: Celery uses synchronous requests library.
    AsyncTasQ uses async httpx for better concurrency.

    Args:
        user_id: User ID to fetch
        base_url: Base URL of mock API server

    Returns:
        User data from API
    """
    response = requests.get(f"{base_url}/users/{user_id}?latency=100", timeout=10)
    response.raise_for_status()
    return response.json()


@app.task
def fetch_order_http(order_id: int, base_url: str = "http://localhost:8080") -> dict[str, Any]:
    """Fetch order data from mock API (sync HTTP I/O).

    Args:
        order_id: Order ID to fetch
        base_url: Base URL of mock API server

    Returns:
        Order data from API
    """
    response = requests.get(f"{base_url}/orders/{order_id}?latency=150", timeout=10)
    response.raise_for_status()
    return response.json()


@app.task
def concurrent_http_requests(num_requests: int = 10) -> list[dict[str, Any]]:
    """Make multiple HTTP requests sequentially (Celery limitation).

    Note: Unlike AsyncTasQ which uses asyncio.gather for true concurrency,
    Celery requires sequential requests or manual threading.

    Args:
        num_requests: Number of requests to make

    Returns:
        List of responses
    """
    results = []
    for i in range(num_requests):
        response = requests.get(f"http://localhost:8080/users/{i}?latency=50", timeout=10)
        results.append(response.json())
    return results


# ============================================================================
# Scenario 3: CPU-Bound Tasks
# ============================================================================


@app.task
def parse_json_sync(json_string: str) -> dict[str, Any]:
    """Parse JSON (light CPU work).

    Args:
        json_string: JSON string to parse

    Returns:
        Parsed dictionary
    """
    return json.loads(json_string)


@app.task
def compute_factorial_sync(number: int) -> int:
    """Compute factorial (moderate CPU work).

    With prefork workers, this runs in separate process (bypasses GIL).
    With thread workers, this is GIL-bound (slower).

    Args:
        number: Number to compute factorial for

    Returns:
        Factorial result
    """
    result = 1
    for i in range(1, number + 1):
        result *= i
    return result


@app.task
def compute_hash_process(data: bytes, iterations: int = 100000) -> str:
    """Compute PBKDF2 hash (heavy CPU work).

    Best with prefork workers (multiprocessing).
    Equivalent to AsyncTasQ ProcessTask.

    Args:
        data: Data to hash
        iterations: Number of PBKDF2 iterations

    Returns:
        Hexadecimal hash string
    """
    result = hashlib.pbkdf2_hmac("sha256", data, b"salt", iterations)
    return result.hex()


@app.task
def hash_data_heavy_process(data: bytes) -> str:
    """Hash 10MB of data (heavy CPU-bound work).

    With prefork workers, achieves full CPU utilization.

    Args:
        data: Binary data to hash

    Returns:
        SHA256 hexadecimal hash
    """
    return hashlib.sha256(data).hexdigest()


# ============================================================================
# Scenario 4: Mixed Workload
# ============================================================================


@app.task
def mixed_io_task(task_id: int) -> str:
    """Light I/O task (60% of mixed workload)."""
    response = requests.get(f"http://localhost:8080/users/{task_id}?latency=50", timeout=10)
    return response.json()["name"]


@app.task
def mixed_cpu_light(data: str) -> dict[str, Any]:
    """Light CPU task (30% of mixed workload) - JSON parsing."""
    return json.loads(data)


@app.task
def mixed_cpu_heavy(data: bytes) -> str:
    """Heavy CPU task (10% of mixed workload) - hashing."""
    return hashlib.sha256(data).hexdigest()


# ============================================================================
# Scenario 5: Serialization Efficiency
# ============================================================================


@app.task
def small_payload_task(data: dict[str, Any]) -> dict[str, Any]:
    """Task with small JSON-friendly payload."""
    return {"processed": True, **data}


@app.task
def large_payload_task(data: dict[str, Any]) -> int:
    """Task with large nested payload (tests serialization efficiency).

    Note: Celery uses JSON by default, which is less efficient than
    AsyncTasQ's msgpack. Pickle can be used but has security concerns.
    """

    def count_items(obj: Any) -> int:
        if isinstance(obj, dict):
            return sum(count_items(v) for v in obj.values())
        elif isinstance(obj, list):
            return sum(count_items(v) for v in obj)
        return 1

    return count_items(data)


@app.task
def binary_payload_task(data_hex: str) -> str:
    """Task with binary payload (JSON-encoded as hex string).

    Note: Celery's JSON serializer requires base64/hex encoding for binary.
    AsyncTasQ's msgpack handles binary natively (more efficient).

    Args:
        data_hex: Hexadecimal-encoded binary data

    Returns:
        MD5 hash of data
    """
    data = bytes.fromhex(data_hex)
    return hashlib.md5(data).hexdigest()


# ============================================================================
# Scenario 7: Real-World Order Processing
# ============================================================================


@app.task
def validate_order(order_id: int) -> dict[str, Any]:
    """Step 1: Validate order data."""
    response = requests.get(f"http://localhost:8080/orders/{order_id}", timeout=10)
    order = response.json()

    # Simple validation
    if order["total"] <= 0:
        raise ValueError("Invalid order total")

    return order


@app.task(bind=True, max_retries=3)
def charge_payment(
    self,
    order_id: int,
    amount: float,
    error_rate: float = 0.05,
) -> dict[str, str]:
    """Step 2: Charge payment (with retry on failure).

    Note: Celery requires manual retry configuration.
    AsyncTasQ has built-in retry logic in Task base class.
    """
    try:
        response = requests.get(
            f"http://localhost:8080/error-simulation?error_rate={error_rate}&latency=200",
            timeout=10,
        )
        response.raise_for_status()

        return {
            "order_id": str(order_id),
            "amount": str(amount),
            "status": "charged",
            "transaction_id": f"txn_{order_id}",
        }
    except requests.exceptions.HTTPError as exc:
        # Retry on error
        raise self.retry(exc=exc, countdown=2) from exc


@app.task
def send_confirmation_email(order_id: int, user_email: str) -> dict[str, str]:
    """Step 3: Send order confirmation email."""
    time.sleep(0.1)  # Simulate email service latency
    return {
        "order_id": str(order_id),
        "email": user_email,
        "status": "sent",
    }


@app.task
def update_inventory(order_id: int, items: list[dict[str, Any]]) -> dict[str, int]:
    """Step 4: Update inventory counts."""
    time.sleep(0.05)  # Simulate database write
    updated_count = len(items)
    return {
        "order_id": order_id,
        "items_updated": updated_count,
    }


# ============================================================================
# Scenario 8: Cold Start Testing
# ============================================================================


@app.task
def first_task() -> str:
    """First task to execute after worker startup (cold start test)."""
    return "Worker initialized successfully"


# ============================================================================
# Utility Tasks
# ============================================================================


@app.task
def sleep_task(duration: float) -> float:
    """Task that sleeps for specified duration (for timing tests)."""
    time.sleep(duration)
    return duration


@app.task
def error_task(message: str = "Intentional error") -> None:
    """Task that always fails (for error handling tests)."""
    raise ValueError(message)


@app.task(bind=True, max_retries=3)
def retry_task(self, attempt: int, max_attempts: int = 3) -> dict[str, int | str]:
    """Task that fails until max attempts (for retry testing)."""
    if attempt < max_attempts:
        try:
            raise ValueError(f"Attempt {attempt}/{max_attempts} failed")
        except ValueError as exc:
            raise self.retry(exc=exc, countdown=1) from exc

    return {
        "attempt": attempt,
        "status": "success",
    }
