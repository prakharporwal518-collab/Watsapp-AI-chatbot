.PHONY: install run test lint migrate migration secrets chat

install:        ## Create a virtualenv and install dependencies
	python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

run:            ## Start the API with auto-reload
	.venv/bin/uvicorn app.main:app --reload --port 8000

test:           ## Run all tests
	.venv/bin/pytest -q

lint:           ## Lint with ruff
	.venv/bin/ruff check .

migrate:        ## Apply database migrations
	.venv/bin/alembic upgrade head

migration:      ## Create a migration after changing models: make migration m="add column"
	.venv/bin/alembic revision --autogenerate -m "$(m)"

secrets:        ## Generate encryption/hash/internal secrets for .env
	.venv/bin/python scripts/generate_secrets.py

chat:           ## Chat with the bot in your terminal (no WhatsApp needed)
	.venv/bin/python scripts/chat_cli.py
