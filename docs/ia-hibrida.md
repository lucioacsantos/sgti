# Engine de IA híbrida (LLM ↔ Local sem LLM)

O SGTI suporta **dois providers de inferência** selecionáveis para as funcionalidades de IA (RAG sobre a base de conhecimento e análise de alarmes do Zabbix):

| Provider | Embeddings | Geração | Requisitos |
|---|---|---|---|
| `llm` | nomic-embed-text (768 dims, via API HTTP) | LLM llama3.2 (abstrativo) | Servidor LLM compatível com API do Ollama + modelos baixados |
| `local` | sentence-transformers em CPU (384 dims, em-processo) | Determinística: taxonomia regex + extração literal dos manuais | `pip install torch sentence-transformers` — **sem serviço externo** |

O provider é escolhido **por request** (campo `provider` no payload) ou por ambiente (`AI_PROVIDER=local`), o que permite desligar o servidor LLM por completo caso não seja liberado na infraestrutura, sem perder as funcionalidades de IA.

---

## 1. Arquitetura

```
                          ┌──────────────────────────────┐
  request "provider" ───► │  ai_engine.resolve_provider  │
  ou env AI_PROVIDER      └──────────────┬───────────────┘
                                         │
             ┌───────────────────────────┴──────────────────────────┐
             ▼                                                      ▼
        provider "llm"                                    provider "local"
  ┌──────────────────────────┐                        ┌──────────────────────────────┐
  │ llm_client.embed (HTTP)  │                        │ SentenceTransformer.encode   │
  │ llm_client.chat          │                        │ (torch CPU; AVX-512 acelera) │
  │ llm_client.chat_stream   │                        │ + taxonomia de alarmes       │
  └──────────────────────────┘                        │ (regex) + templates          │
                                                      │ + extração do RAG (citação   │
                                                      │ literal, zero alucinação)    │
                                                      └──────────────────────────────┘
```

Módulos envolvidos:

- **`backend/ai_engine.py`** — camada de abstração: resolução de provider, embeddings dos dois engines, taxonomia de alarmes e geração local determinística.
- **`backend/knowledge.py`** — RAG: indexação/busca passam o provider adiante; com `local`, a resposta é extrativa.
- **`backend/routers/integrations.py`** — endpoints aceitam `provider` e roteiam para o engine adequado.
- **`backend/llm_client.py`** — cliente da API de LLM compatível com Ollama (provider `llm`).

## 2. Isolamento dos espaços vetoriais (ponto crítico)

Embeddings de modelos diferentes **não são comparáveis** (dimensões e espaços distintos: nomic-embed-text = 768 dims; MiniLM multilingual = 384 dims).

Por isso cada documento registra a assinatura do provider usado na indexação na coluna **`documento.embed_provider`** (migrations `b3e4f5a6c7d8` e `c4d5e6f7a8b9`):

```
"llm:nomic-embed-text"
"local:paraphrase-multilingual-MiniLM-L12-v2"
```

A busca semântica (`knowledge.search`) **filtra trechos pela mesma assinatura** do provider da consulta. Consequências práticas:

- Trocou o provider? **Reindexe** a base de conhecimento para o novo provider (`POST /ia/knowledge/indexar` com `provider`).
- Bases indexadas em providers diferentes **coexistem** no banco sem conflito.
- Documentos já indexados com a assinatura antiga são normalizados pela migration `c4d5e6f7a8b9` (`ollama:*` → `llm:*`).

## 3. Endpoints (campo `provider` opcional em todos)

| Endpoint | Uso do provider |
|---|---|
| `POST /ia/knowledge/indexar` | indexa/reindexa o diretório Markdown com o provider escolhido (grava `embed_provider`) |
| `POST /ia/knowledge/buscar` | busca semântica apenas entre trechos do mesmo provider |
| `POST /ia/knowledge/perguntar` | RAG: llm → LLM abstrativo; local → extração literal |
| `POST /ia/knowledge/perguntar/stream` | idem, NDJSON; com local, o texto é fatiado em chunks |
| `POST /ia/alarmes/analisar` | análise do alarme Zabbix (CMDB + RAG + geração) |
| `POST /zabbix/alarmes/observacao-ia/` | observação registrada no próprio alarme (Zabbix RPC) |
| `POST /ia/` | geração livre: llm → LLM; local → classificação na taxonomia |
| `GET /ia/modelos/` | lista modelos do servidor LLM **e** o status do engine local (o servidor LLM pode estar fora) |

> Novos endpoints usam o prefixo genérico `/ia/`. Os prefixos antigos `/ollama/*` continuam respondendo como **aliases deprecated** — o provider é escolhido no payload, não na URL. Payloads com `"provider": "ollama"` continuam aceitos, normalizados para `llm`.

## 4. Provider "local" — como funciona a geração

Sem LLM não há paraphrase. A engine local é **determinística e auditável**:

### 4.1 Taxonomia de alarmes (`ai_engine.TAXONOMIA_ALARMES`)

Regex por categoria → diagnóstico padrão + ações recomendadas + equipe de escalonamento:

| Categoria | Gatilhos (exemplos) |
|---|---|
| `disco` | "disk space", "filesystem", "/var", partição |
| `cpu` | "cpu", "load average", processador |
| `memória` | "memory", "swap", OOM |
| `rede` | "interface", "packet", "crc", latência |
| `serviço` | "service down", systemd/unit, "zabbix agent" |
| `certificado` | "ssl/tls", "certificate expires" |
| `banco de dados` | postgres, oracle, mysql, "too many connections" |

Estrutura da análise gerada (idêntica ao contratinho do prompt do LLM — 4 seções):

```
(1) Diagnóstico provável: provável problema de disco: uso/espaço de disco acima do limite...
(2) Impacto e criticidade: ativo: srv01 | ambiente: Produção | criticidade CMDB: Crítica | ...
(3) Ação recomendada: Procedimento documentado [Proc Disco § Limpeza, score 0.82]: <texto do manual>
(4) Escalação: escalar para equipe de infraestrutura responsável pelo SO; ...

Fonte: engine local determinística (sem LLM); ...
```

Prioridades: se o RAG recuperou trecho, este é citado literalmente (com documento e score); sem trecho, entram as ações padrão da categoria. O impacto vem **sempre** do CMDB (ambiente, criticidade, aplicações hospedadas, dependências) — igual no provider llm.

### 4.2 RAG extrativo (`ai_engine.local_rag_answer`)

A resposta cita os melhores trechos entre colchetes `[1] Documento § Seção (score ...)` com o conteúdo **real** dos manuais — sem alucinação possível. Se não houver trecho, o texto indica explicitamente ausência de procedimento e recomenda escalonamento.

## 5. Configuração

```env
# backend/.env
AI_PROVIDER=llm                    # llm | local  (default do sistema)
# Alias legado "ollama" continua aceito no payload (normalizado para llm)

# Provider local
LOCAL_EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2
```

### Instalação do provider local

```bash
# torch CPU primeiro (evita baixar ~2GB de pacotes CUDA/nvidia não usados)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install sentence-transformers
```

- O modelo recomendado (`paraphrase-multilingual-MiniLM-L12-v2`, ~120MB) roda bem só com CPU; AVX-512 dos servidores acelera o torch. Alternativa de maior qualidade: `paraphrase-multilingual-mpnet-base-v2` (768 dims).
- Embeddings são gerados em-processo, **lazy** (carrega no primeiro uso) e thread-safe (singleton com lock).
- Se a lib não estiver instalada, endpoints com `provider: local` respondem **HTTP 503** com instrução — os demais endpoints de IA continuam funcionando.
- Sem env do LLM configurada? O provider local funciona normalmente (não há dependência entre os engines).

## 6. Testes

`backend/tests/test_ai_hybrid.py` cobre: resolução/assinatura de provider, taxonomia, análise local (com e sem CMDB/RAG), RAG extrativo, isolamento entre providers, indexação com provider nos endpoints, streaming local e observação no Zabbix sem LLM. Os testes de integração (`test_ai_integrations.py`) cobrem os endpoints novos e os aliases legados `/ollama/*` — o provider `llm` permanece o default.

## 7. Quando usar cada provider

| Cenário | Recomendação |
|---|---|
| Servidor LLM liberado na infra, GPU disponível | `llm` — análises mais ricas e abstrativas |
| Sem servidor LLM/GPU (ex.: restrição de infra), ou priorizando auditabilidade | `local` — zero dependência externa, respostas reprodutíveis |
| Manuais com procedimentos bem documentados | `local` costuma ser **mais** adequado: o analista quer o texto exato do manual, não um paraphrase |

Os dois engines podem operar em conjunto (bases indexadas em providers diferentes coexistem); o frontend/integração escolhe o provider por request.