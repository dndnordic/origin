#!/bin/bash
set -e

# Determine script directory and load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/configs/settings.conf"

# Create backup directories
mkdir -p $BASE_PATH/backups/gitea/{daily,weekly,monthly}
mkdir -p $BASE_PATH/backups/postgres/{dumps,wal}

# Create backup script for Gitea
cat > /usr/local/bin/gitea-backup.sh << EOF
#!/bin/bash
# Backup script for Gitea
BACKUP_DIR="$BASE_PATH/backups/gitea"
DATE=\$(date +%Y%m%d_%H%M%S)

# Stop Gitea service
systemctl stop gitea

# Backup database
su -c "pg_dump -U $DB_USER $DB_NAME > \${BACKUP_DIR}/daily/gitea_db_\${DATE}.sql" postgres

# Backup repositories and data
tar -czf \${BACKUP_DIR}/daily/gitea_data_\${DATE}.tar.gz $BASE_PATH/gitea/data
tar -czf \${BACKUP_DIR}/daily/gitea_config_\${DATE}.tar.gz $BASE_PATH/gitea/config

# Start Gitea service
systemctl start gitea

# Cleanup old backups (keep last $BACKUP_RETENTION_DAYS days)
find \${BACKUP_DIR}/daily -name "gitea_*.sql" -type f -mtime +$BACKUP_RETENTION_DAYS -delete
find \${BACKUP_DIR}/daily -name "gitea_*.tar.gz" -type f -mtime +$BACKUP_RETENTION_DAYS -delete

# Weekly backup (on Sunday)
if [ \$(date +%u) -eq 7 ]; then
    cp \${BACKUP_DIR}/daily/gitea_db_\${DATE}.sql \${BACKUP_DIR}/weekly/
    cp \${BACKUP_DIR}/daily/gitea_data_\${DATE}.tar.gz \${BACKUP_DIR}/weekly/
    cp \${BACKUP_DIR}/daily/gitea_config_\${DATE}.tar.gz \${BACKUP_DIR}/weekly/
    # Keep weekly backups for 4 weeks
    find \${BACKUP_DIR}/weekly -name "gitea_*.sql" -type f -mtime +28 -delete
    find \${BACKUP_DIR}/weekly -name "gitea_*.tar.gz" -type f -mtime +28 -delete
fi

# Monthly backup (on 1st of month)
if [ \$(date +%d) -eq 01 ]; then
    cp \${BACKUP_DIR}/daily/gitea_db_\${DATE}.sql \${BACKUP_DIR}/monthly/
    cp \${BACKUP_DIR}/daily/gitea_data_\${DATE}.tar.gz \${BACKUP_DIR}/monthly/
    cp \${BACKUP_DIR}/daily/gitea_config_\${DATE}.tar.gz \${BACKUP_DIR}/monthly/
fi

echo "Backup completed at \${DATE}"
EOF

# Make script executable
chmod +x /usr/local/bin/gitea-backup.sh

# Create cron job for daily backups
echo "0 2 * * * root /usr/local/bin/gitea-backup.sh > $BASE_PATH/gitea/logs/backup.log 2>&1" > /etc/cron.d/gitea-backup

# Create emergency recovery script
mkdir -p $BASE_PATH/security/emergency
cat > $BASE_PATH/security/emergency/recovery.sh << 'EOF'
#!/bin/bash
# Emergency recovery script

echo "Emergency Recovery System"
echo "========================="
echo

echo "You have emergency recovery access."

# Menu for recovery options
echo "Recovery Options:"
echo "1. Restart Gitea service"
echo "2. Restart Origin Docker service"
echo "3. Restart Singularity Docker service"
echo "4. Restore Gitea configuration from backup"
echo "5. Restore database from backup"
echo "6. Restore repository from backup"
echo "7. Exit"

read -p "Select an option: " OPTION

case $OPTION in
  1)
    systemctl restart gitea
    echo "Gitea service restarted."
    ;;
  2)
    systemctl restart docker-origin
    echo "Origin Docker service restarted."
    ;;
  3)
    systemctl restart docker-singularity
    echo "Singularity Docker service restarted."
    ;;
  4)
    read -p "Enter backup date (YYYYMMDD): " BACKUP_DATE
    cp -a $BASE_PATH/backups/gitea/daily/gitea_config_${BACKUP_DATE}* $BASE_PATH/gitea/config/
    echo "Configuration restored from backup."
    ;;
  5)
    read -p "Enter backup date (YYYYMMDD): " BACKUP_DATE
    sudo -u postgres psql -c "DROP DATABASE gitea;"
    sudo -u postgres psql -c "CREATE DATABASE gitea OWNER gitea;"
    sudo -u postgres psql gitea < $BASE_PATH/backups/gitea/daily/gitea_db_${BACKUP_DATE}*.sql
    echo "Database restored from backup."
    ;;
  6)
    read -p "Enter repository name: " REPO_NAME
    read -p "Enter backup date (YYYYMMDD): " BACKUP_DATE
    mkdir -p /tmp/repo-restore
    tar -xzf $BASE_PATH/backups/gitea/daily/gitea_data_${BACKUP_DATE}*.tar.gz -C /tmp/repo-restore
    cp -a /tmp/repo-restore$BASE_PATH/gitea/data/gitea-repositories/*/$REPO_NAME.git $BASE_PATH/gitea/data/gitea-repositories/
    rm -rf /tmp/repo-restore
    chown -R gitea:gitea $BASE_PATH/gitea/data/gitea-repositories/$REPO_NAME.git
    echo "Repository restored from backup."
    ;;
  7)
    echo "Exiting recovery system."
    exit 0
    ;;
  *)
    echo "Invalid option."
    exit 1
    ;;
esac
EOF

chmod +x $BASE_PATH/security/emergency/recovery.sh

# Set proper permissions
chown -R root:root $BASE_PATH/security
chmod -R 750 $BASE_PATH/security

echo "Backup system setup completed successfully"