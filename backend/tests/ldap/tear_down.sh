#!/bin/bash
# Para e remove o ambiente LDAP de teste (inclui o volume de dados).
set -e
docker compose down -v
echo "Ambiente LDAP de teste removido."