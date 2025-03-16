#!/bin/bash
set -e

# Determine script directory and load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/configs/settings.conf"

# Check if Caddy is already installed
if command -v caddy &> /dev/null; then
    echo "Caddy is already installed, skipping..."
else
    # Install Caddy
    echo "Installing Caddy..."
    dnf -y install yum-utils
    dnf config-manager --add-repo https://copr.fedorainfracloud.org/coprs/g/caddy/caddy/repo/epel-9/group_caddy-caddy-epel-9.repo
    dnf -y install caddy
fi

# Create Caddy configuration for Gitea with the external hostname
mkdir -p $BASE_PATH/caddy/config
cat << EOF > $BASE_PATH/caddy/config/Caddyfile
$DOMAIN {
    reverse_proxy localhost:3000
    tls {
        protocols tls1.2 tls1.3
        prefer_server_ciphers
    }
    log {
        output file $BASE_PATH/caddy/logs/gitea.log
    }
}
EOF

# Create log directory
mkdir -p $BASE_PATH/caddy/logs
mkdir -p $BASE_PATH/caddy/data

# Set proper ownership
chown -R caddy:caddy $BASE_PATH/caddy

echo "Caddy setup completed successfully"