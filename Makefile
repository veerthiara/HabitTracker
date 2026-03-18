.PHONY: backend-install backend-run backend-health backend-docker-up backend-docker-down client-install client-run client-build

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