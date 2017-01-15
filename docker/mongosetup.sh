#!/bin/bash
set -m
set -e

[ -z "$MONGODB_ADMIN_PASS" ] && echo "Please provide an admin password (MONGODB_ADMIN_PASS)!" && exit 1
[ -z "$MONGODB_RW_PASS" ] && echo "Please provide a read/write user password (MONGODB_RW_PASS)!" && exit 1
[ -z "$MONGODB_RO_PASS" ] && echo "Please provide a read-only user password (MONGODB_RO_PASS)!" && exit 1

cmd="mongod --auth"

$cmd &

MONGODB_ADMIN=${MONGODB_ADMIN:-"admin"}
MONGODB_DBNAME=${MONGODB_DBNAME:-"test"}
MONGODB_RW_USER=${MONGODB_RW_USER:-"rwusr"}
MONGODB_RO_USER=${MONGODB_RO_USER:-"rousr"}

DBDOWN=1
while [[ DBDOWN -ne 0 ]]; do
    echo "Waiting for MongoDB availability..."
    sleep 3
    mongo admin --eval "help" > /dev/null 2>&1
    DBDOWN=$?
done

echo "Creating admin user"
mongo admin --eval "db.createUser({ user: '$MONGODB_ADMIN', pwd: '$MONGODB_ADMIN_PASS', roles: [ { role: 'root', db: 'admin' } ] });"

# dbOwner
echo "Creating read/write user ${MONGODB_RW_USER} for database ${MONGODB_DBNAME}"
mongo admin -u $MONGODB_ADMIN -p $MONGODB_ADMIN_PASS << EOF
use $MONGODB_DBNAME
db.createUser({user: '$MONGODB_RW_USER', pwd: '$MONGODB_RW_PASS', roles:[{role:'readWrite',db:'$MONGODB_DBNAME'}]})
EOF

echo "Creating read-only user ${MONGODB_RO_USER} for database ${MONGODB_DBNAME}"
mongo admin -u $MONGODB_ADMIN -p $MONGODB_ADMIN_PASS << EOF
use $MONGODB_DBNAME
db.createUser({user: '$MONGODB_RO_USER', pwd: '$MONGODB_RO_PASS', roles:[{role:'read',db:'$MONGODB_DBNAME'}]})
EOF

fg
