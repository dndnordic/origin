#!/bin/bash
set -e

# Display banner
echo "=========================================================="
echo "     Genesis Infrastructure Initial Installation Script   "
echo "=========================================================="
echo ""
echo "This script will set up the entire Genesis infrastructure"
echo "including Gitea, Origin, and Singularity environments"
echo ""

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
  echo "Error: This script must be run as root"
  exit 1
fi

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source configuration
if [ -f "${SCRIPT_DIR}/configs/settings.conf" ]; then
  source "${SCRIPT_DIR}/configs/settings.conf"
else
  echo "Error: Configuration file not found"
  exit 1
fi

# Create directory structure
echo "Creating directory structure..."
${SCRIPT_DIR}/scripts/01-create-directories.sh

# Create users
echo "Creating system users..."
${SCRIPT_DIR}/scripts/02-create-users.sh

# Configure SSH
echo "Setting up SSH keys and configurations..."
${SCRIPT_DIR}/scripts/03-setup-ssh.sh

# Create symlinks
echo "Creating symlinks..."
${SCRIPT_DIR}/scripts/04-create-symlinks.sh

# Set up PostgreSQL
echo "Setting up PostgreSQL..."
${SCRIPT_DIR}/scripts/05-setup-postgres.sh

# Set up Docker environments
echo "Setting up Docker environments..."
${SCRIPT_DIR}/scripts/06-setup-docker.sh

# Set up Gitea
echo "Setting up Gitea..."
${SCRIPT_DIR}/scripts/07-setup-gitea.sh

# Set up Caddy
echo "Setting up Caddy web server..."
${SCRIPT_DIR}/scripts/08-setup-caddy.sh

# Configure backup system
echo "Configuring backup system..."
${SCRIPT_DIR}/scripts/09-setup-backups.sh

# Setup services
echo "Setting up systemd services..."
${SCRIPT_DIR}/scripts/10-setup-services.sh

# Set permissions
echo "Setting appropriate permissions..."
${SCRIPT_DIR}/scripts/11-set-permissions.sh

# Verify installation
echo "Verifying installation..."
${SCRIPT_DIR}/scripts/12-verify-installation.sh

echo ""
echo "=========================================================="
echo "     Genesis Installation Complete!                      "
echo "=========================================================="
echo ""
echo "You can now access Gitea at: https://${DOMAIN}"
echo ""
echo "Next steps:"
echo "1. Add mhugo's SSH key to /home/mhugo/.ssh/authorized_keys"
echo "2. Configure repositories in Gitea"
echo "3. Set up the build system webhooks"
echo ""