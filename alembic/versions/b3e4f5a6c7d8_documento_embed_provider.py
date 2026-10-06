"""documento.embed_provider — provider de embeddings da indexação (engine híbrida)

Permite conviver com dois providers de IA (ollama / local sentence-transformers):
cada documento registra qual modelo gerou seus embeddings e a busca semântica
só compara trechos no mesmo espaço vetorial.

Revision ID: b3e4f5a6c7d8
Revises: a1f2c3d4e5f6
Create Date: 2026-10-06 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3e4f5a6c7d8'
down_revision: Union[str, Sequence[str], None] = 'a1f2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona a coluna embed_provider e a preenche retroativamente."""
    op.add_column(
        'documento',
        sa.Column('embed_provider', sa.String(255), nullable=False,
                  server_default='ollama:nomic-embed-text'),
    )
    op.create_index('ix_documento_embed_provider', 'documento', ['embed_provider'])
    # Documentos indexados antes desta migration vieram do Ollama
    op.execute(
        "UPDATE documento SET embed_provider = 'ollama:nomic-embed-text' "
        "WHERE embed_provider IS NULL OR embed_provider = ''"
    )


def downgrade() -> None:
    """Remove a coluna embed_provider."""
    op.drop_index('ix_documento_embed_provider', table_name='documento')
    op.drop_column('documento', 'embed_provider')