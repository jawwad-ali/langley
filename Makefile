# Developer command shortcuts for the Langley monorepo.
#
# These wrap `uv` so contributors don't memorize flags. On Windows without
# `make`, run the underlying `uv` commands directly (see README.md).
#
# Usage: make <target>

.PHONY: help install lint format type test test-live eval run clean

help:
	@echo "install    Sync the uv workspace (creates .venv, installs deps)"
	@echo "lint       Ruff lint (check only)"
	@echo "format     Ruff format + lint --fix"
	@echo "type       Pyright strict type check"
	@echo "test       Run offline unit + eval tests (no network, no OpenAI spend)"
	@echo "test-live  Run live tests too (needs network + OPENAI_API_KEY)"
	@echo "eval       Run the offline eval harness over the golden dataset"
	@echo "run        Analyze a token: make run QUERY=<mint-or-symbol>"
	@echo "clean      Remove caches and build artifacts"

install:
	uv sync

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check . --fix

type:
	uv run pyright

test:
	uv run pytest -m "not live"

test-live:
	uv run pytest

eval:
	uv run python -m langley_risk.evals.run

run:
	uv run python -m langley_risk "$(QUERY)"

clean:
	rm -rf .ruff_cache .pytest_cache .coverage htmlcov coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
