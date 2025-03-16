# GitHub Setup for Origin Governance System

To complete the setup of the governance system, please follow these instructions to configure GitHub repositories and users correctly.

## GitHub Users

The following users have been created:
- **mikkihugo**: Mikael Hugo, the human authority
- **dnd-genesis**: Infrastructure deployment account
- **dnd-origin**: The Origin governance system
- **dnd-singularity**: The Singularity AI system

## Required Repository Settings

### 1. Organization Setup

First, ensure all users are members of the dndnordic organization:

```bash
# Check current organization members
gh api orgs/dndnordic/members

# For each user, add to organization if not already a member
gh api orgs/dndnordic/memberships/dnd-origin --method PUT
gh api orgs/dndnordic/memberships/dnd-singularity --method PUT
```

### 2. Repository Permissions

Set appropriate permissions for each repository:

#### Origin Repository (dndnordic/origin)

```bash
# Ensure key human users have admin access
gh api repos/dndnordic/origin/collaborators/mikkihugo --method PUT -f permission=admin

# Genesis account for infrastructure management
gh api repos/dndnordic/origin/collaborators/dnd-genesis --method PUT -f permission=admin

# Origin system: read-only access (can see but not approve)
gh api repos/dndnordic/origin/collaborators/dnd-origin --method PUT -f permission=read

# Singularity system: no access at all
gh api repos/dndnordic/origin/collaborators/dnd-singularity --method DELETE || true
```

#### Singularity Repository (dndnordic/singularity)

```bash
# Mikael: admin access
gh api repos/dndnordic/singularity/collaborators/mikkihugo --method PUT -f permission=admin

# Genesis: admin access
gh api repos/dndnordic/singularity/collaborators/dnd-genesis --method PUT -f permission=admin

# Origin: write access (allows approving changes)
gh api repos/dndnordic/singularity/collaborators/dnd-origin --method PUT -f permission=write

# Singularity: write access (allows proposing changes to itself)
gh api repos/dndnordic/singularity/collaborators/dnd-singularity --method PUT -f permission=write
```

#### Genesis Repository (dndnordic/genesis)

```bash
# Mikael: admin access
gh api repos/dndnordic/genesis/collaborators/mikkihugo --method PUT -f permission=admin

# Genesis: admin access
gh api repos/dndnordic/genesis/collaborators/dnd-genesis --method PUT -f permission=admin

# Origin: write access (allows approving changes)
gh api repos/dndnordic/genesis/collaborators/dnd-origin --method PUT -f permission=write

# Singularity: no access
gh api repos/dndnordic/genesis/collaborators/dnd-singularity --method DELETE || true
```

### 3. Branch Protection for Origin Repository

To ensure Mikael has final authority over Origin changes:

1. In GitHub web interface, go to the Origin repository
2. Navigate to Settings > Branches > Branch protection rules
3. Click "Add rule"
4. Set the branch name pattern to "main"
5. Enable these settings:
   - ✅ Require a pull request before merging
   - ✅ Require approvals (1)
   - ✅ Dismiss stale pull request approvals when new commits are pushed
   - ✅ Require review from Code Owners
   - ✅ Restrict who can push to matching branches: add only mikkihugo and dnd-genesis
   - ✅ Require signed commits
   - ✅ Require linear history
   - ✅ Require conversation resolution before merging
   - ✅ Do not allow bypassing the above settings
   - ✅ Include administrators (critical for security!)
   
Alternatively, try the GitHub CLI (might need manual configuration through web UI):

```bash
gh api repos/dndnordic/origin/branches/main/protection \
  --method PUT \
  --raw-field '{
    "required_status_checks": {
      "strict": true,
      "contexts": ["security-scan"]
    },
    "enforce_admins": true,
    "required_pull_request_reviews": {
      "dismissal_restrictions": {
        "users": ["mikkihugo"],
        "teams": []
      },
      "dismiss_stale_reviews": true,
      "require_code_owner_reviews": true,
      "required_approving_review_count": 1
    },
    "restrictions": {
      "users": ["mikkihugo", "dnd-genesis"],
      "teams": []
    },
    "required_linear_history": true,
    "allow_force_pushes": false,
    "allow_deletions": false,
    "required_conversation_resolution": true,
    "required_signatures": true
  }'
```

### 4. Setup GitHub Webhooks

For GitHub webhook integration:

1. Go to the Origin repository settings: Settings → Webhooks → Add webhook
2. Set Payload URL to: `https://origin-api.dndnordic.com/api/github/webhook`
3. Content type: `application/json`
4. Secret: Same as the `GITHUB_WEBHOOK_SECRET` in your secrets
5. Events: Select "Pull requests" and "Pull request reviews"
6. Add webhook

## Security Verification

After completing these steps, verify the security model works as expected:

1. Try creating a PR to Origin as dnd-origin (should be able to create PR but not approve)
2. Try creating a PR to Singularity as dnd-origin (should be able to create AND approve)
3. Try creating a PR to Origin as dnd-singularity (should be denied access)
4. Try creating a PR to Origin as mikkihugo (should be able to create and approve)

This ensures the proper security boundaries are in place for the governance hierarchy.