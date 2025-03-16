# Origin Deployment Guide

This document provides a complete guide for deploying the Origin governance system and setting up the proper security hierarchy.

## Overview

Origin is now ready for deployment with:

1. **Docker and Kubernetes configurations** for deploying to Vultr or other cloud providers
2. **GitHub Actions CI/CD** for automated deployment
3. **User and permission model** that enforces the governance hierarchy
4. **Self-hosted runner setup** for custom GitHub Actions environments

## Step 1: GitHub Organization Setup

The Origin governance system requires the correct security model to enforce Mikael's authority. Follow the detailed instructions in [docs/github_setup.md](docs/github_setup.md) to:

1. Configure repository permissions for all users:
   - `dnd-origin` - Origin governance system (read-only access to Origin)
   - `dnd-singularity` - Singularity AI system (no access to Origin)
   - `mikkihugo` - Mikael's account (admin access, required approver)
   - `dnd-genesis` - Infrastructure account (admin access for maintenance)

2. Set up branch protection rules for the Origin repository to ensure:
   - All changes require pull request approval
   - Code owners (Mikael) must approve changes
   - Commits must be signed
   - Only authorized users can push to the main branch

## Step 2: Local Deployment (Development)

For local testing and development, use Docker Compose:

```bash
# Start all services locally
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## Step 3: Kubernetes Deployment (Production)

For production deployment to Kubernetes:

### 3.1 Prepare Secrets

```bash
# Create secrets template and fill values
make create-secrets-template
cp k8s-secrets.env.template k8s-secrets.env
# Edit k8s-secrets.env with your values
```

### 3.2 Build and Push Docker Image

```bash
# Login to registry
docker login registry.vultr.dndnordic.com -u <username> -p <password>

# Build and push the image
make build push
```

### 3.3 Deploy to Kubernetes

```bash
# Deploy to Kubernetes (Vultr by default)
make deploy-k8s
```

## Step 4: Setting Up GitHub Runners

For complete functionality, Origin requires these self-hosted GitHub runners:

### 4.1 WSL Runner on Mikael's Machine

```bash
# Get a runner token
RUNNER_TOKEN=$(gh api repos/dndnordic/origin/actions/runners/registration-token --method POST --jq '.token')

# Set up the runner
make setup-runner RUNNER_TOKEN=$RUNNER_TOKEN

# Start the runner
cd ~/origin-runner && ./run.sh
```

### 4.2 Vultr Runner for Cloud Operations

```bash
# Use the included setup script
cd scripts
./setup-vultr-runner.sh <runner-token> origin-vultr-runner
```

## Step 5: Verify Deployment

After deployment, verify the system is working:

```bash
# Check Kubernetes pods
kubectl get pods -n governance-system

# Check logs
kubectl logs -n governance-system deployment/origin

# Access the API and Web UI
kubectl port-forward -n governance-system svc/origin 8000:8000
kubectl port-forward -n governance-system svc/origin 5000:5000
```

## Security Verification

Ensure the security model is working as expected with these tests:

1. Create a PR to Origin as dnd-origin (should be able to create but not approve)
2. Create a PR to Singularity as dnd-origin (should be able to approve)
3. Create a PR to Origin as mikkihugo (should be able to approve)
4. Verify dnd-singularity cannot access the Origin repository

## Next Steps

1. Set up the GitHub webhook for notification on PR events
2. Configure domain and TLS for the production API endpoint
3. Set up monitoring and alerting for the Origin system

For detailed troubleshooting information, see [kubernetes/README.md](kubernetes/README.md).