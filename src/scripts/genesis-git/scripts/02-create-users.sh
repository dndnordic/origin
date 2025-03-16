#!/bin/bash
set -e

# Determine script directory and load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/configs/settings.conf"

# Create system users if they don't exist
id -u gitea &>/dev/null || useradd -r -u $GITEA_UID -m -d $BASE_PATH/gitea -s /bin/bash gitea
id -u builder &>/dev/null || useradd -r -u $BUILDER_UID -m -d $BASE_PATH/builds -s /bin/bash builder
id -u recovery &>/dev/null || useradd -u $RECOVERY_UID -m -d /home/recovery -s /bin/bash recovery
id -u mhugo &>/dev/null || useradd -m -d /home/mhugo -s /bin/bash mhugo
id -u singularity &>/dev/null || useradd -r -u $SINGULARITY_UID -m -d $BASE_PATH/singularity -s /bin/bash singularity
id -u origin &>/dev/null || useradd -r -u $ORIGIN_UID -m -d $BASE_PATH/origin -s /bin/bash origin
id -u genesis &>/dev/null || useradd -r -u $GENESIS_UID -m -d $BASE_PATH/genesis -s /bin/bash genesis

# Add mhugo to sudo/wheel group
usermod -aG wheel mhugo

# Create isolation groups
groupadd -f docker-origin
groupadd -f docker-singularity

# Add users to appropriate groups
usermod -aG docker-origin origin
usermod -aG docker-singularity singularity
usermod -aG docker mhugo
usermod -aG docker builder
usermod -aG docker genesis

# Add subuid and subgid mappings for user namespace isolation
grep -q "^singularity:" /etc/subuid || echo "singularity:100000:65536" >> /etc/subuid
grep -q "^singularity:" /etc/subgid || echo "singularity:100000:65536" >> /etc/subgid
grep -q "^origin:" /etc/subuid || echo "origin:200000:65536" >> /etc/subuid
grep -q "^origin:" /etc/subgid || echo "origin:200000:65536" >> /etc/subgid

echo "System users created successfully"