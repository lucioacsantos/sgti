from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional, List
from datetime import datetime
import ipaddress


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
    areas_id: Optional[int] = None
    ambiente_id: Optional[int] = None
    tipo_id: Optional[int] = None
    status_id: Optional[int] = None
    criticidade_id: Optional[int] = None
    sor_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class AtivoUpdate(BaseModel):
    """Todos os campos são opcionais — somente os enviados serão atualizados."""
    nome: Optional[str] = None
    descricao: Optional[str] = None
    areas_id: Optional[int] = None
    ambiente_id: Optional[int] = None
    tipo_id: Optional[int] = None
    status_id: Optional[int] = None
    criticidade_id: Optional[int] = None
    sor_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class AtivoResponse(AtivoBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EnderecoIpBase(BaseModel):
    ativo_id: int
    ip: str
    tipo: Optional[str] = "IPv4"
    interface: Optional[str] = None
    descricao: Optional[str] = None
    primario: Optional[bool] = False
    ativo: Optional[bool] = True

    @field_validator("ip")
    @classmethod
    def validar_ip(cls, v):
        try:
            ipaddress.ip_interface(v)  # aceita IP puro ou com máscara (CIDR)
        except ValueError:
            raise ValueError(f"'{v}' não é um endereço IP/CIDR válido")
        return v

class EnderecoIpUpsert(BaseModel):
    """Usado no upsert: identifica pelo par (ativo_id, ip)."""
    ativo_id: int
    ip: str
    tipo: Optional[str] = "IPv4"
    interface: Optional[str] = None
    descricao: Optional[str] = None
    primario: Optional[bool] = False
    ativo: Optional[bool] = True

    @field_validator("ip")
    @classmethod
    def validar_ip(cls, v):
        try:
            ipaddress.ip_interface(v)
        except ValueError:
            raise ValueError(f"'{v}' não é um endereço IP/CIDR válido")
        return v

    model_config = ConfigDict(from_attributes=True)

class EnderecoIpResponse(BaseModel):
    id: int
    ativo_id: int
    ip: str
    tipo: Optional[str] = None
    interface: Optional[str] = None
    descricao: Optional[str] = None
    primario: bool
    ativo: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TipoAtivoResponse(BaseModel):
    id: int
    nome: str

    model_config = ConfigDict(from_attributes=True)

class TipoAtivoCreate(BaseModel):
    nome: str

class AmbienteResponse(BaseModel):
    id: int
    nome: str

    model_config = ConfigDict(from_attributes=True)

class AmbienteCreate(BaseModel):
    nome: str

class StatusAtivoResponse(BaseModel):
    id: int
    nome: str

    model_config = ConfigDict(from_attributes=True)

class StatusAtivoCreate(BaseModel):
    nome: str

class CriticidadeResponse(BaseModel):
    id: int
    nivel: str

    model_config = ConfigDict(from_attributes=True)

class CriticidadeCreate(BaseModel):
    nivel: str

class SistemaOperacionalResponse(BaseModel):
    id: int
    abreviacao: str
    descricao: str
    lifecycle: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

class AplicacaoCreate(AplicacaoBase):
    pass

class AplicacaoResponse(AplicacaoBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class AreasResponse(BaseModel):
    id: int
    nome: str
    sigla: str

    model_config = ConfigDict(from_attributes=True)

class AreasCreate(BaseModel):
    nome: str
    sigla: str

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


# ---- Base de conhecimento (RAG: nomic-embed-text + llama3.2) ----

class KnowledgeIndexRequest(BaseModel):
    """Solicita (re)indexação de um diretório de Markdown."""
    diretorio: Optional[str] = None
    recriar: bool = False

class TrechoCitado(BaseModel):
    documento: str
    arquivo: str
    titulo_secao: Optional[str] = None
    score: float
    conteudo: str

class KnowledgeIndexResponse(BaseModel):
    arquivos_encontrados: int
    documentos_indexados: int
    trechos_indexados: int
    documentos_removidos: int
    duracao_segundos: float

class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 5

class KnowledgeSearchResponse(BaseModel):
    query: str
    resultados: list[TrechoCitado]

class KnowledgeAskRequest(BaseModel):
    pergunta: str
    top_k: int = 5
    chat_model: Optional[str] = None
    embed_model: Optional[str] = None

class KnowledgeAskResponse(BaseModel):
    pergunta: str
    resposta: str
    trechos: list[TrechoCitado]

class AlarmAnalysisRequest(BaseModel):
    """Payload do webhook do Zabbix para análise de alarme via RAG + CMDB."""
    event_id: str
    host: str
    problema: str
    severidade: Optional[str] = None
    mensagem: Optional[str] = None
    top_k: int = 5

class AlarmAnalysisResponse(BaseModel):
    event_id: str
    host: str
    problema: str
    analise: str
    trechos: list[TrechoCitado]
    contexto_cmdb: dict


class TipoRelacionamentoBase(BaseModel):
    nome: str
    descricao: Optional[str] = None


class TipoRelacionamentoCreate(TipoRelacionamentoBase):
    pass


class TipoRelacionamentoResponse(TipoRelacionamentoBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ClusterBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    ativo_id: Optional[int] = None


class ClusterCreate(ClusterBase):
    pass


class ClusterResponse(ClusterBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class NamespaceBase(BaseModel):
    nome: str
    cluster_id: Optional[int] = None
    ativo_id: Optional[int] = None


class NamespaceCreate(NamespaceBase):
    pass


class NamespaceResponse(NamespaceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class RelacionamentoBase(BaseModel):
    origem_id: int
    destino_id: int
    tipo_id: int
    descricao: Optional[str] = None


class RelacionamentoCreate(RelacionamentoBase):
    pass


class RelacionamentoResponse(RelacionamentoBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServicoBase(BaseModel):
    nome: str
    tipo: Optional[str] = None
    host_id: Optional[int] = None
    ativo_id: Optional[int] = None


class ServicoCreate(ServicoBase):
    pass


class ServicoResponse(ServicoBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ServicoNegocioBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    ativo_id: Optional[int] = None


class ServicoNegocioCreate(ServicoNegocioBase):
    pass


class ServicoNegocioResponse(ServicoNegocioBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class InstanciaAplicacaoBase(BaseModel):
    aplicacao_id: int
    ativo_id: Optional[int] = None
    porta: Optional[int] = None
    path_execucao: Optional[str] = None
    comando_execucao: Optional[str] = None


class InstanciaAplicacaoCreate(InstanciaAplicacaoBase):
    pass


class InstanciaAplicacaoResponse(InstanciaAplicacaoBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    id: int
    entidade: str
    entidade_id: Optional[int] = None
    acao: Optional[str] = None
    antes: Optional[dict] = None
    depois: Optional[dict] = None
    usuario: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== RECONCILIAÇÃO =====

class ParecerReconciliacaoCreate(BaseModel):
    parecer: str  # retificar | ratificar | ignorar | inconcluso
    comentario: Optional[str] = None

    @field_validator("parecer")
    @classmethod
    def validar_parecer(cls, v: str) -> str:
        permitidos = {"retificar", "ratificar", "ignorar", "inconcluso"}
        if v not in permitidos:
            raise ValueError(f"parecer deve ser um de: {', '.join(sorted(permitidos))}")
        return v


class ParecerReconciliacaoResponse(BaseModel):
    id: int
    analista: str
    parecer: str
    comentario: Optional[str] = None
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemReconciliacaoResponse(BaseModel):
    id: int
    reconciliacao_id: int
    entidade: str
    entidade_id: Optional[int] = None
    campo: Optional[str] = None
    valor_cmdb: Optional[str] = None
    valor_fonte: Optional[str] = None
    detalhe: Optional[str] = None
    confianca: Optional[float] = None
    status: str
    resolvido_por: Optional[str] = None
    resolvido_em: Optional[datetime] = None
    pareceres: List[ParecerReconciliacaoResponse] = []
    analistas: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class ReconciliacaoCreate(BaseModel):
    nome: str
    fonte: str

    @field_validator("fonte")
    @classmethod
    def validar_fonte(cls, v: str) -> str:
        permitidos = {"dump_pgadmin", "zabbix", "manual", "ia"}
        if v not in permitidos:
            raise ValueError(f"fonte deve ser uma de: {', '.join(sorted(permitidos))}")
        return v


class ReconciliacaoResponse(BaseModel):
    id: int
    nome: str
    fonte: str
    status: str
    criado_por: Optional[str] = None
    criado_em: datetime
    concluida_em: Optional[datetime] = None
    total_itens: int = 0
    pendentes: int = 0
    retificados: int = 0
    ratificados: int = 0
    ignorados: int = 0

    model_config = ConfigDict(from_attributes=True)


class ItemDecisaoRequest(BaseModel):
    """Decisão final sobre o item após verificação manual (2+ analistas)."""
    decisao: str  # retificado | ratificado | ignorado

    @field_validator("decisao")
    @classmethod
    def validar_decisao(cls, v: str) -> str:
        permitidos = {"retificado", "ratificado", "ignorado"}
        if v not in permitidos:
            raise ValueError(f"decisao deve ser uma de: {', '.join(sorted(permitidos))}")
        return v


# ===== INFERÊNCIA IA → RECONCILIAÇÃO =====

class ItemInferenciaIA(BaseModel):
    """Ação proposta pela inferência por IA (serviço, instância,
    relacionamento etc.) com a confiabilidade reportada pelo modelo."""
    acao: str  # criar_servico | criar_instancia | criar_relacionamento | ...
    entidade: str  # ativo|aplicacao|servico|instancias_aplicacao|relacionamento|...
    entidade_id: Optional[int] = None
    campo: Optional[str] = None
    valor_proposto: Optional[str] = None
    valor_cmdb: Optional[str] = None
    confianca: float

    @field_validator("confianca")
    @classmethod
    def validar_confianca(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confianca deve estar entre 0.0 e 1.0")
        return v


class ReconciliacaoInferenciaIA(BaseModel):
    """Payload do script de inferência IA: lote de ações inferidas para
    auditoria. Ações com confianca < limiar (padrão 0.9) geram itens
    pendentes de verificação manual (4-olhos); as demais apenas ficam
    registradas como ratificadas automaticamente."""
    nome: Optional[str] = None
    itens: List[ItemInferenciaIA]
    limiar: float = 0.9

    @field_validator("limiar")
    @classmethod
    def validar_limiar(cls, v: float) -> float:
        if not 0.0 < v <= 1.0:
            raise ValueError("limiar deve estar entre 0.0 (exclusivo) e 1.0")
        return v


class ReconciliacaoInferenciaIAResponse(BaseModel):
    """Resultado da abertura de reconciliação a partir de inferência IA."""
    reconciliacao: ReconciliacaoResponse
    limiar: float
    recebidos: int
    pendentes_abertos: int
    auto_ratificados: int
