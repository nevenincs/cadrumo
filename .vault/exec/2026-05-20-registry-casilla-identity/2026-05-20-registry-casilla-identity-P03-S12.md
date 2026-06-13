---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S12'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P03.S12`

Added completeness-gate tests covering a present-manifest divergence, a
missing casilla, and an extra casilla against the live
`RegistryValidator`.

- Modified: `src/aeat/domain/calculations/registry/test_referential_integrity.py`

## Description

Five real-behaviour tests were added, each exercising the live
`RegistryValidator` against constructed `ModeloDefinition` /
`ModeloRevision` material carrying a `DisenoCompletenessManifest` — no
mocks, stubs, skips, or xfail markers. A `_completeness_manifest` helper
builds a minimal manifest grounded on the dummy catalogues; the manifest
is attached to a revision via `model_copy`.

- `test_revision_without_manifest_passes_completeness_gate` — a
  manifest-less revision clears the gate, confirming the rollout-staged
  posture (the gate is a no-op until a manifest is authored).
- `test_completeness_gate_passes_when_manifest_matches_declared_casillas`
  — a revision whose declared casilla set exactly matches its manifest
  validates clean.
- `test_completeness_gate_fails_on_missing_casilla` — a manifest
  expecting casilla `'02'` that the revision omits raises a hard
  `RegistryValidationError` naming the missing casilla.
- `test_completeness_gate_fails_on_extra_casilla` — a casilla `'02'` the
  revision declares but the manifest omits raises a hard
  `RegistryValidationError` naming the extra casilla.
- `test_completeness_gate_fails_on_diverging_segment_qualified_manifest`
  — a multi-segment divergence where the revision declares `00562` under
  `DP200014` and the manifest expects it under `DP200032`; the gate
  reports both the missing and extra segment-qualified pairs, proving the
  gate keys on the `(segmento, number)` identity pair.

The missing-manifest fail-closed case is intentionally NOT asserted as a
hard error here: P03 keeps the gate rollout-staged so a revision with no
manifest passes (covered by the first test). The fail-closed flip lands
in P05 once every casilla-bearing modelo carries a manifest.

## Tests

`pytest` on the five new tests passes; the full
`test_referential_integrity.py` module and `test_modelo_parity_coverage.py`
pass, confirming all 26 modelos remain valid. `ruff check` on the
touched file passes clean.
