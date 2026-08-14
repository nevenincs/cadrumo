---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:d32b3bf0ca9b8d6d02fa20c6bcfff230adb9dab0e5a157ee606d691d14aa93d9'
step_id: 'S39'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Classify every modelo-conditional branch the drift census found outside the registry package on the axis of orchestration routing versus regulatory treatment, exhaustively and by derivation in the shape the modelo-specific embed classifier already uses, because the census supplies the derived set and only the adjudication is missing, with a gate that reds on any branch in the derived set left unclassified

## Scope

- `dev/quality/`
- `src/cadrumo/`
- `src/cadrumo/tests/`

## Description

- Add `dev/quality/modelo_branch_classification.py`: reads the derived branch set
  from the drift census rather than walking the tree a second time, extracts the
  guarded region for every site, and reconciles the set against the ledger.
- Add `dev/quality/modelo_branch_classification.toml`: five shared reasonings
  authored once and referenced by id, one row per site, each orchestration row
  citing a token the gate verifies against the branch at HEAD.
- Add the gate under `src/cadrumo/tests/`: zero unclassified, zero stale rows,
  zero broken citations, a planted branch refused, a broken citation detected,
  and a citation-free orchestration claim refused at load.

## Outcome

128 branches outside the registry package across 65 files, every one adjudicated
after reading it: **115 orchestration routing**, **13 regulatory treatment**. The
14 branches inside the registry package are left to the embed classifier, which
derives the same sites from its own signals; adjudicating them here would give
one site two ledgers that can disagree.

The thirteen regulatory-treatment sites fall into three shapes. Six select WHICH
CASILLA a value lands in per modelo, which is registry data a binding declares as
its target; one of them says so in its own docstring, describing itself as the
output half of a fact the registry already declares. Four decide whether an
obligation applies or what it resolves to on a condition the law fixes, several
citing their governing article in a comment beside the branch. Three encode a
convention of the official design that differs by modelo: a sign rule, a filing
period ordering, and which detail-row section satisfies a required casilla.

The named input is answered: the hardcoded revision ids in
`_iva_wallet_relation_targets.py` are NOT injected as a selector. Every caller
passes the revision id off the already-resolved snapshot, and the literals are
used only as a membership test on that law-determined coordinate. No production
call site passes a literal revision id into snapshot resolution. The machinery
classification stands; the residual is that a Python-resident enumeration of
revision coordinates is registry-shaped data, which is the ordinary embed axis
rather than the more serious selector-injection defect.

Deletion-inventory entries consumed: none. This row classifies and deletes
nothing.

Gate bite proof: a planted module with one modelo branch produced one
unclassified site and exit code 1; removing it restored exit code 0. Nothing
tracked was modified.

## Notes

The sibling embed classifier keeps a machinery claim honest by requiring it to
dispose of every regulatory literal detected in the same module. That mechanism
does not transplant to this axis and the measurement said so before anything was
built: of 128 branch sites, 8 carry any literal inside the guarded body, and most
of those matches were spurious -- `ImportError` contains the substring `importe`,
`FILING_BASELINE` contains `_base`. A disposal rule on that basis would have
reported clean because almost nothing could reach it, and fired wrongly when it
did. It was not shipped.

The honesty mechanism used instead is a falsifiable citation: an orchestration
claim must name a token that appears inside its guarded branch at HEAD, and the
gate verifies it, so a rename breaks the claim rather than letting it outlive the
code. Tokens belonging to the modelo test itself are excluded from the citable
set, so a citation cannot be satisfied by pointing at the condition. Most sites
in this set are scope guards on a function named for one modelo, and for those
the citation is the guarded function: the claim is that this branch guards a
modelo-scoped surface, and renaming that surface to something modelo-neutral
retires the claim.

What the instrument cannot decide is stated in the module rather than assumed
away: a branch that selects a service whose body encodes a rate reads as
orchestration here and is regulatory in substance, and only reading the selected
code settles it.

Independently re-verified 2026-08-14: this record was found already present and
already filled in on disk, UNCOMMITTED (`git status` shows it untracked), when a
separate reconciliation pass reached this row; it is confirmed here rather than
rewritten. Calling `load_ledger()`, `derived_branch_sites()` and `reconcile()`
directly reproduced every stated figure exactly -- 128 ledger entries, 115
orchestration routing, 13 regulatory treatment, 128 derived sites across 65
non-registry files, `report.clean is True` with zero unclassified, stale or
broken-citation entries -- and `pytest src/cadrumo/tests/test_modelo_branch_classification.py`
passed 7/7.
