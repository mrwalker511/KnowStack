.PHONY: install install-dev test test-fast test-unit test-integration lint typecheck fmt clean index index-incremental query serve

PYTHON := python3
PIP    := pip

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev,serve]"

test:
	pytest

test-fast:
	pytest -x -q --no-cov

test-unit:
	pytest -m "not integration" -q --no-cov

test-integration:
	pytest -m integration -v

lint:
	ruff check knowstack tests

fmt:
	ruff format knowstack tests

typecheck:
	mypy knowstack

clean:
	rm -rf .knowstack/ dist/ build/ *.egg-info __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete

# Dev helpers — pass REPO= to override target repository
REPO ?= .

index:
	knowstack index $(REPO)

index-incremental:
	knowstack index $(REPO) --incremental

query:
	knowstack query --interactive

serve:
	knowstack serve $(REPO)
