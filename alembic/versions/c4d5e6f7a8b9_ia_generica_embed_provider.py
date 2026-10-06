"""Normaliza embed_provider legado "ollama:*" → "llm:*"

O provider de IA usado nos nomes de URLs/schemas foi generalizado de
"ollama" para "llm" (a API servidora continua compatível com Ollama).
Documentos indexados com a assinatura antiga recebem a nova, mantendo
os embeddings comparáveis pela nova busca.

Revision ID: c4d5e6f7a8b9
Revises: b3e4f5a6c7d8
Create Date: 2026-10-06 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3e4f5a6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Reescreve assinaturas de provider ollama:* para llm:* (mesmo modelo embutido)."""
    op.execute(
        "UPDATE documento "
        "SET embed_provider = 'llm:' || split_part(embed_provider, ':', 2) "
        "WHERE embed_provider LIKE 'ollama:%'"
    )
    op.alter_column(
        'documento',
        'embed_provider',
        server_default='llm:nomic-embed-text',
        existing_type=sa.String(255),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Volta assinaturas llm:<modelo> para ollama:<modelo>."""
    op.execute(
        "UPDATE documento "
        "SET embed_provider = 'ollama:' || split_part(embed_provider, ':', 2) "
        "WHERE embed_provider LIKE 'llm:%'"
    )
    op.alter_column(
        'documento',
        'embed_provider',
        server_default='ollama:nomic-embed-text',
        existing_type=sa.String(255),
        existing_nullable=False,
    )