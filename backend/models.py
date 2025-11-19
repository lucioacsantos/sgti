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

class Asset(Base):
    __tablename__ = 'assets'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    type = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner = Column(String(200), nullable=False)
    
    related_to = relationship(
        'Asset',
        secondary=asset_relationships,
        primaryjoin=id == asset_relationships.c.source_asset_id,
        secondaryjoin=id == asset_relationships.c.target_asset_id,
        backref='related_from',
        lazy='selectin'
    )

    def __repr__(self):
        return f"<Asset(id={self.id}, name='{self.name}', type='{self.type}')>"

class DadosServico(Base):
    __tablename__ = 'dados_servico'

    id = Column(Integer, primary_key=True, index=True)
    servico_stop = Column(String(200), nullable=False)
    servico_start = Column(String(100), nullable=False)
    servico_validacao = Column(Text, nullable=True)
    servico_usuario = Column(String(200), nullable=False)

    def __repr__(self):
        return f"<DadosServico(id={self.id}, servico_stop='{self.servico_stop}', servico_start='{self.servico_start}', servico_validacao='{self.servico_validacao}', servico_usuario='{self.servico_usuario}')>"