---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S93'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Repair the audited identity-authority regression chain and preserve concurrent locale remediation

## Scope

- `.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md`
- `src/cadrumo/core/product_identity.py`
- `src/cadrumo/core/tests/test_product_identity.py`
- `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md`
- `S89 and S90 execution records`
- `S93 execution record`

## Description

- Restore the accepted identity matrix after the audited `38894ca`, `258abf`, and `e097` regression chain.
- Bind the runtime tuple and its focused contract to product display `CADRUMO` and human executable `aeat`.
- Remove the false second operator re-confirmation, title-case mandate, and appended S89/S90 supersession narratives.
- Preserve the historical S89 and S90 evidence, including their original outcomes and overlap notes.
- Reopen S62-S67 for fresh descendant evidence while keeping historical S89/S90 closed and active S91/S92 open.
- Preserve concurrent plan closures and the active S92 row without editing any S92 runtime, i18n, locale, or parity path.

## Outcome

- The accepted ADR, immutable tuple, and focused contract again agree on the exact matrix: `CADRUMO`, `aeat`, lowercase `cadrumo` machine identities, `cadrumo-mcp`, `CADRUMO_`, both companion distributions, `cadrumo_data`, and authority `AEAT`.
- S05, S86, and S62-S67 are open; S89 and S90 remain historically closed; S91 and S92 remain open; S93 alone closes for this repair.
- The shared plan necessarily cross-commits pre-existing independently evidenced closures and the open S91/S92 rows while preserving their current state.
- The S89 and S90 records retain their original historical evidence and no longer contain the false current-tree supersession appendices.
- Five focused identity tests, Ruff lint and format checks, the exact live tuple assertion, naming-rule synchronization, and the Vaultspec plan check passed.
- Live `aeat --version` reports `CADRUMO 0.1.1`; live `aeat --help` displays `CADRUMO`, authority `AEAT`, `aeat` invocations, and `CADRUMO_` environment guidance.

## Notes

- `_render.py`, the core i18n facade and tests, locale manager/CLI/tests, locale YAML, parity tests, runtime CLI implementation, and descendant CLI prose are outside this Step and were not edited.
- S62-S67 remain open because this authority-only Step does not replace fresh descendant source, catalogue, generated parity, and locale-normalization evidence, even though the current default live help already acknowledges the binding display.

## Status note: retired by S87 contextual-casing remediation

The Description and Outcome above are preserved as historical execution
evidence, not active instructions. S87 retires this reopened lane without
re-executing it: directives to remove the title-case mandate or bind every
prose surface to all-caps are superseded by the contextual contract of
`Cadrumo` in sentence prose and `CADRUMO` in identity contexts.
