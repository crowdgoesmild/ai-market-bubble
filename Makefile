CODEX_PYTHON ?= $(HOME)/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
PYTHON ?= $(shell command -v python3.12 || command -v python3.13 || command -v python3.11 || test -x "$(CODEX_PYTHON)" && printf '%s\n' "$(CODEX_PYTHON)" || printf '%s\n' python3.12)
VENV ?= .venv
VENV_BIN := $(VENV)/bin

.PHONY: setup run sample test lint clean

setup: $(VENV_BIN)/python
	$(VENV_BIN)/python -m pip install --upgrade pip
	$(VENV_BIN)/python -m pip install -e ".[dev]"

$(VENV_BIN)/python:
	$(PYTHON) -m venv $(VENV)

run:
	$(VENV_BIN)/python -m src.run_daily

sample:
	$(VENV_BIN)/python -m src.run_sample

test:
	$(VENV_BIN)/python -m pytest

lint:
	$(VENV_BIN)/python -m ruff check .

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage build dist *.egg-info
