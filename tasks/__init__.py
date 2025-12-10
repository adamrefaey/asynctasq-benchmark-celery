"""AsyncTasQ task definitions package."""

__all__ = [
    # Scenario 1: Basic throughput
    "noop_task",
    "simple_logging_task",
    # Scenario 2: I/O-bound
    "fetch_user_http",
    "fetch_order_http",
    "concurrent_http_requests",
    # Scenario 3: CPU-bound
    "parse_json_sync",
    "ComputeFactorialSync",
    "ComputeHashProcess",
    "HashDataHeavyProcess",
    "BlockingCPUTask",
    # Scenario 4: Mixed
    "mixed_io_task",
    "mixed_cpu_light",
    "MixedCPUHeavy",
    # Scenario 5: Serialization
    "small_payload_task",
    "large_payload_task",
    "binary_payload_task",
    # Scenario 7: Real-world
    "validate_order",
    "charge_payment",
    "send_confirmation_email",
    "update_inventory",
    # Utilities
    "first_task",
    "sleep_task",
    "error_task",
    "retry_task",
]
