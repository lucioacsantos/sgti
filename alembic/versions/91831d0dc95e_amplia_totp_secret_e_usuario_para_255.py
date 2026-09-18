"""amplia totp_secret e usuario para 255

Revision ID: 91831d0dc95e
Revises: 68bb57b2a384
Create Date: 2026-09-18 10:45:17.442020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91831d0dc95e'
down_revision: Union[str, Sequence[str], None] = '68bb57b2a384'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Alargamento é seguro: aumenta limite sem tocar nos dados existentes
    op.alter_column(
        'service_accounts', 'totp_secret',
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=True,
        postgresql_type_=sa.String(length=255),
    )
    op.alter_column(
        'audit_log', 'usuario',
        existing_type=sa.String(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Atenção: se algum valor cifrado > 64 chars foi gravado, o downgrade
    # pode falhar. Recrie o secret 2FA antes de reduzir a coluna.
    op.alter_column(
        'audit_log', 'usuario',
        existing_type=sa.String(length=255),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        'service_accounts', 'totp_secret',
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
