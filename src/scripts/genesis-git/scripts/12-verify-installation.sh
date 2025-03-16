#!/bin/bash
set -e

# Determine script directory and load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/configs/settings.conf"

echo "Verifying installation..."
echo

# Check services
echo "Checking services..."
services=("postgresql" "gitea" "caddy" "docker" "docker-origin" "docker-singularity")
failures=0

for service in "${services[@]}"; do
    if systemctl is-active --quiet $service; then
        echo "✓ $service is running"
    else
        echo "✗ $service is NOT running"
        failures=$((failures+1))
    fi
done

if [ $failures -gt 0 ]; then
    echo "WARNING: $failures services are not running properly."
    echo "Starting services..."
    
    # Try to start services
    for service in "${services[@]}"; do
        if ! systemctl is-active --quiet $service; then
            systemctl start $service
            echo "Starting $service"
        fi
    done
fi

# Check directories
echo
echo "Checking directories..."
directories=(
    "$BASE_PATH/gitea"
    "$BASE_PATH/builds"
    "$BASE_PATH/caddy"
    "$BASE_PATH/auth"
    "$BASE_PATH/security"
    "$BASE_PATH/backups"
    "$BASE_PATH/singularity"
    "$BASE_PATH/origin"
    "$BASE_PATH/genesis"
)

for dir in "${directories[@]}"; do
    if [ -d "$dir" ]; then
        echo "✓ $dir exists"
    else
        echo "✗ $dir does NOT exist"
        failures=$((failures+1))
    fi
done

# Check PostgreSQL
echo
echo "Checking PostgreSQL..."
if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo "✓ PostgreSQL database $DB_NAME exists"
else
    echo "✗ PostgreSQL database $DB_NAME does NOT exist"
    failures=$((failures+1))
fi

# Check Docker contexts
echo
echo "Setting up Docker contexts..."
$BASE_PATH/origin/scripts/setup-origin-context.sh
$BASE_PATH/singularity/scripts/setup-singularity-context.sh

# Create summary
echo
if [ $failures -eq 0 ]; then
    echo "✓ All checks passed! Installation appears to be successful."
    
    # Start services
    systemctl start gitea
    systemctl start docker-origin
    systemctl start docker-singularity
    systemctl start caddy
    
    echo "Services have been started."
    echo
    echo "You can now access Gitea at: https://$DOMAIN"
    echo
    echo "Next steps:"
    echo "1. Add mhugo's SSH key to /home/mhugo/.ssh/authorized_keys"
    echo "2. Create the initial repositories (genesis, origin, singularity)"
    echo "3. Configure branch protection rules according to governance model"
else
    echo "✗ There were $failures failures. Please review the output and fix any issues."
fi

echo
echo "Installation verification completed. Check above for any warnings or errors."