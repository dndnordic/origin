# Mikael's Governance System

This repository contains the governance system for overseeing the Singularity AI project.

## Purpose

The primary purpose of this repository is to provide a complete governance system that ensures:

1. Mikael maintains full oversight over the Singularity system
2. All significant changes go through appropriate approval processes
3. Secure, immutable records are maintained of all governance decisions
4. Clear separation exists between governance and Singularity systems

## Security Model

This repository implements strict security practices:

- All commits must be signed
- Branch protection requires pull request approval
- No direct pushes to protected branches
- YubiKey authentication for critical operations

## Repository Structure

- `/src` - Source code for governance systems
- `/kubernetes` - Deployment configuration
- `/docs` - Documentation