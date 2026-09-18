# Autenticação, 2FA e suporte

## Fluxo de login

```
Usuário + senha → POST /auth/ad/login
        │
        ├── credenciais inválidas → erro
        │
        ├── usuário SEM 2FA → tokens emitidos → sessão iniciada
        │
        └── usuário COM 2FA (totp_enabled) → resposta requires_2fa=true
            SEM tokens (nada é emitido antes do segundo fator)
                │
                └── POST /auth/2fa/login (mesmas credenciais + código TOTP)
                        ├── código válido → tokens emitidos → sessão
                        └── código inválido/expirado → 401, nova tentativa
```

Pontos de segurança:

- A senha da etapa 2FA fica **apenas em memória** no frontend (nunca em localStorage); é descartada ao voltar para "Usar outra conta"
- O backend **não emite tokens** na primeira etapa quando o 2FA está ativo — sem código TOTP não há sessão
- O código TOTP aceita janela de ±30s (`valid_window=1`) para tolerar atraso de relógio

## Habilitar 2FA (autoatendimento)

1. Login → **Administração → Meu 2FA**
2. **Gerar QR Code**: backend gera segredo aleatório (base32), o persiste **cifrado** (AES-256-GCM) e retorna QR + URI de provisionamento (issuer "SGTI CMDB")
3. Escanear com app autenticador (Google Authenticator, FreeOTP, etc.)
4. Digitar o código atual → `POST /auth/2fa/verify` → 2FA **habilitado**
5. No próximo login, o código será exigido

## Desabilitar 2FA

- **Autoatendimento**: Meu 2FA → Desabilitar, exigindo a **senha AD** (revalida credenciais)
- **Suporte por admin** (usuário perdeu o autenticador): Administração → Usuários → botão escudo cortado na linha do usuário → confirmação → `POST /auth/admin/users/{id}/2fa/disable` zera `totp_enabled` **e** apaga o segredo. O usuário loga só com senha e refaz o setup em Meu 2FA.

## Tokens de serviço (automações)

Criados em Administração → Tokens de Serviço (`POST /auth/admin/tokens`, admin):

- Token gerado com `secrets.token_urlsafe(43)`, **exibido uma única vez**, hash bcrypt no banco
- Expiração padrão de 1 ano (configurável)
- Uso: header `X-Service-Token: <token>`
- Revogação: exclusão lógica via lista (ou DELETE do endpoint admin)

## Tokens JWT

| Token | Validade | Uso |
|---|---|---|
| access | 30 min (config.) | chamadas da API |
| refresh | 7 dias | renovação automática pelo interceptor |

O frontend renova o access token automaticamente em 401 (uma tentativa por request); falha de refresh → logout.

## Perfis via grupos AD

No primeiro login o usuário é criado localmente com os perfis derivados dos grupos AD (mapeamento em `ROLE_*` no `.env`). Admin pode ativar/desativar contas e ajustar perfis em Administração → Usuários.