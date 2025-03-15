# Governance Repository Security Setup

This document outlines the security measures that must be applied to the governance repository to ensure proper oversight and authority.

## Branch Protection Rules

Branch protection rules must be applied to the `main` branch to ensure all changes go through proper review:

1. Go to the repository settings: https://github.com/dndnordic/origin/settings/branches
2. Click "Add rule" and set the following:
   - Branch name pattern: `main`
   - Require pull request reviews before merging: ✓
   - Required approving reviews: 1
   - Dismiss stale pull request approvals when new commits are pushed: ✓
   - Require review from Code Owners: ✓
   - Restrict who can dismiss pull request reviews: ✓ (Only Mikael)
   - Require status checks to pass before merging: ✓
   - Require branches to be up to date before merging: ✓
   - Require signed commits: ✓
   - Include administrators: ✓ (Very important - ensures even admins follow rules)
   - Restrict who can push to matching branches: ✓ (Limit to Mikael and dnd-genesis)
   - Allow force pushes: ✗
   - Allow deletions: ✗

## CODEOWNERS Setup

The CODEOWNERS file (already in the repository) ensures that:
1. Mikael must review all changes to the repository
2. Security-critical files can only be approved by Mikael
3. Certain infrastructure files can be reviewed by either Mikael or dnd-genesis

## Signature Requirements

All commits to the repository must be signed. To set up GPG signing:

1. Generate a GPG key: 
   ```
   gpg --full-generate-key
   ```
   
2. List your keys to get the ID:
   ```
   gpg --list-secret-keys --keyid-format=long
   ```
   
3. Export your public key:
   ```
   gpg --armor --export YOUR_KEY_ID
   ```
   
4. Add the GPG key to your GitHub account:
   - Go to Settings → SSH and GPG keys → New GPG key
   - Paste your public key and save

5. Configure git to use your GPG key:
   ```
   git config --global user.signingkey YOUR_KEY_ID
   git config --global commit.gpgsign true
   ```

## YubiKey Integration

For enhanced security, Mikael's GPG key should be stored on a YubiKey:

1. Export the GPG key to the YubiKey (follow YubiKey documentation)
2. Configure git to use the YubiKey for signing:
   ```
   git config --global user.signingkey YOUR_KEY_ID
   git config --global commit.gpgsign true
   ```

## Security Monitoring

1. Enable email notifications for all repository events
2. Set up automated security scanning for all pull requests
3. Regularly audit access and permissions