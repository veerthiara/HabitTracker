.PHONY: backend-install backend-run backend-health backend-docker-up backend-docker-down client-install client-run client-build docs-install docs-run docs-build local-db-up local-db-down local-db-reset local-db-logs local-db-ps local-db-check db-migrate db-downgrade db-revision db-history db-seed embed-notes test-embed

backend-install:
	cd backend && poetry install

backend-run:
	cd backend && poetry run uvicorn main:app --host 127.0.0.1 --port 8000 --reload

backend-health:
	curl --fail --silent http://127.0.0.1:8000/health

backend-docker-up:
	docker compose up --build backend

backend-docker-down:
	docker compose down

client-install:
	cd client && npm install

client-run:
	cd client && npm run dev

client-build:
	cd client && npm run build

docs-install:
	cd website && npm install

docs-run:
	cd website && npm run start

docs-build:
	cd website && npm run build

local-db-up:
	docker compose --env-file infra/local/.env -f infra/local/docker-compose.yml up -d

local-db-down:
	docker compose --env-file infra/local/.env -f infra/local/docker-compose.yml down

# ⚠️  Destroys and recreates the volume — all data is lost.
# Required when switching the Postgres image (e.g. to pgvector/pgvector:pg16).
# After running: make db-migrate && make db-seed
local-db-reset:
	docker compose --env-file infra/local/.env -f infra/local/docker-compose.yml down -v
	docker compose --env-file infra/local/.env -f infra/local/docker-compose.yml up -d

local-db-logs:
	docker compose --env-file infra/local/.env -f infra/local/docker-compose.yml logs -f postgres

local-db-ps:
	docker compose --env-file infra/local/.env -f infra/local/docker-compose.yml ps

local-db-check:
	docker compose --env-file infra/local/.env -f infra/local/docker-compose.yml exec postgres sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT 1;"'

# Alembic migration targets (require local DB to be running and DATABASE_URL set in infra/local/.env)
db-migrate:
	cd backend && poetry run alembic upgrade head

db-downgrade:
	cd backend && poetry run alembic downgrade -1

db-revision:
	cd backend && poetry run alembic revision --autogenerate -m "$(msg)"

db-history:
	cd backend && poetry run alembic history --verbose

db-seed:
	cd backend && poetry run python -m scripts.seed.main

embed-notes:
	cd backend && poetry run python -m scripts.embed.main

test-embed:
	cd backend && poetry run pytest tests/scripts/embed/ -v
