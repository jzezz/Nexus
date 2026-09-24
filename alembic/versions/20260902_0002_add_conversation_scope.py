"""Add persisted conversation scope metadata.

Revision ID: 20260902_0002
Revises: 20260803_0001
Create Date: 2026-09-02 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260902_0002"
down_revision: str | None = "20260803_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None



def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("scoped_document_ids_json", sa.Text(), nullable=False, server_default="[]"),
    )



def downgrade() -> None:
    op.drop_column("conversations", "scoped_document_ids_json")
