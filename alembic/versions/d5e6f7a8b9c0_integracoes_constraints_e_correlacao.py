# Objetivo: Ajusta constraints de unicidade (namespace, servico, instancia, relacionamento) e adiciona bios_uuid/fqdn em ativo.
# Author: Lucio A C Santos — GitHub: https://github.com/lucioacsantos

"""integracoes constraints e correlacao de ativos

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-10-29 20:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _coluna_existe(tabela: str, coluna: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return coluna in {c["name"] for c in insp.get_columns(tabela)}


def _indice_existe(tabela: str, nome: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return nome in {i["name"] for i in insp.get_indexes(tabela)}


def _unique_constraints_por_colunas(tabela: str, colunas: tuple[str, ...]) -> list[str]:
    insp = sa.inspect(op.get_bind())
    alvos = []
    for uq in insp.get_unique_constraints(tabela):
        cols = tuple(uq.get("column_names") or ())
        if cols == colunas and uq.get("name"):
            alvos.append(uq["name"])
    return alvos


def _constraint_existe(tabela: str, nome: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return nome in {uq.get("name") for uq in insp.get_unique_constraints(tabela)}


def upgrade() -> None:
    """Evolui o schema para suportar descoberta multi-fonte via AAP:

    1. Adiciona bios_uuid (único) e fqdn em ativo para correlação vCenter ↔ Satellite.
    2. Substitui UNIQUE(nome) global de namespace por UNIQUE(cluster_id, nome).
    3. Remove UNIQUE(ativo_id) estrito (1:1) de servico e instancia_aplicacao,
       adicionando UNIQUE(ativo_id, nome) e UNIQUE(aplicacao_id, ativo_id, porta).
    4. Adiciona UNIQUE(origem_id, destino_id, tipo_id) em relacionamento.
    """
    # 1. Colunas de correlação em ativo
    if not _coluna_existe("ativo", "bios_uuid"):
        op.add_column("ativo", sa.Column("bios_uuid", sa.String(100), nullable=True))
    if not _coluna_existe("ativo", "fqdn"):
        op.add_column("ativo", sa.Column("fqdn", sa.String(255), nullable=True))

    if not _indice_existe("ativo", "ix_ativo_bios_uuid"):
        op.create_index("ix_ativo_bios_uuid", "ativo", ["bios_uuid"], unique=True)
    if not _indice_existe("ativo", "ix_ativo_fqdn"):
        op.create_index("ix_ativo_fqdn", "ativo", ["fqdn"], unique=False)

    # 2. Namespace: troca UNIQUE(nome) por UNIQUE(cluster_id, nome)
    for uq_name in _unique_constraints_por_colunas("namespace", ("nome",)):
        op.drop_constraint(uq_name, "namespace", type_="unique")
    if not _indice_existe("namespace", "ix_namespace_cluster_id"):
        op.create_index("ix_namespace_cluster_id", "namespace", ["cluster_id"], unique=False)
    if not _constraint_existe("namespace", "uq_namespace_cluster_id_nome"):
        op.create_unique_constraint(
            "uq_namespace_cluster_id_nome", "namespace", ["cluster_id", "nome"]
        )

    # 3. Servico: remove UNIQUE(ativo_id) 1:1 e cria UNIQUE(ativo_id, nome)
    for uq_name in _unique_constraints_por_colunas("servico", ("ativo_id",)):
        op.drop_constraint(uq_name, "servico", type_="unique")
    if not _indice_existe("servico", "ix_servico_ativo_id"):
        op.create_index("ix_servico_ativo_id", "servico", ["ativo_id"], unique=False)
    if not _constraint_existe("servico", "uq_servico_ativo_id_nome"):
        op.create_unique_constraint(
            "uq_servico_ativo_id_nome", "servico", ["ativo_id", "nome"]
        )

    # 4. InstanciaAplicacao: remove UNIQUE(ativo_id) 1:1 e cria UNIQUE(aplicacao_id, ativo_id, porta)
    for uq_name in _unique_constraints_por_colunas("instancia_aplicacao", ("ativo_id",)):
        op.drop_constraint(uq_name, "instancia_aplicacao", type_="unique")
    if not _indice_existe("instancia_aplicacao", "ix_instancia_aplicacao_ativo_id"):
        op.create_index(
            "ix_instancia_aplicacao_ativo_id", "instancia_aplicacao", ["ativo_id"], unique=False
        )
    if not _constraint_existe("instancia_aplicacao", "uq_instancia_aplicacao_app_ativo_porta"):
        op.create_unique_constraint(
            "uq_instancia_aplicacao_app_ativo_porta",
            "instancia_aplicacao",
            ["aplicacao_id", "ativo_id", "porta"],
        )

    # 5. Relacionamento: garante UNIQUE(origem_id, destino_id, tipo_id)
    if not _constraint_existe("relacionamento", "uq_relacionamento_origem_destino_tipo"):
        op.create_unique_constraint(
            "uq_relacionamento_origem_destino_tipo",
            "relacionamento",
            ["origem_id", "destino_id", "tipo_id"],
        )


def downgrade() -> None:
    """Reverte constraints compostas e colunas de correlação."""
    if _constraint_existe("relacionamento", "uq_relacionamento_origem_destino_tipo"):
        op.drop_constraint("uq_relacionamento_origem_destino_tipo", "relacionamento", type_="unique")

    if _constraint_existe("instancia_aplicacao", "uq_instancia_aplicacao_app_ativo_porta"):
        op.drop_constraint(
            "uq_instancia_aplicacao_app_ativo_porta", "instancia_aplicacao", type_="unique"
        )
    if _indice_existe("instancia_aplicacao", "ix_instancia_aplicacao_ativo_id"):
        op.drop_index("ix_instancia_aplicacao_ativo_id", table_name="instancia_aplicacao")
    if not _unique_constraints_por_colunas("instancia_aplicacao", ("ativo_id",)):
        op.create_unique_constraint(
            "instancia_aplicacao_ativo_id_key", "instancia_aplicacao", ["ativo_id"]
        )

    if _constraint_existe("servico", "uq_servico_ativo_id_nome"):
        op.drop_constraint("uq_servico_ativo_id_nome", "servico", type_="unique")
    if _indice_existe("servico", "ix_servico_ativo_id"):
        op.drop_index("ix_servico_ativo_id", table_name="servico")
    if not _unique_constraints_por_colunas("servico", ("ativo_id",)):
        op.create_unique_constraint("servico_ativo_id_key", "servico", ["ativo_id"])

    if _constraint_existe("namespace", "uq_namespace_cluster_id_nome"):
        op.drop_constraint("uq_namespace_cluster_id_nome", "namespace", type_="unique")
    if _indice_existe("namespace", "ix_namespace_cluster_id"):
        op.drop_index("ix_namespace_cluster_id", table_name="namespace")
    if not _unique_constraints_por_colunas("namespace", ("nome",)):
        op.create_unique_constraint("namespace_nome_key", "namespace", ["nome"])

    if _indice_existe("ativo", "ix_ativo_fqdn"):
        op.drop_index("ix_ativo_fqdn", table_name="ativo")
    if _indice_existe("ativo", "ix_ativo_bios_uuid"):
        op.drop_index("ix_ativo_bios_uuid", table_name="ativo")
    if _coluna_existe("ativo", "fqdn"):
        op.drop_column("ativo", "fqdn")
    if _coluna_existe("ativo", "bios_uuid"):
        op.drop_column("ativo", "bios_uuid")
