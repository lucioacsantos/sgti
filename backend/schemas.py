from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ServiceAccountCreate(BaseModel):
    name: str
    days_valid: int = 30  # Tempo de vida do token em dias

    class Config:
        from_attributes = True

class ServiceAccountResponse(BaseModel):
    id: int
    name: str
    token: str
    expires_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


# DOMÍNIOS
class TipoAtivoBase(BaseModel):
    nome: str
    descricao: Optional[str] = None

class TipoAtivoResponse(TipoAtivoBase):
    id: int

    class Config:
        from_attributes = True

class TipoRelacionamentoResponse(BaseModel):
    id: int
    nome: str

    class Config:
        from_attributes = True

class AmbienteResponse(BaseModel):
    id: int
    nome: str

    class Config:
        from_attributes = True

class StatusAtivoResponse(BaseModel):
    id: int
    nome: str

    class Config:
        from_attributes = True

class CriticidadeResponse(BaseModel):
    id: int
    nivel: str

    class Config:
        from_attributes = True

# ATIVO (CMDB CORE)
class AssetBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=255)
    descricao: Optional[str] = None
    responsavel: Optional[str] = None

    tipo_id: int
    ambiente_id: Optional[int] = None
    status_id: Optional[int] = None
    criticidade_id: Optional[int] = None

class AssetCreate(AssetBase):
    pass

class AssetUpdate(BaseModel):
    nome: Optional[str]
    descricao: Optional[str]
    responsavel: Optional[str]

    tipo_id: Optional[int]
    ambiente_id: Optional[int]
    status_id: Optional[int]
    criticidade_id: Optional[int]

class AssetResponse(BaseModel):
    id: int
    nome: str
    descricao: Optional[str]
    responsavel: Optional[str]

    tipo: Optional[TipoAtivoResponse]
    ambiente: Optional[AmbienteResponse]
    status: Optional[StatusAtivoResponse]
    criticidade: Optional[CriticidadeResponse]

    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# versão leve (para evitar payload gigante em grafos)
class AssetBasic(BaseModel):
    id: int
    nome: str

    class Config:
        from_attributes = True


# RELACIONAMENTOS (GRAFO)
class RelationshipCreate(BaseModel):
    origem_id: int = Field(..., description="ID do ativo de origem")
    destino_id: int = Field(..., description="ID do ativo de destino")
    tipo_id: int = Field(..., description="Tipo do relacionamento")

class RelationshipResponse(BaseModel):
    id: int

    origem: AssetBasic
    destino: AssetBasic
    tipo: TipoRelacionamentoResponse

    descricao: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# VISÃO DE GRAFO
class AssetWithRelationships(BaseModel):
    ativo: AssetResponse
    relacionamentos: List[RelationshipResponse]


# SERVIÇOS (AGORA SÃO ATIVOS)
class ServiceResponse(BaseModel):
    id: int
    nome: str
    tipo: TipoAtivoResponse

    class Config:
        from_attributes = True


# AUDIT
class AuditResponse(BaseModel):
    id: int
    entidade: str
    entidade_id: int
    acao: str

    antes: Optional[dict]
    depois: Optional[dict]

    usuario: str
    criado_em: datetime

    class Config:
        from_attributes = True


# TOKEN
class TokenResponse(BaseModel):
    token: str
    expira_em: datetime