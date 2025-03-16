#!/bin/bash
set -e

# Display banner
echo "=========================================================="
echo "     Genesis Infrastructure Removal Script                "
echo "=========================================================="
echo ""
echo "This script will remove the Genesis infrastructure components"
echo "with the option to preserve data"
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
  # Default settings if config not found
  BASE_PATH="/opt"
  echo "Warning: Configuration file not found, using default settings"
fi

# Ask about data preservation
preserve_data=false
read -p "Do you want to preserve data (repositories, database, config)? (y/N): " preserve
if [[ "$preserve" =~ ^[Yy]$ ]]; then
  preserve_data=true
  echo "Data will be preserved during removal."
else
  echo "WARNING: All data will be permanently removed!"
  read -p "Are you sure you want to continue? (y/N): " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Removal canceled."
    exit 0
  fi
fi

# Stop services
echo "Stopping services..."
systemctl stop gitea docker-origin docker-singularity caddy 2>/dev/null || true
systemctl disable gitea docker-origin docker-singularity caddy 2>/dev/null || true

# Remove systemd service files
echo "Removing service files..."
rm -f /etc/systemd/system/gitea.service 
rm -f /etc/systemd/system/docker-origin.service
rm -f /etc/systemd/system/docker-singularity.service
systemctl daemon-reload

# Remove Docker contexts
echo "Removing Docker contexts..."
docker context rm origin 2>/dev/null || true
docker context rm singularity 2>/dev/null || true
rm -rf /etc/docker/contexts

# Remove cron jobs
echo "Removing cron jobs..."
rm -f /etc/cron.d/gitea-backup

# Remove binaries and scripts
echo "Removing binaries and scripts..."
rm -f /usr/local/bin/gitea-backup.sh
[ "$preserve_data" = false ] && rm -f /usr/local/bin/gitea

# Remove directories based on preservation choice
if [ "$preserve_data" = true ]; then
  echo "Preserving data directories..."
  # Only remove non-data directories
  rm -rf $BASE_PATH/auth
  rm -rf $BASE_PATH/security
  
  echo "Disconnecting symlinks..."
  # Remove symlinks but keep the actual data
  rm -f /var/lib/gitea
  rm -f /etc/gitea
  rm -f /var/log/gitea
  rm -f /var/lib/singularity
  rm -f /etc/singularity
  rm -f /var/log/singularity
  rm -f /var/lib/origin
  rm -f /etc/origin
  rm -f /var/log/origin
  rm -f /etc/caddy
  rm -f /var/log/caddy
  rm -f /var/lib/caddy
  rm -f /var/lib/builds
  rm -f /etc/builds
  rm -f /var/log/builds
  
  echo "Data preserved in:"
  echo "- Repository data: $BASE_PATH/gitea/data"
  echo "- Configuration: $BASE_PATH/gitea/config"
  echo "- Database: PostgreSQL database '$DB_NAME'"
  echo "- Backups: $BASE_PATH/backups"
  
  echo "To completely remove data later, run:"
  echo "  rm -rf $BASE_PATH/{gitea,builds,caddy,singularity,origin,genesis,backups}"
  echo "  sudo -u postgres psql -c \"DROP DATABASE $DB_NAME;\""
else
  echo "Removing all data directories..."
  # Full removal of all components
  rm -rf $BASE_PATH/{gitea,builds,caddy,auth,security,singularity,origin,genesis,backups}
  rm -f /var/lib/gitea /etc/gitea /var/log/gitea
  rm -f /var/lib/singularity /etc/singularity /var/log/singularity
  rm -f /var/lib/origin /etc/origin /var/log/origin
  rm -f /etc/caddy /var/log/caddy /var/lib/caddy
  rm -f /var/lib/builds /etc/builds /var/log/builds
  
  # Drop database if PostgreSQL is running
  if systemctl is-active --quiet postgresql; then
    echo "Removing database..."
    sudo -u postgres psql -c "DROP DATABASE $DB_NAME;" || true
    sudo -u postgres psql -c "DROP USER $DB_USER;" || true
  fi
fi

# Keep SSH keys for recovery user
if id recovery &>/dev/null; then
  echo "Recovery user SSH keys preserved in /home/recovery/.ssh/"
fi

# Keep mhugo user intact
echo "User 'mhugo' preserved"

# Ask about removing system users
if [ "$preserve_data" = false ]; then
  read -p "Do you want to remove system users (gitea, builder, origin, singularity, genesis)? (y/N): " remove_users
  if [[ "$remove_users" =~ ^[Yy]$ ]]; then
    echo "Removing system users..."
    userdel -r gitea 2>/dev/null || true
    userdel -r builder 2>/dev/null || true
    userdel -r singularity 2>/dev/null || true
    userdel -r origin 2>/dev/null || true
    userdel -r genesis 2>/dev/null || true
    groupdel docker-origin 2>/dev/null || true
    groupdel docker-singularity 2>/dev/null || true
  fi
fi

echo ""
echo "=========================================================="
echo "     Genesis Infrastructure Removal Complete!             "
echo "=========================================================="
if [ "$preserve_data" = true ]; then
  echo " Data has been preserved and can be reused for reinstallation"
  echo " To reinstall with preserved data, run: ./install.sh"
else
  echo " All components have been completely removed"
fi
echo "=========================================================="