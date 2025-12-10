"""Mock API server for I/O-bound benchmark tests.

Simulates external HTTP APIs with configurable latency.
"""

import asyncio
from typing import Any

from fastapi import FastAPI, Query

app = FastAPI(title="Benchmark Mock API")


@app.get("/")
async def root() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "mock-api"}


@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    latency: int = Query(default=100, ge=0, le=5000, description="Response latency in ms"),
) -> dict[str, Any]:
    """Simulate user API with configurable latency.

    Args:
        user_id: User ID to fetch
        latency: Simulated network/processing delay in milliseconds

    Returns:
        Mock user data
    """
    await asyncio.sleep(latency / 1000)
    return {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com",
        "created_at": "2025-01-01T00:00:00Z",
    }


@app.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    latency: int = Query(default=150, ge=0, le=5000, description="Response latency in ms"),
) -> dict[str, Any]:
    """Simulate order API with configurable latency.

    Args:
        order_id: Order ID to fetch
        latency: Simulated network/processing delay in milliseconds

    Returns:
        Mock order data
    """
    await asyncio.sleep(latency / 1000)
    return {
        "id": order_id,
        "user_id": order_id * 10,
        "status": "pending",
        "total": 99.99,
        "items": [
            {"product_id": 1, "quantity": 2, "price": 29.99},
            {"product_id": 2, "quantity": 1, "price": 39.99},
        ],
        "created_at": "2025-01-01T00:00:00Z",
    }


@app.post("/webhooks/process")
async def process_webhook(
    latency: int = Query(default=200, ge=0, le=5000, description="Processing latency in ms"),
) -> dict[str, str]:
    """Simulate webhook processing with configurable latency.

    Args:
        latency: Simulated processing delay in milliseconds

    Returns:
        Success confirmation
    """
    await asyncio.sleep(latency / 1000)
    return {"status": "processed", "message": "Webhook received"}


@app.get("/heavy-computation")
async def heavy_computation(
    complexity: int = Query(default=1000, ge=1, le=100000, description="Computation complexity"),
    latency: int = Query(default=0, ge=0, le=5000, description="Additional latency in ms"),
) -> dict[str, Any]:
    """Simulate heavy computation with configurable complexity.

    Args:
        complexity: Number of iterations for computation
        latency: Additional simulated delay in milliseconds

    Returns:
        Computation result
    """
    # Simulate some computation
    result = sum(i * i for i in range(complexity))

    if latency > 0:
        await asyncio.sleep(latency / 1000)

    return {
        "complexity": complexity,
        "result": result,
        "status": "completed",
    }


@app.get("/error-simulation")
async def error_simulation(
    error_rate: float = Query(default=0.0, ge=0.0, le=1.0, description="Error probability"),
    latency: int = Query(default=100, ge=0, le=5000, description="Response latency in ms"),
) -> dict[str, str]:
    """Simulate API errors with configurable error rate.

    Args:
        error_rate: Probability of error (0.0 - 1.0)
        latency: Simulated delay before response/error

    Returns:
        Success response or raises error

    Raises:
        HTTPException: Randomly based on error_rate
    """
    await asyncio.sleep(latency / 1000)

    import random

    if random.random() < error_rate:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="Simulated server error")

    return {"status": "success", "message": "No error occurred"}
