---
tags:
  - '#audit'
  - '#registry-integrity-cli-rehome'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:59ec49cfb4b1e801bff8d29d2a93a6a15fe0d5ebfbe2aa4418fde2b928c6b198'
related: []
---

# `registry-integrity-cli-rehome` audit: `Registry integrity CLI rehome`

## Scope

Retire `aeat app registry verify`, place the registry/legal-corpus integrity gate under
`python -m dev.registry.conformance integrity`, preserve the CI gate through
`just check-registry`, retarget product recovery actions, and remove the no-op
post-load authority validation.

## Findings

## Recommendations
