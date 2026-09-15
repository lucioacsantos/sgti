# Procedimento: Serviço ou Host Indisponível (Down)

## Diagnóstico

Alarmes relacionados: `Service is down`, `ICMP ping is unreachable`, `HTTP service is down`.

1. Verificar se o host responde: `ping <host>` e `traceroute <host>`
2. Verificar a porta do serviço: `nc -zv <host> <porta>`
3. Consultar no CMDB o ambiente (Produção/Homologação) e a criticidade
4. Verificar se há manutenção agendada na janela atual
5. Verificar dependências no CMDB (o host depende de qual banco/serviço?)

## Ação Corretiva

### Serviço web (nginx/apache)

```bash
systemctl status nginx
systemctl restart nginx
journalctl -u nginx --since "30 min ago"
```

### Servidor de aplicação

1. Verificar espaço em disco e memória antes de reiniciar
2. Reiniciar a instância conforme procedimento da aplicação
3. Validar saúde após restart (health check)

### Banco de dados

- NÃO reiniciar banco de produção sem aprovação do DBA
- Verificar conexões ativas: `pg_stat_activity` (PostgreSQL)

## Impacto

- Hosts críticos no CMDB com relacionamento "Depende de" podem causar
  indisponibilidade em cascata — avaliar os dependentes antes de qualquer ação.

## Escalonamento

- Produção crítica: abrir ponte imediata com GOSD e COINF
- Homologação: escalar para CODEV no horário comercial

## Referências

- Runbook interno SGTI-PROC-003