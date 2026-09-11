---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:8dc716bf62a1261868ba37f1f8dbdde07432f0af799cc874fdf5dca75ede9ca3'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S33 routing retirement`

## Scope

Reviewed the S33 removal of the two residual routing aliases, including the retenciones resolver relocation, CLI consumers, registry-applicability calendar derivation, and the external-constants negative census.

## Findings

No material findings. The old aliases and private retenciones module have no remaining production reference; consumers read their specialized owner directly, the calendar derives IVA coverage from applicability rules, and the retirement census asserts absence plus the technical boundary.

## Recommendations

No remediation is required for S33.
