# Relatório Executivo — SGTI CMDB (LUMEN)

**Data:** 28/09/2026 · **Público:** Gerência Executiva
**Status da verificação:** 87 testes automatizados de backend passando · build do frontend OK · branch `main` sincronizada

---

## 1. Resumo executivo

O SGTI CMDB ("LUMEN") é uma plataforma própria de gerenciamento de configuração que cria e mantém um **mapa vivo da infraestrutura de TI** — ativos, aplicações, serviços e suas dependências — preenchido por automação, inferência lexical e por IA local (LLM), com **validação humana obrigatória** para descobertas de baixa confiança e **trilha de auditoria integral**.

O ciclo operacional central já entregue: **automação grava, painel lê e corrige** — com segurança criptográfica de nível bancário nas colunas sensíveis.

---

## 2. Funcionalidades implementadas (já versionadas)

### 2.1 Núcleo CMDB
- **Ativos**: servidores físicos/virtuais, containers, equipamentos de rede e estações de trabalho, com tipo, ambiente, status, criticidade, SO (com lifecycle), área responsável e **múltiplos IPs (IPv4/IPv6)** com flag de IP primário (desmarcação automática dos demais).
- **Upsert idempotente** para automações (`ON CONFLICT` atômico no PostgreSQL): reexecução nunca duplica dados; audit log distingue CREATE de UPDATE.
- **Aplicações**: catálogo de sistemas com linguagens, bancos de dados, áreas de tecnologia e negócio.
- **Dados de referência**: CRUD admin completo (tipos, ambientes, status, criticidades, SOs, áreas, tipos de relacionamento).

### 2.2 Mapa de TI (Infraestrutura)
- Clusters, Namespaces, Serviços (componente técnico), Serviços de Negócio (capability percebida pelo usuário), Instâncias de Aplicação e Relacionamentos tipados (*Depende de, Contém, Conecta-se a, Executa, Hospeda, Replica para, Integra com, Backup de*).

### 2.3 Autenticação e segurança
- Login **AD/LDAP duplo** (Active Directory ou OpenLDAP) → JWT access + refresh.
- **2FA TOTP opcional**: QR code autoatendimento, segredo cifrado (AES-256-GCM), suporte de admin (zerar 2FA de usuário que perdeu o autenticador), senha nunca persistida em storage.
- **Tokens de serviço** para automações (bcrypt, exibição única, expiração).
- **crypto_lock**: colunas sensíveis cifradas; sistema bloqueado até desbloqueio no boot por proprietário credenciado (nome + CPF).
- Rate limiting (100 req/min), CORS, security headers, correlation IDs em toda request.

### 2.4 Auditoria
- Registro completo de mutações (entidade, ação, estado antes/depois, usuário, timestamp), filtrável; correlation ID para rastreamento ponta a ponta.

### 2.5 Integrações e IA
- **Zabbix**: webhook de alarmes com enriquecimento por IA.
- **Ollama (IA local)**: perguntas em linguagem natural à base de conhecimento (manuais indexados) com **respostas citando trechos** (RAG) — tela de Assistente IA.
- Base de conhecimento inicial: procedimentos de alta de CPU, disco cheio, memória e serviço down.

### 2.6 Frontend (Vue 3)
- Dashboard, Ativos (busca server-side, filtros, paginação), Infraestrutura (8 abas), Dados de Referência, Auditoria, Integrações, Assistente IA e Administração (visível só para admin).
- **Exportação XLSX** das listagens (inclusive com sigla do SO).
- Componentes reutilizáveis (paginação, confirmação, erros, loading).

### 2.7 Pipeline de carga e inferência
- `seed.py`: dados mestre + service account.
- `import_test_data.py`: importação idempotente de dumps pgAdmin (dry-run, tratamento de FKs inexistentes).
- `infer_infra_map.py`: inferência **lexical/regex** de serviços, instâncias (match ativo↔aplicação por tokens fortes) e relacionamentos por regras estruturadas (multi-host, app→banco).
- Qualidade: suíte de 87 testes (autenticação, 2FA, crypto, CRUD, infra, relacionamentos, integrações, LDAP real via Docker).

---

## 3. Implementações em andamento (ainda não commitadas)

> Bloco entregue em desenvolvimento, **aguardando commit**: módulo de **Reconciliação** + inferência por IA integrada ao fluxo de validação.

### 3.1 Módulo de Reconciliação com workflow de quatro olhos ⭐ principal novidade
- **3 tabelas novas**: `reconciliacao` (execução), `item_reconciliacao` (discrepância), `parecer_reconciliacao` (voto do analista) + migration Alembic `a1f2c3d4e5f6` (coluna `confianca`).
- **Detecção automática de discrepâncias** (7 regras D1–D7): ativo sem IP, sem ambiente, aplicação sem instância, instância sem ativo, cluster sem ativo, serviço/FK órfãs.
- **Workflow de quatro olhos real**: decisão exige **≥ 2 analistas distintos** com parecer registrado; o criador da execução **não pode retificar sozinho**; o decisor deve ter participado da verificação; decisões/conclusão restritas a admin; 1 parecer por analista por item.
- Tudo com audit log (CREATE, PARECER, DECISAO, CONCLUIR, CANCELAR).
- **Painel web completo** (`ReconciliacoesView.vue`, 704 linhas): listagem com contagens (pendentes/retificados/ratificados/ignorados), filtro por status, registro de parecer e decisão.

### 3.2 Inferência por IA (Ollama — llama3.2 + embeddings) integrada à reconciliação
- `infer_infra_map_ia.py` (738 linhas): substitui dicionários regex por **LLM local**, mantendo o contrato idempotente via API (`--dry-run`, `--sem-ia`, `--limiar-confianca`).
- Cada ação inferida reporta **confiabilidade (0..1)**; endpoint `POST /reconciliacoes/inferencia`:
  - confiança **< 0,9** → abre item pendente exigindo quatro olhos;
  - confiança **≥ 0,9** → registrado já ratificado (auditoria sem trabalho manual).
- Badge de confiabilidade no painel (vermelho < 70% · âmbar < 90% · verde ≥ 90%).

### 3.3 Endurecimento de segurança (crypto_lock)
- **Validação de base64 canônico** no decrypt: rejeita manipulação de bits de padding que passariam despercebidos na verificação GCM (anti-malleability).

### 3.4 Robustez e qualidade
- Correção de serialização de erros 422 (ValueError não-serializável no JSON).
- Correção de colisão de `token_hash` UNIQUE em usuários de teste.
- Reorganização dos scripts de suporte para `scripts/` (seed, importações, inferências).
- `LUMEN.md`: material de pitch executivo com analogia elétrica e storyboard de vídeo institucional.

---

## 4. Vantagens das abordagens utilizadas

| Abordagem | Vantagem |
|---|---|
| Upsert idempotente (`ON CONFLICT`) | Automações podem rodar quantas vezes quiserem sem duplicar; sem race conditions |
| Dual auth (JWT + service token) | Modelo "automação grava, painel lê/corrige" sem compartilhar credenciais humanas |
| Inferência via API (nunca direto no banco) | Todo post passa por autenticação + audit log; nada escapa da trilha |
| `--dry-run` em todo pipeline | Revisão antes de gravar; zero risco na primeira carga |
| IA **local** (Ollama) | Sem envio de dados sensíveis para nuvem; custo zero de token; operável offline |
| Confiabilidade calibrada + limiar | Balanceia automação e risco: alta confiança flui, baixa confiança vira tarefa humana |
| Four-eyes no schema (não só na UI) | A regra de negócio vive no backend — impossível burlar pela interface |
| SQLAlchemy + Alembic | Evolução de schema versionada e reversível |
| Testes com LDAP real (Docker) | Valida integração de verdade, não mock superficial |
| Vue 3 + serviços tipados | Frontend compilado com type-check; componentes reutilizáveis |

---

## 5. Inovações alcançadas

1. **CMDB auto-descoberto com IA local**: primeiro mapa de TI preenchido por LLM on-premise (sem nuvem), combinando inferência lexical determinística + LLM com self-report de confiança.
2. **Governança algorítmica**: a IA não apenas sugere — o sistema **impõe** revisão humana por four-eyes quando a confiança fica abaixo do limiar, com separação de responsabilidades (criador não valida a própria inferência).
3. **Crypto-lock em Cython**: chave derivada do proprietário (nome+CPF), sistema inoperante até desbloqueio, cifra AES-256-GCM em colunas — e agora com validação canônica anti-tamper.
4. **Auditoria de inferência**: até as ações automáticas de alta confiança ficam registradas (`ratificado por inferencia_ia`) — rastreabilidade total de decisão humana e de máquina.
5. **RAG institucional**: assistente que responde com **trechos citados** dos manuais, acelerando a resolução de incidentes (procedimentos operacionais já indexados).
6. **Material LUMEN**: narrativa executiva ("desenho elétrico da TI") + storyboard pronto para vídeo de divulgação.

---

## 6. Pontos de atenção

| # | Ponto | Detalhe | Recomendação |
|---|---|---|---|
| 1 | **Debt técnico `utcnow()`** | 64 warnings de deprecação de datetime (Python 3.13) | Migrar para `datetime.now(UTC)` |
| 2 | Detecção de discrepâncias O(N) | `detectar_discrepancias` varre tabelas inteiras em memória | Migração para queries agregadas quando o volume crescer |
| 3 | Decisão não corrige o dado | "Retificado" muda o **status do item**, não o registro do CMDB | Fase 2: aplicar a correção automaticamente na decisão |
| 4 | Fonte `zabbix` prevista não integrada | Schema aceita, mas alarmes Zabbix ainda não abrem reconciliação | Integrar webhook → reconciliação |
| 5 | Papéis de reconciliação via token_hash | `_require_admin` lê JSON do token (acoplamento) | Modelar papéis explicitamente |
| 6 | `test.db` e `cmdb_banco_teste/` no workspace | Arquivos de teste na raiz | Limpeza/`.gitignore` |
| 7 | Commit pendente grande | ~390 linhas novas + 1.000 removidas aguardando versionamento | Comitar módulo de reconciliação em breve (revisão prévia) |
| 8 | Arquitetura admin-only nas decisões | Decisão final exige perfil admin; avaliar ampliar a analistas plenos | Definir matriz de papéis com a gestão |

---

## 7. Próximos passos sugeridos

1. **Commit do módulo de Reconciliação** (backend + frontend + migration + testes) — já validado pela suíte.
2. Piloto de reconciliação com dados reais: rodar detecção D1–D7, medir volume de itens e tempo médio de verificação four-eyes.
3. Integrar alarmes Zabbix como fonte de reconciliação (fonte `zabbix`).
4. Correção automática do CMDB na decisão "retificar".
5. Limpeza de deprecações (`utcnow`) e artefatos de teste.
6. Produzir o vídeo institucional LUMEN (storyboard pronto em `LUMEN.md`).

---

## 8. Indicadores de qualidade

- **87 testes backend** — 100% passando.
- **Build de produção frontend** — OK (1,08 s, bundle principal 156 kB).
- **Cobertura funcional**: autenticação/2FA, crypto, CRUD de ativos/IPs/infra/relacionamentos, auditoria, integrações e o novo fluxo de reconciliação (260 linhas de teste dedicadas).