#!/bin/bash
set -e

# Determine script directory and load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/configs/settings.conf"

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "Installing PostgreSQL..."
    dnf -y install postgresql postgresql-server postgresql-contrib
    
    # Initialize PostgreSQL
    postgresql-setup --initdb
    
    # Start and enable PostgreSQL service
    systemctl enable postgresql
    systemctl start postgresql
fi

# Check if database exists
if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo "Creating database for Gitea..."
    
    # Create database and user for Gitea
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
    sudo -u postgres psql -c "ALTER USER $DB_USER WITH SUPERUSER;"
    
    # Allow local connections
    sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = 'localhost'/g" /var/lib/pgsql/data/postgresql.conf
    
    # Update pg_hba.conf to allow local connections with password
    if ! grep -q "host    $DB_NAME    $DB_USER    127.0.0.1/32    md5" /var/lib/pgsql/data/pg_hba.conf; then
        echo "host    $DB_NAME    $DB_USER    127.0.0.1/32    md5" >> /var/lib/pgsql/data/pg_hba.conf
    fi
    
    # Restart PostgreSQL
    systemctl restart postgresql
fi

echo "PostgreSQL setup completed successfully"