# Origin Makefile for common operations

# Configuration
DOCKER_REGISTRY := registry.vultr.dndnordic.com
IMAGE_NAME := origin
TAG := latest
KUBE_NAMESPACE := governance-system
KUBE_ENV := vultr

.PHONY: all build push deploy-local deploy-k8s run test clean setup-runner

all: build

# Build the Docker image
build:
	@echo "Building Docker image $(DOCKER_REGISTRY)/$(IMAGE_NAME):$(TAG)..."
	docker build -t $(DOCKER_REGISTRY)/$(IMAGE_NAME):$(TAG) .

# Push the Docker image to registry
push: build
	@echo "Pushing Docker image $(DOCKER_REGISTRY)/$(IMAGE_NAME):$(TAG)..."
	docker push $(DOCKER_REGISTRY)/$(IMAGE_NAME):$(TAG)

# Run the application locally with docker-compose
run:
	@echo "Starting Origin with docker-compose..."
	docker-compose up -d

# Stop the local instance
stop:
	@echo "Stopping Origin..."
	docker-compose down

# Deploy to Kubernetes
deploy-k8s:
	@echo "Deploying to Kubernetes ($(KUBE_ENV))..."
	@if [ ! -f k8s-secrets.env ]; then \
		echo "Error: k8s-secrets.env file not found. Create it first with required secret values."; \
		exit 1; \
	fi
	# Export environment variables for secrets substitution
	@export $$(cat k8s-secrets.env | xargs); \
	kubectl apply -f kubernetes/namespace.yaml; \
	envsubst < kubernetes/secrets.yaml | kubectl apply -f -; \
	envsubst < kubernetes/registry-credentials.yaml | kubectl apply -f -; \
	kubectl apply -k kubernetes/cloud-providers/$(KUBE_ENV)

# Set up GitHub Actions runner locally
setup-runner:
	@echo "Setting up GitHub Actions runner..."
	@if [ -z "$(RUNNER_TOKEN)" ]; then \
		echo "Error: RUNNER_TOKEN must be provided. Get it from GitHub repository settings or run:"; \
		echo "gh api repos/dndnordic/origin/actions/runners/registration-token --method POST --jq '.token'"; \
		exit 1; \
	fi
	@mkdir -p ~/origin-runner
	@cd ~/origin-runner; \
	RUNNER_VERSION=$$(curl -s https://api.github.com/repos/actions/runner/releases/latest | grep tag_name | cut -d '"' -f 4 | cut -c 2-); \
	echo "Downloading GitHub runner version $${RUNNER_VERSION}..."; \
	curl -o actions-runner-linux-x64-$${RUNNER_VERSION}.tar.gz -L https://github.com/actions/runner/releases/download/v$${RUNNER_VERSION}/actions-runner-linux-x64-$${RUNNER_VERSION}.tar.gz; \
	tar xzf actions-runner-linux-x64-$${RUNNER_VERSION}.tar.gz; \
	./config.sh --url https://github.com/dndnordic/origin --token $(RUNNER_TOKEN) --name "local-origin-runner" --labels "self-hosted,local,origin" --work _work --unattended; \
	echo "Runner configured successfully."
	@echo "To start the runner, execute: cd ~/origin-runner && ./run.sh"

# Create k8s-secrets.env template
create-secrets-template:
	@echo "Creating k8s-secrets.env template..."
	@cat > k8s-secrets.env.template << 'EOF'
# Template for Kubernetes secrets (fill in the values and rename to k8s-secrets.env)
GITHUB_TOKEN_BASE64=
GITHUB_WEBHOOK_SECRET_BASE64=
MIKAEL_AUTH_TOKEN_BASE64=
DND_GENESIS_GITHUB_TOKEN_BASE64=
GITHUB_RUNNER_TOKEN_BASE64=
VULTR_REGISTRY_AUTH_BASE64=
VULTR_REGISTRY_CONFIG_BASE64=
EOF
	@echo "Template created at k8s-secrets.env.template"
	@echo "Fill in the values and rename to k8s-secrets.env before deploying."

# Run tests
test:
	@echo "Running tests..."
	python -m unittest discover -s tests

# Clean up build artifacts
clean:
	@echo "Cleaning up..."
	docker-compose down
	docker system prune -f