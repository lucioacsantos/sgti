from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Boolean, Float, Index, JSON
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import bcrypt
import os

# Use JSON instead of JSONB for SQLite compatibility in tests
if os.getenv("TESTING") == "1":
    JSONB = JSON
    INET = String

import crypto_guard
from sqlalchemy.types import TypeDecorator, String as SAString


class EncryptedText(TypeDecorator):
    """Coluna de texto cifrada com crypto_lock (AES-256-GCM) antes de ir ao banco."""

    impl = SAString
    cache_ok = True

    def __init__(self, length=255, **kwargs):
        # Valor cifrado (v1.<nonce>.<ct>) ocupa ~84+ chars; 255 evita truncamento
        super().__init__(length, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if crypto_guard.is_encrypted(value):
            return value
        return crypto_guard.encrypt_value(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if crypto_guard.is_encrypted(value):
            return crypto_guard.decrypt_value(value)
        return value


# TABELAS DE APOIO
class Criticidade(Base):
    __tablename__ = "criticidade"
    id = Column(Integer, primary_key=True)
    nivel = Column(String(50), unique=True, nullable=False)

class TipoAtivo(Base):
    __tablename__ = "tipo_ativo"
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)

class Ambiente(Base):
    __tablename__ = "ambiente"
    id = Column(Integer, primary_key=True)
    nome = Column(String(50), unique=True, nullable=False)

class StatusAtivo(Base):
    __tablename__ = "status_ativo"
    id = Column(Integer, primary_key=True)
    nome = Column(String(50), unique=True, nullable=False)

class Areas(Base):
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), unique=True, nullable=False)
    sigla = Column(String(50), unique=True, nullable=False)

class SistemaOperacional(Base):
    __tablename__ = "sor"
    id = Column(Integer, primary_key=True)
    abreviacao = Column(String(100), unique=True, nullable=False)
    descricao = Column(String(255), nullable=False)
    lifecycle = Column(String(50))

class Aplicacao(Base):
    __tablename__ = "aplicacao"
    id = Column(Integer, primary_key=True, index=True)
    sistema = Column(String(255), unique=True, nullable=False)
    descricao = Column(String(255))
    objetivo = Column(Text)
    linguagens = Column(String(255))
    bancos_dados = Column(String(255))
    area_tecnologia = Column(String(255))
    area_negocio = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())

# TABELA ATIVO
class Ativo(Base):
    __tablename__ = "ativo"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False, index=True)
    descricao = Column(Text)

    tipo_id = Column(Integer, ForeignKey("tipo_ativo.id"), nullable=False)
    ambiente_id = Column(Integer, ForeignKey("ambiente.id"))
    status_id = Column(Integer, ForeignKey("status_ativo.id"))
    criticidade_id = Column(Integer, ForeignKey("criticidade.id"))
    sor_id = Column(Integer, ForeignKey("sor.id"))

    areas_id = Column(Integer, ForeignKey("areas.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamentos
    ambiente = relationship("Ambiente")
    criticidade = relationship("Criticidade")
    tipo = relationship("TipoAtivo")
    status = relationship("StatusAtivo")
    sor = relationship("SistemaOperacional")
    areas = relationship("Areas")

# TABELA ENDERECO_IP
class EnderecoIp(Base):
    __tablename__ = "endereco_ip"

    id = Column(Integer, primary_key=True, index=True)
    ativo_id = Column(Integer, ForeignKey("ativo.id", ondelete="CASCADE"), nullable=False, index=True)
    ip = Column(INET, nullable=False, index=True)
    tipo = Column(String(20), default="IPv4")
    interface = Column(String(50))
    descricao = Column(String(255))
    primario = Column(Boolean, default=False)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    ativo_rel = relationship("Ativo")

    __table_args__ = (
        Index("ix_endereco_ip_ativo_id_ip", "ativo_id", "ip", unique=True),
    )


# TABELA SERVICE ACCOUNT
class ServiceAccount(Base):
    __tablename__ = "service_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    totp_secret = Column(EncryptedText(255), nullable=True)
    totp_enabled = Column(Boolean, default=False, nullable=False, server_default="false")

    def set_token(self, token: str) -> None:
        """Hash and store token."""
        self.token_hash = bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()

    def verify_token(self, token: str) -> bool:
        """Verify a plaintext token against stored hash."""
        try:
            return bcrypt.checkpw(token.encode(), self.token_hash.encode())
        except ValueError:
            # token_hash não é um hash bcrypt (ex.: JSON de usuário AD)
            return False


# TABELA TIPO RELACIONAMENTO
class TipoRelacionamento(Base):
    __tablename__ = "tipo_relacionamento"

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)
    descricao = Column(Text)


# TABELA CLUSTER
class Cluster(Base):
    __tablename__ = "cluster"

    id = Column(Integer, primary_key=True)
    nome = Column(String(255), unique=True, nullable=False)
    descricao = Column(Text)
    ativo_id = Column(Integer, ForeignKey("ativo.id", ondelete="SET NULL"), unique=True)

    ativo = relationship("Ativo")


# TABELA NAMESPACE
class Namespace(Base):
    __tablename__ = "namespace"

    id = Column(Integer, primary_key=True)
    nome = Column(String(255), unique=True, nullable=False)
    cluster_id = Column(Integer, ForeignKey("cluster.id", ondelete="CASCADE"))
    ativo_id = Column(Integer, ForeignKey("ativo.id", ondelete="SET NULL"), unique=True)

    cluster = relationship("Cluster")
    ativo = relationship("Ativo")


# TABELA RELACIONAMENTO
class Relacionamento(Base):
    __tablename__ = "relacionamento"

    id = Column(Integer, primary_key=True)
    origem_id = Column(Integer, ForeignKey("ativo.id", ondelete="CASCADE"), nullable=False, index=True)
    destino_id = Column(Integer, ForeignKey("ativo.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo_id = Column(Integer, ForeignKey("tipo_relacionamento.id"), nullable=False)
    descricao = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    origem = relationship("Ativo", foreign_keys=[origem_id])
    destino = relationship("Ativo", foreign_keys=[destino_id])
    tipo = relationship("TipoRelacionamento")


# TABELA SERVICO
class Servico(Base):
    __tablename__ = "servico"

    id = Column(Integer, primary_key=True)
    nome = Column(String(255), nullable=False)
    tipo = Column(String(50))
    host_id = Column(Integer)
    ativo_id = Column(Integer, ForeignKey("ativo.id", ondelete="SET NULL"), unique=True)

    ativo = relationship("Ativo")


# TABELA SERVICO NEGOCIO
class ServicoNegocio(Base):
    __tablename__ = "servico_negocio"

    id = Column(Integer, primary_key=True)
    nome = Column(String(255), nullable=False)
    descricao = Column(Text)
    ativo_id = Column(Integer, ForeignKey("ativo.id", ondelete="SET NULL"), unique=True)

    ativo = relationship("Ativo")


# TABELA INSTANCIA APLICACAO
class InstanciaAplicacao(Base):
    __tablename__ = "instancia_aplicacao"

    id = Column(Integer, primary_key=True)
    aplicacao_id = Column(Integer, ForeignKey("aplicacao.id", ondelete="CASCADE"), nullable=False, index=True)
    ativo_id = Column(Integer, ForeignKey("ativo.id", ondelete="SET NULL"), unique=True)
    porta = Column(Integer)
    path_execucao = Column(String(255))
    comando_execucao = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    aplicacao = relationship("Aplicacao")
    ativo = relationship("Ativo")


# TABELA DOCUMENTO (BASE DE CONHECIMENTO - MANUAIS E PROCEDIMENTOS)
class Documento(Base):
    __tablename__ = "documento"

    id = Column(Integer, primary_key=True)
    nome = Column(String(255), unique=True, nullable=False, index=True)
    arquivo = Column(String(512), nullable=False)
    titulo = Column(String(255))
    conteudo_hash = Column(String(64), nullable=False)
    # Provider/modelo de embeddings usado na indexação ("llm:nomic-embed-text",
    # "local:paraphrase-multilingual-MiniLM-L12-v2"; legado "ollama:*"). Embeddings
    # de modelos distintos não são comparáveis: a busca casa provider → provider.
    embed_provider = Column(String(255), nullable=False, server_default="llm:nomic-embed-text")
    indexado_em = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())

    trechos = relationship(
        "TrechoDocumento", back_populates="documento", cascade="all, delete-orphan"
    )


# TABELA TRECHO DOCUMENTO (CHUNK COM EMBEDDING)
class TrechoDocumento(Base):
    __tablename__ = "trecho_documento"

    id = Column(Integer, primary_key=True)
    documento_id = Column(
        Integer, ForeignKey("documento.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordem = Column(Integer, nullable=False)
    titulo_secao = Column(String(255))
    conteudo = Column(Text, nullable=False)
    embedding = Column(JSONB, nullable=False)

    documento = relationship("Documento", back_populates="trechos")


# TABELA AUDIT LOG
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    entidade = Column(String(100), nullable=False, index=True)
    entidade_id = Column(Integer, index=True)
    acao = Column(String(50))
    antes = Column(JSONB)
    depois = Column(JSONB)
    usuario = Column(EncryptedText(255))
    created_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_audit_log_entidade_entidade_id", "entidade", "entidade_id"),
        Index("ix_audit_log_entidade_created_at", "entidade", "created_at"),
    )

# TABELA RECONCILIAÇÃO (CMDB ↔ FONTE EXTERNA / INVENTÁRIO)
class Reconciliacao(Base):
    """Execução de uma reconciliação entre o CMDB e uma fonte de dados
    (ex.: import_test_data, Zabbix, dump do pgAdmin). Cada execução agrega
    itens de discrepância que exigem verificação manual por 2+ analistas
    (workflow de quatro olhos) antes da retificação/ratificação."""
    __tablename__ = "reconciliacao"

    id = Column(Integer, primary_key=True)
    nome = Column(String(255), nullable=False)
    fonte = Column(String(100), nullable=False)  # dump_pgadmin|zabbix|manual|ia
    status = Column(String(30), nullable=False, server_default="aberta", index=True)
    # aberta | em_verificacao | concluida | cancelada
    criado_por = Column(EncryptedText(255))
    criado_em = Column(DateTime, server_default=func.now())
    concluida_em = Column(DateTime)

    itens = relationship("ItemReconciliacao", back_populates="reconciliacao",
                         cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_reconciliacao_status_fonte", "status", "fonte"),
    )


class ItemReconciliacao(Base):
    """Uma discrepância detectada: entidade CMDB vs valor da fonte externa.

    decisão: pendente | retificado (CMDB ajustado p/ fonte) | ratificado
             (fonte confirmada como errada, CMDB mantido) | ignorado
    verificação exige >=2 analistas distintos registrando parecer."""
    __tablename__ = "item_reconciliacao"

    id = Column(Integer, primary_key=True)
    reconciliacao_id = Column(Integer, ForeignKey("reconciliacao.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    entidade = Column(String(100), nullable=False)   # ativo|aplicacao|servico|...
    entidade_id = Column(Integer, index=True)        # id no CMDB (None p/ novo na fonte)
    campo = Column(String(100))
    valor_cmdb = Column(Text)
    valor_fonte = Column(Text)
    detalhe = Column(Text)
    # Confiabilidade da inferência (0..1). Nulo = detecção estrutural/manual;
    # preenchido quando o item nasce de inferência por IA.
    confianca = Column(Float)
    status = Column(String(30), nullable=False, server_default="pendente", index=True)
    # pendente | em_verificacao | retificado | ratificado | ignorado
    resolvido_por = Column(String(100))
    resolvido_em = Column(DateTime)

    reconciliacao = relationship("Reconciliacao", back_populates="itens")
    pareceres = relationship("ParecerReconciliacao", back_populates="item",
                             cascade="all, delete-orphan")


class ParecerReconciliacao(Base):
    """Parecer individual de um analista sobre um item (4-olhos)."""
    __tablename__ = "parecer_reconciliacao"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("item_reconciliacao.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    analista = Column(String(100), nullable=False)
    parecer = Column(String(30), nullable=False)
    # retificar | ratificar | ignorar | inconcluso
    comentario = Column(Text)
    criado_em = Column(DateTime, server_default=func.now())

    item = relationship("ItemReconciliacao", back_populates="pareceres")
