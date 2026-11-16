# Integração vRNI (Aria Operations for Networks) — SGTI CMDB

Playbooks Ansible (100% `uri` + Jinja2, sem código externo) que:

1. **Coletam** do VMware Aria Operations for Networks via API `/api/ni` (token de 5 h): inventário de VMs e fluxos de tráfego na janela configurável;
2. **Inferem relacionamentos** casando os IPs dos endpoints dos fluxos com os endereços IP cadastrados no CMDB (`/enderecos-ip`) — casou → cria `Relacionamento` do tipo "Conecta-se a" (POST idempotente em `/relacionamentos`); 
3. **Abrem reconciliação** (`POST /reconciliacoes/inferencia`, fonte `ia`) para IP de endpoint/VM que **não** casou com ativo do CMDB (itens pendentes de verificação dos analistas — quatro olhos), para IP duplicado entre ativos e para IP detectado pelo vRNI sem cadastro;
4. Devolvem estatísticas via `set_stats` para condicionais de *workflow job template* no AAP.

API vRNI **6.13.0** confirmada nos endpoints: `POST /auth/token`, `GET /entities/{vms,flows}` (cursor), `POST /entities/fetch` (lotes ≤ 1000), `POST /search`.

## Arquivos

```
ansible/
├── ansible.cfg
├── inventory/hosts.yml
├── group_vars/all/vrni.yml.example      # exemplo de variáveis (renomeie p/ vrni.yml ou use AAP)
└── playbooks/
    ├── vrni_site.yml                    # sequência completa (coleta + inferência)
    ├── vrni_coleta.yml                  # P1: token, listas paginadas, bulk fetch, artefatos
    ├── vrni_reconciliacao.yml           # P2: match por IP, relacionamentos, reconciliação
    └── tasks/
        ├── vrni_listar.yml              # paginação recursiva por cursor (vRNI)
        ├── vrni_fetch.yml               # bulk fetch em lotes (vRNI)
        └── cmdb_listar.yml              # paginação skip/limit (CMDB)
```

Artefatos da coleta ficam em `/tmp/sgti_vrni/{vms,flows}.json` (pode trocar em `vrni_artifacts_dir`); a inferência os carrega — prefira rodar `vrni_site.yml` como um único Job Template (mesma execução, mesmo workspace do EE).

## Execução manual

```bash
cd ansible
cp group_vars/all/vrni.yml.example group_vars/all/vrni.yml   # edite (token vRNI/CMDB)
ansible-playbook playbooks/vrni_site.yml
# ou separadamente:
ansible-playbook playbooks/vrni_coleta.yml
ansible-playbook playbooks/vrni_reconciliacao.yml
```

Parâmetros úteis (`-e`): `vrni_flows_days=7 vrni_max_flows=50000 vrni_page_size=1000 vrni_artifacts_dir=/tmp/vrni recon_limiar=0.95 vrni_tipo_fluxos="Conecta-se a"`.

Domínio de autenticação: `vrni_domain_type` (padrão `LOCAL`) e, para LDAP, também `vrni_domain_value` — o corpo enviado ao `/auth/token` vira `{"domain": {"domain_type": "LDAP", "value": "seu.dominio"}}`; sem `vrni_domain_value`, envia só `{"domain_type": "LOCAL"}`.

Pré-requisitos no control node / EE: `ansible-core` 2.15+ (nada além dos builtins `ansible.builtin.*`).

## Automatizando no AAP (Automation Platform)

1. **Project**: aponte a este repositório (SCM).
2. **Execution Environment**: padrão do AAP (contém `ansible-core`) é suficiente.
3. **Credential Type** customizado (Administration → Credential Types) — inputs:

   ```yaml
   fields:
     - id: vrni_password
       label: Senha vRNI
       type: string
       secret: true
     - id: cmdb_service_token
       label: Service token CMDB (integracao-zabbix)
       type: string
       secret: true
   injectors:
     env:
       VRNI_PASSWORD: "{{ vrni_password }}"
       CMDB_SERVICE_TOKEN: "{{ cmdb_service_token }}"
   ```

   As variáveis do exemplo leem o segredo do ambiente — crie uma Credential desse tipo (VRNI + CMDB Service Token) e vincule ao Job Template.
4. **Job Templates**:
   - `vRNI — coleta` → `playbooks/vrni_coleta.yml`
   - `vRNI — reconciliação` → `playbooks/vrni_reconciliacao.yml`
   - Ou um único Job Template com `vrni_site.yml`.
5. **Workflow Job Template**: `coleta (success) → reconciliação (success) → notificação dos analistas`. As estatísticas (`set_stats`) ficam no artefato do job de reconciliação: `vrni_reconciliacao_id`, `vrni_pendentes`, `vrni_discrepancias`, `vrni_relacionamentos_criados` — úteis para condicionais/notificações no workflow.

## Mapeamento de discrepâncias → Itens de reconciliação

| Situação vRNI | Item (`action`) | confiança |
|---|---|---|
| IP de endpoint do fluxo sem ativo no CMDB | `localizar_ativo` | 0.0 → pendente |
| IP da VM do vRNI sem cadastro no CMDB | `cadastrar_ip` | 0.0 → pendente |
| Mesmo IP em mais de um ativo | `revisar_ip_duplicado` | 0.0 → pendente |
| Relacionamento criado com sucesso (HTTP 201) | `criar_relacionamento` | 1.0 → auto ratificado |
| Relacionamento já existente (HTTP 200) | — (idempotência) | — |

O tipo usado nos fluxos vem de `vrni_tipo_fluxos` (padrão "Conecta-se a", criado pelo seed do CMDB); se não existir, o playbook falha com mensagem clara.

## Ajustes e limites conhecidos

- Fluxo direcional: A→B e B→A geram relacionamentos distintos (mesma direção do tráfego).
- **Endpoints externos**: com `vrni_ignorar_externos: true` (padrão), fluxos em que um dos lados não tem VM correspondente no vRNI (típico de tráfego de/para internet) são desconsiderados nesta fase — não geram relacionamento nem discrepância. Em `false`, o comportamento anterior volta: o endpoint sem cassamento vira item `localizar_ativo`.
- Tráfego VM→"IP externo": o endpoint externo só casará se o IP existir no CMDB; do contrário vira discrepância (apenas com `vrni_ignorar_externos: false`).
- Fluxos excluídos: origem = destino (mesmo ativo — ruído intra-host) não gera relacionamento.
- Janela padrão de fluxos: 3 dias (`vrni_flows_days`); limite de itens: `vrni_max_flows` (guardas de paginação embutidas).
- `vrni_validate_certs=false` por padrão (vRNI costuma ter certificado interno); ajuste em `group_vars/all/vrni.yml` em produção.
- Token vRNI expira em 5 h — cada execução autentica novamente.
