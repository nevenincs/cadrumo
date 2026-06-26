---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S01'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---




# complete the abandoned-stale peer base-binding work for casillas 01/04/07/28 (bound to ledger_iva_aggregation base_amount_sum) by adding them to the M303 completeness manifest and construct so the calculation closure and manifest agree

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/`
- `src/aeat/_data/registry/aeat/modelos/303/`

## Description

Completed the régimen-general per-tier base bindings whose work a peer had left
stale and uncommitted (~2 days) in the M303 casilla files. The base casillas were
already bound to their `ledger_iva_aggregation` `base_amount_sum` bindings (01
super-reducido, 04 reducido, 07 general repercutido base; 28 soportado-interiores
base) and so were in the calculation closure, but they were absent from the
completeness manifest and the construct — the source of the long-standing
manifest-drift red.

- Added casillas 01/04/07/28 to the M303 completeness manifest (peer-clean file).
- Added the four base bindings to the construct's bindings list and the four
  casillas to the construct's casillas list. Construct legal coverage already held
  (art-88 repercutido base / art-92 soportado base were present).

Files under
`src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/`
(completeness_manifest, revision.toml).

## Outcome

The registry loads; casillas 01/04/07/28 leave the manifest-drift closure-only set.
The original step waited for the peer to land their bases; the peer work was
abandoned-stale, so this Step completed it additively without disturbing the peer's
casilla-bind edits and without committing.

## Notes

The remaining tree red (`test_tautology_gate` on a committed peer iva-wallet test)
is unrelated peer-owned test debt outside this campaign's surface.
