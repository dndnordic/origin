# User Creation Instructions

To properly set up the governance system, we need to create these GitHub users:

## dnd-origin

This account represents the Origin governance system. It needs:
- Write access to singularity repository
- Write access to genesis repository
- Read access to origin repository (can never approve changes to itself)

## dnd-singularity

This account represents the Singularity system. It needs:
- Write access to its own repository
- No access to origin repository

## Steps to create these accounts

1. Create both GitHub accounts with unique email addresses
2. Add them to the dndnordic organization
3. Configure repository permissions:
   - origin repository: dnd-origin = Read
   - singularity repository: dnd-origin = Write, dnd-singularity = Write
   - genesis repository: dnd-origin = Write

## Branch protection rules

For the origin repository:
\\\

Run this command to apply branch protection:
\\{"message":"Invalid request.\n\nNo subschema in \"anyOf\" matched.\nNo subschema in \"anyOf\" matched.\nNo subschema in \"anyOf\" matched.\nNo subschema in \"anyOf\" matched.\nNo subschema in \"anyOf\" matched.\nNo subschema in \"anyOf\" matched.\nNo subschema in \"anyOf\" matched.\nNo subschema in \"anyOf\" matched.\nNo subschema in \"anyOf\" matched.\nFor 'properties/strict', \"true\" is not a boolean.\nNot all subschemas of \"allOf\" matched.\nFor 'anyOf/1', {\"contexts\" => [\"security-scan\"], \"strict\" => \"true\"} is not a null.\nFor 'properties/dismiss_stale_reviews', \"true\" is not a boolean.\nFor 'properties/require_code_owner_reviews', \"true\" is not a boolean.\nFor 'properties/required_approving_review_count', \"1\" is not an integer.\nNot all subschemas of \"allOf\" matched.\nFor 'anyOf/1', {\"bypass_pull_request_allowances\" => {\"users\" => [\"mikkihugo\"]}, \"dismiss_stale_reviews\" => \"true\", \"dismissal_restrictions\" => {\"users\" => [\"mikkihugo\"]}, \"require_code_owner_reviews\" => \"true\", \"required_approving_review_count\" => \"1\"} is not a null.\nFor 'allOf/0', \"true\" is not a boolean.\nNot all subschemas of \"allOf\" matched.\nFor 'anyOf/1', \"true\" is not a null.\nFor 'allOf/0', \"true\" is not a boolean.\nNot all subschemas of \"allOf\" matched.\nFor 'anyOf/1', \"true\" is not a null.\nFor 'allOf/0', \"true\" is not a boolean.\nNot all subschemas of \"allOf\" matched.\nFor 'anyOf/1', \"true\" is not a null.\nFor 'allOf/0', \"false\" is not a boolean.\nNot all subschemas of \"allOf\" matched.\nFor 'anyOf/1', \"false\" is not a null.\nFor 'allOf/0', \"false\" is not a boolean.\nNot all subschemas of \"allOf\" matched.\nFor 'anyOf/1', \"false\" is not a null.\n\"teams\" wasn't supplied.\nNot all subschemas of \"allOf\" matched.\nFor 'anyOf/1', {\"users\" => [\"mikkihugo\", \"dnd-genesis\"]} is not a null.\nFor 'allOf/0', \"true\" is not a boolean.\nNot all subschemas of \"allOf\" matched.\nFor 'anyOf/1', \"true\" is not a null.","documentation_url":"https://docs.github.com/rest/branches/branch-protection#update-branch-protection","status":"422"}\
