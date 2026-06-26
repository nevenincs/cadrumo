---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S05'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---




# fix the prorrata-porcentaje no-volume-data default from 0 to 100 (full right to deduct, LIVA art-94) so a fully-taxable trader's export unblocks, with a regression test - the correct peer-clean fix for defect C2

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/303/`

## Description

Fixed the Modelo 303 prorrata export-block (defect C2) at its root: the
prorrata-porcentaje formula returned the literal 0 when no prorrata-volume data
was declared (volumen-total = 0). For a fully-taxable trader — the common autónomo
with no exempt-without-right operations — there is no prorrata limitation, so the
regulated deduction percentage is 100 (full right to deduct, LIVA art. 94). The
0 default zeroed every deduction and diverged from the 100 the filing validator
expects, blocking the filing.

- Changed the `if_then_else` else branch of `modelo-303-iva-prorrata-porcentaje`
  from `literal = "0"` to `literal = "100"` in the M303 revision (peer-clean file;
  not the peer-held casilla file).
- Added regression `test_modelo_303_prorrata_defaults_to_100_when_no_volume_data`
  proving prorrata-porcentaje resolves to 100 with no volume data, with the
  expected value derived from the regulated full-deduction default (not re-running
  the formula).

Modified files:

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`
- `src/aeat/domain/calculations/registry/tests/test_modelo_303_registry.py`

## Outcome

178 M303 registry + formula-runtime + application tests pass plus the new
regression; prorrata-porcentaje = 100 in the no-volume case, unblocking a
fully-taxable trader's filing. This is the correct, peer-clean resolution of C2 —
better than the volume-binding originally planned (S03/S04), which a per-period
base sum cannot implement correctly for mixed traders.

## Notes

The faithful mixed-trader prorrata (the prior-year definitive percentage applied
provisionally with Q4 regularisation, LIVA art. 104/104bis) is a cross-period
stateful mechanism and remains ADR-deferred; S03/S04 are re-scoped to record that
the per-period volume binding would ship wrong figures and is superseded by this
formula default for the common case. No peer-held M303 file was edited (the
formula lives in revision.toml, which is peer-clean).
