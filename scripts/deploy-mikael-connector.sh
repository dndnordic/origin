#!/bin/bash

# Script to deploy Mikael's WSL GPU connector to a Kubernetes cluster
# Usage: ./deploy-mikael-connector.sh --host <hostname-or-ip> [--namespace <namespace>] [--port <port>]

set -e

# Default values
NAMESPACE="origin-system"
PORT="8000"
HOST=""

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --host) HOST="$2"; shift ;;
        --namespace) NAMESPACE="$2"; shift ;;
        --port) PORT="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Validate required parameters
if [ -z "$HOST" ]; then
    echo "Error: --host parameter is required"
    echo "Usage: ./deploy-mikael-connector.sh --host <hostname-or-ip> [--namespace <namespace>] [--port <port>]"
    exit 1
fi

# Create namespace if it doesn't exist
echo "Creating namespace $NAMESPACE if it doesn't exist..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Update the ConfigMap with the provided host and port
echo "Updating ConfigMap with host=$HOST and port=$PORT..."
cat > /tmp/mikael-configmap.yaml << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: mikael-wsl-connector-config
  namespace: $NAMESPACE
data:
  wsl_host: "$HOST"
  wsl_port: "$PORT"
  description: "Mikael's WSL GPU connector for LLM inference"
  gpu_type: "NVIDIA GeForce RTX 4080"
EOF

# Apply the ConfigMap
kubectl apply -f /tmp/mikael-configmap.yaml

# Apply the Service and Deployment
echo "Deploying LLM connector service and deployment..."
kubectl apply -f kubernetes/mikael-llm-connector-service.yaml
kubectl apply -f kubernetes/mikael-llm-connector-deployment.yaml

# Check deployment status
echo "Checking deployment status..."
kubectl rollout status deployment/mikael-llm-connector -n $NAMESPACE

echo "Deployment completed successfully!"
echo "You can access the LLM connector service at: mikael-llm-connector.$NAMESPACE.svc.cluster.local:5000"

# Optional: Create a port-forward for testing
echo ""
echo "To test the connection, run:"
echo "kubectl port-forward svc/mikael-llm-connector -n $NAMESPACE 5000:5000"
echo "Then access http://localhost:5000"