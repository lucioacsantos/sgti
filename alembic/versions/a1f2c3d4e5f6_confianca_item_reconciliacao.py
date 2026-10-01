"""adiciona confianca em item_reconciliacao (inferencia IA)

Revision ID: a1f2c3d4e5f6
Revises: 91831d0dc95e
Create Date: 2026-09-22 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '91831d0dc95e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona a coluna de confiabilidade da inferência por IA."""
    op.add_column(
        'item_reconciliacao',
        sa.Column('confianca', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Remove a coluna de confiabilidade."""
    op.drop_column('item_reconciliacao', 'confianca')