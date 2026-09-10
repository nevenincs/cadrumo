---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:61eda667419e91fe0878247c78ffbe6abf341803290dff3d64faab45b68139f6'
step_id: 'S40'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Make the continuity gate READ the lineage origin marker and treat seeded and grounded chains differently. Writing the marker without a consumer leaves it decorative, and a seeded chain is inference written down rather than a statement — the gate must not accept one as evidence of the other. Proof: a seeded chain and a grounded chain with identical content produce different gate outcomes.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/_validate_cross_revision_lineage_origin.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_cross_revision.py`
- `M` `src/cadrumo/domain/calculations/registry/validate_registry_scope.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_casilla_lineage_continuity.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_casilla_lineage_continuity.py src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py src/cadrumo/domain/calculations/registry/tests/test_casilla_lineage_origin.py` -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`

## Notes

- Code review: the executing agent could not launch the reviewer persona; the orchestrating session reviewed the diff against the ADR's inheritance rules instead.
- Ruling: a `grounded` row with non-empty evidence satisfies the semantic-linkage gate without a role, but only when every link it takes part in is grounded; seeded or unmarked links never lift the requirement.
- Measured on HEAD `da3fa7249bcb20a8391dd40557aa7992ad52bdd9` with the lineage seeding uncommitted in the working tree (891 `seeded`, 76 `grounded` rows); both gates report zero refusals.
- Persistent failure: the full `src/cadrumo/domain/calculations/registry/tests` run reports 41 failures, none of which reach the changed code.
- Follow-on for a later step: unset `continuidad_origin` still conflates an authored declaration with an unexamined row; the totality gate needs that split.
