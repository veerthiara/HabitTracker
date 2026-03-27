"""add embedding column to notes

Revision ID: 0003_note_embeddings
Revises: 0002_enable_pgvector
Create Date: 2026-03-20

Adds a nullable vector(768) embedding column to the notes table and
creates an HNSW index for cosine-similarity search.

Dimension (768) matches nomic-embed-text via Ollama.
If the embedding model changes, add a new migration — do not edit this one.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_note_embeddings"
down_revision: Union[str, None] = "0002_enable_pgvector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBED_DIMS = 768


def upgrade() -> None:
    # Add nullable embedding column using raw DDL — avoids importing pgvector in the
    # migration environment. Existing rows are unaffected (column defaults to NULL).
    op.execute(f"ALTER TABLE notes ADD COLUMN IF NOT EXISTS embedding vector({EMBED_DIMS})")

    # HNSW index for fast approximate cosine-distance search.
    # m=16, ef_construction=64 are sensible defaults for small datasets.
    op.execute(
        "CREATE INDEX IF NOT EXISTS notes_embedding_hnsw_idx "
        "ON notes USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS notes_embedding_hnsw_idx")
    op.execute("ALTER TABLE notes DROP COLUMN IF EXISTS embedding")
