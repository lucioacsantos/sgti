# Análise: SGTI CMDB (LUMEN) × Stack Atlassian

**Data:** 21/10/2026
**Escopo:** funcionalidades versionadas em `main` vs. produtos Atlassian relevantes.

**Produtos de referência Atlassian:** Jira Service Management (JSM) **Assets/Insight** (CMDB) + **Compass** (catálogo de serviços) + **Opsgenie** (alertas) + **Rovo** (IA) + **Guard** (identidade) + **Confluence** (conhecimento).

---

## 1. Funcionalidades implementadas (todas versionadas em `main` — 127 testes)

| Módulo | Conteúdo |
|---|---|
| **Núcleo CMDB** | Ativos (tipo, ambiente, status, criticidade, SO+lifecycle), múltiplos IPs com flag primário, upsert idempotente `ON CONFLICT` |
| **Mapa de TI** | Clusters, Namespaces, Serviços, Serviços de Negócio, Instâncias de Aplicação, Relacionamentos tipados (8 tipos) |
| **Aplicações + Dados de referência** | CRUD admin completo |
| **Reconciliação** ⭐ | 3 tabelas (`reconciliacao`, `item_reconciliacao`, `parecer_reconciliacao`), detecção automática D1–D7 (fonte `manual`), **fonte `zabbix` via webhook** (`POST /reconciliacoes/zabbix/alarme`, com dedupe), **correção automática do CMDB na decisão "retificar"**, workflow **four-eyes imposed no backend** (≥2 analistas, criador não retifica sozinho, decisor participante) |
| **Inferência IA integrada** | `scripts/infer_infra_map_ia.py`; `POST /reconciliacoes/inferencia`: confiança <0,9 → item pendente (four-eyes); ≥0,9 → auto-ratificado com trilha; `scripts/infer_infra_map.py` (lexical) como baseline determinístico |
| **Segurança** | AD/LDAP (duplo) → JWT access+refresh, 2FA TOTP opcional cifrado (AES-256-GCM), service tokens (bcrypt, expiração), `crypto_lock` em Cython com validação canônica anti-tamper, rate limit, correlation IDs |
| **Auditoria** | Log de todas as mutações (antes/depois) — incluindo decisões humanas e de máquina (pareceres, decisão e auto-ratificação por inferência) |
| **Integrações/IA** | Webhook de alarmes com enriquecimento por IA, RAG sobre base de conhecimento (`/ia/knowledge/`), análise de alarmes, compatibilidade Zabbix ≥ 7.0 (auth Bearer) |
| **Frontend Vue 3** | Dashboard, Ativos, Infra (8 abas), Reconciliações (workflow completo), Auditoria, Integrações, Assistente IA, Admin; exportação XLSX |
| **Pipeline** | `scripts/seed.py`, `scripts/import_test_data.py` (dump pgAdmin), `scripts/infer_infra_map.py`, `scripts/infer_infra_map_ia.py` (LLM local) |
| **Qualidade** | Suíte de 127 testes (autenticação, crypto, CRUD, infra, reconciliação, IA, LDAP real via Docker opcional); migrações Alembic idempotentes |

---

## 2. Comparativo com Atlassian

| Capacidade | SGTI (main) | Atlassian | Diferença |
|---|---|---|---|
| **CMDB / ativos** | ✅ upsert idempotente | ✅ JSM Assets, schemas flexíveis | Atlassian tem schemas dinâmicos por objeto; SGTI é schema fixo, mas com invariantes fortes (IP primário único no banco) |
| **Grafo de relacionamentos** | ✅ tipado, CRUD | ✅ Insight graph + Compass dependencies | **Compass é mais rico em visualização** (service graph, scorecards, health); SGTI não tem viewer gráfico nem análise de impacto/transitiva (what-if) |
| **Descoberta (discovery)** | ✅ por inferência lexical + IA local sobre dados existentes | ✅ Atlassian Discovery (agents, nuvem) | SGTI descobre via scripts idempotentes + IA com self-reported confidence; sem varredura de rede/agentes |
| **Reconciliação** | ✅ D1–D7 + fonte Zabbix + four-eyes + correção automática | ⚠️ Insight reconcilia atributos por regra simples | **Forte diferencial**: Atlassian reconcilia campo a campo sem workflow; SGTI impõe **4-olhos no backend** e aplica a correção automaticamente após decisão colegiada |
| **IA** | ✅ RAG (LLM local) + análise de alarmes + inferência com confiabilidade calibrada | ✅ Rovo (nuvem, assistente, agentes) | **SGTI roda 100% on-premise (LLM local)** — dado sensível não sai; Rovo é SaaS. Calibração por limiar (0,9 → humano) não tem análogo direto |
| **Auditoria** | ✅ antes/depois, filtrável, inclui decisões de IA e pareceres | ✅ Assets audit log | Paridade; SGTI adiciona rastreabilidade de decisão de máquina (`ratificado por inferencia_ia`) |
| **Autenticação** | ✅ AD/LDAP + 2FA TOTP próprio | ✅ Guard (SSO/2FA centralizado) | Atlassian terceiriza 2FA ao Guard; SGTI embute (mais controle, mais manutenção) |
| **Criptografia de colunas / lock** | ✅ AES-256-GCM + anti-malleability | ⚠️ CSEK no cloud, nada "lock out" | **Inexistente na Atlassian**: bloqueio de boot por credencial do proprietário (nome+CPF) é modelo próprio |
| **Alertas/monitoramento** | ✅ webhook Zabbix → reconciliação com dedupe + enriquecimento IA | ✅ Opsgenie maduro (on-call, escalonamento, dedupe) | Opsgenie está à frente: falta on-call, regras de roteamento |
| **Change/impacto (ITSM)** | ❌ | ✅ JSM change management com risk assessment via Insight | Brecha maior: SGTI não tem workflow de mudança/aprovação de mudanças |
| **Docs/conhecimento** | ⚠️ RAG de manuais indexados | ✅ Confluence (completo) | SGTI indexa, não oferece autoria/colaboração |

---

## 3. Onde SGTI está à frente da Atlassian

1. **Reconciliação com governança four-eyes algorítmica** — Insight/Assets não tem nada equivalente; a regra vive no backend (409/403 no schema, não na UI) e a decisão dispara **correção automática auditada**.
2. **IA local com confiança calibrada** — alta confiança registra sozinha (com trilha), baixa confiança vira tarefa humana: pipeline de descoberta auditável, não apenas assistente.
3. **Crypto-lock** — nenhum produto Atlassian trava a operação até desbloqueio credenciado.
4. **Ciclo alarme → discrepância → decisão → correção** fechado no produto, com dedupe e fonte externa (Zabbix) integrada.

---

## 4. Gaps vs Atlassian (roadmap)

- Sem visualização gráfica do mapa/grafo (maior lacuna percebida pelo usuário final — é o produto central da Compass).
- Sem análise de impacto transitiva ("o que derruba se este ativo cair") — os dados existem, faltam endpoint e tela.
- Sem workflow de mudança (JSM change) nem catálogo de serviços com health/scorecards (Compass).
- Sem on-call/roteamento de alertas (Opsergenie) — o webhook Zabbix cobre a entrada, não o fluxo de resposta a incidente.

---

## 5. Resumo

Em **núcleo CMDB + auditoria + segurança**, paridade ou vantagem própria; em **reconciliação com governança assistida por IA e correção automática**, SGTI supera a Atlassian. Os próximos passos para fechar o ciclo conceitual do `LUMEN.md` são a **visualização gráfica do mapa** e a **análise de impacto (what-if)** — o ciclo alarme → reconciliação → correção já está entregue e versionado.