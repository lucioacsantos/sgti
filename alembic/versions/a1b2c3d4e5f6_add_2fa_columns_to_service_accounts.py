"""Add 2FA columns to service_accounts

Revision ID: a1b2c3d4e5f6
Revises: 45529f9a81e0
Create Date: 2026-09-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '45529f9a81e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('service_accounts', sa.Column('totp_secret', sa.String(length=64), nullable=True))
    op.add_column('service_accounts', sa.Column('totp_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('service_accounts', 'totp_enabled')
    op.drop_column('service_accounts', 'totp_secret')