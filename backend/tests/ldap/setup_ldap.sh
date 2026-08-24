#!/bin/bash
# This script populates the OpenLDAP container with test users and groups

CONTAINER_NAME="openldap_test"

echo "Waiting for LDAP to be ready..."
until curl -s http://localhost:8080 > /dev/null; do
  sleep 2
done

echo "Adding Groups..."
# Group for Admin
ldapadd -x -D "cn=admin,dc=energia,dc=org,dc=br" -w admin -f - <<EOF
dn: cn=G_GESIN_GOSD_OMIS,ou=groups,dc=energia,dc=org,dc=br
objectClass: groupOfNames
cn: G_GESIN_GOSD_OMIS
member: cn=admin,dc=energia,dc=org,dc=br
EOF

# Group for Read
ldapadd -x -D "cn=admin,dc=energia,dc=org,dc=br" -w admin -f - <<EOF
dn: cn=G_GESIN,ou=groups,dc=energia,dc=org,dc=br
objectClass: groupOfNames
cn: G_GESIN
member: cn=testuser,ou=people,dc=energia,dc=org,dc=br
EOF

echo "Adding Organizational Units..."
ldapadd -x -D "cn=admin,dc=energia,dc=org,dc=br" -w admin -f - <<EOF
dn: ou=people,dc=energia,dc=org,dc=br
objectClass: organizationalUnit
ou: people
---
dn: ou=groups,dc=energia,dc=org,dc=br
objectClass: organizationalUnit
ou: groups
EOF

echo "Adding Users..."
# Admin User
ldapadd -x -D "cn=admin,dc=energia,dc=org,dc=br" -w admin -f - <<EOF
dn: cn=admin,ou=people,dc=energia,dc=org,dc=br
objectClass: inetOrgPerson
objectClass: posixAccount
cn: admin
sn: Admin
uid: admin
sAMAccountName: admin
userPassword: admin
uidNumber: 1000
gidNumber: 1000
homeDirectory: /home/admin
EOF

# Read User
ldapadd -x -D "cn=admin,dc=energia,dc=org,dc=br" -w admin -f - <<EOF
dn: cn=testuser,ou=people,dc=energia,dc=org,dc=br
objectClass: inetOrgPerson
objectClass: posixAccount
cn: testuser
sn: Test User
uid: testuser
sAMAccountName: testuser
userPassword: password
uidNumber: 1001
gidNumber: 1001
homeDirectory: /home/testuser
EOF

echo "LDAP Setup Complete!"
