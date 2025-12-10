# AsyncTasQ vs Celery Benchmarking Suite - Justfile

# Default recipe to display help
default:
    @just --list

# ============================================================================
# Initialization
# ============================================================================

# Install all dependencies and setup environment
init:
    @echo "📦 Installing Python dependencies with uv..."
    uv sync --all-extras
    @echo "🐳 Checking Docker installation..."
    docker --version
    docker compose version
    @echo "✅ Initialization complete. Run 'just docker-up' to start infrastructure."

# Setup monitoring stack (Prometheus + Grafana)
setup-monitoring:
    @echo "📊 Configuring monitoring stack..."
    mkdir -p infrastructure/prometheus infrastructure/grafana/dashboards
    @echo "✅ Monitoring setup complete"

# ============================================================================
# Infrastructure Management
# ============================================================================

# Start infrastructure services (Redis, optional Prometheus/Grafana for monitoring)
docker-up:
    @echo "🐳 Starting Redis and core infrastructure..."
    docker compose -f infrastructure/docker-compose.yml up -d redis
    @echo "⏳ Waiting for Redis to be healthy..."
    sleep 5
    @just check-health

# Start infrastructure with monitoring stack
docker-up-monitoring:
    @echo "🐳 Starting Redis and monitoring stack..."
    docker compose -f infrastructure/docker-compose.yml --profile monitoring up -d
    @echo "⏳ Waiting for services to be healthy..."
    sleep 10
    @just check-health

# Start infrastructure with mock API
docker-up-mock:
    @echo "🐳 Starting Redis and mock API..."
    docker compose -f infrastructure/docker-compose.yml --profile mock-api up -d
    @echo "⏳ Waiting for services to be healthy..."
    sleep 5
    @just check-health

# Stop all infrastructure services
docker-down:
    @echo "🛑 Stopping all infrastructure services..."
    docker compose -f infrastructure/docker-compose.yml down

# View logs from all services
docker-logs service="":
    #!/usr/bin/env bash
    if [ -z "{{service}}" ]; then
        docker compose -f infrastructure/docker-compose.yml logs -f
    else
        docker compose -f infrastructure/docker-compose.yml logs -f {{service}}
    fi

# Remove all volumes and reset state
docker-clean:
    @echo "🧹 Cleaning up Docker volumes and data..."
    docker compose -f infrastructure/docker-compose.yml down -v
    @echo "✅ Clean complete"

# Check health of all services
check-health:
    @echo "🏥 Checking service health..."
    @docker compose -f infrastructure/docker-compose.yml ps
    @echo ""
    @echo "Redis: $(docker compose -f infrastructure/docker-compose.yml exec -T redis redis-cli ping 2>/dev/null || echo 'DOWN')"

# ============================================================================
# Workers
# ============================================================================

# Start AsyncTasQ worker (foreground)
worker-asynctasq:
    @echo "🚀 Starting AsyncTasQ worker..."
    python -m asynctasq worker --queue default --concurrency 10

# Start Celery worker (foreground)
worker-celery:
    @echo "🚀 Starting Celery worker..."
    uv run celery -A tasks.celery_tasks worker --loglevel=info --concurrency=10

# ============================================================================
# Benchmarking
# ============================================================================

# Run all benchmark scenarios (requires workers to be running!)
benchmark-all:
    @echo "⚠️  Make sure workers are running before starting benchmarks!"
    @echo "   Run 'just worker-asynctasq' or 'just worker-celery' in separate terminals."
    @echo ""
    @echo "🚀 Running all benchmark scenarios..."
    uv run python -m benchmarks.runner --all --runs 10

# Run specific scenario (1-11, requires workers to be running!)
benchmark scenario:
    @echo "⚠️  Make sure workers are running before starting benchmarks!"
    @echo ""
    @echo "🔬 Running scenario {{scenario}}..."
    uv run python -m benchmarks.runner --scenario {{scenario}} --runs 10

# Quick benchmark (1 run per scenario for testing, requires workers!)
benchmark-quick:
    @echo "⚠️  Make sure workers are running before starting benchmarks!"
    @echo ""
    @echo "⚡ Running quick benchmark..."
    uv run python -m benchmarks.runner --all --runs 1

# 24-hour stress test
benchmark-stress:
    @echo "💪 Starting 24-hour stress test..."
    uv run python -m benchmarks.runner --stress --duration 86400

# Run scenario with verbose output
benchmark-verbose scenario:
    @echo "🔬 Running scenario {{scenario}} with verbose output..."
    uv run python -m benchmarks.runner --scenario {{scenario}} --runs 10 --verbose

# ============================================================================
# Profiling
# ============================================================================

# Profile AsyncTasQ worker with py-spy
profile-asynctasq duration="60":
    @echo "🔍 Profiling AsyncTasQ worker for {{duration}} seconds..."
    uv run py-spy record -o results/profile_asynctasq.svg --duration {{duration}} -- python -m asynctasq worker

# Profile Celery worker with py-spy
profile-celery duration="60":
    @echo "🔍 Profiling Celery worker for {{duration}} seconds..."
    uv run py-spy record -o results/profile_celery.svg --duration {{duration}} -- celery -A tasks.celery_tasks worker --loglevel=info

# Profile memory usage
profile-memory:
    @echo "🧠 Profiling memory usage..."
    uv run python -m memory_profiler benchmarks/scenario_1_throughput.py

# ============================================================================
# Analysis and Reporting
# ============================================================================

# Run statistical analysis on results
analyze:
    @echo "📊 Running statistical analysis..."
    uv run python -m analysis.analyzer

# Generate visualizations
visualize:
    @echo "📈 Generating charts..."
    uv run python -m analysis.visualizer

# Generate full HTML report
report:
    @echo "📄 Generating comprehensive report..."
    uv run python -m analysis.report_generator
    @echo "✅ Report generated at results/summary_report.html"

# Export Prometheus metrics to CSV
export-metrics:
    @echo "💾 Exporting Prometheus metrics..."
    uv run python -m analysis.prometheus_exporter

# ============================================================================
# Redis Utilities
# ============================================================================

# Flush all Redis data
reset-redis:
    @echo "🗑️  Flushing Redis database..."
    docker compose -f infrastructure/docker-compose.yml exec redis redis-cli FLUSHALL
    @echo "✅ Redis flushed"

# Show Redis info
redis-info:
    @echo "📊 Redis information:"
    docker compose -f infrastructure/docker-compose.yml exec redis redis-cli INFO server
    @echo ""
    @echo "Memory usage:"
    docker compose -f infrastructure/docker-compose.yml exec redis redis-cli INFO memory | grep used_memory_human
    @echo ""
    @echo "Connected clients:"
    docker compose -f infrastructure/docker-compose.yml exec redis redis-cli INFO clients | grep connected_clients

# Monitor Redis commands in real-time
redis-monitor:
    @echo "👀 Monitoring Redis commands (Ctrl+C to stop)..."
    docker compose -f infrastructure/docker-compose.yml exec redis redis-cli MONITOR

# ============================================================================
# Development
# ============================================================================

# Format code with Ruff
format:
    uv run ruff format .

# Auto-fix linting issues
lint-fix:
    uv run ruff check --fix .

# Run type checker
typecheck:
    uv run pyright .

# Full CI pipeline
ci: format lint-fix typecheck
    @echo "✅ All CI checks passed!"
    @echo "✅ CI pipeline passed"

# ============================================================================
# Utilities
# ============================================================================

# Clean generated files
clean:
    @echo "🧹 Cleaning generated files..."
    rm -rf results/*.csv results/*.json results/*.svg results/*.html
    rm -rf .pytest_cache .ruff_cache .mypy_cache __pycache__
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    @echo "✅ Clean complete"

# Show project info
info:
    @echo "AsyncTasQ vs Celery Benchmarking Suite"
    @echo "======================================="
    @echo "Python:     $(uv run python --version)"
    @echo "Docker:     $(docker --version)"
    @echo "Compose:    $(docker compose version)"
    @echo "UV:         $(uv --version)"
    @echo ""
    @echo "Infrastructure Status:"
    @just check-health

# Check for outdated dependencies
outdated:
    uv pip list --outdated
