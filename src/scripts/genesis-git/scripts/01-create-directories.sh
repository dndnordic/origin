#!/bin/bash
set -e

# Determine script directory and load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/configs/settings.conf"

# Create main directories
mkdir -p $BASE_PATH/gitea/{data,config,logs,scripts}
mkdir -p $BASE_PATH/builds/{data,config,logs,workspaces,scripts}
mkdir -p $BASE_PATH/caddy/{config,logs,data}
mkdir -p $BASE_PATH/auth/{keys/{gitea,origin,singularity,builder,recovery},config}
mkdir -p $BASE_PATH/security/{ssh,firewall,emergency,certs}
mkdir -p $BASE_PATH/monitoring/{prometheus,grafana,alerts,logs}
mkdir -p $BASE_PATH/backups/{gitea/{repos,config,daily,weekly,monthly},postgres/{dumps,wal},builds/config,system/etc,caddy/{config,certs},auth,security,monitoring}
mkdir -p $BASE_PATH/singularity/{data,logs,config,scripts}
mkdir -p $BASE_PATH/origin/{data,logs,config,scripts}
mkdir -p $BASE_PATH/genesis/{ssh-keys,scripts,config,logs}

# Create standard directories if they don't exist
mkdir -p /var/lib/gitea /etc/gitea /var/log/gitea
mkdir -p /var/lib/builds /etc/builds /var/log/builds
mkdir -p /etc/caddy /var/log/caddy /var/lib/caddy
mkdir -p /var/lib/singularity /var/log/singularity /etc/singularity
mkdir -p /var/lib/origin /var/log/origin /etc/origin
mkdir -p /var/backups/{gitea,postgres,caddy,auth,security}

echo "Directory structure created successfully"