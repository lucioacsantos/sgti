from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

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

class SistemaOperacional(Base):
    __tablename__ = "sor"
    id = Column(Integer, primary_key=True)
    abreviacao = Column(String(100), unique=True, nullable=False)
    descricao = Column(String(255), nullable=False)
    lifecycle = Column(String(50))

# TABELA ATIVO
class Ativo(Base):
    __tablename__ = "ativo"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    descricao = Column(Text)

    tipo_id = Column(Integer, ForeignKey("tipo_ativo.id"), nullable=False)
    ambiente_id = Column(Integer, ForeignKey("ambiente.id"))
    status_id = Column(Integer, ForeignKey("status_ativo.id"))
    criticidade_id = Column(Integer, ForeignKey("criticidade.id"))
    sor_id = Column(Integer, ForeignKey("sor.id"))

    responsavel = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamentos
    ambiente = relationship("Ambiente")
    criticidade = relationship("Criticidade")
    tipo = relationship("TipoAtivo")
    status = relationship("StatusAtivo")
    sor = relationship("SistemaOperacional")

# TABELA SERVICE ACCOUNT
class ServiceAccount(Base):
    __tablename__ = "service_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)