# GitHub Actions Runners Setup Guide

This document explains how to set up GitHub Actions runners for the dndnordic organization.

## Runner Architecture

The dndnordic organization uses a specialized runner architecture to support its governance system:

1. **Mikael's Windows WSL Machine (MIKKI-BUNKER)**
   - Purpose: LLM operations, YubiKey authentication, governance oversight
   - Labels: `self-hosted`, `Windows`, `WSL`, `X64`, `LLM`, `GPU`
   - Repository: Origin
   - Setup script: `/home/sing/origin/scripts/setup-windows-llm-runner.sh`

2. **Linux Docker Builder**
   - Purpose: Building Docker images, running containerized builds, deployments
   - Labels: `self-hosted`, `Linux`, `Docker`, `X64`, `builder`
   - Repository: Origin
   - Setup script: `/home/sing/origin/scripts/setup-linux-docker-runner.sh`

3. **Genesis Repository Runner**
   - Purpose: Genesis-specific build operations
   - Labels: `self-hosted`, `Linux`, `Docker`, `X64`, `genesis`
   - Repository: Genesis
   - Setup script: `/home/sing/genesis/scripts/setup-genesis-runner.sh`

## Installation Instructions

### 1. On Mikael's Windows Machine (WSL)

```bash
# Clone the Origin repository if not already present
cd ~
git clone https://github.com/dndnordic/origin.git
cd origin

# Make the script executable
chmod +x scripts/setup-windows-llm-runner.sh

# Run the script
./scripts/setup-windows-llm-runner.sh
```

### 2. On Linux Docker Builder Machine

```bash
# Clone the Origin repository if not already present
cd ~
git clone https://github.com/dndnordic/origin.git
cd origin

# Make the script executable
chmod +x scripts/setup-linux-docker-runner.sh

# Run the script
./scripts/setup-linux-docker-runner.sh
```

### 3. On Genesis Repository Runner Machine

```bash
# Clone the Genesis repository if not already present
cd ~
git clone https://github.com/dndnordic/genesis.git
cd genesis

# Make the script executable and ensure the directory exists
mkdir -p scripts
chmod +x scripts/setup-genesis-runner.sh

# Run the script
./scripts/setup-genesis-runner.sh
```

## Obtaining New Registration Tokens

The tokens in the scripts expire after 1 hour. To generate new ones:

```bash
# For Origin repository
gh api repos/dndnordic/origin/actions/runners/registration-token --method POST | jq -r '.token'

# For Genesis repository
gh api repos/dndnordic/genesis/actions/runners/registration-token --method POST | jq -r '.token'

# For Singularity repository
gh api repos/dndnordic/singularity/actions/runners/registration-token --method POST | jq -r '.token'
```

## Moving to Organization-level Runners (Future)

Currently, runners are configured at the repository level. In the future, we plan to upgrade to organization-level runners for better management. This requires:

1. Having `admin:org` scope permissions in the GitHub token
2. Using the organization endpoint for registration tokens:
   ```bash
   gh api orgs/dndnordic/actions/runners/registration-token --method POST | jq -r '.token'
   ```
3. Using the organization URL when configuring runners:
   ```bash
   ./config.sh --url https://github.com/dndnordic --token YOUR_TOKEN
   ```

## Workflow File Configuration

When configuring GitHub Actions workflow files, use the appropriate labels to target specific runners:

```yaml
# For LLM tasks on Mikael's machine
jobs:
  analyze:
    runs-on: [self-hosted, Windows, WSL, X64, LLM, GPU]
    
# For Docker builds on Linux
jobs:
  build:
    runs-on: [self-hosted, Linux, Docker, X64, builder]
    
# For Genesis-specific tasks
jobs:
  genesis_task:
    runs-on: [self-hosted, Linux, Docker, X64, genesis]
```

## Troubleshooting

If you encounter issues with runner setup:

1. Check the logs in `~/[runner-directory]/_diag/`
2. Run the status script for the relevant runner:
   - `~/llm-runner-status.sh`
   - `~/docker-runner-status.sh`
   - `~/genesis-runner-status.sh`
3. Verify GitHub connectivity
4. Check Docker functionality for Docker-enabled runners
5. Ensure the runner service is running: `sudo ./svc.sh status`

## Security Considerations

1. Runners have access to repository secrets
2. Docker-enabled runners should be secured properly
3. YubiKey authentication should be used for sensitive operations
4. Regularly rotate access tokens
5. Ensure runners operate with least privilege necessary