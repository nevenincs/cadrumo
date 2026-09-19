---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:90d13efd23c6a4d89d4a3aa89c647feab378848f5e724cc7dc315fa1f177f3c0'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `P05 S130 code review`

## Scope

Independent review of S130 predecessor `dfdd054b32` and closure `80d4f65aa4`, the CI-lane plan and evidence ADRs, all five owner modules, direct consumers, terminal-precondition inventory, tests, size/baseline state, and current `HEAD`.

## Findings

No HIGH, CRITICAL, MEDIUM, or LOW findings.

## Recommendations

No follow-up is required from this review.

The split has coherent direct ownership: IVA screening, IVA refusal, Renta expenses, retenciones and support live in their respective defining modules, while `_modelo_bindings.py` keeps calculation-facing resolver assembly without a facade re-export. The terminal inventory includes the refusal and retenciones owners; M100/Renta, IVA/refusal and retenciones paths retain their real focused evidence. The execution record supplies executable commands and literal `20 passed` plus intentional M100 deselection evidence. All owners remain below the default ceiling; `_modelo_bindings.py`'s stale hub pin is explicitly deferred only to P05.S227, with no baseline raise.
