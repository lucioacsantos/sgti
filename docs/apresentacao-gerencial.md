# Apresentação — SGTI CMDB (LUMEN)
**Gerência Executiva · 28/09/2026 · ~15 slides**

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

## Slide 4 — Funcionalidades entregues (1/2)
- **Inventário completo**: servidores físicos/virtuais, containers, rede, IPs (primário automático)
- **Mapa de TI**: clusters, namespaces, serviços técnicos e de negócio, instâncias, relacionamentos tipados
- **Automação segura**: gravação idempotente (nunca duplica), tokens de serviço, dry-run
- **Auditoria integral**: quem, quando, o que mudou, antes/depois, correlation ID

## Slide 5 — Funcionalidades entregues (2/2)
- **Segurança**: login AD + 2FA, criptografia AES-256-GCM com crypto-lock, rate limiting
- **IA local (LLM on-premise)**: assistente com respostas **citadas dos manuais** (RAG), integração Zabbix
- **Frontend moderno**: dashboard, 8 abas de infraestrutura, exportação XLSX, permissões por perfil

## Slide 6 — ⭐ Novidade: módulo de Reconciliação (em homologação)
- Detecta **automaticamente** inconsistências: ativo sem IP, aplicação sem instância, clusters órfãos…
- Cada discrepância vira um item de trabalho com **workflow de quatro olhos**
- Nenhuma correção sem **2+ analistas** — nem o criador pode validar sozinho
- Status da suíte: **87 testes passando** (implementação concluída, aguardando commit)

## Slide 7 — ⭐ Inovação: inferência por IA com confiabilidade calibrada
- LLM **local** (sem nuvem, sem custo de token) descobre serviços e dependências
- Cada descoberta vem com **nota de confiabilidade** (0–100%)
- Abaixo de 90% → vira **tarefa humana** no painel de reconciliação
- Acima → registrada com auditoria automática
- **A IA não decide sozinha: propõe, e especialistas confirmam**

## Slide 8 — Inovações alcançadas
1. Primeiro CMDB da casa auto-descoberto por IA on-premise
2. Governança algorítmica: four-eyes imposto pelo sistema, não pela boa vontade
3. Crypto-lock em Cython: sistema "soldado" até o dono (nome+CPF) desbloquear
4. Auditoria de decisões humanas **e de máquina**
5. Assistente RAG com citações dos procedimentos internos

## Slide 9 — Vantagens das abordagens
- **Idempotência**: automações rodam sempre, sem duplicar
- **IA local**: dados sensíveis nunca saem da rede
- **Regras no backend**: four-eyes impossível de burlar pela UI
- **Dry-run em tudo**: revisão antes de gravar
- **Testes com LDAP real**: validação de verdade, não de brinquedo

## Slide 10 — Benefícios para a organização
- ⚡ **Menos surpresas**: impacto visível antes da mudança
- 🚑 **Incidentes mais rápidos**: mapa mostra serviços afetados na hora
- 🕒 **Menos planilha**: descoberta automática libera a equipe
- 🔐 **Compliance**: trilha de auditoria + criptografia de nível bancário

## Slide 11 — Pontos de atenção (transparência com a gerência)
- Decisão "retificar" hoje valida; **fase 2** aplicará a correção automática
- Alarmes Zabbix ainda não abrem reconciliação (rota prevista no desenho)
- Débitos técnicos leves (datetime deprecado, queries O(N)) — saneamento programado
- **Commit do módulo de reconciliação pendente** (código pronto e testado)

## Slide 12 — Próximos passos
1. Commit + homologação do módulo de Reconciliação
2. Piloto com dados reais (volume de itens × tempo de verificação)
3. Integração Zabbix → reconciliação
4. Correção automática na decisão
5. Vídeo institucional LUMEN (storyboard pronto)

## Slide 13 — Indicadores
- **87 testes automatizados** passando
- Build de produção OK (frontend ~99 kB gzipped principal)
- Suíte cobre auth/2FA, cripto, CRUD, auditoria, integrações, reconciliação

## Slide 14 — Fechamento
**"Antes de tocar em qualquer coisa, eu sei exatamente onde a energia vai."**
LUMEN: o sistema nervoso digital da nossa TI — proativo, preciso e confiável.

---
### Apêndice (dúvidas prováveis)
- *Por que IA local?* — sigilo de dados + custo zero + offline
- *E se a IA errar?* — abaixo de 90% nada entra sem 2 analistas; tudo auditado
- *Quanto custa operar?* — sem licença de CMDB comercial nem tokens de nuvem; roda em servidor próprio