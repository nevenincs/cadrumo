---
tags:
  - '#audit'
  - '#docs-static-deployment'
date: '2026-07-10'
modified: '2026-07-10'
related: []
---
# `docs-static-deployment` audit: `Docs delivery policy`

## Scope

Review deployment policy, the static origin, and the publish command.

## Findings

### GitHub publishing | high | Release policy forbids it.

`2026-04-12-release-please-adr` forbids GitHub Actions publishing.

### Existing CI | low | Verification is allowed.

`2026-04-12-ci-github-actions-adr` allows read-only CI without secrets.

### static-origin | pass | No critical or high issue remains.

Template validation passes and dotted bucket names are rejected.

### docs-publish | pass | No critical or high issue remains.

The command binds uploads to CloudFormation outputs and verifies the canonical host.

## Recommendations

- Use a human-gated local AWS deployment script.
- Do not add a GitHub deployment workflow.
- Keep docs verification in existing CI.
