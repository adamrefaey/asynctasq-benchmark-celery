# AsyncTasQ vs Celery Benchmark Infrastructure

Simplified Docker Compose setup for benchmarking asynctasq and Celery over Redis.

## Services

### Core Services (Always Running)

- **Redis 8.4** - Message broker for both asynctasq and Celery
  - Port: 6379
  - Persistent storage with AOF
  - 2GB memory limit with LRU eviction
  - Latest stable release (Dec 2025)

### Optional Services (Profiles)

#### Monitoring Stack (`--profile monitoring`)
- **Prometheus 3.1** - Metrics collection (port 9090)
- **Grafana 11.4** - Metrics visualization (port 3000)
  - Default credentials: admin/admin
- **Node Exporter 1.8** - System metrics (port 9100)

#### Mock API (`--profile mock-api`)
- **FastAPI Mock API** - HTTP server for I/O-bound tests (port 8080)
  - Configurable latency endpoints
  - User and order simulation endpoints

## Quick Start

```bash
# Start Redis only (minimal setup)
just docker-up

# Start with monitoring stack
just docker-up-monitoring

# Start with mock API
just docker-up-mock

# Stop all services
just docker-down

# Clean up volumes and reset state
just docker-clean

# Check service health
just check-health
```

## Network

All services run on `benchmark-net` bridge network for isolated communication.

## Volumes

- `redis-data` - Redis persistence
- `prometheus-data` - Metrics history (monitoring profile)
- `grafana-data` - Dashboard configs (monitoring profile)

## Configuration Files

- `docker-compose.yml` - Service definitions
- `prometheus/prometheus.yml` - Prometheus scrape config
- `grafana/provisioning/` - Grafana datasources and dashboards
- `Dockerfile.mock-api` - Mock API container build
- `mock_api.py` - FastAPI application for I/O tests

## Why Redis Only?

This benchmark focuses on comparing asynctasq and Celery using their most common deployment scenario: Redis as the message broker. This provides:

- **Fair comparison** - Both frameworks perform best with Redis
- **Simplicity** - No need to manage multiple databases
- **Production relevance** - Redis is the most popular broker choice
- **Resource efficiency** - Minimal infrastructure overhead

For multi-driver benchmarks of asynctasq alone, see the main asynctasq repository.
