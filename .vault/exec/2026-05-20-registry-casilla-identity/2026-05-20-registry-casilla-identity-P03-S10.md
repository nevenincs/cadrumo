---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S10'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P03.S10`

Added the per-modelo, rollout-staged Diseño-completeness gate to
`RegistryValidator`.

- Modified: `src/aeat/domain/calculations/registry/_validate.py`

## Description

`_emit_completeness_gate_failures` was added next to
`_emit_casilla_identity_failures` and wired into `_validate_revision`
immediately after the `(segmento, number)` identity check. For a
revision that declares a `completeness_manifest`, the gate compares the
revision's declared `(segmento, number)` casilla set against the
manifest's expected set and appends a hard failure for every divergence:
a casilla the manifest expects but the revision does not declare
(missing casilla), and a casilla the revision declares but the manifest
does not list (extra casilla). Failures are segment-qualified when a
`segmento` is set and bare-numbered otherwise.

The gate is deliberately **per-modelo and rollout-staged** per the
schema-hardening ADR's rollout discipline. A revision that has not yet
been given a `completeness_manifest` produces no failure — the
manifest-authoring migration (P05) is staged, and a casilla-bearing
revision must keep loading while its manifest is still being authored.
A modelo that HAS a manifest is enforced strictly: any divergence is a
hard `RegistryValidationError` at registry validation. The fail-closed
flip — making a missing manifest itself a hard error — is explicitly
deferred to P05, which lands after every casilla-bearing modelo carries
a manifest. Landing this Step in P03 therefore does not red any of the
26 modelos, because no manifests exist yet.

## Tests

`pytest` on `test_referential_integrity.py`, `test_modelo_200_registry.py`
and `test_modelo_parity_coverage.py` — all pass, confirming the gate is
a no-op for every manifest-less modelo and all 26 modelos remain valid.
`ruff check` on the touched file passes clean. Dedicated completeness-gate
tests (present manifest diverges / missing casilla / extra casilla) land
in `P03.S12`.
