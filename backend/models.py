from sqlalchemy import Column, Integer, String, Text, ForeignKey, Table
from sqlalchemy.orm import relationship
from database import Base

asset_relationships = Table(
    'asset_relationships',
    Base.metadata,
    Column('source_asset_id', Integer, ForeignKey('assets.id', ondelete='CASCADE'), primary_key=True),
    Column('target_asset_id', Integer, ForeignKey('assets.id', ondelete='CASCADE'), primary_key=True),
    Column('relationship_type', String(100), nullable=False)
)

service_assets = Table(
    "service_assets",
    Base.metadata,
    Column("service_id", ForeignKey("dados_servico.id"), primary_key=True),
    Column("asset_id", ForeignKey("assets.id"), primary_key=True),
)


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    owner = Column(String(100), nullable=True)

    # Serviços associados a este asset
    services = relationship(
        "DadosServico",
        secondary=service_assets,
        back_populates="hosts",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<Asset id={self.id} name='{self.name}'>"

class DadosServico(Base):
    __tablename__ = 'dados_servico'

    id = Column(Integer, primary_key=True, index=True)
    tipo_servico = Column(String(100), nullable=False)
    nome_servico = Column(String(200), nullable=False)
    servico_stop = Column(String(200), nullable=False)
    servico_start = Column(String(100), nullable=False)
    servico_validacao = Column(Text, nullable=True)
    servico_usuario = Column(String(200), nullable=False)

    # Assets associados
    hosts = relationship(
        "Asset",
        secondary=service_assets,
        back_populates="services",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<DadosServico id={self.id} nome='{self.nome_servico}'>"