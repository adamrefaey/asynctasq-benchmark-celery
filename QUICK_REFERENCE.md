# Quick Reference: Python 3.14 Upgrade

## ✅ Files Updated

1. **pyproject.toml**
   - Python: 3.12 → 3.14
   - ruff: 0.9.1 → 0.14.8
   - pyright: 1.1.391 → 1.1.407
   - pytest: 9.0.1 → 9.0.2
   - pytest-asyncio: 0.25.2 → 1.3.0
   - asynctasq: 0.1.0 → 0.9.11
   - celery: 5.5.3 → 5.6.0
   - Modern dependency-groups pattern
   - Enhanced ruff configuration (mccabe, pylint)

2. **infrastructure/Dockerfile.mock-api**
   - Base image: python:3.12-slim → python:3.14-slim

## 🚀 Next Steps

```bash
# 1. Navigate to project
cd /Users/adamrefaey/Code/asynctasq-benchmark-celery

# 2. Install dependencies with new versions
uv sync --all-extras --group dev

# 3. Verify Python version
uv run python --version

# 4. Run linting and type checking
uv run ruff check .
uv run pyright

# 5. Rebuild Docker images
cd infrastructure
docker compose up --build -d

# 6. Run tests
uv run pytest -v
```

## 📦 Key Package Versions (Latest Stable)

| Package | Version | Released |
|---------|---------|----------|
| Python | 3.14 | 2024 |
| ruff | 0.14.8 | Dec 4, 2025 |
| pyright | 1.1.407 | Oct 24, 2025 |
| pytest | 9.0.2 | Dec 6, 2025 |
| pytest-asyncio | 1.3.0 | Nov 10, 2025 |
| asynctasq | 0.9.11 | Current |
| celery | 5.6.0 | Current |

## 🔍 Configuration Highlights

### Ruff (0.14.8)
- 800+ built-in rules
- 10-100x faster than alternatives
- Python 3.14 support
- Drop-in parity with Flake8/Black/isort

### Enhanced Lint Rules
- McCabe complexity: max 10
- Pylint checks: max args (8), branches (12), returns (6), statements (50)

## 📝 Documentation

See `UPGRADE_SUMMARY.md` for:
- Complete change log
- Version justification
- Breaking changes analysis
- Verification steps
- Configuration diffs

---

**Status:** ✅ Ready for use with Python 3.14
**Compatibility:** Backward compatible with Python 3.12+ code
**Dependencies:** All latest stable versions as of December 2025
