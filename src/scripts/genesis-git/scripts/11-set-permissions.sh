#!/bin/bash
set -e

# Determine script directory and load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/configs/settings.conf"

# Set appropriate permissions
chown -R gitea:gitea $BASE_PATH/gitea
chmod -R 750 $BASE_PATH/gitea
chown -R postgres:postgres $BASE_PATH/backups/postgres
chmod -R 750 $BASE_PATH/backups/postgres
chown -R caddy:caddy $BASE_PATH/caddy
chmod -R 750 $BASE_PATH/caddy
chown -R caddy:caddy $BASE_PATH/backups/caddy
chmod -R 750 $BASE_PATH/backups/caddy
chown -R builder:builder $BASE_PATH/builds
chmod -R 750 $BASE_PATH/builds
chown -R root:root $BASE_PATH/security
chmod -R 750 $BASE_PATH/security
chown -R root:root $BASE_PATH/auth
chmod -R 750 $BASE_PATH/auth
chown -R mhugo:mhugo /home/mhugo
chown -R recovery:recovery /home/recovery
chown -R origin:docker-origin $BASE_PATH/origin
chmod -R 750 $BASE_PATH/origin
chown -R singularity:docker-singularity $BASE_PATH/singularity
chmod -R 750 $BASE_PATH/singularity
chown -R genesis:genesis $BASE_PATH/genesis
chmod -R 750 $BASE_PATH/genesis

# Genesis has read access to all keys
chmod -R 640 $BASE_PATH/genesis/ssh-keys
chown -R genesis:genesis $BASE_PATH/genesis/ssh-keys

# Set SSH permissions
find /home/recovery/.ssh -type f -name "*.pub" -exec chmod 644 {} \;
find /home/recovery/.ssh -type f -name "id_*" ! -name "*.pub" -exec chmod 600 {} \;
find $BASE_PATH/gitea/.ssh -type f -name "*.pub" -exec chmod 644 {} \;
find $BASE_PATH/gitea/.ssh -type f -name "id_*" ! -name "*.pub" -exec chmod 600 {} \;
find $BASE_PATH/origin/.ssh -type f -name "*.pub" -exec chmod 644 {} \;
find $BASE_PATH/origin/.ssh -type f -name "id_*" ! -name "*.pub" -exec chmod 600 {} \;
find $BASE_PATH/singularity/.ssh -type f -name "*.pub" -exec chmod 644 {} \;
find $BASE_PATH/singularity/.ssh -type f -name "id_*" ! -name "*.pub" -exec chmod 600 {} \;
find $BASE_PATH/genesis/.ssh -type f -name "*.pub" -exec chmod 644 {} \;
find $BASE_PATH/genesis/.ssh -type f -name "id_*" ! -name "*.pub" -exec chmod 600 {} \;
find $BASE_PATH/builder/.ssh -type f -name "*.pub" -exec chmod 644 {} \;
find $BASE_PATH/builder/.ssh -type f -name "id_*" ! -name "*.pub" -exec chmod 600 {} \;

echo "Permissions set successfully"