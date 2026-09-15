#!/bin/bash
# Sobe e popula o OpenLDAP de teste (os dados base já entram via estrutura.ldif
# montada no container). Este script valida o ambiente e aplica o LDIF de apoio
# (grupos extras), além de conferir o bind de cada usuário de teste.

set -e

CONTAINER_NAME="openldap_test"
ADMIN_DN="cn=admin,dc=lacstech,dc=local"
ADMIN_PW="admin"
BASE_DN="dc=lacstech,dc=local"

echo "=== 1. Subindo containers ==="
docker compose up -d

echo "=== 2. Aguardando LDAP ficar pronto ==="
for i in $(seq 1 30); do
  if docker exec "$CONTAINER_NAME" ldapsearch -x -H ldap://localhost:389 \
      -D "$ADMIN_DN" -w "$ADMIN_PW" -b "$BASE_DN" "(objectClass=organization)" >/dev/null 2>&1; then
    echo "LDAP pronto (tentativa $i)"
    break
  fi
  sleep 2
  if [ "$i" -eq 30 ]; then
    echo "ERRO: LDAP não ficou pronto a tempo"
    docker logs "$CONTAINER_NAME" | tail -20
    exit 1
  fi
done

echo "=== 3. Verificando estrutura carregada via LDIF ==="
docker exec "$CONTAINER_NAME" ldapsearch -x -H ldap://localhost:389 \
  -D "$ADMIN_DN" -w "$ADMIN_PW" -b "ou=users,$BASE_DN" "(objectClass=*)" dn \
  | grep "^dn:" || { echo "ERRO: usuários não encontrados — estrutura.ldif não carregada"; exit 1; }

echo "=== 4. Testando binds dos usuários ==="
for cred in "uid=lucio,ou=users,$BASE_DN:Admin123:lucio" \
            "uid=analista,ou=users,$BASE_DN:Analista123:analista" \
            "uid=estagio,ou=users,$BASE_DN:Estagio123:estagio"; do
  DN=$(echo "$cred" | cut -d: -f1)
  PW=$(echo "$cred" | cut -d: -f2)
  USER=$(echo "$cred" | cut -d: -f3)
  if docker exec "$CONTAINER_NAME" ldapwhoami -x -H ldap://localhost:389 \
      -D "$DN" -w "$PW" >/dev/null 2>&1; then
    echo "OK  bind: $USER"
  else
    echo "ERRO bind: $USER ($DN)"
    exit 1
  fi
done

echo "=== 5. Conferindo grupos (memberOf) ==="
docker exec "$CONTAINER_NAME" ldapsearch -x -H ldap://localhost:389 \
  -D "$ADMIN_DN" -w "$ADMIN_PW" -b "ou=users,$BASE_DN" "(uid=lucio)" memberOf \
  | grep "memberOf" || echo "AVISO: lucio sem memberOf"

echo ""
echo "LDAP de teste pronto!"
echo "  URL:      ldap://127.0.0.1:389 (network_mode host)"
echo "  Base DN:  $BASE_DN"
echo "  Admin:    cn=admin,dc=lacstech,dc=local / admin"
echo "  Usuários: lucio@lacstech.local/Admin123 (admin) | analista@lacstech.local/Analista123 (read) | estagio@lacstech.local/Estagio123 (viewer)"
echo "  phpLDAPadmin: http://localhost:8080"