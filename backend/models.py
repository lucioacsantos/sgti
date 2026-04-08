from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey,
    DateTime, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import func, Index

from database import Base

import secrets
from datetime import datetime, timedelta


# TOKENS DE SERVIÇO
class ServiceAccount(Base):
    __tablename__ = "service_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)  # Ex: "Ansible-Automation"
    token = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)

    def is_valid(self):
        return self.is_active and self.expires_at > datetime.utcnow()


# AUDIT
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)

    entidade = Column(String(50), nullable=False)
    entidade_id = Column(Integer, nullable=False)

    acao = Column(String(20), nullable=False)

    antes = Column(JSONB, nullable=True)
    depois = Column(JSONB, nullable=True)

    usuario = Column(String(100), nullable=False)

    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_entidade", "entidade"),
        Index("ix_audit_entidade_id", "entidade_id"),
        Index("ix_audit_criado_em", "criado_em"),
    )


class AuditMixin:
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)


# TOKENS
class ApiToken(Base):
    __tablename__ = "api_token"

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)

    ativo = Column(Boolean, default=True)
    expira_em = Column(DateTime, nullable=True)

    criado_em = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, onupdate=func.now())


# DOMÍNIOS
class TipoAtivo(Base):
    __tablename__ = "tipo_ativo"

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)
    descricao = Column(Text)


class TipoRelacionamento(Base):
    __tablename__ = "tipo_relacionamento"

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)
    descricao = Column(Text)


class Ambiente(Base):
    __tablename__ = "ambiente"

    id = Column(Integer, primary_key=True)
    nome = Column(String(50), unique=True, nullable=False)


class StatusAtivo(Base):
    __tablename__ = "status_ativo"

    id = Column(Integer, primary_key=True)
    nome = Column(String(50), unique=True, nullable=False)


class Criticidade(Base):
    __tablename__ = "criticidade"

    id = Column(Integer, primary_key=True)
    nivel = Column(String(50), unique=True, nullable=False)


# CORE CMDB
class Ativo(Base, AuditMixin):
    __tablename__ = "ativo"

    id = Column(Integer, primary_key=True)

    nome = Column(String(255), nullable=False)
    descricao = Column(Text)

    tipo_id = Column(Integer, ForeignKey("tipo_ativo.id"), nullable=False)
    ambiente_id = Column(Integer, ForeignKey("ambiente.id"))
    status_id = Column(Integer, ForeignKey("status_ativo.id"))
    criticidade_id = Column(Integer, ForeignKey("criticidade.id"))

    responsavel = Column(String(255))

    tipo = relationship("TipoAtivo")
    ambiente = relationship("Ambiente")
    status = relationship("StatusAtivo")
    criticidade = relationship("Criticidade")

    def __repr__(self):
        return f"<Ativo id={self.id} nome='{self.nome}'>"


# RELACIONAMENTOS (GRAFO)
class Relacionamento(Base):
    __tablename__ = "relacionamento"

    id = Column(Integer, primary_key=True)

    origem_id = Column(Integer, ForeignKey("ativo.id", ondelete="CASCADE"), nullable=False)
    destino_id = Column(Integer, ForeignKey("ativo.id", ondelete="CASCADE"), nullable=False)

    tipo_id = Column(Integer, ForeignKey("tipo_relacionamento.id"), nullable=False)

    descricao = Column(Text)

    created_at = Column(DateTime, server_default=func.now())

    origem = relationship("Ativo", foreign_keys=[origem_id])
    destino = relationship("Ativo", foreign_keys=[destino_id])
    tipo = relationship("TipoRelacionamento")

    def __repr__(self):
        return f"<Relacionamento {self.origem_id} -> {self.destino_id}>"