#!/bin/bash
set -e

# Determine script directory and load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/configs/settings.conf"

# Generate SSH keys for system users and store them in genesis
for user in gitea builder recovery singularity origin genesis; do
  # Create SSH directory
  if [ "$user" == "recovery" ]; then
    SSH_DIR="/home/$user/.ssh"
  else
    SSH_DIR="$BASE_PATH/$user/.ssh"
  fi
  
  mkdir -p "$SSH_DIR"
  
  if [ ! -f "$SSH_DIR/id_ed25519" ]; then
    # Generate SSH key
    ssh-keygen -t ed25519 -f "$SSH_DIR/id_ed25519" -N "" -C "$user@$DOMAIN"
    
    # Copy to genesis repository
    cp "$SSH_DIR/id_ed25519" "$BASE_PATH/genesis/ssh-keys/$user.key"
    cp "$SSH_DIR/id_ed25519.pub" "$BASE_PATH/genesis/ssh-keys/$user.key.pub"
    
    # Add to authorized_keys
    cat "$SSH_DIR/id_ed25519.pub" >> "$SSH_DIR/authorized_keys"
    
    echo "Generated SSH key for $user"
  else
    echo "SSH key for $user already exists, skipping"
  fi
done

# Create SSH config for Genesis to access all users
cat > $BASE_PATH/genesis/.ssh/config << EOF
# SSH configuration for Genesis
Host gitea-local
  HostName localhost
  User gitea
  Port 22
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking no

Host origin-local
  HostName localhost
  User origin
  Port 22
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking no

Host singularity-local
  HostName localhost
  User singularity
  Port 22
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking no

Host builder-local
  HostName localhost
  User builder
  Port 22
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking no

Host recovery-local
  HostName localhost
  User recovery
  Port 22
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking no
EOF

# Setup SSH for emergency access
mkdir -p /etc/ssh/sshd_config.d
cat > $BASE_PATH/security/ssh/emergency.conf << EOF
# Emergency access port
Port 2222
Match User recovery
    PasswordAuthentication no
    PubkeyAuthentication yes
EOF

ln -sf $BASE_PATH/security/ssh/emergency.conf /etc/ssh/sshd_config.d/emergency.conf

# Setup SSH for mhugo (but don't generate keys)
mkdir -p /home/mhugo/.ssh
touch /home/mhugo/.ssh/authorized_keys
chmod 700 /home/mhugo/.ssh
chmod 600 /home/mhugo/.ssh/authorized_keys
chown -R mhugo:mhugo /home/mhugo/.ssh

echo "SSH configuration completed successfully"