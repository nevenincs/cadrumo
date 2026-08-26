---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:e4109baddb3e452c149df7f4e3d838ee3ebaf08fa37841c0820d3e4d25fd5110'
step_id: 'S175'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Registry facade family census and disposition scheduling

## Scope

- `dev/quality/registry_facade_family_census.py`
- `dev/quality/registry_facade_family_census.v1.json`
- `dev/tests/test_registry_facade_family_census.py`
- `.vault/audit/2026-08-26-tui-architecture-registry-facade-family-census-audit.md`
- `.vault/plan/2026-08-11-tui-architecture-plan.md`

## Description

- Derive the fixed 78-pair c941 denominator from the historic rename delta.
- Bind all reviewed source and consumer evidence to immutable Git commit `aef1e903cebe8e463c5ac1c3192b30f2b4f3e8c8`, never the dirty working tree.
- Resolve relative imports, TypeAlias nodes, exact package attributes, and literal/nonliteral dynamic imports; retain structured per-row RAG, owner, competitor, and substitutability evidence.
- Keep the reviewed 54/9/13/2 disposition inventory and one future Step per row.
- Add a separate current-terminal observer so future H/P/D path disappearance is valid without a compatibility surface.

## Outcome

The matrix is deterministic, schema-versioned, immutable-evidence-bound, and bound to canonical plan Steps. The S175 check fails closed for changed historical pairs, an evidence-commit mismatch, stale consumer/measurement/dynamic-import evidence, missing source/import or terminal locators, unresolved or grouped rows, invalid terminal state, wrong disposition count, duplicate mapping, absent plan Step, or a final gate that does not depend on every disposition Step.

Sol independently failed frozen `976d47eb75` because its evidence was current-worktree-derived and incomplete. This remediation replaces that approach with Git-object evidence and future-safe terminal checking. Focused regression coverage includes relative-import measurement, TypeAlias, fixtures, dynamic unresolved calls, precise package attributes, immutable reproducibility/dirty-tree immunity, and future H/P/D removal.

S175 remains open. A new independent Sol architecture review is required before it may close; S173 and affected registry work remain blocked accordingly.

## Validation

- `python dev/quality/registry_facade_family_census.py --check`: passed through the terminal-state command's prerequisite check.
- `python dev/quality/registry_facade_family_census.py --check-current-terminal`: passed; 78 open disposition Steps, 77 ordinary open proofs, and 1 missing future defining-owner destination pending its hard-move Step.
- `pytest -q -n 0 dev/tests/test_registry_facade_family_census.py`: 14 passed in 138.54 seconds.
- Ruff format/check and `ty check dev/quality/registry_facade_family_census.py`: passed.
- `vault check all --feature tui-architecture`: no S175 errors; 18 pre-existing feature-wide warnings remain outside this Step's owned documents.
- `git diff --check`: passed.

## Notes

No production registry module, package facade, re-export, shim, alias, or disposition implementation was changed. This isolated remediation branch is based on frozen baseline `976d47eb759dcbc65b01cc3aa1f5dd8ef43c2268`; it has not been integrated into shared main.
