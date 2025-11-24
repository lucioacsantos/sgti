from pydantic import BaseModel, Field
from typing import List, Optional

class AssetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Nome do ativo")
    type: str = Field(..., min_length=1, max_length=100, description="Tipo do ativo (VM, Container, Switch, etc)")
    description: Optional[str] = Field(None, description="Descrição detalhada do ativo")
    owner: str = Field(..., min_length=1, max_length=200, description="Proprietário do ativo")

class AssetCreate(AssetBase):
    pass

class AssetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    type: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    owner: Optional[str] = Field(None, min_length=1, max_length=200)

class AssetResponse(AssetBase):
    id: int

    class Config:
        from_attributes = True

class AssetWithRelationships(AssetResponse):
    related_to: List[AssetResponse] = []

class RelationshipCreate(BaseModel):
    source_asset_id: int = Field(..., description="ID do ativo de origem")
    target_asset_id: int = Field(..., description="ID do ativo de destino")
    relationship_type: str = Field(..., min_length=1, max_length=100, description="Tipo de relacionamento (hospeda, depende, conecta, etc)")

class RelationshipResponse(BaseModel):
    source_asset_id: int
    target_asset_id: int
    relationship_type: str
    source_asset: AssetResponse
    target_asset: AssetResponse

class AssetBasic(BaseModel):
    id: int
    name: str
    type: str

    class Config:
        orm_mode = True

class ServiceCreate(BaseModel):
    tipo_servico: str
    nome_servico: str
    servico_stop: str
    servico_start: str
    servico_validacao: Optional[str] = None
    servico_usuario: str
    host_ids: List[int] = []


class ServiceResponse(BaseModel):
    id: int
    tipo_servico: str
    nome_servico: str
    servico_stop: str
    servico_start: str
    servico_validacao: Optional[str]
    servico_usuario: str
    hosts: List[AssetBasic]

    class Config:
        orm_mode = True
