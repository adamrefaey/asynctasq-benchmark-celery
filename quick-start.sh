#!/usr/bin/env bash
# Quick start script for AsyncTasQ vs Celery benchmarking

set -e

echo "======================================================================"
echo "AsyncTasQ vs Celery Benchmarking Suite - Quick Start"
echo "======================================================================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose v2."
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "❌ uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "✅ Prerequisites checked"
echo ""

# Install Python dependencies
echo "📦 Installing Python dependencies..."
uv sync --all-extras
echo "✅ Dependencies installed"
echo ""

# Start infrastructure
echo "🐳 Starting infrastructure services..."
docker compose -f infrastructure/docker-compose.yml up -d

echo "⏳ Waiting for services to be healthy (30 seconds)..."
sleep 30

echo "✅ Infrastructure ready"
echo ""

# Quick health check
echo "🏥 Checking service health..."
docker compose -f infrastructure/docker-compose.yml ps
echo ""

# Show next steps
echo "======================================================================"
echo "✅ Setup complete! Next steps:"
echo "======================================================================"
echo ""
echo "1. Run a quick test:"
echo "   just benchmark-quick"
echo ""
echo "2. Run all benchmarks (takes ~2 hours):"
echo "   just benchmark-all"
echo ""
echo "3. Run specific scenario:"
echo "   just benchmark 1  # Basic throughput"
echo "   just benchmark 2  # I/O-bound"
echo "   just benchmark 3  # CPU-bound"
echo ""
echo "4. View results:"
echo "   just report"
echo "   open results/summary_report.html"
echo ""
echo "5. Monitor in real-time:"
echo "   Grafana:    http://localhost:3000 (admin/admin)"
echo "   Prometheus: http://localhost:9090"
echo ""
echo "6. Stop infrastructure when done:"
echo "   just docker-down"
echo ""
echo "======================================================================"
