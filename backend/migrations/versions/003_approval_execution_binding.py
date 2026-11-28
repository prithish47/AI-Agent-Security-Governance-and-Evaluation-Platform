"""Add policy_version and agent_risk_ceiling to approval_requests

Revision ID: 003_approval_execution_binding
Revises: 002_refresh_token_rotation
Create Date: 2026-11-28 11:25:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_approval_execution_binding"
down_revision: Union[str, None] = "002_refresh_token_rotation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "approval_requests",
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "approval_requests",
        sa.Column("agent_risk_ceiling", sa.String(length=20), nullable=False, server_default="MEDIUM"),
    )


def downgrade() -> None:
    with op.batch_alter_table("approval_requests") as batch_op:
        batch_op.drop_column("agent_risk_ceiling")
        batch_op.drop_column("policy_version")
