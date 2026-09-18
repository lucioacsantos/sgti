# Funcionalidades do sistema

## Módulos

### 1. Ativos (CMDB core)

O núcleo do CMDB. Cada **ativo** representa um host físico ou virtual, com:

- **Identificação**: nome (único), descrição
- **Classificação**: tipo (Servidor Físico/Virtual, Container, Equipamento de Rede, Estação de Trabalho), ambiente (Produção/Homologação/Desenvolvimento/Teste), status (Ativo/Inativo/Em Manutenção/Desativado), criticidade (Baixa→Crítica)
- **Contexto**: sistema operacional (com lifecycle), área responsável
- **Rede**: múltiplos endereços IP (IPv4/IPv6) por ativo, com tipo, interface, descrição e flag de IP **primário** (apenas um por ativo; o sistema desmarca os demais automaticamente)

Criação/atualização por automações usa **upsert idempotente**: ativo por `nome`, IP por par `ativo_id+ip` (PostgreSQL `ON CONFLICT` atômico). Toda operação automática grava audit log distinguindo CREATE de UPDATE.

### 2. Aplicações

Catálogo de sistemas de negócio: nome, descrição, objetivo, linguagens, bancos de dados, área de tecnologia e área de negócio. É o ponto de partida para a inferência de instâncias (ver [inferencias.md](inferencias.md)).

### 3. Infraestrutura & Mapa de TI

Entidades que ligam ativos a aplicações, formando o mapa:

| Entidade | O que representa | Campos chave |
|---|---|---|
| **Cluster** | Agrupamento físico/lógico (ex.: vSphere) | nome, descrição, ativo associado (único) |
| **Namespace** | Partição lógica dentro de um cluster | nome, cluster_id, ativo (único) |
| **Serviço** | Componente técnico: processo/daemon em um host (ex.: Cassandra, LDAP, NiFi) | nome, tipo (database/integration/erp...), ativo (único) |
| **Serviço de Negócio** | Capability percebida pelo usuário final (ex.: "Portal de Medição") — agnóstica de infraestrutura | nome, descrição, ativo (opcional) |
| **Instância de Aplicação** | Uma aplicação executando em um host | aplicacao_id, ativo (único), porta, path, comando |
| **Relacionamento** | Conexão tipada entre dois ativos | origem, destino, tipo, descrição |

**Serviço vs Serviço de Negócio**: o serviço é o "como/onde" (tecnologia rodando num host, alimentado por descoberta); o serviço de negócio é o "para quê" (o que o usuário consome, topo da cadeia para análise de impacto). A ligação entre os mundos acontece por relacionamentos e instâncias de aplicação.

**Tipos de relacionamento** pré-instalados: *Depende de*, *Contém*, *Conecta-se a*, *Executa*, *Hospeda*, *Replica para*, *Integra com*, *Backup de*.

### 4. Dados de referência

Tabelas de apoio mantidas por admin via tela de Dados de Referência: tipos de ativo, ambientes, status, criticidades, sistemas operacionais, áreas e tipos de relacionamento. CRUD completo sob `/admin/*`.

### 5. Auditoria

`GET /audit-logs/` — registro paginado de todas as mutações, com entidade, entidade_id, ação (CREATE/UPDATE/DELETE), estado anterior/posterior, usuário e timestamp. Filtrável por entidade e id. Correlation ID acompanha cada request para rastreamento.

### 6. Autenticação e segurança

- **Usuários**: login AD/LDAP → JWT access+refresh, com **2FA TOTP opcional** (ver [autenticacao-2fa.md](autenticacao-2fa.md))
- **Automações**: `X-Service-Token` (bcrypt no banco, expiração por conta)
- **2FA por usuário**: segredo cifrado (AES-256-GCM) no banco; admin pode zerar o 2FA de outro usuário para suporte
- **crypto_lock**: colunas sensíveis cifradas; sistema bloqueado até desbloqueio no boot
- **Rate limiting** (100 req/min), CORS, security headers, correlation IDs

### 7. Integrações

- **Zabbix**: webhook de alarmes (`/integrations/zabbix/alarm`) com enriquecimento via Ollama
- **Ollama (IA)**: perguntas à base de conhecimento com RAG (`/ollama/knowledge/perguntar`) — responde com trechos citados de manuais indexados

## Modelo de autenticação da API

`get_current_actor` aceita, em ordem:

1. `Authorization: Bearer <JWT>` — usuário AD (fluxo do frontend)
2. `X-Service-Token: <token>` — automações/scripts (hash bcrypt na tabela `service_accounts`)

Isso permite o modelo operacional central: **automação grava, painel lê/corrige**.

## Scripts de suporte

| Script | Função |
|---|---|
| `backend/seed.py` | Popula dados mestre + ativos de exemplo + service account |
| `backend/import_test_data.py` | Importa dump pgAdmin de ativos/aplicações (idempotente) |
| `backend/infer_infra_map.py` | Gera serviços, instâncias e relacionamentos por inferência, via API |

Ver [inferencias.md](inferencias.md) para o funcionamento detalhado.