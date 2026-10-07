"""adiciona confianca em item_reconciliacao (inferencia IA)

Revision ID: a1f2c3d4e5f6
Revises: 91831d0dc95e
Create Date: 2026-09-22 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent / "backend"))

from models import EncryptedText


# revision identifiers, used by Alembic.
revision: str = 'a1f2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '91831d0dc95e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabela_existe(nome: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return nome in insp.get_table_names()


def _coluna_existe(tabela: str, coluna: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return coluna in {c["name"] for c in insp.get_columns(tabela)}


def upgrade() -> None:
    """Adiciona a coluna de confiabilidade da inferência por IA.

    Idempotente: se a tabela foi criada por metadata.create_all (boot da app)
    já com a coluna atual do models.py, pula o ADD COLUMN sem falhar.
    """
    if _tabela_existe('item_reconciliacao'):
        if not _coluna_existe('item_reconciliacao', 'confianca'):
            op.add_column(
                'item_reconciliacao',
                sa.Column('confianca', sa.Float(), nullable=True),
            )
        return

    # Tabela ausente (baseline não a cria): sobe reconciliacao ->
    # item_reconciliacao -> parecer_reconciliacao conforme os models atuais
    if not _tabela_existe('reconciliacao'):
        op.create_table(
            'reconciliacao',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('nome', sa.String(255), nullable=False),
            sa.Column('fonte', sa.String(100), nullable=False),
            sa.Column('status', sa.String(30), nullable=False,
                      server_default='aberta'),
            sa.Column('criado_por', EncryptedText(255), nullable=True),
            sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()')),
            sa.Column('concluida_em', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_reconciliacao_status', 'reconciliacao', ['status'])
        op.create_index('ix_reconciliacao_status_fonte', 'reconciliacao',
                        ['status', 'fonte'])

    op.create_table(
        'item_reconciliacao',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('reconciliacao_id', sa.Integer(),
                  sa.ForeignKey('reconciliacao.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('entidade', sa.String(100), nullable=False),
        sa.Column('entidade_id', sa.Integer(), nullable=True),
        sa.Column('campo', sa.String(100), nullable=True),
        sa.Column('valor_cmdb', sa.Text(), nullable=True),
        sa.Column('valor_fonte', sa.Text(), nullable=True),
        sa.Column('detalhe', sa.Text(), nullable=True),
        sa.Column('confianca', sa.Float(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False,
                  server_default='pendente'),
        sa.Column('resolvido_por', sa.String(100), nullable=True),
        sa.Column('resolvido_em', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_item_reconciliacao_reconciliacao_id',
                    'item_reconciliacao', ['reconciliacao_id'])
    op.create_index('ix_item_reconciliacao_entidade_id',
                    'item_reconciliacao', ['entidade_id'])
    op.create_index('ix_item_reconciliacao_status',
                    'item_reconciliacao', ['status'])

    if not _tabela_existe('parecer_reconciliacao'):
        op.create_table(
            'parecer_reconciliacao',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('item_id', sa.Integer(),
                      sa.ForeignKey('item_reconciliacao.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('analista', sa.String(100), nullable=False),
            sa.Column('parecer', sa.String(30), nullable=False),
            sa.Column('comentario', sa.Text(), nullable=True),
            sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()')),
        )
        op.create_index('ix_parecer_reconciliacao_item_id',
                        'parecer_reconciliacao', ['item_id'])


def downgrade() -> None:
    """Remove a coluna de confiabilidade."""
    if _coluna_existe('item_reconciliacao', 'confianca'):
        op.drop_column('item_reconciliacao', 'confianca')