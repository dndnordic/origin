#!/bin/bash
# Setup script for Windows WSL LLM runner for Mikael's machine

set -e

# Set variables
RUNNER_NAME="mikael-wsl-llm-runner"
RUNNER_DIR=~/actions-runner
GITHUB_ORG="dndnordic"
GITHUB_REPO="origin"

# Ensure prerequisites
command -v curl >/dev/null 2>&1 || { echo "Curl is required but not installed. Aborting."; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq is required but not installed. Aborting."; exit 1; }
command -v gh >/dev/null 2>&1 || { echo "GitHub CLI is required but not installed. Aborting."; exit 1; }

# Create runner directory
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# Check if LLM server is running
echo "Checking LLM server status..."
if ! curl -s http://localhost:8000/health > /dev/null; then
  echo "Warning: LLM server does not appear to be running on port 8000."
  echo "Please ensure the LLM service is running before using this runner."
  read -p "Continue anyway? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborting setup."
    exit 1
  fi
fi

# Download the latest runner
echo "Downloading the latest runner package..."
LATEST_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | jq -r '.tag_name' | sed 's/^v//')

# Download for Linux x64 (WSL is Linux)
curl -O -L "https://github.com/actions/runner/releases/download/v${LATEST_VERSION}/actions-runner-linux-x64-${LATEST_VERSION}.tar.gz"
tar xzf "./actions-runner-linux-x64-${LATEST_VERSION}.tar.gz"
rm "./actions-runner-linux-x64-${LATEST_VERSION}.tar.gz"

# Check GitHub CLI authentication
echo "Checking GitHub authentication..."
gh auth status || {
    echo "GitHub CLI is not authenticated. Please run 'gh auth login' first."
    exit 1
}

# Get a runner registration token
echo "Getting runner registration token..."
RUNNER_TOKEN=$(gh api "repos/${GITHUB_ORG}/${GITHUB_REPO}/actions/runners/registration-token" --method POST | jq -r '.token')

if [ -z "$RUNNER_TOKEN" ] || [ "$RUNNER_TOKEN" == "null" ]; then
    echo "Failed to get runner token. Please check your GitHub authentication."
    exit 1
fi

# Configure the runner
echo "Configuring the runner..."
./config.sh --url "https://github.com/${GITHUB_ORG}/${GITHUB_REPO}" \
            --token "$RUNNER_TOKEN" \
            --name "$RUNNER_NAME" \
            --labels "self-hosted,Windows,WSL,X64,LLM,GPU" \
            --unattended \
            --replace

# Install as a service
echo "Installing runner as a service..."
sudo ./svc.sh install

# Start the service
echo "Starting the runner service..."
sudo ./svc.sh start

# Set up YubiKey auth script
echo "Setting up YubiKey authentication helper script..."
cat > ~/yubikey-auth-setup.sh << 'EOF'
#!/bin/bash
# YubiKey authentication setup for GitHub Actions

# Check if pcscd service is installed
if ! command -v pcscd &> /dev/null; then
    echo "Installing PC/SC daemon for smart card support..."
    sudo apt-get update
    sudo apt-get install -y pcscd pcsc-tools
fi

# Start pcscd service
echo "Starting PC/SC daemon..."
sudo systemctl enable pcscd
sudo systemctl start pcscd

# Check if YubiKey tools are installed
if ! command -v ykman &> /dev/null; then
    echo "Installing YubiKey Manager..."
    sudo apt-get install -y yubikey-manager
fi

# Verify YubiKey is connected
echo "Checking for YubiKey..."
if ykman list | grep -q "YubiKey"; then
    echo "YubiKey detected!"
    ykman info
else
    echo "No YubiKey detected. Please insert your YubiKey and try again."
    exit 1
fi

echo "YubiKey setup complete for GitHub Actions authentication."
EOF

chmod +x ~/yubikey-auth-setup.sh

# Create status check script
cat > ~/llm-runner-status.sh << 'EOF'
#!/bin/bash
echo "==== GitHub Runner Status ===="
cd ~/actions-runner && sudo ./svc.sh status

echo -e "\n==== LLM Server Status ===="
curl -s http://localhost:8000/health || echo "LLM server not responding!"

echo -e "\n==== YubiKey Status ===="
if command -v ykman &> /dev/null; then
    ykman list || echo "No YubiKey detected!"
else
    echo "YubiKey Manager not installed!"
fi

echo -e "\n==== Disk Space ===="
df -h /

echo -e "\n==== Memory Usage ===="
free -h

echo -e "\n==== GPU Status ===="
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi || echo "NVIDIA drivers not working properly!"
else
    echo "NVIDIA tools not installed!"
fi
EOF

chmod +x ~/llm-runner-status.sh

# Create Tailscale network configuration
echo "Setting up Tailscale network configuration for LLM server..."
cat > ~/tailscale-mikael-bunker.sh << 'EOF'
#!/bin/bash
# Configure Tailscale for Mikael's LLM Bunker

# Check if Tailscale is installed
if ! command -v tailscale &> /dev/null; then
    echo "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
fi

# Get authorization key from GitHub secrets (requires jq and gh CLI)
AUTH_KEY=$(gh api repos/dndnordic/genesis/actions/secrets/MIKAEL_TAILSCALE_AUTH_KEY --jq .value || \
          echo "TAILSCALE_AUTHKEY_HERE")

# Start Tailscale with hostname mikki-bunker.local
echo "Starting Tailscale..."
sudo tailscale up --authkey="$AUTH_KEY" --hostname="mikki-bunker"

# Set up advertised routes
echo "Setting up advertised routes for LLM server..."
sudo tailscale up --advertise-routes=192.168.1.0/24

echo "Tailscale setup complete. Your node should be accessible as 'mikki-bunker.local'"
EOF

chmod +x ~/tailscale-mikael-bunker.sh

echo "Runner setup complete! You can check its status with ~/llm-runner-status.sh"
echo "Labels: self-hosted, Windows, WSL, X64, LLM, GPU"
echo ""
echo "Next steps:"
echo "1. Run ~/yubikey-auth-setup.sh to configure YubiKey authentication"
echo "2. Run ~/tailscale-mikael-bunker.sh to configure Tailscale networking"