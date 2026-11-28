"""Add refresh token rotation family tracking columns

Revision ID: 002_refresh_token_rotation
Revises: 001_initial_schema
Create Date: 2026-11-28 11:05:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_refresh_token_rotation"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("family_id", sa.Uuid(), nullable=True))
    op.add_column("refresh_tokens", sa.Column("replaced_by_token_id", sa.Uuid(), nullable=True))
    op.add_column("refresh_tokens", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))

    # Backfill existing refresh_tokens rows so each gets a unique session family_id
    op.execute(sa.text("UPDATE refresh_tokens SET family_id = id WHERE family_id IS NULL"))

    with op.batch_alter_table("refresh_tokens") as batch_op:
        batch_op.alter_column("family_id", existing_type=sa.Uuid(), nullable=False)

    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    with op.batch_alter_table("refresh_tokens") as batch_op:
        batch_op.drop_column("revoked_at")
        batch_op.drop_column("replaced_by_token_id")
        batch_op.drop_column("family_id")
