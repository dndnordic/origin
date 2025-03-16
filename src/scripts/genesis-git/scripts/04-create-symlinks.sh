#!/bin/bash
set -e

# Determine script directory and load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/configs/settings.conf"

# Create symlinks for Gitea
rm -rf /var/lib/gitea && ln -sf $BASE_PATH/gitea/data /var/lib/gitea
rm -rf /etc/gitea && ln -sf $BASE_PATH/gitea/config /etc/gitea
rm -rf /var/log/gitea && ln -sf $BASE_PATH/gitea/logs /var/log/gitea

# Create symlinks for Singularity
rm -rf /var/lib/singularity && ln -sf $BASE_PATH/singularity/data /var/lib/singularity
rm -rf /etc/singularity && ln -sf $BASE_PATH/singularity/config /etc/singularity
rm -rf /var/log/singularity && ln -sf $BASE_PATH/singularity/logs /var/log/singularity

# Create symlinks for Origin
rm -rf /var/lib/origin && ln -sf $BASE_PATH/origin/data /var/lib/origin
rm -rf /etc/origin && ln -sf $BASE_PATH/origin/config /etc/origin
rm -rf /var/log/origin && ln -sf $BASE_PATH/origin/logs /var/log/origin

# Create reference symlinks to PostgreSQL
ln -sf /var/lib/pgsql/data $BASE_PATH/gitea/db
ln -sf /var/log/postgresql $BASE_PATH/gitea/db-logs

# Create symlinks for Build System
ln -sf $BASE_PATH/builds/data /var/lib/builds
ln -sf $BASE_PATH/builds/config /etc/builds
ln -sf $BASE_PATH/builds/logs /var/log/builds

# Create symlinks for Caddy
rm -rf /etc/caddy && ln -sf $BASE_PATH/caddy/config /etc/caddy
rm -rf /var/log/caddy && ln -sf $BASE_PATH/caddy/logs /var/log/caddy
rm -rf /var/lib/caddy && ln -sf $BASE_PATH/caddy/data /var/lib/caddy

# Create symlinks for backups
ln -sf $BASE_PATH/backups/gitea /var/backups/gitea
ln -sf $BASE_PATH/backups/postgres /var/backups/postgres
ln -sf $BASE_PATH/backups/caddy /var/backups/caddy
ln -sf $BASE_PATH/backups/auth /var/backups/auth
ln -sf $BASE_PATH/backups/security /var/backups/security

echo "Symlinks created successfully"