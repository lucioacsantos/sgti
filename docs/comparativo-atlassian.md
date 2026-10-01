# Análise: SGTI CMDB (LUMEN) × Stack Atlassian

**Data:** 29/09/2026
**Escopo:** funcionalidades versionadas em `main` + bloco não commitado (working tree) vs. produtos Atlassian relevantes.

**Produtos de referência Atlassian:** Jira Service Management (JSM) **Assets/Insight** (CMDB) + **Compass** (catálogo de serviços) + **Opsgenie** (alertas) + **Rovo** (IA) + **Guard** (identidade) + **Confluence** (conhecimento).

---

## 1. Funcionalidades implementadas

### 1.1 Versionadas (branch `main` — 87 testes passando)

| Módulo | Conteúdo |
|---|---|
| **Núcleo CMDB** | Ativos (tipo, ambiente, status, criticidade, SO+lifecycle), múltiplos IPs com flag primário, upsert idempotente `ON CONFLICT` |
| **Mapa de TI** | Clusters, Namespaces, Serviços, Serviços de Negócio, Instâncias de Aplicação, Relacionamentos tipados (8 tipos) |
| **Aplicações + Dados de referência** | CRUD admin completo |
| **Segurança** | AD/LDAP (duplo) → JWT access+refresh, 2FA TOTP opcional cifrado (AES-256-GCM), service tokens (bcrypt, expiração), `crypto_lock` em Cython, rate limit, correlation IDs |
| **Auditoria** | Log de todas as mutações (antes/depois), filtrável |
| **Integrações/IA** | Webhook Zabbix com enriquecimento Ollama, RAG sobre base de conhecimento (`/ollama/knowledge/`), análise de alarmes |
| **Frontend Vue 3** | Dashboard, Ativos, Infra (8 abas), Auditoria, Integrações, Assistente IA, Admin; exportação XLSX |
| **Pipeline** | `seed.py`, `import_test_data.py` (dump pgAdmin), `infer_infra_map.py` (lexical/regex) |

### 1.2 Não commitadas (working tree — "bloco LUMEN")

| Item | Escopo |
|---|---|
| **Módulo Reconciliação** ⭐ | 3 tabelas novas (`reconciliacao`, `item_reconciliacao`, `parecer_reconciliacao`), router `backend/routers/reconciliacoes.py` (412 linhas), migration `a1f2c3d4e5f6` (coluna `confianca`), teste dedicado (260 linhas) |
| **Detecção automática D1–D7** | Ativo sem IP/ambiente, app sem instância, instância sem ativo, cluster sem ativo, FK órfã |
| **Four-eyes real (no backend)** | ≥2 analistas distintos, criador não retifica sozinho, decisor precisa ter dado parecer, admin-only na decisão/conclusão — 409/403 no schema, não na UI |
| **Painel Reconciliações** | `ReconciliacoesView.vue` (705 linhas): contagens, filtro, parecer, decisão, badge de confiança |
| **Inferência IA integrada** | `scripts/infer_infra_map_ia.py`; `POST /reconciliacoes/inferencia`: confiança <0,9 → item pendente; ≥0,9 → auto-ratificado com trilha |
| **Anti-tamper** | Validação base64 canônico no decrypt do `crypto_lock.pyx` |
| **Reorganização** | Scripts movidos para `scripts/`, `LUMEN.md` (pitch + storyboard) |

---

## 2. Comparativo com Atlassian

| Capacidade | SGTI (main) | SGTI (pendente) | Atlassian | Diferença |
|---|---|---|---|---|
| **CMDB / ativos** | ✅ upsert idempotente | — | ✅ JSM Assets, schemas flexíveis | Atlassian tem schemas dinâmicos por objeto; SGTI é schema fixo, mas com invariantes fortes (IP primário único no banco) |
| **Grafo de relacionamentos** | ✅ tipado, CRUD | — | ✅ Insight graph + Compass dependencies | **Compass é mais rico em visualização** (service graph, scorecards, health); SGTI não tem viewer gráfico nem análise de impacto/transitiva (`what-if` do LUMEN.md ainda não existe em código) |
| **Descoberta (discovery)** | ⚠️ via scripts de import | ✅ IA local | ✅ Atlassian Discovery (agents, nuvem) | SGTI descobre por inferência lexical+LLM sobre dados existentes; sem varredura de rede/agentes |
| **Reconciliação** | — | ✅ D1–D7 + four-eyes + confiança IA | ⚠️ Insight reconcilia atributos por regra simples | **Forte diferencial**: Atlassian reconcilia campo a campo sem workflow; SGTI impõe **4-olhos no backend** com separação de responsabilidades — o equivalente Atlassian seria Jira approvals, que existe mas fora do CMDB |
| **IA** | ⚠️ RAG (Ollama) + análise de alarmes | ✅ inferência com self-reported confidence | ✅ Rovo (nuvem, assistente, agentes) | **SGTI roda 100% on-premise (Ollama)** — dado sensível não sai; Rovo é SaaS. Calibração por limiar (0,9 → humano) não tem análogo direto |
| **Auditoria** | ✅ antes/depois, filtrável | ✅ inclui decisões de IA | ✅ Assets audit log | Paridade; SGTI adiciona rastreabilidade de decisão de máquina (`ratificado por inferencia_ia`) |
| **Autenticação** | ✅ AD/LDAP + 2FA TOTP próprio | — | ✅ Guard (SSO/2FA centralizado) | Atlassian terceiriza 2FA ao Guard; SGTI embute (mais controle, mais manutenção) |
| **Criptografia de colunas / lock** | ✅ AES-256-GCM, crypto_lock | ✅ anti-malleability | ⚠️ CSEK no cloud, nada "lock out" | **Inexistente na Atlassian**: bloqueio de boot por credencial do proprietário (nome+CPF) é modelo próprio |
| **Alertas/monitoramento** | ⚠️ webhook Zabbix → enriquecimento IA | ⚠️ fonte `zabbix` prevista, não integrada | ✅ Opsgenie maduro (on-call, escalonamento, dedupe) | Opsgenie está à frente: falta on-call, dedupe, regras de roteamento |
| **Change/impacto (ITSM)** | ❌ | ❌ | ✅ JSM change management com risk assessment via Insight | Brecha maior: SGTI não tem workflow de mudança/aprovação de mudanças |
| **Docs/conhecimento** | ⚠️ RAG de manuais indexados | — | ✅ Confluence (completo) | SGTI indexa, não oferece autoria/colaboração |

---

## 3. Onde SGTI está à frente da Atlassian

1. **Reconciliação com governança four-eyes algorítmica** — Insight/Assets não tem nada equivalente; a força é a regra viver no backend, não na UI.
2. **IA local com confiança calibrada** abrindo tarefas humanas automaticamente — Rovo é assistente, não pipeline de descoberta auditável com limiar.
3. **Crypto-lock** — nenhum produto Atlassian trava a operação até desbloqueio credenciado.

---

## 4. Gaps vs Atlassian (prioridade de roadmap)

- Sem visualização gráfica do mapa/grafo (maior lacuna percebida pelo usuário final — é o produto central da Compass).
- Sem análise de impacto transitiva ("o que derruba se este ativo cair") — a dependência existe nos dados, mas não há endpoint nem tela.
- Sem workflow de mudança (JSM change) nem catálogo de serviços com health/scorecards (Compass).
- Fonte Zabbix ainda não abre reconciliações automaticamente (prevista no schema, item 4 do relatório).
- Decisão "retificado" não corrige o dado no CMDB (fase 2 planejada).

---

## 5. Resumo

Em **núcleo CMDB + auditoria + segurança**, paridade ou vantagem própria; em **reconciliação/governança assistida por IA**, SGTI supera a Atlassian; em **descoberta ativa, visualização, ITSM (change/on-call) e ecossistema**, a Atlassian está maduramente à frente — e é aí que os próximos passos (integração Zabbix→reconciliação, correção automática na decisão "retificar", grafo visual de impacto) fechariam o ciclo que o `LUMEN.md` vende conceitualmente mas o código ainda não entrega.