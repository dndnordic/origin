# Tailscale Network for Origin and Singularity

This document describes how to use the Tailscale mesh network for secure communication between dndnordic repositories and services.

**Managed by:** dnd-genesis and mikki

## Available Infrastructure

- **Mikael's WSL Machine (MIKKI-BUNKER)**: 
  - Hardware: Windows with GPU
  - Hosts the central LLM Ingest Server
  - Provides access to inexpensive token processing
  - Accessible to both Origin and Singularity
  - Used only for token processing, not for running applications

- **Linux Docker Builder Runner**:
  - Labels: `self-hosted, Linux, Docker, X64, builder`
  - Used for container builds and deployments
  - Used by both repositories for image building
  - Managed by Mikael (@mikki)

## Repository Structure

- **Origin**: 
  - Governance system that oversees Singularity
  - Includes central LLM service configuration
  - Connects to Mikael's ingest server for token processing
  - Builds its own Docker images on the Linux builder
  - Deploys services to Kubernetes

- **Singularity**: 
  - Core AI engine with self-evolution capabilities
  - Builds its own Docker images on the Linux Docker runner
  - Connects to the same central LLM ingest server as Origin
  - Uses the shared token processing service for operations

## How to Use Infrastructure in Workflows

### For Docker Build and Deployment Operations

Use the Linux Docker builder runner for all container-related operations:

```yaml
jobs:
  docker-build-job:
    runs-on: [self-hosted, Linux, Docker, X64, builder]
    steps:
      # Docker build steps here
```

### For Connecting to the LLM Ingest Server

Both repositories should connect to the centralized LLM ingest server over Tailscale:

```
# Example Python code for connecting to the ingest server via Tailscale
import requests

def process_tokens(prompt):
    # Using Tailscale .local domain for secure access
    response = requests.post(
        "http://mikki-bunker.local:8000/api/generate",
        json={
            "prompt": prompt,
            "max_tokens": 100
        },
        headers={
            "Authorization": "Bearer ${INGEST_API_KEY}"
        }
    )
    return response.json()
```

For external access (optional), the Origin system manages a Cloudflare Zero Trust tunnel:

```
# Example external access through Cloudflare Zero Trust
import requests

def process_tokens_external(prompt):
    response = requests.post(
        "https://llm-api.dndnordic.com/api/generate",
        json={
            "prompt": prompt,
            "max_tokens": 100
        },
        headers={
            "Authorization": "Bearer ${INGEST_API_KEY}",
            "CF-Access-Client-Id": "${CF_CLIENT_ID}",
            "CF-Access-Client-Secret": "${CF_CLIENT_SECRET}"
        }
    )
    return response.json()
```

## Important Notes

- Only Mikael should manage the infrastructure
- Both repositories share one centralized LLM ingest server
- All communication happens over the Tailscale VPN mesh network
- External access is optionally managed by Origin using Cloudflare Zero Trust
- Each repository builds its own Docker images on the shared Linux Docker runner
- The LLM ingest server runs on Mikael's Windows machine (mikki-bunker.local) with GPU
- The Docker builder runs on a Linux server (linux-builder.local)
- All machines must be connected to the Tailscale network
- Services are accessed via their .local domains inside the Tailscale network
- Each repository maintains its own deployment workflow
- All infrastructure is already set up and maintained by Mikael

## Tailscale VPN Setup

To connect to the Tailscale network:

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Join the network - follow prompts to authenticate
sudo tailscale up

# Verify connection and see available machines
tailscale status

# Test connection to services
ping mikki-bunker.local
ping linux-builder.local
```

## Deployment Architecture with Tailscale

```
┌───────────────────┐      ┌───────────────────┐     ┌───────────────────┐
│   Genesis Repo    │      │   Origin Repo     │     │ Singularity Repo  │
├───────────────────┤      ├───────────────────┤     ├───────────────────┤
│ - Admin Access    │──┐   │ - Governance      │     │ - AI Engine       │
│ - API Keys        │  │   │ - Configuration   │◄────┤ - Self-Evolution  │
│ - Secrets         │  │   │ - CF Zero Trust   │     │ - Implementation  │
└───────────────────┘  │   └───────┬───────────┘     └────────┬──────────┘
                       │           │                          │
                       │           │                          │
                       │           └──────────┬──────────────┘
                       │                      │
                       ▼                      ▼
         ┌───────────────────────────────────────────┐
         │            Tailscale Mesh Network         │
         │                                           │
         │  ┌───────────────────┐ ┌──────────────┐   │  ┌───────────────┐
         │  │ mikki-bunker.local│ │genesis-admin │   │  │Docker Registry│
         │  ├───────────────────┤ ├──────────────┤   │  ├───────────────┤
         │  │ - LLM Ingest      │ │- Admin Keys  │   │  │ - origin      │
         │  │   Server (8000)   │ │- Permissions │   │  │ - singularity │
         │  └───────────────────┘ └──────────────┘   │  └───────────────┘
         │                                           │
         │  ┌───────────────────┐                    │  ┌───────────────┐
         │  │ linux-builder.local                    │  │ External      │
         │  ├───────────────────┤                    │  │ Access (Opt.) │
         │  │ - Docker Builder  ├────────────────────┼──► - Cloudflare  │
         │  │   Runner          │                    │  │   Zero Trust  │
         │  └───────────────────┘                    │  └───────────────┘
         └───────────────────────────────────────────┘
```

