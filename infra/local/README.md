# Local Infra

This folder contains local infrastructure resources that can be started independently of application code.

## Current scope

- PostgreSQL for local development

## Prerequisites

- Docker Desktop

## Setup

1. Create local env file:

```bash
cp infra/local/.env.example infra/local/.env
```

2. Start Postgres:

```bash
make local-db-up
```

3. Check container status:

```bash
make local-db-ps
```

4. Run a basic query check:

```bash
make local-db-check
```

Expected output includes:

```text
?column?
----------
        1
```

5. Follow logs when needed:

```bash
make local-db-logs
```

6. Stop local DB:

```bash
make local-db-down
```
