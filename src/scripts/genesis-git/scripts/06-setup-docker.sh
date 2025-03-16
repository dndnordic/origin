#!/bin/bash
set -e

# Determine script directory and load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/configs/settings.conf"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    dnf -y install yum-utils
    dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo
    dnf -y install docker-ce docker-ce-cli containerd.io
    
    # Start and enable Docker service
    systemctl enable docker
    systemctl start docker
fi

# Create Docker daemon configurations for isolation
mkdir -p /etc/docker/contexts/origin
mkdir -p /etc/docker/contexts/singularity

# Create Docker daemon configuration for Singularity
cat > /etc/docker/contexts/singularity/daemon.json << EOF
{
  "userns-remap": "singularity",
  "data-root": "$BASE_PATH/singularity/docker",
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "default-runtime": "runc",
  "runtimes": {
    "restricted": {
      "path": "/usr/bin/runc",
      "runtimeArgs": [
        "--cpu-quota=80000",
        "--memory=4G",
        "--pids-limit=100",
        "--cpu-shares=1024"
      ]
    }
  }
}
EOF

# Create Docker daemon configuration for Origin
cat > /etc/docker/contexts/origin/daemon.json << EOF
{
  "userns-remap": "origin",
  "data-root": "$BASE_PATH/origin/docker",
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "default-runtime": "runc",
  "runtimes": {
    "restricted": {
      "path": "/usr/bin/runc",
      "runtimeArgs": [
        "--cpu-quota=80000",
        "--memory=8G",
        "--pids-limit=200",
        "--cpu-shares=2048"
      ]
    }
  }
}
EOF

# Create script to run Docker commands in Origin context
cat > $BASE_PATH/origin/scripts/docker-origin << 'EOF'
#!/bin/bash
docker --context origin "$@"
EOF
chmod +x $BASE_PATH/origin/scripts/docker-origin

# Create script to run Docker commands in Singularity context
cat > $BASE_PATH/singularity/scripts/docker-singularity << 'EOF'
#!/bin/bash
docker --context singularity "$@"
EOF
chmod +x $BASE_PATH/singularity/scripts/docker-singularity

# Create Docker context for Origin
cat > $BASE_PATH/origin/scripts/setup-origin-context.sh << 'EOF'
#!/bin/bash
docker context create origin --description "Origin isolated context" --docker "host=unix:///var/run/docker-origin.sock"
EOF
chmod +x $BASE_PATH/origin/scripts/setup-origin-context.sh

# Create Docker context for Singularity
cat > $BASE_PATH/singularity/scripts/setup-singularity-context.sh << 'EOF'
#!/bin/bash
docker context create singularity --description "Singularity isolated context" --docker "host=unix:///var/run/docker-singularity.sock"
EOF
chmod +x $BASE_PATH/singularity/scripts/setup-singularity-context.sh

# Create directories for Docker data
mkdir -p $BASE_PATH/origin/docker
mkdir -p $BASE_PATH/singularity/docker

echo "Docker environment setup completed successfully"