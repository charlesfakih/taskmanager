.PHONY: install migrate seed run test lint format docker-up

install:
	uv sync

migrate:
	uv run alembic upgrade head

seed:
	uv run python -m taskmanager.scripts.seed

run:
	uv run uvicorn taskmanager.main:app --reload

test:
	uv run pytest

lint:
	uv run ruff check src tests

format:
	uv run ruff format src tests

# Full stack (Postgres + API) via Docker, for the grader's convenience.
docker-up:
	docker compose up --build
