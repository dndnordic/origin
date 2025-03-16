#!/bin/bash
set -e

# Determine script directory and load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/configs/settings.conf"

# Create Gitea service file
cat > /etc/systemd/system/gitea.service << EOF
[Unit]
Description=Gitea (Git with a cup of tea)
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=gitea
Group=gitea
WorkingDirectory=$BASE_PATH/gitea/
Environment=USER=gitea HOME=$BASE_PATH/gitea GITEA_WORK_DIR=$BASE_PATH/gitea
ExecStart=/usr/local/bin/gitea web --config $BASE_PATH/gitea/config/app.ini
Restart=always
RestartSec=2s
Type=simple
WatchdogSec=30s

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for Docker Origin
cat > /etc/systemd/system/docker-origin.service << EOF
[Unit]
Description=Docker Application Container Engine (Origin Context)
Documentation=https://docs.docker.com
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/bin/dockerd --config-file=/etc/docker/contexts/origin/daemon.json --host unix:///var/run/docker-origin.sock
ExecReload=/bin/kill -s HUP \$MAINPID
TimeoutSec=0
RestartSec=2
Restart=always
User=origin
Group=docker-origin
WorkingDirectory=$BASE_PATH/origin
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for Docker Singularity
cat > /etc/systemd/system/docker-singularity.service << EOF
[Unit]
Description=Docker Application Container Engine (Singularity Context)
Documentation=https://docs.docker.com
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/bin/dockerd --config-file=/etc/docker/contexts/singularity/daemon.json --host unix:///var/run/docker-singularity.sock
ExecReload=/bin/kill -s HUP \$MAINPID
TimeoutSec=0
RestartSec=2
Restart=always
User=singularity
Group=docker-singularity
WorkingDirectory=$BASE_PATH/singularity
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
EOF

# Reload daemon and enable services
systemctl daemon-reload
systemctl enable gitea
systemctl enable caddy
systemctl enable docker-origin
systemctl enable docker-singularity

echo "Services setup completed successfully"