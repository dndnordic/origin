#!/bin/bash

# Script to deploy Mikael's WSL GPU connector to a Kubernetes cluster
# Usage: ./deploy-mikael-connector.sh --host <hostname-or-ip> [--namespace <namespace>] [--port <port>]

# Do not exit on errors, we want to continue regardless
set +e

# Default values
NAMESPACE="origin-system"
PORT="8000"
HOST=""
PAUSE_DURATION=30  # Seconds to pause between major steps

# Helper function for pausing with messages
pause_with_message() {
    message=$1
    duration=${2:-$PAUSE_DURATION}
    
    echo ""
    echo "===================================================="
    echo "$message"
    echo "Pausing for $duration seconds..."
    echo "===================================================="
    echo ""
    
    sleep $duration
}

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --host) HOST="$2"; shift ;;
        --namespace) NAMESPACE="$2"; shift ;;
        --port) PORT="$2"; shift ;;
        --pause) PAUSE_DURATION="$2"; shift ;;
        *) echo "Unknown parameter: $1"; echo "Continuing anyway..."; ;;
    esac
    shift
done

# Validate parameters but don't exit
if [ -z "$HOST" ]; then
    echo "Warning: --host parameter is recommended"
    echo "Using default hostname: mikael-desktop.headnet.internal"
    HOST="mikael-desktop.headnet.internal"
    pause_with_message "Using default hostname" 10
fi

# Print deployment information
echo "======================================================================"
echo "Deploying Mikael's WSL GPU connector with the following configuration:"
echo "- Host: $HOST"
echo "- Namespace: $NAMESPACE"
echo "- Port: $PORT"
echo "- Pause duration: $PAUSE_DURATION seconds"
echo "======================================================================"
sleep 5

# Step 1: Create namespace
pause_with_message "Step 1/5: Creating namespace $NAMESPACE if it doesn't exist..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
if [ $? -ne 0 ]; then
    echo "Warning: Failed to create namespace. Will attempt to continue anyway."
else
    echo "Namespace ready."
fi

# Step 2: Update and apply the ConfigMap
pause_with_message "Step 2/5: Creating and applying ConfigMap..."
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
  retry_attempts: "5"
  retry_delay_seconds: "10"
  connection_timeout_seconds: "30"
EOF

echo "ConfigMap created. Applying to Kubernetes..."
kubectl apply -f /tmp/mikael-configmap.yaml
if [ $? -ne 0 ]; then
    echo "Warning: Failed to apply ConfigMap. Will attempt to continue anyway."
else
    echo "ConfigMap applied successfully."
fi

# Step 3: Apply the Service
pause_with_message "Step 3/5: Deploying LLM connector service..."
kubectl apply -f kubernetes/mikael-llm-connector-service.yaml
if [ $? -ne 0 ]; then
    echo "Warning: Failed to apply Service. Will attempt to continue anyway."
else
    echo "Service deployed successfully."
fi

# Step 4: Apply the Deployment with a long timeout to ensure it's created
pause_with_message "Step 4/5: Deploying LLM connector deployment..."
kubectl apply -f kubernetes/mikael-llm-connector-deployment.yaml
if [ $? -ne 0 ]; then
    echo "Warning: Failed to apply Deployment. Will attempt to continue anyway."
else
    echo "Deployment created successfully."
fi

# Step 5: Wait for deployment to be ready (but don't fail if it times out)
pause_with_message "Step 5/5: Waiting for deployment to become ready... (this may take several minutes)"
echo "Checking deployment status (timeout after 5 minutes)..."
kubectl rollout status deployment/mikael-llm-connector -n $NAMESPACE --timeout=300s
if [ $? -ne 0 ]; then
    echo "Warning: Deployment is not ready yet, but we'll continue."
    echo "You can check the status later with: kubectl rollout status deployment/mikael-llm-connector -n $NAMESPACE"
else
    echo "Deployment is ready!"
fi

# Display pods for verification
echo ""
echo "Current pods in the $NAMESPACE namespace:"
kubectl get pods -n $NAMESPACE
sleep 5

# Display helpful information
echo ""
echo "=================================================================="
echo "Deployment process completed!"
echo "=================================================================="
echo ""
echo "Your LLM connector service is accessible at:"
echo "mikael-llm-connector.$NAMESPACE.svc.cluster.local:5000"
echo ""
echo "To test the connection, run:"
echo "kubectl port-forward svc/mikael-llm-connector -n $NAMESPACE 5000:5000"
echo "Then access http://localhost:5000/health"
echo ""
echo "To check the logs of the connector:"
echo "kubectl logs -f deployment/mikael-llm-connector -n $NAMESPACE"
echo ""
echo "If the connector isn't working properly, verify that Mikael's WSL"
echo "environment is running the connector service at $HOST:$PORT"
echo "=================================================================="