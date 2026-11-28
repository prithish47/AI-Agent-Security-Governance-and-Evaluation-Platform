"""Add conversation_history to executions, and binding_version, policy_id, tool_schema_hash to approval_requests

Revision ID: 004_secure_execution_resumption
Revises: 003_approval_execution_binding
Create Date: 2026-11-28 11:35:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_secure_execution_resumption"
down_revision: Union[str, None] = "003_approval_execution_binding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON_TYPE = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    # 1. executions.conversation_history
    op.add_column(
        "executions",
        sa.Column("conversation_history", JSON_TYPE, nullable=False, server_default="[]"),
    )

    # 2. approval_requests fields for enhanced cryptographic binding
    op.add_column(
        "approval_requests",
        sa.Column("binding_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "approval_requests",
        sa.Column("policy_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "approval_requests",
        sa.Column("tool_schema_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("approval_requests") as batch_op:
        batch_op.drop_column("tool_schema_hash")
        batch_op.drop_column("policy_id")
        batch_op.drop_column("binding_version")

    with op.batch_alter_table("executions") as batch_op:
        batch_op.drop_column("conversation_history")
