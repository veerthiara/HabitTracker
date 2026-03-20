.PHONY: backend-install backend-run backend-health backend-docker-up backend-docker-down client-install client-run client-build local-db-up local-db-down local-db-logs local-db-ps local-db-check db-migrate db-downgrade db-revision db-history

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

local-db-up:
	docker compose --env-file infra/local/.env -f infra/local/docker-compose.yml up -d

local-db-down:
	docker compose --env-file infra/local/.env -f infra/local/docker-compose.yml down

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