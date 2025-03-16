# Genesis Infrastructure Setup

This directory contains the automated setup scripts for the Genesis infrastructure, which includes:

- Gitea git server with PostgreSQL backend
- Docker environments for Origin and Singularity
- Caddy web server with automatic SSL
- Complete backup system
- SSH key management
- Security infrastructure

## Prerequisites

- AlmaLinux 9 or compatible RHEL 9 based system
- Root access
- Internet connectivity for package downloads

## Installation

1. Review and customize the configuration in `configs/settings.conf`
2. Make the install script executable: `chmod +x install.sh`
3. Run the installation script as root: `sudo ./install.sh`

## Directory Structure

The installation creates the following organized directory structure:

```
/opt/
├── gitea/            # Gitea server files
│   ├── config/       # Configuration
│   ├── data/         # Repository data
│   └── logs/         # Logs
├── builds/           # Build system
├── caddy/            # Caddy web server
├── auth/             # Authentication files
├── security/         # Security configuration
├── backups/          # Backup storage
│   ├── daily/        # Daily backups
│   ├── weekly/       # Weekly backups
│   └── monthly/      # Monthly backups
├── singularity/      # Singularity environment
├── origin/           # Origin environment
└── genesis/          # Genesis management
    └── ssh-keys/     # Centralized SSH key storage
```

## User Structure

The installation creates the following users with isolated permissions:

- `gitea`: Manages the Git server
- `builder`: Runs the build system
- `singularity`: Runs Singularity containers in isolated namespace
- `origin`: Runs Origin containers in isolated namespace
- `genesis`: Manages the infrastructure
- `recovery`: Emergency access account
- `mhugo`: Human administrator account

## Post-Installation

After installation completes:

1. Add mhugo's SSH key to `/home/mhugo/.ssh/authorized_keys`
2. Access Gitea at https://your-domain-name
3. Create the initial repositories (genesis, origin, singularity)
4. Configure branch protection rules according to governance model
5. Set up the build system webhooks

## Maintenance

- Daily backups run automatically at 2:00 AM
- Weekly backups are created on Sundays
- Monthly backups are created on the 1st of each month
- All backups are stored in `/opt/backups` with proper retention

## Emergency Recovery

For emergency recovery:

1. Connect via SSH to port 2222 as the recovery user
2. Run the recovery script: `/opt/security/emergency/recovery.sh`
3. Follow the prompts to restore services or data

## Scripts Overview

- `install.sh`: Main installation script
- `scripts/01-create-directories.sh`: Creates directory structure
- `scripts/02-create-users.sh`: Sets up system users
- `scripts/03-setup-ssh.sh`: Configures SSH keys and access
- `scripts/04-create-symlinks.sh`: Creates symlinks for standard paths
- `scripts/05-setup-postgres.sh`: Sets up PostgreSQL database
- `scripts/06-setup-docker.sh`: Configures Docker environments
- `scripts/07-setup-gitea.sh`: Installs and configures Gitea
- `scripts/08-setup-caddy.sh`: Sets up Caddy web server
- `scripts/09-setup-backups.sh`: Configures backup system
- `scripts/10-setup-services.sh`: Creates systemd services
- `scripts/11-set-permissions.sh`: Sets proper permissions
- `scripts/12-verify-installation.sh`: Verifies the installation