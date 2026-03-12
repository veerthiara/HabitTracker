FROM python:3.11-slim

ENV POETRY_VERSION=2.1.1 \
	POETRY_NO_INTERACTION=1 \
	POETRY_VIRTUALENVS_IN_PROJECT=true

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

WORKDIR /app

COPY pyproject.toml /app/

RUN poetry install --no-root

COPY . /app

CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
