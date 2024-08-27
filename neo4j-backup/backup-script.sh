#!/bin/bash
set -e

# Set variables
NEO4J_HOST="notello-neo4j-standalone-neo4j"
NEO4J_PORT="6362"
BACKUP_DIR="/backups"
BACKUP_NAME="neo4j-backup-$(date +%Y%m%d-%H%M%S)"

# Perform the backup
neo4j-admin backup --from=${NEO4J_HOST}:${NEO4J_PORT} --backup-dir=${BACKUP_DIR} --name=${BACKUP_NAME}

# Remove backups older than 10 days
find ${BACKUP_DIR} -type d -mtime +10 -exec rm -rf {} +