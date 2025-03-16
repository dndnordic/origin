#!/bin/bash
# Setup script for Linux Docker builder runner

set -e

# Set variables
RUNNER_NAME="docker-builder-$(hostname)"
RUNNER_DIR=~/actions-runner
GITHUB_ORG="dndnordic"
GITHUB_REPO="origin"

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed. Aborting."; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "Curl is required but not installed. Aborting."; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq is required but not installed. Aborting."; exit 1; }
command -v gh >/dev/null 2>&1 || { echo "GitHub CLI is required but not installed. Aborting."; exit 1; }

# Create runner directory
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# Download the latest runner
echo "Downloading the latest runner package..."
LATEST_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | jq -r '.tag_name' | sed 's/^v//')

# Download for Linux x64
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
            --labels "self-hosted,Linux,Docker,X64,builder" \
            --unattended \
            --replace

# Install as a service
echo "Installing runner as a service..."
sudo ./svc.sh install

# Start the service
echo "Starting the runner service..."
sudo ./svc.sh start

# Create status check script
cat > ~/docker-runner-status.sh << 'EOF'
#!/bin/bash
echo "==== GitHub Runner Status ===="
cd ~/actions-runner && sudo ./svc.sh status

echo -e "\n==== Docker Status ===="
docker info | grep "Server Version" || echo "Docker not running!"

echo -e "\n==== Disk Space ===="
df -h /

echo -e "\n==== Memory Usage ===="
free -h
EOF

chmod +x ~/docker-runner-status.sh

echo "Runner setup complete! You can check its status with ~/docker-runner-status.sh"
echo "Labels: self-hosted, Linux, Docker, X64, builder"