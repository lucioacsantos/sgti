# Relatório Executivo — SGTI CMDB (LUMEN)

**Data:** 21/10/2026 · **Público:** Gerência Executiva
**Status da verificação:** 127 testes automatizados de backend (suíte verde) · build do frontend OK (1,15 s) · branch `main` sincronizada

---

## 1. Resumo executivo

O SGTI CMDB ("LUMEN") é uma plataforma própria de gerenciamento de configuração que cria e mantém um **mapa vivo da infraestrutura de TI** — ativos, aplicações, serviços e suas dependências — preenchido por automação, inferência lexical e por IA local (LLM), com **validação humana obrigatória** para descobertas de baixa confiança e **trilha de auditoria integral**.

O **ciclo operacional completo já está entregue e versionado**: automação grava → painel lê e corrige → reconciliação detecta discrepâncias (inclusive a partir de alarmes reais do Zabbix) → decisão colegiada aplica a correção automaticamente, com segurança criptográfica nas colunas sensíveis e auditoria em cada passada.

---

## 2. Funcionalidades implementadas (entregues e versionadas)

### 2.1 Núcleo CMDB
- **Ativos**: servidores físicos/virtuais, containers, equipamentos de rede e estações de trabalho, com tipo, ambiente, status, criticidade, SO (com lifecycle), área responsável e **múltiplos IPs (IPv4/IPv6)** com flag de IP primário (desmarcação automática dos demais).
- **Upsert idempotente** para automações (`ON CONFLICT` atômico no PostgreSQL): reexecução nunca duplica dados; audit log distingue CREATE de UPDATE.
- **Aplicações**: catálogo de sistemas com linguagens, bancos de dados, áreas de tecnologia e negócio.
- **Dados de referência**: CRUD admin completo (tipos, ambientes, status, criticidades, SOs, áreas, tipos de relacionamento).

### 2.2 Mapa de TI (Infraestrutura)
- Clusters, Namespaces, Serviços (componente técnico), Serviços de Negócio (capability percebida pelo usuário), Instâncias de Aplicação e Relacionamentos tipados (*Depende de, Contém, Conecta-se a, Executa, Hospeda, Replica para, Integra com, Backup de*).

### 2.3 Módulo de Reconciliação ⭐
- **Detecção automática de discrepâncias** (7 regras D1–D7): ativo sem IP, sem ambiente, aplicação sem instância, instância sem ativo, cluster sem ativo, serviço/FK órfãs.
- **Fonte `zabbix` integrada**: o webhook de alarmes (`POST /reconciliacoes/zabbix/alarme`) abre execução de reconciliação automaticamente, com dedupe por entidade/campo/valor da fonte — o incidente real entra direto no fluxo de governança.
- **Correção automática na decisão "retificar"**: a decisão colegiada aplica a correção no CMDB (criação de ativo ausente, alinhamento de referências etc.) com audit log do antes/depois.
- **Workflow de quatro olhos real, imposto pelo backend**: decisão exige **≥ 2 analistas distintos** com parecer registrado; o criador da execução **não pode retificar sozinho**; o decisor deve ter participado da verificação; 1 parecer por analista por item.
- Tudo com audit log (CREATE, PARECER, DECISAO, CONCLUIR, CANCELAR) e **painel web completo** (listagem com contagens, filtros, parecer e decisão).

### 2.4 Inferência com IA (LLM local)
- `scripts/infer_infra_map_ia.py`: substitui os dicionários regex por **LLM local**, mantendo o contrato idempotente via API (`--dry-run`, `--sem-ia`, `--limiar-confianca`).
- Cada ação inferida reporta **confiabilidade (0..1)**; endpoint `POST /reconciliacoes/inferencia`:
  - confiança **< 0,9** → abre item pendente exigindo quatro olhos;
  - confiança **≥ 0,9** → registrado já ratificado (auditoria sem trabalho manual).
- Badge de confiabilidade no painel (vermelho < 70% · âmbar < 90% · verde ≥ 90%).

### 2.5 Autenticação e segurança
- Login **AD/LDAP duplo** (Active Directory ou OpenLDAP) → JWT access + refresh.
- **2FA TOTP opcional**: QR code autoatendimento, segredo cifrado (AES-256-GCM), suporte de admin (zerar 2FA de usuário que perdeu o autenticador), senha nunca persistida em storage.
- **Tokens de serviço** para automações (bcrypt, exibição única, expiração) — modelo "automação grava, painel lê e corrige".
- **crypto_lock**: colunas sensíveis cifradas; sistema bloqueado até desbloqueio no boot por proprietário credenciado (nome + CPF), com **validação canônica anti-tamper** no decrypt.
- Rate limiting (100 req/min), CORS, security headers, correlation IDs em toda request.

### 2.6 Auditoria
- Registro completo de mutações (entidade, ação, estado antes/depois, usuário, timestamp), filtrável; correlation ID para rastreamento ponta a ponta — incluindo **decisões humanas e de máquina** (pareceres, decisões e auto-ratificação por inferência).

### 2.7 Integrações e IA de operação
- **Zabbix**: compatível com Zabbix **≥ 7.0** (autenticação via Bearer), webhook de alarmes com enriquecimento por IA e **abertura automática de reconciliação**.
- **IA local (LLM on-premise)**: perguntas em linguagem natural à base de conhecimento (manuais indexados) com **respostas citando trechos** (RAG) — tela de Assistente IA; variante determinística em CPU (sem LLM) quando necessário.
- Base de conhecimento inicial: procedimentos de alta de CPU, disco cheio, memória e serviço down.

### 2.8 Frontend (Vue 3)
- Dashboard, Ativos (busca server-side, filtros, paginação), Infraestrutura (8 abas), Reconciliações, Dados de Referência, Auditoria, Integrações, Assistente IA e Administração (visível só para admin).
- **Exportação XLSX** das listagens (inclusive com sigla do SO) e componentes reutilizáveis (paginação, confirmação, erros, loading).

### 2.9 Pipeline de carga e inferência
- `scripts/seed.py`: dados mestre + service account.
- `scripts/import_test_data.py`: importação idempotente de dumps pgAdmin (dry-run, tratamento de FKs inexistentes).
- `scripts/infer_infra_map.py`: inferência **lexical/regex** de serviços, instâncias e relacionamentos — baseline determinístico.
- Qualidade: suíte de **127 testes** (autenticação, crypto, CRUD, infra, relacionamentos, integrações, IA, reconciliação, LDAP real via Docker opcional).

---

## 3. Entregas recentes (desde o último relatório, 28/09)

| Entrega | Detalhe |
|---|---|
| **Módulo de Reconciliação + inferência integrada** | Antes pendente de commit; agora **versionado em `main`** com suíte dedicada |
| **Fonte Zabbix → reconciliação** | Webhook abre execução fonte `zabbix` com dedupe; alarmes reais alimentam o workflow |
| **Correção automática na decisão** | "Retificar" aplica o conserto no CMDB, não apenas muda o status do item |
| **Higiene técnica** | Migração `utcnow()` → `datetime.now(UTC)` (eliminação dos warnings de deprecação); artefatos de teste removidos do versionamento (`.gitignore`) |
| **Migrações Alembic idempotentes** | Reexecução segura mesmo com schema adiantado pelo boot — menos fricção operacional |
| **Erros de upstream** | Falha de LLM/Zabbix responde **502 com detalhe** em vez de propagar 404 enganoso |
| **Zabbix ≥ 7.0** | Autenticação via header Bearer, mantendo compatibilidade com versões anteriores |
| **Dependências** | Correções de vulnerabilidades (Dependabot); variante de requirements para ambientes **sem GPU** (CPU) |
| **Licença** | Código publicado sob **GNU GPL v3** (arquivo LICENSE + referência no README) |

---

## 4. Vantagens das abordagens utilizadas

| Abordagem | Vantagem |
|---|---|
| Upsert idempotente (`ON CONFLICT`) | Automações podem rodar quantas vezes quiserem sem duplicar; sem race conditions |
| Dual auth (JWT + service token) | Modelo "automação grava, painel lê/corrige" sem compartilhar credenciais humanas |
| Inferência via API (nunca direto no banco) | Todo post passa por autenticação + audit log; nada escapa da trilha |
| `--dry-run` em todo pipeline | Revisão antes de gravar; zero risco na primeira carga |
| IA **local** (LLM on-premise) | Sem envio de dados sensíveis para nuvem; custo zero de token; operável offline |
| Confiabilidade calibrada + limiar | Balanceia automação e risco: alta confiança flui, baixa confiança vira tarefa humana |
| Four-eyes no backend (não só na UI) | A regra de negócio vive no schema (409/403) — impossível burlar pela interface |
| Correção automática pós-decisão | A decisão colegiada produz efeito no dado com trilha antes/depois — zero retrabalho manual |
| SQLAlchemy + Alembic (migrações idempotentes) | Evolução de schema versionada, reversível e reexecutável com segurança |
| Testes com LDAP real (Docker) | Valida integração de verdade, não mock superficial |

---

## 5. Inovações alcançadas

1. **CMDB auto-descoberto com IA local**: primeiro mapa de TI preenchido por LLM on-premise (sem nuvem), combinando inferência lexical determinística + LLM com self-report de confiança.
2. **Governança algorítmica**: a IA não apenas sugere — o sistema **impõe** revisão humana por four-eyes quando a confiança fica abaixo do limiar, com separação de responsabilidades (criador não valida a própria inferência).
3. **Ciclo fechado alarme → correção**: o alarme do Zabbix vira discrepância, a discrepância vira decisão colegiada e a decisão aplica o conserto — tudo com dedupe e auditoria.
4. **Crypto-lock em Cython**: chave derivada do proprietário (nome+CPF), sistema inoperante até desbloqueio, cifra AES-256-GCM em colunas com validação canônica anti-tamper.
5. **Auditoria de inferência**: até as ações automáticas de alta confiança ficam registradas (`ratificado por inferencia_ia`) — rastreabilidade total de decisão humana e de máquina.
6. **RAG institucional**: assistente que responde com **trechos citados** dos manuais, acelerando a resolução de incidentes.
7. **Material LUMEN**: narrativa executiva ("desenho elétrico da TI") + storyboard pronto para vídeo de divulgação.

---

## 6. Pontos de atenção e evolução contínua

| # | Ponto | Situação atual | Próximo passo |
|---|---|---|---|
| 1 | Detecção de discrepâncias O(N) | Varre tabelas em memória — OK no volume atual | Queries agregadas quando o volume crescer |
| 2 | Papéis de reconciliação via token_hash | Funcional (acoplamento técnico conhecido) | Modelar papéis explicitamente |
| 3 | Arquitetura admin-only nas decisões | Conservador e seguro para o estágio atual | Avaliar ampliar a analistas plenos com a gestão |
| 4 | Revogação completa de sessões | Refresh token com expiração de 7 dias | Endurecimento do ciclo (revogação/rotação) + rate limiting nas rotas de login |
| 5 | Visualização do mapa | Mapa navegável em tabelas/abas | Grafo visual + análise de impacto "what-if" |

---

## 7. Próximos passos sugeridos

1. **Piloto de reconciliação com dados reais**: executar detecção D1–D7 + fonte Zabbix, medir volume de itens e tempo médio de verificação four-eyes.
2. **Grafo visual do mapa** com análise de impacto transitiva ("o que derruba se este ativo cair").
3. **Endurecimento de segurança contínuo**: ciclo completo de revogação de sessões, rate limiting nas rotas de autenticação, pipeline de CI integrando a suíte de testes e o check de migrações.
4. **Cobertura adicional de testes**: ciclo de 2FA/refresh e módulo de dados de referência.
5. **Vídeo institucional LUMEN** (storyboard pronto em `LUMEN.md`).
6. **Evolução da coleta automática**: conectores dedicados para fontes de inventário, reutilizando a malha de service tokens já existente.

---

## 8. Indicadores de qualidade

- **127 testes backend** — suíte verde (119 executam em qualquer ambiente + 8 de LDAP real que exigem o laboratório Docker opcional; sem ambiente, são saltados com segurança).
- **Build de produção frontend** — OK (1,15 s; bundle principal ≈ 156 kB, ≈ 59 kB comprimido).
- **Migrações de banco** idempotentes e versionadas — reexecução segura.
- **Cobertura funcional**: autenticação/crypto, CRUD de ativos/IPs/infra/relacionamentos, auditoria, integrações IA (híbrida), reconciliação (workflow D1–D7 + fonte Zabbix + correção automática) e pipeline de inferência.
- **Licenciamento**: GNU GPL v3.