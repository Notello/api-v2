#!/bin/bash
set -e

# Set variables
NEO4J_URI="neo4j://my-neo4j-release:6362"
NEO4J_USER="neo4j"  # Replace with your actual username
NEO4J_PASSWORD="fJ72xFm2jbvBIo"  # Replace with your actual password
BACKUP_DIR="/backups"
BACKUP_NAME="neo4j-backup-$(date +%Y%m%d-%H%M%S)"

# Perform the backup
neo4j-admin database dump neo4j \
  --to-path=${BACKUP_DIR} \
  --overwrite-destination=true \
  --from=${NEO4J_URI} \
  --username=${NEO4J_USER} \
  --password=${NEO4J_PASSWORD}

# Rename the backup file to include timestamp
mv ${BACKUP_DIR}/neo4j.dump ${BACKUP_DIR}/${BACKUP_NAME}.dump

# Remove backups older than 10 days
find ${BACKUP_DIR} -name "neo4j-backup-*.dump" -type f -mtime +10 -delete

echo "Backup completed successfully"