# Diagramas do Piloto: Descoberta, Inferência IA e Alarmes (Ansible → SGTI CMDB)

**Data:** 26/10/2026
**Escopo:** operação de descoberta do piloto — Ansible Automation Platform (AAP) executando playbooks contra **vCenter ×3**, **Red Hat Satellite** e **OpenShift** — mais a **inferência por IA** (`infer_infra_map_ia.py`) e a **triagem de alarmes do Zabbix com IA** (RAG + contexto CMDB), todos povoados/via API com gravação idempotente.

Todo o tráfego usa **`X-Service-Token`** (conta de automação, hash bcrypt) e cada gravação gera **audit log** (CREATE/UPDATE, antes/depois, correlation ID).

---

## 1. Panorama geral — "Estação Central"

Três linhas de descoberta que convergem na mesma plataforma. O AAP é a estação central: cada fonte tem seu próprio playbook, todos desembarcam nos mesmos endpoints idempotentes da API.

```mermaid
flowchart TB
  classDef fonte fill:#0b1e3a,stroke:#3b82f6,color:#e6f0ff,stroke-width:2px
  classDef aap fill:#7f1d1d,stroke:#ef4444,color:#ffe6e6,stroke-width:2px
  classDef api fill:#14532d,stroke:#22c55e,color:#e9fff3,stroke-width:2px
  classDef cmdb fill:#4c1d95,stroke:#a78bfa,color:#f3e8ff,stroke-width:4px

  subgraph FONTES["🌐 Fontes da verdade"]
    V1["🖥️ vCenter A<br/>VMs · SOs · IPs"]
    V2["🖥️ vCenter B<br/>VMs · SOs · IPs"]
    V3["🖥️ vCenter C<br/>VMs · SOs · IPs"]
    S["🛰️ Red Hat Satellite<br/>hosts gerenciados"]
    O["☸️ OpenShift<br/>clusters · namespaces"]
  end

  subgraph AAP["🚂 Ansible Automation Platform — estação central"]
    P1["📜 Playbook vSphere<br/>inventário completo da VM"]
    P2["📜 Playbook Satellite<br/>inventário de hosts"]
    P3["📜 Playbook OpenShift<br/>malha containers"]
  end

  subgraph API["🚪 API SGTI · autenticação X-Service-Token"]
    E1["PUT /ativos/{nome}<br/>upsert idempotente"]
    E2["POST /enderecos-ip<br/>upsert ON CONFLICT"]
    E3["POST /sistema-operacional/<br/>somente se faltar"]
    E4["POST /clusters · /namespaces/<br/>somente se faltar"]
  end

  BANCO[("🧠 CMDB LUMEN<br/>ativos · IPs · SOs<br/>clusters · namespaces<br/>+ trilha de auditoria")]

  V1 --> P1
  V2 --> P1
  V3 --> P1
  S  --> P2
  O  --> P3

  P1 --> E1
  P1 --> E2
  P1 --> E3
  P2 --> E1
  P3 --> E4

  E1 --> BANCO
  E2 --> BANCO
  E3 --> BANCO
  E4 --> BANCO

  class V1,V2,V3,S,O fonte
  class P1,P2,P3 aap
  class E1,E2,E3,E4 api
  class BANCO cmdb
```

> 🎨 **Leitura:** três "linhas ferroviárias" (vSphere, Satellite, OpenShift) partem das fontes, se encontram na estação AAP e entregam passageiros (dados) em guichês padronizados (endpoints). Ninguém entra no pátio (CMDB) sem passagem válida e registro bilheteira (auditoria).

---

## 2. Playbook vSphere ×3 — "Da lâmina ao inventário"

Uma única execução varre os três vCenters e encadeia três camadas idempotentes: sistema operacional → máquina virtual → IPs.

```mermaid
flowchart TD
  classDef coleta fill:#f0f9ff,stroke:#0284c7,color:#0c4a6e
  classDef decisao fill:#fffbeb,stroke:#f59e0b,color:#7c2d12
  classDef grava fill:#f0fdf4,stroke:#16a34a,color:#14532d
  classDef fim fill:#fdf2f8,stroke:#db2777,color:#831843

  INICIO([⏱️ Agenda AAP dispara o playbook]) --> CONECTA

  subgraph FASE1["Fase 1 — catálogo de SOs"]
    CONECTA["🔌 Conecta aos 3 vCenters<br/>coleta VMs e sistema operacional<br/>(nome + sigla + lifecycle)"]:::coleta
    SO{"🆕 SO já existe<br/>no CMDB?"}:::decisao
    SO_ADD["POST /sistema-operacional/<br/>cria o registro"]:::grava
    SO_OK["Reaproveita o registro<br/>existente"]:::grava
  end

  subgraph FASE2["Fase 2 — máquinas virtuais"]
    VM{"VM já existe<br/>(nome case-insensitive)?"}:::decisao
    VM_CRIA["PUT /ativos/{nome}<br/>→ 201 CREATE + auditoria"]:::grava
    VM_UPDATE["PUT /ativos/{nome}<br/>→ 200 UPDATE + auditoria<br/>(antes/depois)"]:::grava
  end

  subgraph FASE3["Fase 3 — endereços IP"]
    IP["POST /enderecos-ip/<br/>INSERT … ON CONFLICT (ativo_id, ip)<br/>nada duplica"]:::grava
    PRIM{"IP marcado<br/>como primário?"}:::decisao
    DEMOTE["Sistema desmarca os outros<br/>IPs do ativo (1 primário só)"]:::grava
  end

  PROX{"Existem mais<br/>VMs no vCenter?"}:::decisao
  FIM([✅ CMDB espelha a virtualização<br/>playbook segura para rodar sempre]):::fim

  CONECTA --> SO
  SO -- não --> SO_ADD --> VM
  SO -- sim --> SO_OK --> VM
  VM -- não --> VM_CRIA --> IP
  VM -- sim --> VM_UPDATE --> IP
  IP --> PRIM
  PRIM -- sim --> DEMOTE --> PROX
  PRIM -- não --> PROX
  PROX -- sim --> VM
  PROX -- não --> FIM

  class INICIO,FIM fim
```

> 🛡️ **Garantia:** rodar o playbook duas vezes seguidas não muda nada de substantivo nem cria órfãos — é o princípio da **idempotência** que sustenta agendamento de alta frequência.

---

## 3. Playbook Satellite — "Host com seguro anti-duplicidade"

Coleta todos os hosts gerenciados e os acrescenta sem risco de cópia duplicada (a defesa fica no nome case-insensitive do ativo).

```mermaid
flowchart LR
  classDef sat fill:#fff7ed,stroke:#ea580c,color:#7c2d12
  classDef guarda fill:#fef2f2,stroke:#dc2626,color:#7f1d1d,stroke-width:3px
  classDef ok fill:#f0fdf4,stroke:#16a34a,color:#14532d

  SAT[("🛰️ Red Hat Satellite<br/>todos os hosts gerenciados")]:::sat
  LOOP["🔁 Para cada host<br/>coletado"]
  GUARDA{"🛡️ Guarda anti-duplicidade:<br/>já existe ativo com esse nome?<br/>(comparação case-insensitive)"}:::guarda
  NOVO["PUT /ativos/{nome}<br/>→ CRIA o host<br/>auditado como CREATE"]:::ok
  ATUALIZA["PUT /ativos/{nome}<br/>→ ATUALIZA dados do host<br/>auditado como UPDATE"]:::ok
  AUD[("🧾 Audit log<br/>quem/qual automação,<br/>o que mudou, correlation ID")]

  SAT --> LOOP --> GUARDA
  GUARDA -- ausente --> NOVO --> AUD
  GUARDA -- presente --> ATUALIZA --> AUD
  AUD --> PROX{"próximo host?"}
  PROX -- sim --> LOOP
  PROX -- não --> FECHA([✅ hosts do Satellite<br/>sincronizados com o CMDB]):::ok
```

> 🎨 **Leitura:** a guarda anti-duplicidade é um "detector de metais" na porta de entrada: só passa o host inédito; o conhecido é apenas polido (atualizado) — nunca reproduzido.

---

## 4. Playbook OpenShift — "Do cluster ao namespace"

Captura a malha de containers em duas altitudes: o cluster (física/lógica agrupadora) e os namespaces dentro dele.

```mermaid
flowchart TD
  classDef oc fill:#e0f2fe,stroke:#0369a1,color:#082f49
  classDef dec fill:#fffbeb,stroke:#f59e0b,color:#7c2d12
  classDef grava fill:#f0fdf4,stroke:#16a34a,color:#14532d

  OCP[("☸️ OpenShift<br/>cluster_name + lista de namespaces")]:::oc
  CL{"🏛️ Cluster já registrado<br/>no CMDB?"}:::dec
  CL_ADD["POST /clusters/<br/>cria o cluster"]:::grava
  CL_ID["Recupera o id do cluster<br/>existente"]:::grava
  NS{"📦 Namespace já existe<br/>nele?"}:::dec
  NS_ADD["POST /namespaces/<br/>cria namespace com cluster_id"]:::grava
  NS_SKIP["Mantém o namespace<br/>já catalogado"]:::grava
  PROX{"Mais namespaces<br/>no cluster?"}:::dec
  FIM([✅ mapa de containers<br/>atualizado no CMDB]):::grava

  OCP --> CL
  CL -- não --> CL_ADD --> NS
  CL -- sim --> CL_ID --> NS
  NS -- não --> NS_ADD --> PROX
  NS -- sim --> NS_SKIP --> PROX
  PROX -- sim --> NS
  PROX -- não --> FIM

  class FIM grava
```

> 🎨 **Leitura:** o cluster é o "prédio" — criado uma única vez; os namespaces são os "apartamentos" catalogados um a um, sempre amarrados ao prédio via `cluster_id`. Relançar o playbook não constrói prédio nem apartamento duplicado.

---

## 5. Sequência no backend — por que nunca duplica

Detalhe técnico do contrato idempotente entre AAP, API e PostgreSQL (o "trilho" que os playbooks usam).

```mermaid
sequenceDiagram
  autonumber
  participant AAP as 📜 AAP (playbook)
  participant API as 🚪 API SGTI
  participant PG as 🐘 PostgreSQL
  participant AUD as 🧾 Audit log

  rect rgb(240,249,255)
  note over AAP,PG: Upsert do ativo (máquina virtual / host)
  AAP->>API: PUT /ativos/{nome}
  API->>PG: SELECT … WHERE lower(nome) = :nome
  alt nome inédito
    API->>PG: INSERT ativo
    API->>AUD: CREATE (antes vazio / depois completo)
    API-->>AAP: 201 Created
  else nome conhecido
    API->>PG: UPDATE campos alterados
    API->>AUD: UPDATE (antes/depois, correlation ID)
    API-->>AAP: 200 OK
  end
  end

  rect rgb(240,253,244)
  note over AAP,PG: Upsert do endereço IP
  AAP->>API: POST /enderecos-ip/ (ativo_id, ip, primario)
  API->>API: primário? → desmarca demais IPs do ativo
  API->>PG: INSERT … ON CONFLICT (ativo_id, ip) DO UPDATE
  API-->>AAP: 201 (novo) · 200 (atualizado)
  end
```

> 🧩 **Resumo do contrato:** a mesma chamada repetida N vezes produz **no máximo 1 criação** (201 na primeira) e só gera UPDATE quando algo de fato muda — sempre com trilha de auditoria.

---

## 6. O que cada fonte deixa no CMDB

```mermaid
mindmap
  root(("CMDB LUMEN após o piloto"))
    vCenter ×3
      Ativos VM (tipo Servidor Virtual)
      SOs nome+sigla+lifecycle
      IPs múltiplos + 1 primário
    Red Hat Satellite
      Hosts gerenciados
      Atualização idempotente
    OpenShift
      Clusters
      Namespaces cluster_id
    Tudo auditado
      CREATE ou UPDATE
      antes → depois
      correlation ID
```

---

## 7. Contrato por fonte (referência rápida)

| Fonte | O que coleta | Endpoint SGTI | Comportamento idempotente |
|---|---|---|---|
| **vCenter ×3** | SO (nome, sigla, lifecycle) | `POST /sistema-operacional/` | cria apenas quando não existe |
| **vCenter ×3** | Machine virtual | `PUT /ativos/{nome}` | upsert por nome (case-insensitive): 201 CREATE · 200 UPDATE |
| **vCenter ×3** | Endereços IP | `POST /enderecos-ip/` | `ON CONFLICT (ativo_id, ip)` no PostgreSQL; flag primário única |
| **Red Hat Satellite** | Hosts | `PUT /ativos/{nome}` | guarda anti-duplicidade por nome case-insensitive |
| **OpenShift** | Cluster | `POST /clusters/` | consulta antes de criar |
| **OpenShift** | Namespaces | `POST /namespaces/` | consulta antes de criar; sempre ligado ao `cluster_id` |

Autenticação de todas as chamadas: header **`X-Service-Token`**. Toda mutação: **audit log** distinguindo CREATE de UPDATE.

---

# Parte 2 — Descoberta assistida por IA e triagem de alarmes

## 8. Pipelines de inferência — "Estúdio de fotografia de TI"

O script `infer_infra_map_ia.py` funciona como um estúdio fotográfico do mapa de TI: em quatro poses, o LLM local (llama3.2 + nomic-embed-text) retrata serviços, encaixa aplicações, batiza negócios e lê dependências — **cada foto sai com o selo de confiança**. O script lexical (`infer_infra_map.py`, dicionário regex) é o modo "retrato determinístico" — disponível via `--sem-ia` como baseline.

```mermaid
flowchart TD
  classDef etapa fill:#f5f3ff,stroke:#7c3aed,color:#2e1065,stroke-width:2px
  classDef decisao fill:#fffbeb,stroke:#f59e0b,color:#7c2d12
  classDef grava fill:#f0fdf4,stroke:#16a34a,color:#14532d
  classDef humano fill:#fdf2f8,stroke:#db2777,color:#831843

  IN([🚀 Playbook de inferência inicia<br/>usa o inventário já populado no CMDB]) --> L1
  subgraph ESTUDIO["🤖 Estúdio de descoberta — LLM 100% local (sem nuvem, sem custo de token)"]
    L1["📷 Pose 1 — retrata serviços:<br/>para cada ativo, nome + tipo + confiança"]:::etapa
    L2["🧩 Pose 2 — encaixa ativos ↔ aplicações:<br/>match por tokens fortes + confiança"]:::etapa
    L3["🏷️ Pose 3 — batiza serviços de negócio:<br/>grupos por área de negócio + confiança"]:::etapa
    L4["🔗 Pose 4 — lê o texto das aplicações<br/>e extrai dependências citadas + confiança"]:::etapa
  end
  EMPACOTA["📦 Central de auditoria:<br/>cada ação empacotada com o selo<br/>de confiabilidade (0–100%)"]
  GATE{"⚖️ Limiar de confiança<br/>(padrão 90%)"}:::decisao
  PEND["⚠️ confiança < 90%:<br/>item PENDENTE (fonte: ia)"]:::humano
  AUTO["✅ confiança ≥ 90%:<br/>item já RATIFICADO<br/>(resolvido por inferencia_ia)"]:::grava
  ENDPOINT[("POST /reconciliacoes/inferencia<br/>endpoint oficial de auditoria da IA")]
  PAINEL["🧑‍🤝‍🧑 Painel de Reconciliações<br/>badge por item: 🔴 <70% · 🟠 <90% · 🟢 ≥90%"]:::humano
  QUATRO["👀 Workflow de quatro olhos:<br/>2+ analistas registram parecer<br/>(criador não valida sozinho)"]:::humano
  RETIF["🔧 decisão 'retificar':<br/>correção aplicada no CMDB<br/>automaticamente + auditoria"]:::grava
  RATIF["📌 decisão 'ratificar/ignorar':<br/>CMDB mantido, trilha preservada"]:::grava

  IN --> L1 --> L2 --> L3 --> L4
  L4 --> EMPACOTA --> ENDPOINT
  ENDPOINT --> GATE
  GATE -- baixa --> PEND --> PAINEL --> QUATRO
  QUATRO --> RETIF
  QUATRO --> RATIF
  GATE -- suficiente --> AUTO --> PAINEL

  class IN,EMPACOTA grava
```

> 🎨 **Leitura:** o estúdio nunca entrega o álbum sem carimbo de qualidade. Fotos bem-sucedidas (≥ 90%) vão direto para o arquivo oficial (já ratificado, com trilha); as duvidosas voltam para a bancada dos especialistas (four-eyes) — **a IA propõe, os humanos confirmam**.

---

## 9. Sequência do portão de confiabilidade — calibração em ação

```mermaid
sequenceDiagram
  autonumber
  participant SC as 🤖 Script de inferência IA
  participant API as 🚪 API /reconciliacoes/inferencia
  participant PG as 🐘 item_reconciliacao
  participant AN as 👀 Analistas (4 olhos)

  loop cada ação inferida (serviço, instância, relacionamento, dependência)
    SC->>API: POST ação + confiança (0..1)
    alt confiança ≥ 0,9 (limiar)
      API->>PG: status ratificado · resolvido_por=inferencia_ia
      Note over PG: trilha preservada, sem trabalho manual
    else confiança < 0,9
      API->>PG: status pendente · confiança registrada
      AN->>API: parecer 1 (retificar / ratificar / ignorar / inconcluso)
      AN->>API: parecer 2 (analista distinto)
      AN->>API: decisão colegiada
      Note over API,PG: "retificar" → aplica a correção no CMDB automaticamente + auditoria
    end
  end
```

> 🧩 **Resumo:** o portão é o mesmo para human e máquina — baixa confiança vira **tarefa humana com guarda de dois pares**; alta confiança entra com trilha auditável. Nenhuma das vias grava sem passar pelo endpoint.

---

## 10. Triagem de alarmes com IA — "O analista júnior que nunca dorme"

Cada alarme do Zabbix pode ser analisado pela IA **dentro da rede**: a API monta o contexto do host no CMDB, busca procedimentos na base de conhecimento (RAG) e devolve uma análise em **4 seções** (diagnóstico → impacto → ação recomendada → escalonamento), citando os documentos usados.

```mermaid
flowchart LR
  classDef alarme fill:#fef2f2,stroke:#dc2626,color:#7f1d1d,stroke-width:2px
  classDef api fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
  classDef saida fill:#f0fdf4,stroke:#16a34a,color:#14532d

  ALM[("🔔 Alarme Zabbix<br/>event_id · host · problema · severidade")]:::alarme
  EP["POST /ia/alarmes/analisar<br/>(provider opcional)"]:::api
  CTX["🧭 Contexto CMDB montado automaticamente:<br/>ativo + ambiente + criticidade + IPs +<br/>relacionamentos + serviços + aplicações"]:::api
  RAG[("📚 Base de conhecimento (manuais)<br/>busca semântica no provider da consulta")]:::api

  subgraph ENGINES["⚙️ resolve_provider"]
    direction LR
    LLM["🧠 provider llm<br/>llama3.2 abstrativo<br/>em 4 seções + citações [Nome do Doc]"]
    LOC["📐 provider local<br/>sem LLM: taxonomia regex<br/>+ citação literal do manual<br/>(zero alucinação)"]
  end

  ANL["📋 Análise para o analista:<br/>(1) diagnóstico provável<br/>(2) impacto e criticidade (do CMDB)<br/>(3) ação passo a passo (do manual)<br/>(4) quando e para quem escalar"]:::saida

  ALM --> EP --> CTX
  EP --> RAG
  EP --> LLM
  EP --> LOC
  CTX --> LLM
  CTX --> LOC
  RAG --> LLM
  RAG --> LOC
  LLM --> ANL
  LOC --> ANL
```

> 🎨 **Leitura:** dois motores para o mesmo propósito — o LLM redige com fluência quando há servidor liberado; a engine local (determinística) funciona sem LLM algum e **cita o manual ao pé da letra**. O impacto vem **sempre do CMDB**: um alarme em host "Baixa" é tratado de forma diferente de um em host "Crítica" com 5 aplicações hospedadas.

### Variante: a observação vira registro no próprio alarme

```mermaid
sequenceDiagram
  autonumber
  participant AUT as 🧑‍💻 Automação/SO
  participant API as 🚪 POST /zabbix/alarmes/observacao-ia/
  participant ZBX as 🔔 Zabbix (RPC)
  participant IA as 🤖 engine IA (llm | local)

  AUT->>API: event_id (+ provider, question)
  API->>ZBX: get_open_problem(event_id)
  ZBX-->>API: problema aberto (nome, severidade)
  API->>IA: gera observação objetiva
  IA-->>API: análise do alarme
  API->>ZBX: add_event_observation(event_id, análise)
  API-->>AUT: resposta + resultado da escrita no Zabbix
```

> 💡 A IA não só responde: **escreve a análise dentro do alarme no Zabbix** — o analista que abrir o evento encontra a triagem já documentada.

---

## 11. A esteira completa — "Do bip ao mapa corrigido"

Ciclo fechado que liga alarme, IA, reconciliação e a melhoria contínua do próprio mapa:

```mermaid
flowchart TD
  classDef zax fill:#fef2f2,stroke:#dc2626,color:#7f1d1d
  classDef ia fill:#f5f3ff,stroke:#7c3aed,color:#2e1065
  classDef recon fill:#fffbeb,stroke:#f59e0b,color:#7c2d12
  classDef fixo fill:#f0fdf4,stroke:#16a34a,color:#14532d

  1[("🔔 Zabbix dispara alarme")]:::zax
  2["🤖 triagem com IA:<br/>contexto CMDB + procedimentos (RAG)"]:::ia
  3[("📨 webhook /reconciliacoes/zabbix/alarme")]:::zax
  4{"Regras Z1–Z3:<br/>algo diverge do CMDB?"}:::recon
  5["dedupe: item idêntico<br/>aberto não reaparece"]:::recon
  6{"👀 quatro olhos:<br/>2+ analistas decidem"}:::recon
  7["🔧 'retificar':<br/>CMDB corrigido automaticamente<br/>(+ criação de ativo se host inédito)"]:::fixo
  8["📌 'ratificar': Zabbix<br/>estava errado, CMDB mantido"]:::fixo
  9[("🧠 CMDB atualizado + auditoria")]:::fixo
  10["🤖 próxima análise de alarme<br/>enxerga contexto melhor:<br/>impacto e dependências mais precisos"]:::ia

  1 --> 2 --> 3 --> 4
  4 -- sem divergência --> 9
  4 -- divergência --> 5 --> 6
  6 --> 7 --> 9
  6 --> 8 --> 9
  9 --> 10 -. nova detecção, ciclo repete fortalecido .-> 1

  class 1,3 zax
  class 2,10 ia
  class 4,5,6 recon
  class 7,8,9 fixo
```

> 💡 **Resumo executivo:** quanto mais alarmes passam pela esteira, **mais preciso fica o mapa** que a IA usa para triar o próximo alarme — o sistema melhora operando, sem intervenção manual além da decisão especializada.

---

## 12. Contrato das rotas de IA (referência rápida)

| Fonte / consumidor | Operação | Endpoint SGTI | Comportamento |
|---|---|---|---|
| **Script de inferência IA** | reporta ações executadas | `POST /reconciliacoes/inferencia` | fonte `ia`: < limiar → `pendente` (4 olhos) · ≥ limiar → `ratificado` (por `inferencia_ia`) |
| **Zabbix** | webhook de alarme | `POST /reconciliacoes/zabbix/alarme` | regras Z1–Z3 · dedupe de itens abertos · acúmulo em uma execução fonte `zabbix` |
| **Analista/NOC** | triagem de alarme | `POST /ia/alarmes/analisar` | contexto CMDB + RAG · provider `llm` (abstrativo) ou `local` (taxonomia + citação literal) · análise em 4 seções |
| **Automação** | observação no alarme | `POST /zabbix/alarmes/observacao-ia/` | busca o problema na RPC do Zabbix, gera observação e registra no próprio evento |
| **Qualquer um** | pergunta aos manuais | `POST /ia/knowledge/perguntar[/stream]` | RAG com citações; provider por request (`llm` ↔ `local`) |
| **Qualquer um** | indexar/base | `POST /ia/knowledge/indexar` | grava assinatura do provider (`embed_provider`) — bases de providers distintos coexistem |

> ⚖️ **Onde a IA pode e onde não pode:** a IA pode **triar, inferir e propor**; só grava "já ratificado" quando a própria confiança calibrada libera (≥ 90%). Correções de baixa confiança e divergências Z1–Z3 **sempre** passam pelo workflow de quatro olhos — imposto pelo backend, não pela boa vontade.

---

# Parte 3 — Governança da máquina

## 13. Ciclo de vida do item de reconciliação — máquina de estados do four-eyes

O workflow inteiro vive no backend (`reconciliacoes.py`): qualquer tentativa de atalho responde **403/409** antes de tocar no banco. O diagrama embaixo é a máquina de estados real de `item_reconciliacao`:

```mermaid
stateDiagram-v2
  direction LR
  [*] --> pendente: discrepância nasce<br/>(D1–D7 · Z1–Z3 · IA < 90%)
  pendente --> em_verificacao: 1º parecer registrado
  em_verificacao --> em_verificacao: novos pareceres<br/>(1 por analista — repetido vira 409)
  em_verificacao --> retificado: decisão do admin (regra dos quatro olhos)<br/>→ CMDB corrigido automaticamente
  em_verificacao --> ratificado: decisão do admin (regra dos quatro olhos)<br/>→ fonte confirmada errada, CMDB mantido
  em_verificacao --> ignorado: decisão do admin (regra dos quatro olhos)
  retificado --> [*]: auditoria CORRECAO<br/>(antes → depois)
  ratificado --> [*]: trilha preservada
  ignorado --> [*]: trilha preservada

  note right of pendente
    Guardas impostas no backend
    · parecer 'retificar' do criador → 403
    · decisão exige ≥ 2 analistas → 409
    · decisor precisa ter registrado parecer → 403
    · parecer é exclusivo de admin
  end note
```

> 🎨 **Leitura:** o item só sai do trilho pendente/verificação por uma das três portas finais — e todas exigem a mesma chave: **duas pessoas**. Nem o criador da execução consegue abrir a porta "retificado" sozinho.

## 14. Correção automática — o que a decisão "retificar" aplica no CMDB

Cada tipo de discrepância tem sua regra de reparo (`aplicar_correcao_cmdb`). Onde a regra não garante integridade, o sistema **recusa conscientemente** e registra a nota — nada é aplicado às cegas:

```mermaid
flowchart TD
  classDef fixo fill:#f0fdf4,stroke:#16a34a,color:#14532d
  classDef recusa fill:#fef2f2,stroke:#dc2626,color:#7f1d1d
  classDef dec fill:#fffbeb,stroke:#f59e0b,color:#7c2d12

  D{"Decisão colegiada:<br/>'retificar'"}:::dec --> C{"Tipo de discrepância<br/>(entidade / campo)?"}:::dec

  C -- "ativo / host_nao_cadastrado" --> R1["🏗️ cria o ativo novo<br/>(tipo padrão 'Servidor Virtual')"]:::fixo
  C -- "ativo / ambiente·status·criticidade" --> R2["🔁 ajusta o campo de referência<br/>para o valor da fonte"]:::fixo
  C -- "ativo / nome" --> R3["✏️ renomeia o ativo"]:::fixo
  C -- "ativo / endereco_ip" --> R4["🌐 valida o IP e associa ao ativo<br/>(primário automático se for o 1º)"]:::fixo
  C -- "instancia·cluster / ativo_id" --> R5["🔗 vincula registro ↔ ativo<br/>(vínculo único preservado)"]:::fixo
  C -- "sem regra para o caso" --> N0["🚧 correção não aplicável:<br/>nota no detalhe + auditoria"]:::recusa

  R1 --> G1{"nome já existe<br/>no CMDB?"}:::dec
  G1 -- sim --> R1N["❕ recusa e explica"]:::recusa
  G1 -- não --> AUD
  R2 --> G2{"valor existe como<br/>referência válida?"}:::dec
  G2 -- não --> R1N
  G2 -- sim --> AUD
  R3 --> G3{"nome já é<br/>idêntico?"}:::dec
  G3 -- sim --> R1N
  G3 -- não --> AUD
  R4 --> G4{"IP é válido<br/>e ainda não registrado?"}:::dec
  G4 -- não --> R1N
  G4 -- sim --> AUD
  R5 --> G5{"alvo existe e<br/>vínculo único livre?"}:::dec
  G5 -- não --> R1N
  G5 -- sim --> AUD

  AUD[("🧾 audit log ação CORRECAO<br/>antes → depois · analista executor")]:::fixo
```

> 🛡️ **Filosofia:** automação corajosa em aplicar, **humilde em recusar** — cada recusa é explicada no próprio item e auditada. O analista nunca fica sem saber por que a correção não foi aplicada.

## 15. Segurança — do login ao crypto-lock

Autenticação (AD/LDAP com fallback, 2FA TOTP opcional, JWT) e a trava de boot do sistema:

```mermaid
sequenceDiagram
  autonumber
  participant U as 🧑‍💼 Usuário
  participant FE as 🖥️ Frontend Vue
  participant API as 🚪 API /auth
  participant AD as 🏢 AD/LDAP (backend duplo)
  participant PG as 🐘 Banco (2FA cifrado AES-256-GCM)

  U->>FE: matrícula + senha
  FE->>API: POST /auth/ad/login
  API->>AD: bind LDAP (primário → fallback)
  AD-->>API: credenciais válidas
  alt 2FA já habilitado para o usuário
    API->>PG: carrega segredo TOTP (descriptografado na hora)
    API-->>FE: pede código de 6 dígitos
    FE->>API: POST /auth/2fa/login (código)
    API-->>FE: ✅ JWT access + refresh
  else 2FA não habilitado
    API-->>FE: ✅ JWT access + refresh
  end
  FE->>API: todas as chamadas com Bearer JWT
```

```mermaid
flowchart LR
  classDef ok fill:#f0fdf4,stroke:#16a34a,color:#14532d
  classDef pare fill:#fff7ed,stroke:#ea580c,color:#7c2d12

  BOOT([⚡ Boot do backend]) --> VALIDA{"🧰 crypto_lock<br/>(Cython, anti-tamper)<br/>valida a assinatura<br/>do ambiente?"}
  VALIDA -- "assinatura íntegra" --> CRED{"🔑 dono desbloqueia?<br/>(nome + CPF credenciado)"}
  CRED -- sim --> ABERTO["🔓 sistema operacional:<br/>colunas cifradas acessíveis"]:::ok
  CRED -- não --> TRAVADO["🔒 sistema 'soldado':<br/>não opera até desbloqueio"]:::pare
  VALIDA -- "tamper detectado" --> TRAVADO
```

> 🎨 **Leitura:** a senha abre a porta de entrada; o crypto-lock é o **cofre do prédio** — mesmo com a porta aberta, nada circula sem a chave do dono validada por módulo compilado (`.so` Cython) resistente à violação.

## 16. O esqueleto do CMDB — modelo de dados essencial

O "desenho elétrico" do banco que sustenta todos os fluxos acima (relações-chave, simplificado):

```mermaid
erDiagram
  ATIVO ||--o{ ENDERECO_IP : possui
  ATIVO ||--o| SERVICO : "hospeda único"
  ATIVO ||--o| INSTANCIA_APLICACAO : "executa único"
  ATIVO ||--o| CLUSTER : "representado por"
  ATIVO ||--o| NAMESPACE : "representado por"
  ATIVO ||--o{ RELACIONAMENTO : "origem"
  ATIVO ||--o{ RELACIONAMENTO : "destino"
  APLICACAO ||--o{ INSTANCIA_APLICACAO : instala
  CLUSTER ||--o{ NAMESPACE : particiona
  TIPO_RELACIONAMENTO ||--o{ RELACIONAMENTO : tipifica
  RECONCILIACAO ||--o{ ITEM_RECONCILIACAO : agrega
  ITEM_RECONCILIACAO ||--o{ PARECER_RECONCILIACAO : recebe
  ATIVO {
    string nome PK "case-insensitive"
    int tipo_id FK
    int ambiente_id FK
    int status_id FK
    int criticidade_id FK
    int sor_id FK "SO + lifecycle"
  }
  ENDERECO_IP {
    int ativo_id FK
    string ip "único por ativo"
    bool primario "apenas 1 por ativo"
  }
  INSTANCIA_APLICACAO {
    int aplicacao_id FK
    int ativo_id FK "único"
    int porta
  }
  ITEM_RECONCILIACAO {
    int reconciliacao_id FK
    string entidade
    string campo
    string valor_cmdb
    string valor_fonte
    float confianca "IA, quando aplicável"
    string status
  }
  PARECER_RECONCILIACAO {
    int item_id FK
    string analista "1 parecer por analista"
    string parecer
  }
```

> 🧩 **Três invariantes visíveis de cara:** a) nome do ativo é a chave de upsert das automações; b) os vínculos "hospeda/executa/representa" são **único** — a IA e as correções respeitam; c) cada parecer é pessoal e intransferível — é isso que torna o four-eyes matemático.