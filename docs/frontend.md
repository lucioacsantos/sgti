# Guia do frontend

Painel web (Vue 3) em `http://localhost:5173`. Login via AD; todas as telas respeitam o perfil do usuário (elementos administrativos aparecem só para admin).

## Layout

Após o login, o cabeçalho lateral (AdminLayout) dá acesso a: Dashboard, Ativos, Infraestrutura, Dados de Referência, Auditoria, Integrações, Assistente IA e Administração (só admin). Botão de logout e nome do usuário no topo.

---

## Login (com 2FA)

Fluxo em duas etapas quando o usuário tem 2FA habilitado:

1. **Usuário + senha** → validação no AD
2. Se `requires_2fa` → painel de **código de 6 dígitos** (app autenticador); erros mostram mensagem específica ("Código 2FA inválido ou expirado")
3. "Usar outra conta" volta para credenciais e descarta a senha pendente (nunca persistida em storage)

Detalhes de habilitação/suporte em [autenticacao-2fa.md](autenticacao-2fa.md).

---

## Dashboard

Cards de estatísticas (ativos, aplicações, IPs), acessos rápidos e health do sistema.

---

## Ativos

Tabela principal do inventário: busca server-side, filtros por tipo/ambiente/área, paginação. Detalhe do ativo mostra IPs associados (primário destacado) e relacionamentos. Admin edita/exclui.

---

## Infraestrutura & Mapa de TI

Oito abas; busca local filtra os registros exibidos em todas elas (e reseta a página). Nomes de FKs (ativo, aplicação, cluster, tipo) são resolvidos automaticamente.

| Aba | Colunas | Admin pode |
|---|---|---|
| **Aplicações** | sistema, descrição, área de negócio, linguagens | — (somente leitura) |
| **Clusters** | id, nome, descrição, ativo | — |
| **Namespaces** | id, nome, cluster, ativo | — |
| **Serviços** | id, nome, tipo, ativo | ✏️ editar · 🗑 excluir |
| **Serviços de Negócio** | id, nome, descrição, ativo | ✏️ editar · 🗑 excluir |
| **Instâncias** | id, aplicação, host, porta, path, comando | ✏️ editar · 🗑 excluir |
| **Relacionamentos** | id, origem → destino, tipo, descrição | ✏️ editar · 🗑 excluir |
| **Endereços IP** | endereço, tipo, interface, ativo, primário | — (gerido por automação) |

### Paginação

- **Serviços, negócios, instâncias, clusters...**: carregam a lista inteira e paginam no cliente (25/página)
- **Relacionamentos e IPs**: paginados no servidor (50/página) — a navegação busca a próxima página na API

### Edição manual (perfil admin)

Botões aparecem na coluna **Ações** apenas para admins:

- **Editar (lápis)**: abre modal com os campos da entidade. Em instâncias e relacionamentos, ativos/aplicações/tipos aparecem em dropdown com nomes legíveis. Salvar grava via API e registra audit log.
- **Excluir (lixeira)**: diálogo de confirmação; ao confirmar, o item é removido (audit log DELETE). Nada é excluído sem confirmação.

Usuários não-admin não veem os botões; chamadas diretas à API recebem 403.

---

## Dados de Referência

CRUD admin das tabelas de apoio (tipos, ambientes, status, criticidades, SOs, áreas, tipos de relacionamento). Modal de criação/edição + confirmação de exclusão; exclusão de tipo de relacionamento em uso responde erro com a contagem de vínculos.

---

## Auditoria

Log paginado e filtrável (entidade, id). Útil para conferir correções manuais: cada UPDATE/DELETE manual de infraestrutura aparece aqui com o usuário responsável e o estado anterior/posterior.

---

## Assistente IA

Chat com a base de conhecimento (RAG/Ollama): pergunta → resposta + trechos citados dos documentos indexados. Requer Ollama configurado.

---

## Administração (admin)

Três abas:

### Usuários

Lista de contas AD/locais: perfis (badges), status 2FA, ativo/inativo (toggle) e ações:

- **Toggle ativo/inativo**: habilita/desabilita login
- **Zerar 2FA (escudo cortado)**: diálogo de confirmação; remove o 2FA de quem perdeu o autenticador. O usuário refaz o setup no próximo login (aba Meu 2FA).

### Tokens de Serviço

Contas de automação: criação (nome + expiração), **token em claro exibido uma única vez** na criação, copiar para clipboard, revogar (confirmação) e listar.

### Meu 2FA

- **Setup**: gera QR Code + segredo (app autenticador) → código de 6 dígitos para ativar
- **Desabilitar**: exige a senha AD do próprio usuário
- Estado atual exibido com badge (habilitado/desabilitado)

---

## Padrões de UX usados em todo o painel

| Padrão | Onde |
|---|---|
| Busca local com reset de página | todas as tabelas de lista |
| Paginação client-side vs server-side | conforme suporte do endpoint |
| Diálogo de confirmação antes de ação destrutiva | exclusões, revogação, zerar 2FA |
| Spinner por linha durante ação | toggles e exclusões |
| Feedback: banner verde (sucesso) / vermelho (erro) | topo de cada tela |
| Nomes legíveis no lugar de FKs | ativos, apps, clusters, tipos de relacionamento |
| Botões de ação visíveis só para admin | infraestrutura, dados de referência, admin |