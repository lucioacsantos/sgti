# Apresentação — SGTI CMDB (LUMEN)
**Gerência Executiva · 26/10/2026 · ~16 slides**

---

## Slide 1 — Capa
**LUMEN — Iluminando a Infraestrutura de TI**
O mapa vivo da nossa tecnologia: descoberto por IA, validado por especialistas, auditado de ponta a ponta.

## Slide 2 — O problema
- Gerenciar TI hoje = navegar uma cidade sem mapa
- Falhas: descobrir tarde o que afetou um serviço
- Mudanças que derrubam sistemas críticos sem aviso
- Planilhas manuais, sempre desatualizadas

## Slide 3 — O que é o LUMEN
- CMDB próprio: catálogo de ativos, aplicações, serviços e **dependências**
- "Desenho elétrico da TI": sabe onde cada fio passa antes de mexer no disjuntor
- Plataforma web segura, auditável, com integrações de monitoramento
- 100% desenvolvida em casa — sem licença de CMDB comercial

## Slide 4 — Funcionalidades entregues (1/2)
- **Inventário completo**: servidores físicos/virtuais, containers, rede, IPs (primário automático)
- **Mapa de TI**: clusters, namespaces, serviços técnicos e de negócio, instâncias, relacionamentos tipados
- **Automação segura**: gravação idempotente (nunca duplica), tokens de serviço, dry-run
- **Auditoria integral**: quem, quando, o que mudou, antes/depois, correlation ID

## Slide 5 — Funcionalidades entregues (2/2)
- **Segurança**: login AD + 2FA, criptografia AES-256-GCM com crypto-lock
- **IA local (LLM on-premise)**: assistente com respostas **citadas dos manuais** (RAG), integração Zabbix ≥ 7.0
- **Frontend moderno**: dashboard, 8 abas de infraestrutura, exportação XLSX, permissões por perfil

## Slide 6 — ⭐ Módulo de Reconciliação: entregue e versionado
- Detecta **automaticamente** inconsistências: ativo sem IP/IP órfão, aplicação sem instância, FKs órfãs… (7 regras)
- Cada discrepância vira um item de trabalho com **workflow de quatro olhos**
- Nenhuma correção sem **2+ analistas** — nem o criador pode validar sozinho
- **Novidade**: alarmes do Zabbix abrem reconciliação automaticamente (webhook, com dedupe)
- **Novidade**: a decisão "retificar" **aplica a correção no CMDB** automaticamente, com auditoria

## Slide 7 — ⭐ Inovação: inferência por IA com confiabilidade calibrada
- LLM **local** (sem nuvem, sem custo de token) descobre serviços e dependências
- Cada descoberta vem com **nota de confiabilidade** (0–100%)
- Abaixo do limiar (90%) → vira **tarefa humana** no painel de reconciliação
- Acima → registrada já validada, com auditoria automática
- **A IA não decide sozinha: propõe, e especialistas confirmam**

## Slide 8 — Inovações alcançadas
1. Primeiro CMDB da casa auto-descoberto por IA on-premise
2. Governança algorítmica: four-eyes imposto pelo sistema, não pela boa vontade
3. **Ciclo fechado**: alarme → discrepância → decisão colegiada → correção aplicada, tudo auditado
4. Crypto-lock em Cython: sistema "soldado" até o dono (nome+CPF) desbloquear
5. Auditoria de decisões humanas **e de máquina**
6. Assistente RAG com citações dos procedimentos internos

## Slide 9 — Vantagens das abordagens
- **Idempotência**: automações rodam sempre, sem duplicar
- **IA local**: dados sensíveis nunca saem da rede
- **Regras no backend**: four-eyes impossível de burlar pela UI
- **Dry-run em tudo**: revisão antes de gravar
- **Correção automática auditada**: decisão colegiada vira ação no CMDB sem retrabalho manual
- **Testes com LDAP real**: validação de verdade, não de brinquedo

## Slide 10 — Benchmark: SGTI × Atlassian (JSM Assets + Compass + Opsgenie + Rovo)
Para cobrir o mesmo escopo do SGTI, seria preciso combinar **pelo menos 4 produtos** Atlassian:

| Capacidade | SGTI (LUMEN) | Atlassian |
|---|---|---|
| **Reconciliação** | 7 regras automáticas + fonte Zabbix + **four-eyes no backend** + correção automática auditada | Reconciliação de atributos por regra simples, **sem workflow colegiado** |
| **IA** | LLM **100% local**, confiança calibrada (< 90% vira tarefa humana) | Rovo: SaaS — dados e alarmes trafegam na nuvem |
| **Governança** | 4 olhos imposto pelo código da API (409/403), não pela boa vontade | Depende do processo do time sobre o produto |
| **Crypto-lock** | Exclusivo (Cython, desbloqueio pelo dono: nome+CPF) | **Inexistente** em qualquer produto |
| **Ciclo alarme→correção** | Fechado: Zabbix → discrepância → decisão → CMDB corrigido | Opsgenie cobre alertas, não fecha o ciclo na base |
| **Auditoria** | Total — inclui decisões de máquina e pareceres | Paridade |
| **Grafo visual / gestão de mudanças** | No roadmap (próximas entregas) | **Ponto forte do concorrente** (Compass/JSM) — reconhecido e priorizado |

## Slide 11 — Por que o SGTI supera o pacote comercial
1. **Custo**: sem licença por agente/usuário, anual e crescente — no modelo Atlassian, o mesmo escopo exigiria JSM Assets + Compass + Opsgenie + Guard
2. **Sigilo**: IA local on-premise — alarmes, contextos e dados sensíveis **nunca saem da rede** (no concorrente, tudo é nuvem)
3. **Governança que o sistema impõe**: quatro olhos inseparável da API; decisão colegiada **aplica a correção com auditoria** — único do mercado
4. **Encaixe na realidade da casa**: Zabbix ≥ 7.0, AD/LDAP e regras D1–D7/Z1–Z3 sob medida, evoluindo com o nosso processo
5. **Soberania**: roadmap interno, sem lock-in, sem dependência de fornecedor

## Slide 12 — Benefícios para a organização
- ⚡ **Menos surpresas**: impacto visível antes da mudança
- 🚑 **Incidentes mais rápidos**: mapa mostra serviços afetados na hora — e o alarme do Zabbix já entra no fluxo de correção
- 🕒 **Menos planilha**: descoberta automática libera a equipe
- 🔐 **Compliance**: trilha de auditoria + criptografia de nível bancário

## Slide 13 — Maturidade e evolução contínua
- **Qualidade mensurável**: suíte de 127 testes automatizados; migrações de banco versionadas e idempotentes
- **Endurecimento programado**: revogação completa de sessões, rate limiting ampliado nas rotas de login, pipeline de CI
- **Roadmap de valor**: visualização gráfica do mapa (grafo), análise de impacto "what-if" (o que derruba se este ativo cair?)
- Transparência: backlog técnico está identificado e priorizado, sem surpresas

## Slide 14 — Próximos passos
1. Piloto de reconciliação com dados reais (volume de itens × tempo de verificação)
2. Grafo visual do mapa + análise de impacto "what-if"
3. Endurecimento contínuo: ciclo de sessões (revogação), rate limiting de login, CI
4. Vídeo institucional LUMEN (storyboard pronto)

## Slide 15 — Indicadores
- **127 testes automatizados** (119 executáveis em qualquer ambiente + 8 de LDAP real com Docker opcional)
- Build de produção OK (frontend 1,15 s — bundle principal ≈ 156 kB, ≈ 59 kB comprimido)
- Suíte cobre auth/2FA, cripto, CRUD, auditoria, integrações, IA e reconciliação

## Slide 16 — Fechamento
**"Antes de tocar em qualquer coisa, eu sei exatamente onde a energia vai."**
LUMEN: o sistema nervoso digital da nossa TI — proativo, preciso e confiável.

---
### Apêndice (dúvidas prováveis)
- *Por que IA local?* — sigilo de dados + custo zero + offline
- *E se a IA errar?* — abaixo de 90% nada entra sem 2 analistas; tudo auditado
- *E os alarmes do Zabbix?* — viram itens de reconciliação automaticamente, com dedupe, e passam pelo mesmo workflow
- *Quanto custa operar?* — sem licença de CMDB comercial nem tokens de nuvem; roda em servidor próprio
- *Por que não comprar uma solução comercial (Atlassian)?* — o mesmo escopo exigiria 4+ assinaturas SaaS com licença por agente/usuário; a IA seria em nuvem (dados saem da casa); a reconciliação do Assets não tem workflow colegiado nem aplica correção automática. As lacunas do SGTI (grafo visual, gestão de mudanças) estão no roadmap — ver `comparativo-atlassian.md`