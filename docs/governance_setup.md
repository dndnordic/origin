# Governance System User Setup Guide

This document provides instructions for setting up the correct GitHub users and permissions to implement the security model of the Origin governance system.

## User Accounts and Their Roles

### 1. mikkihugo (Mikael Hugo)
- **Role**: Human authority and ultimate approver
- **Permissions needed**:
  - Admin access to Origin repository
  - Final approval rights for all Origin changes
  - Only user who can approve self-improvement proposals

### 2. dnd-genesis
- **Role**: Infrastructure and setup account
- **Permissions needed**:
  - Admin access to all repositories for setup and maintenance
  - Used for CI/CD and deployment operations

### 3. dnd-origin
- **Role**: The Origin governance system itself
- **Permissions needed**:
  - **Read-only** access to Origin repository (cannot approve changes to itself)
  - Write access to Singularity repository (can approve Singularity changes)
  - Write access to Genesis repository (can approve Genesis changes)

### 4. dnd-singularity
- **Role**: The Singularity AI system itself
- **Permissions needed**:
  - Write access to its own repository (can propose self-improvements)
  - No access to Origin repository

## Setup Instructions

### Creating the User Accounts

1. Create GitHub accounts for `dnd-origin` and `dnd-singularity` with secure credentials
2. Add these accounts to the dndnordic organization
3. Store credentials securely in the vault

### Setting Repository Permissions

#### Origin Repository (`dndnordic/origin`)
- mikkihugo: Admin
- dnd-genesis: Admin
- dnd-origin: Read
- dnd-singularity: No access

#### Singularity Repository (`dndnordic/singularity`)
- mikkihugo: Admin
- dnd-genesis: Admin
- dnd-origin: Write (allows approving Singularity changes)
- dnd-singularity: Write (allows proposing self-improvements)

#### Genesis Repository (`dndnordic/genesis`)
- mikkihugo: Admin
- dnd-genesis: Admin
- dnd-origin: Write (allows approving Genesis changes)
- dnd-singularity: No access

### Enabling Branch Protection

Run the `Setup Repository Settings` workflow in the GitHub Actions UI to configure:

1. Branch protection rules for the `main` branch
2. Required reviews from code owners (Mikael)
3. Required status checks
4. Signature verification requirements

### Configuring Automation

1. Set up GitHub Actions for CI/CD
2. Configure the GitHub webhook to notify the Origin API
3. Set up self-hosted runners on:
   - Mikael's WSL environment
   - Vultr cloud infrastructure

## Verification Steps

After setup, verify the correct permissions by:

1. Having dnd-origin attempt to approve a change to the Origin repository (should fail)
2. Having dnd-origin approve a change to the Singularity repository (should succeed)
3. Having Mikael approve a change to the Origin repository (should succeed)
4. Having dnd-singularity attempt to access the Origin repository (should fail)

## Emergency Procedures

In case of security issues:

1. Mikael can revoke all bot account tokens using the YubiKey-secured killswitch
2. Reset credentials and rotate all tokens
3. Review audit logs for unauthorized access attempts