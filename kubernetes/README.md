# Origin Kubernetes Deployment

This directory contains Kubernetes manifests for deploying the Origin governance system.

## Components

- **Origin API & Web UI**: Core governance system that provides the API and web interface
- **Immutable Database**: ImmuDB instance for storing immutable governance records
- **GitHub Runner**: Self-hosted GitHub runner for CI/CD pipelines
- **Mikael's WSL Connector**: Special connector that establishes a secure connection to Mikael's WSL environment

## Deployment Instructions

### Prerequisites

1. Kubernetes cluster with kubectl access
2. Access to the dndnordic container registry
3. Properly configured secrets (see below)

### Special Notes on Mikael's GPU Connector

The repository includes a special connector for utilizing Mikael's NVIDIA GeForce RTX 4080 GPU for LLM operations through WSL. For detailed setup instructions, see [mikael_wsl_gpu_setup.md](../docs/mikael_wsl_gpu_setup.md).

To deploy the connector to Kubernetes, use:

```bash
./scripts/deploy-mikael-connector.sh --host <mikael-hostname-or-ip>
```

This allows the Origin system to offload intensive LLM inference tasks to Mikael's GPU without requiring cloud GPU resources.

### Setting up Secrets

Before deploying, you need to create a `secrets.env` file with the following variables:

```bash
# GitHub tokens for API access and webhooks
GITHUB_TOKEN=your_github_token                        # For general GitHub API operations
GITHUB_WEBHOOK_SECRET=your_webhook_secret             # For verifying webhook payloads
DND_GENESIS_GITHUB_TOKEN=genesis_bot_token            # For dnd-genesis bot operations

# Authentication tokens
MIKAEL_AUTH_TOKEN=yubikey_auth_token                  # For Mikael's YubiKey authentication

# GitHub runner token (can be obtained with the gh cli)
# Get a new token: gh api -X POST repos/dndnordic/origin/actions/runners/registration-token --jq .token
GITHUB_RUNNER_TOKEN=github_runner_registration_token  # For registering self-hosted runners

# Vultr registry authentication - used by runners to push/pull Docker images
# Format: username:password base64 encoded
VULTR_REGISTRY_AUTH_BASE64=base64_encoded_auth_string # For accessing Vultr container registry
VULTR_REGISTRY_CONFIG_BASE64=base64_encoded_config    # Base64 encoded docker config.json

# Headscale authentication for secure networking
# Generate from Headscale admin console
HEADSCALE_AUTH_KEY=hskey-auth-randomstring            # Used to connect to the Headscale network

# Mikael's WSL connection details (accessed via Headscale)
MIKAEL_WSL_HOST=hostname.headnet.internal             # Headscale hostname for Mikael's machine
MIKAEL_WSL_PORT=ssh_port                              # Usually 22 but may be custom
MIKAEL_WSL_USER=ssh_username                          # Usually 'mikael'
MIKAEL_SSH_KEY="-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----"                    # SSH key for accessing Mikael's WSL
```

Then convert them to base64:

```bash
# For standard environment variables
cat secrets.env | while IFS= read -r line; do
  if [[ ! "$line" =~ ^# && ! -z "$line" ]]; then
    key=$(echo $line | cut -d= -f1)
    value=$(echo $line | cut -d= -f2-)
    echo "${key}_BASE64=$(echo -n "$value" | base64 -w 0)"
  fi
done > k8s-secrets.env

# Also create Docker config.json for Vultr registry
# This should match the auth values in docker-registry-config.yaml
cat > docker-config.json << EOF
{
  "auths": {
    "registry.vultr.dndnordic.com": {
      "auth": "${VULTR_REGISTRY_AUTH_BASE64}"
    }
  }
}
EOF
echo "VULTR_REGISTRY_CONFIG_BASE64=$(cat docker-config.json | base64 -w 0)" >> k8s-secrets.env
rm docker-config.json

# Instead of using environment variables directly, you can also use GitHub Secrets
# by adding them to the repository settings and then retrieving them here
# (useful for CI/CD pipelines that deploy to Kubernetes)
if [ -n "${GITHUB_ACTIONS}" ]; then
  echo "Running in GitHub Actions environment, using GitHub Secrets..."
  # These would be set as GitHub Secrets in the repository settings
  GITHUB_TOKEN_BASE64=$(echo -n "$GITHUB_TOKEN" | base64 -w 0)
  GITHUB_WEBHOOK_SECRET_BASE64=$(echo -n "$GITHUB_WEBHOOK_SECRET" | base64 -w 0)
  MIKAEL_AUTH_TOKEN_BASE64=$(echo -n "$MIKAEL_AUTH_TOKEN" | base64 -w 0)
  DND_GENESIS_GITHUB_TOKEN_BASE64=$(echo -n "$DND_GENESIS_GITHUB_TOKEN" | base64 -w 0)
  GITHUB_RUNNER_TOKEN_BASE64=$(echo -n "$GITHUB_RUNNER_TOKEN" | base64 -w 0)
  HEADSCALE_AUTH_KEY_BASE64=$(echo -n "$HEADSCALE_AUTH_KEY" | base64 -w 0)
  MIKAEL_WSL_HOST_BASE64=$(echo -n "$MIKAEL_WSL_HOST" | base64 -w 0)
  MIKAEL_WSL_PORT_BASE64=$(echo -n "$MIKAEL_WSL_PORT" | base64 -w 0)
  MIKAEL_WSL_USER_BASE64=$(echo -n "$MIKAEL_WSL_USER" | base64 -w 0)
  MIKAEL_SSH_KEY_BASE64=$(echo -n "$MIKAEL_SSH_KEY" | base64 -w 0)
fi
```

### Deploying to Kubernetes

1. Apply the namespace first:

```bash
kubectl apply -f kubernetes/namespace.yaml
```

2. Create the secrets:

```bash
export $(cat k8s-secrets.env | xargs)
envsubst < kubernetes/secrets.yaml | kubectl apply -f -
```

3. Deploy to Vultr using kustomize:

```bash
kubectl apply -k kubernetes/cloud-providers/vultr
```

4. The WSL connector will connect to Mikael's existing runner if it already exists, or set up a new one if needed. To check the connection status:

```bash
kubectl logs -f -n governance-system deployment/mikael-wsl-connector
```

5. Verify the runner is properly registered and active:

```bash
# List runners for Origin repository (requires GitHub admin rights)
gh api repos/dndnordic/origin/actions/runners --jq '.runners[] | {name, status, busy, labels: [.labels[].name]}'
```

### Accessing the Deployment

- **API**: Access via https://origin-api.dndnordic.com
- **Web UI**: Access via port-forwarding or through the ingress if configured:
  ```bash
  kubectl port-forward -n governance-system svc/origin 5000:5000
  ```

### Checking Status

```bash
kubectl get all -n governance-system
```

### Viewing Logs

```bash
# Origin core
kubectl logs -n governance-system deployment/origin

# WSL Connector
kubectl logs -n governance-system deployment/mikael-wsl-connector

# GitHub Runner
kubectl logs -n governance-system deployment/github-runner
```

### Managing GitHub Runners

To view and manage GitHub runners:

```bash
# List all runners
gh api repos/dndnordic/origin/actions/runners --jq '.runners[] | {id, name, status, busy, os, labels: [.labels[].name]}'

# Get details of a specific runner
gh api repos/dndnordic/origin/actions/runners/RUNNER_ID --jq '.'

# Remove a runner
gh api -X DELETE repos/dndnordic/origin/actions/runners/RUNNER_ID
```

### Working with the Vultr Container Registry

```bash
# Log in to the registry
docker login registry.vultr.dndnordic.com -u username -p password

# Tag an image
docker tag origin:latest registry.vultr.dndnordic.com/origin:latest

# Push an image
docker push registry.vultr.dndnordic.com/origin:latest

# Pull an image
docker pull registry.vultr.dndnordic.com/origin:latest
```

## Troubleshooting

### Common Issues

1. **WSL Connection Failures**:
   - Verify SSH key is correct in the secrets
   - Check that Mikael's WSL environment is running the Headscale client
   - Verify Headscale auth key is valid and has the correct permissions
   - Run `kubectl logs deployment/mikael-wsl-connector` to check Headscale connection status
   - Ensure Mikael's Headscale node is online in the Headscale admin console

2. **Mikael's GPU Connector Issues**:
   - Verify Mikael's WSL environment is set up correctly: `wsl nvidia-smi`
   - Check that PyTorch with CUDA is installed and working: `wsl ~/activate-origin-llm.sh && python -c "import torch; print(torch.cuda.is_available())"`
   - Ensure the connector service is running: `wsl ps -ef | grep origin-wsl`
   - Check the connector logs: `wsl cat ~/connector-test.log`
   - Verify the Kubernetes connector is deployed correctly: `kubectl get deployment mikael-llm-connector -n origin-system`
   - Check Kubernetes connector logs: `kubectl logs deployment/mikael-llm-connector -n origin-system`

3. **GitHub Runner Registration Failures**:
   - Check that the GITHUB_RUNNER_TOKEN is valid and not expired
   - Verify the runner has appropriate permissions for the repository
   - Use GitHub settings to check registered runners: `https://github.com/dndnordic/origin/settings/actions/runners`

4. **ImmuDB Connection Issues**:
   - Check if the StatefulSet is running correctly
   - Verify the persistent volume is correctly bound
   
5. **GitHub Secrets/Variables Issues**:
   - Check repository settings at `https://github.com/dndnordic/origin/settings/secrets/actions`
   - Verify all required secrets are set correctly (GITHUB_TOKEN, HEADSCALE_AUTH_KEY, etc.)
   - Some values may need to be set as repository Variables instead of Secrets

### Support Contacts

For issues with:
- **Kubernetes Deployment**: Contact the DevOps team
- **Origin Application**: Contact the Governance team
- **WSL Connection**: Contact Mikael directly
- **GPU/ML Inference**: Contact the ML Engineering team or Mikael for GPU-specific issues