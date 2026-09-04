---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:00e5549bfe20050bc4eef27448cd541cd00a7cf22bdaaabbc36c5c0cc23a3082'
step_id: 'S409'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give Home's actions, resumable declarations, agenda, evidence and messages zones their installed readers. All five are hard-coded UNAVAILABLE in the secure generation input, so the production Home an operator meets is five refusals and a Ledger summary. The application authorities the accepted due-driven decision names -- next actions, backlog, agenda, calendar evidence, notification snapshots -- exist and nothing yet calls them.

## Scope

- `src/cadrumo/application/workbench_generation.py`

## Changes

- `M` `src/cadrumo/application/workbench_generation.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/tests/test_workbench_generation.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/tests/test_installed_workbench.py src/cadrumo/entrypoints/tui/tests/test_workbench_security.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.types` -> `pass`

## Notes

PARTIAL: one of six Home zones. The agenda needed only facts the door already held, so it
is now AVAILABLE with its entries, and the agenda-evidence zone carries the evidence read's
own AEAT state -- NEVER_CAPTURED before a pull -- rather than a blanket refusal that would
have implied a broken reader.

The other five stay refused and each names what is missing, because none can be derived
honestly from what the session reads today. Actions needs the next-actions projector.
Declarations cannot be built at all from the current ref: HomeDeclarationResume requires a
human name the DeclarationsWorkspaceDeclarationRefV1 does not carry, and synthesising one
would be fabrication. Ledger readiness enforces that review, unclassified and
missing-evidence counts are subsets of the entry count, and the Ledger area counts are not
provably subsets, so mapping them across could publish a false total or trip the invariant;
the semantics have to be settled before that zone can be filled. Messages has no
notification projection.
