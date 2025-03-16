# Mikael's Governance System (Origin)

This repository contains the governance system for overseeing the Singularity AI project.

## Purpose

The primary purpose of this repository is to provide a complete governance system that ensures:

1. Mikael maintains full oversight over the Singularity system
2. All significant changes go through appropriate approval processes
3. Secure, immutable records are maintained of all governance decisions
4. Clear separation exists between governance and Singularity systems
5. Centralized credential and identity management

## Security Model

This repository implements strict security practices:

- All commits must be signed
- Branch protection requires pull request approval
- No direct pushes to protected branches
- YubiKey authentication for critical operations
- Secure vault for credential management
- Killswitch capability for emergency control

## High Availability Architecture

Origin is designed with redundancy in mind:

- Kubernetes deployment supports multiple replicas with pod anti-affinity
- Database connections support multiple endpoints with failover
- Configuration enables scaling to full HA when needed
- Connection retry logic with circuit breaker patterns
- StatefulSets prepared for distributed database deployments

While initially deployed with minimal redundancy to reduce complexity, the infrastructure is prepared for full HA deployment in the future as the system matures.

## Repository Structure

- `/src` - Source code for governance systems
  - `/api` - REST APIs and client SDKs
  - `/database` - Database integration with triple storage pattern
  - `/governance` - Core governance logic
  - `/security` - Vault manager and authentication systems
  - `/web` - Web interface and dashboards
- `/kubernetes` - Deployment configuration
  - `/cloud-providers` - Cloud-specific configurations
  - `/patches` - Environment-specific customizations
- `/docs` - Documentation
- `/.github` - GitHub Actions workflows for CI/CD

## Deployment Guide

There are multiple ways to deploy Origin:

### 1. Local Development

```bash
# Start all services locally
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 2. Manual Kubernetes Deployment

```bash
# Create secrets template and fill values
make create-secrets-template
cp k8s-secrets.env.template k8s-secrets.env
# Edit k8s-secrets.env with your values

# Build and push the Docker image
make build push

# Deploy to Kubernetes
make deploy-k8s
```

### 3. GitHub Actions CI/CD

The repository includes GitHub Actions workflows for CI/CD:

1. Push changes to the `main` branch, or
2. Use the "Build and Deploy Origin" action in GitHub Actions UI

#### Required GitHub Secrets

For the CI/CD workflow to function, these secrets must be configured:

- `VULTR_REGISTRY_USERNAME` - Username for Vultr container registry
- `VULTR_REGISTRY_PASSWORD` - Password for Vultr container registry
- `KUBECONFIG` - Base64-encoded Kubernetes config file
- `GITHUB_TOKEN` - Token for GitHub API access
- `GITHUB_WEBHOOK_SECRET` - Secret for validating GitHub webhooks
- `MIKAEL_AUTH_TOKEN` - YubiKey authentication token
- `DND_GENESIS_GITHUB_TOKEN` - Token for dnd-genesis bot operations
- `GITHUB_RUNNER_TOKEN` - For GitHub runner registration
- `VULTR_REGISTRY_AUTH_BASE64` - Base64-encoded registry auth
- `VULTR_REGISTRY_CONFIG_BASE64` - Base64-encoded Docker config

You can add these in the repository settings: Settings → Secrets and Variables → Actions

### 4. Setting Up GitHub Runners

For complete functionality, Origin requires these self-hosted GitHub runners:

1. **WSL Runner**: On Mikael's WSL environment
   ```bash
   # Get a runner token
   RUNNER_TOKEN=$(gh api repos/dndnordic/origin/actions/runners/registration-token --method POST --jq '.token')
   
   # Set up the runner
   make setup-runner RUNNER_TOKEN=$RUNNER_TOKEN
   
   # Start the runner
   cd ~/origin-runner && ./run.sh
   ```

2. **Vultr Runner**: A dedicated virtual machine with Docker support
   ```bash
   # Get a runner token
   RUNNER_TOKEN=$(gh api repos/dndnordic/origin/actions/runners/registration-token --method POST --jq '.token')
   
   # On the Vultr VM, execute:
   mkdir -p ~/actions-runner && cd ~/actions-runner
   curl -o actions-runner-linux-x64-2.311.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz
   tar xzf actions-runner-linux-x64-2.311.0.tar.gz
   ./config.sh --url https://github.com/dndnordic/origin --token $RUNNER_TOKEN --name "origin-vultr-runner" --labels "self-hosted,vultr,docker-enabled,origin" --work _work --unattended
   sudo ./svc.sh install
   sudo ./svc.sh start
   ```

## Verifying Deployment

After deployment, verify the system is working:

```bash
# Kubernetes deployment
kubectl get pods -n governance-system
kubectl logs -n governance-system deployment/origin

# Access the API
kubectl port-forward -n governance-system svc/origin 8000:8000
curl http://localhost:8000/api/health

# Access the web UI
kubectl port-forward -n governance-system svc/origin 5000:5000
# Visit http://localhost:5000 in your browser
```

## Common Issues and Troubleshooting

See [kubernetes/README.md](kubernetes/README.md) for detailed troubleshooting information.

## Setting Up GitHub Webhook

For GitHub webhook integration:

1. Go to repository settings: Settings → Webhooks → Add webhook
2. Set Payload URL to: `https://origin-api.dndnordic.com/api/github/webhook`
3. Content type: `application/json`
4. Secret: Same as the `GITHUB_WEBHOOK_SECRET` in your secrets
5. Events: Select "Pull requests" and "Pull request reviews"
6. Add webhook