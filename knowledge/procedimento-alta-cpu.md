# Procedimento: Alta de CPU em Servidor

## Diagnóstico

Alarme relacionado: `CPU utilization is too high` ou `Load average is too high`.

Passos iniciais:

1. Identificar processos com maior consumo: `top -b -n1 | head -30`
2. Verificar load average histórico: `sar -q | tail -10`
3. Verificar processos em D state: `ps -eo state,pid,cmd | grep "^D"`

## Causas Comuns

- Backup executando em horário de pico
- Consultas SQL pesadas (verificar se host depende de banco no CMDB)
- Compilação/pipeline CI executando no servidor errado
- Ataque ou varredura (verificar conexões: `ss -tn state established | wc -l`)

## Ação Corretiva

1. Identificar o processo responsável com `pidstat -u 1 5`
2. Se for processo conhecido de manutenção, aguardar conclusão
3. Se for processo órfão/desconhecido, avaliar `kill -TERM <pid>` após aprovação
4. Documentar no ticket a causa raiz encontrada

## Escalonamento

- Escalar para a área responsável pela aplicação (verificar CMDB)
- Se o host for crítico no CMDB, abrir ponte com GOSD

## Referências

- Runbook interno SGTI-PROC-002