# Mikael's WSL GPU Setup for Origin System

This document provides instructions for setting up Mikael's Windows machine with WSL and GPU access for the Origin system.

## Overview

The setup allows the Origin system to use Mikael's NVIDIA GeForce RTX 4080 GPU for LLM inference operations through a connector service running in WSL, which is accessed by a Kubernetes deployment in the Origin system.

## Prerequisites

- Windows 11 with WSL 2 installed
- NVIDIA GeForce RTX 4080 GPU
- NVIDIA drivers for Windows with WSL support
- GitHub Actions runner with custom labels: `self-hosted`, `Windows`, `WSL`, `GPU`

## Setup Process

The setup process consists of three main parts:

1. Setting up the GitHub runner on Mikael's Windows machine
2. Setting up PyTorch with CUDA support in WSL
3. Setting up the WSL connector service
4. Deploying the Origin connector to a Kubernetes cluster

### 1. Setting up the GitHub Runner

The GitHub runner has already been set up on Mikael's Windows machine with the following labels:
- `self-hosted`
- `Windows`
- `WSL`
- `GPU`

### 2. Setting up PyTorch with CUDA Support

The PyTorch environment has been set up in WSL on Mikael's machine with CUDA support. To activate the environment, run:

```bash
wsl
~/activate-origin-llm.sh
```

This will activate the Python virtual environment with PyTorch and CUDA support.

### 3. Setting up the WSL Connector Service

The WSL connector service has been set up to listen on port 8000. To start the service manually, run:

```bash
wsl
~/activate-origin-llm.sh
python ~/origin-wsl-simple.py
```

This will start the connector service that listens for connections from the Origin system and provides access to the GPU for inference operations.

### 4. Deploying the Origin Connector to Kubernetes

To deploy the Origin connector to a Kubernetes cluster, you need to know the hostname or IP address of Mikael's machine. Then run:

```bash
./scripts/deploy-mikael-connector.sh --host <mikael-hostname-or-ip>
```

This will deploy a Kubernetes service and deployment that will connect to Mikael's WSL connector service.

## Verification

To verify that the setup is working correctly, you can run the following tests:

1. Verify GPU access in WSL:
   ```bash
   wsl
   nvidia-smi
   ```

2. Verify PyTorch with CUDA support:
   ```bash
   wsl
   ~/activate-origin-llm.sh
   python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
   ```

3. Test the connector service:
   ```bash
   wsl
   ~/activate-origin-llm.sh
   python ~/origin-wsl-simple.py
   ```

4. Test the Kubernetes connector:
   ```bash
   kubectl port-forward svc/mikael-llm-connector -n origin-system 5000:5000
   curl http://localhost:5000/health
   ```

## Troubleshooting

If you encounter any issues with the setup, check the following:

1. Verify that the WSL 2 is running correctly:
   ```bash
   wsl --status
   ```

2. Verify that the NVIDIA drivers are installed correctly in WSL:
   ```bash
   wsl
   nvidia-smi
   ```

3. Verify that the connector service is running in WSL:
   ```bash
   wsl
   ps -ef | grep origin-wsl
   ```

4. Check the logs of the connector service:
   ```bash
   wsl
   cat ~/connector-test.log
   ```

5. Check the logs of the Kubernetes connector:
   ```bash
   kubectl logs -f deployment/mikael-llm-connector -n origin-system
   ```

## Resources

- [NVIDIA CUDA WSL Documentation](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)
- [PyTorch CUDA Documentation](https://pytorch.org/docs/stable/notes/cuda.html)
- [WSL 2 Documentation](https://learn.microsoft.com/en-us/windows/wsl/about)