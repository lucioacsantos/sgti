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
    areas_id: Optional[int] = None

class AtivoCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None
    area_id: Optional[int] = None
    ambiente_id: Optional[int] = None
    tipo_id: Optional[int] = None
    status_id: Optional[int] = None
    criticidade_id: Optional[int] = None
    sor_id: Optional[int] = None

    class Config:
        from_attributes = True

class AtivoUpdate(BaseModel):
    """Todos os campos são opcionais — somente os enviados serão atualizados."""
    nome: Optional[str] = None
    descricao: Optional[str] = None
    area_id: Optional[int] = None
    ambiente_id: Optional[int] = None
    tipo_id: Optional[int] = None
    status_id: Optional[int] = None
    criticidade_id: Optional[int] = None
    sor_id: Optional[int] = None

    class Config:
        from_attributes = True

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

class SistemaOperacionalCreate(BaseModel):
    abreviacao: str
    descricao: str
    lifecycle: Optional[str] = None

class AplicacaoBase(BaseModel):
    sistema: str
    descricao: Optional[str] = None
    objetivo: Optional[str] = None
    linguagens: Optional[str] = None
    bancos_dados: Optional[str] = None
    area_tecnologia: Optional[str] = None
    area_negocio: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class AplicacaoCreate(AplicacaoBase):
    pass

class AplicacaoResponse(AplicacaoBase):
    pass

class AreasResponse(BaseModel):
    id: int
    nome: str
    sigla: str

    class Config:
        from_attributes = True

class OllamaRequest(BaseModel):
    question: str
    model: Optional[str] = None

class OllamaResponse(BaseModel):
    response: str

class ZabbixOllamaObservationRequest(BaseModel):
    event_id: str
    question: str
    model: Optional[str] = None

class ZabbixOllamaObservationResponse(BaseModel):
    event_id: str
    problem_name: Optional[str] = None
    ollama_response: str
    zabbix_result: dict
