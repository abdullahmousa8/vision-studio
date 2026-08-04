PYTHON ?= python
PYTEST ?= $(PYTHON) -m pytest
RUFF ?= $(PYTHON) -m ruff
CELERY ?= $(PYTHON) -m celery
ALEMBIC ?= alembic

.PHONY: help install dev test lint format run migrate worker docker-up docker-down docker-logs clean

help:
	@echo "Targets:"
	@echo "  install      create venv and install package with dev extras"
	@echo "  dev          run dev dependencies (lint/test aliases)"
	@echo "  test         run unit tests"
	@echo "  lint         run ruff check + format check"
	@echo "  format       auto-fix and format with ruff"
	@echo "  run          start the API with uvicorn (reload)"
	@echo "  migrate      apply alembic migrations to the local DB"
	@echo "  worker       start a Celery worker (pipeline/dlq/default queues)"
	@echo "  docker-up    build and start the full stack via docker compose"
	@echo "  docker-down  stop the stack"
	@echo "  docker-logs  tail api + worker logs"
	@echo "  clean        remove caches"

install:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTEST) tests/unit -q

lint:
	$(RUFF) check app tests
	$(RUFF) format --check app tests

format:
	$(RUFF) check --fix app tests
	$(RUFF) format app tests

run:
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	$(ALEMBIC) upgrade head

worker:
	$(CELERY) -A app.core.celery_app worker --loglevel=info --queues=pipeline,dlq,default

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api worker

clean:
	$(PYTHON) -m ruff clean
	rm -rf .pytest_cache .ruff_cache .mypy_cache
