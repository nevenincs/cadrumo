---
tags:
  - '#audit'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:e28345977673f50a0e89f6796964b61317d367aa1b9c557a7c9622292b353524'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# `canonical-identifiers` audit: `s11 contract`

## Scope

Audit the S11 CLI declaration-row contract migration from bare `str` to the
canonical `AeatExpedienteId` alias.

## Findings

No S11 findings. The payload imports `AeatExpedienteId` through the canonical
public `core.identity` facade and reuses its existing 12-32 uppercase
alphanumeric AEAT constraint. The diff changes no other declaration field,
wire key, producer, or registration.

### unrelated-focused-lane-failures | low | Existing integration inventory assertions are red

The focused live-read integration module has 33 passing tests and one failure
because the asserted subgroup inventory omits `deudas`. The wider
schema-conformance lane has 332 passing tests and one profile-precondition
refusal for `--tax-residence-jurisdiction-scope`. Neither signature references
the S11 payload or its identifier constraint.

## Recommendations

Repair the live-read subgroup inventory and profile-precondition expectation in
their owning campaigns; do not widen S11 beyond its one declared payload field.
