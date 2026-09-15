# Procedimento: Problemas de Memória (Out of Memory / Swap)

## Diagnóstico

Alarmes relacionados: `Out of memory (OOM)`, `Memory usage is too high`,
`Swap is being used`.

1. Verificar consumo atual: `free -h`
2. Identificar maiores consumidores: `ps aux --sort=-%mem | head -15`
3. Verificar eventos OOM no kernel: `dmesg | grep -i "out of memory"`
4. Verificar swap: `swapon --show`

## Ação Corretiva

1. Identificar o processo que disparou o OOM killer no `dmesg`
2. Se for vazamento conhecido da aplicação, reiniciar a instância
   seguindo o procedimento da aplicação
3. Ajustar limites de memória (systemd/cgroup/docker) se aplicável
4. Propor aumento de RAM se o padrão se repetir (abrir chamado para COINF)

## Atenção

- Servidores PostgreSQL: verificar `work_mem`, `shared_buffers` e `effective_cache_size`
- Java: verificar parâmetros `-Xmx` da JVM

## Escalonamento

- OOM recorrente: escalar para a área da aplicação (verificar CMDB)
- Banco de dados: envolver DBA/COINF

## Referências

- Runbook interno SGTI-PROC-004