# Procedimento: Disco Cheio em Servidor Linux

## Diagnóstico

Quando o Zabbix dispara o alarme `Free disk space is less than 10%` ou
`Free inodes is less than 10%` em um servidor Linux, verificar:

1. Uso atual do disco: `df -h`
2. Inodes: `df -i`
3. Maiores diretórios: `du -h --max-depth=2 / 2>/dev/null | sort -rh | head -20`

## Ação Corretiva

### Limpeza de logs

```bash
# Truncar logs grandes sem reiniciar serviços
truncate -s 0 /var/log/syslog.1
journalctl --vacuum-size=500M
find /var/log -name "*.gz" -mtime +30 -delete
```

### Limpeza de pacotes

```bash
apt-get clean
apt-get autoremove -y
docker system prune -f   # se houver docker
```

## Escalonamento

Escalar para COINF se:
- Partição `/` acima de 90% após limpeza
- Crescimento causado por banco de dados (envolver DBA)
- Necessário redimensionamento de volume LVM

## Referências

- Documentação Zabbix trigger: "Space is not available"
- Runbook interno SGTI-PROC-001