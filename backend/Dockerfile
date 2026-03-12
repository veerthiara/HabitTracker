FROM python:3.9-slim

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Set Poetry environment variables
ENV POETRY_CACHE_DIR=/root/.cache/pypoetry
ENV POETRY_VENV_CACHE_DIR=/root/.cache/pypoetry/virtualenvs
ENV PATH="/root/.poetry/bin:$PATH"

# Copy the pyproject.toml and poetry.lock files
COPY backend/pyproject.toml backend/poetry.lock /app/

# Install dependencies with Poetry
RUN cd /app && poetry install --no-interaction
WORKDIR /app

# Remove the old RUN command

# Use Poetry to run the application
CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
