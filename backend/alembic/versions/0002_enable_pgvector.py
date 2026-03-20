"""enable pgvector extension

Revision ID: 0002_enable_pgvector
Revises: 0001_initial
Create Date: 2026-03-20

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_enable_pgvector"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Requires the pgvector/pgvector:pg16 Docker image (or pgvector installed in Postgres).
    # Safe to run multiple times — IF NOT EXISTS is idempotent.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Dropping the extension will fail if any column of type vector still exists.
    # Remove embedding columns first (see 0003_note_embeddings) before running downgrade here.
    op.execute("DROP EXTENSION IF EXISTS vector")
