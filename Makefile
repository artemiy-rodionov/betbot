.PHONY: help install test lint fmt format check

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Sync dependencies (incl. dev group)
	uv sync --group dev

test:  ## Run the test suite (extra args: make test ARGS="-k pending -v")
	uv run --group dev pytest $(ARGS)

lint:  ## Lint with ruff and flake8
	uvx ruff check betbot test_bot.py
	uv run flake8 betbot test_bot.py

fmt:  ## Auto-format with ruff
	uvx ruff format betbot test_bot.py

format: fmt  ## Alias for fmt

check: lint test  ## Lint then run tests
