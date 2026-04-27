from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AtivoBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    tipo_id: int
    ambiente_id: Optional[int] = None
    status_id: Optional[int] = None
    criticidade_id: Optional[int] = None
    sor_id: Optional[int] = None
    responsavel: Optional[str] = None

class AtivoCreate(AtivoBase):
    pass

class AtivoResponse(AtivoBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class TipoAtivoResponse(BaseModel):
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

class SistemaOperacionalResponse(BaseModel):
    id: int
    abreviacao: str
    descricao: str
    lifecycle: Optional[str] = None

    class Config:
        from_attributes = True