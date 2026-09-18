# Documentação — SGTI CMDB

Índice da documentação de funcionalidades e usabilidade. Para instalação, veja o [README](../README.md). Referência completa de endpoints no Swagger (`http://localhost:8000/docs`).

| Documento | Conteúdo |
|---|---|
| [funcionalidades.md](funcionalidades.md) | Visão geral do sistema: módulos, modelo de dados e conceitos |
| [frontend.md](frontend.md) | Guia de usabilidade de cada tela do painel |
| [autenticacao-2fa.md](autenticacao-2fa.md) | Login AD, 2FA TOTP, habilitação e suporte (zerar 2FA) |
| [inferencias.md](inferencias.md) | Como funcionam a importação e a inferência do mapa de TI |

## Visão geral em 1 minuto

O SGTI CMDB gerencia **ativos de TI** (servidores físicos e virtuais), seus **endereços IP**, **aplicações** de negócio e a malha de **infraestrutura** que os conecta: clusters, namespaces, serviços técnicos, serviços de negócio, instâncias de aplicação e relacionamentos tipados.

O modelo de operação é dividido em dois fluxos:

1. **Automações (escrita)** — coletadores descobrem e atualizam o CMDB via API usando service tokens (ex.: integração Zabbix, inventário de servidores). Endpoints de criação aceitam `X-Service-Token` ou JWT de usuário.
2. **Painel web (leitura + correção)** — usuários AD autenticados (com 2FA opcional) consultam o mapa de TI; perfis **admin** podem retificar ou excluir qualquer item de infraestrutura manualmente, com tudo registrado em auditoria.

O mapa de TI pode ser **semeado por inferência** a partir de dados importados: descrições de ativos geram serviços, aplicações casadas com hosts geram instâncias, e dependências citadas em documentação geram relacionamentos — sempre idempotente, sempre via API (ver [inferencias.md](inferencias.md)).

## Perfis e permissões

| Perfil | Origem | Pode |
|---|---|---|
| admin | grupo AD mapeado em `ROLE_ADMIN` | tudo: dados mestres, usuários, zerar 2FA, edição manual de infraestrutura |
| analyst / reviewer / reconciliator / revisor | grupos AD | operações de dados e reconciliação |
| viewer | default | somente leitura |

A edição manual de infraestrutura (serviços, serviços de negócio, instâncias, relacionamentos) é exclusiva de **admin** e sempre grava audit log.