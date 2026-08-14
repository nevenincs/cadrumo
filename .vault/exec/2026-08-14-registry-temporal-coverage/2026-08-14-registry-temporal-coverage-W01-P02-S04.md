---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:c3fc6e1c2885b666b29f46c94f59036ce2172146a6e7bd0b307ee94b7231394b'
step_id: 'S04'
related:
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-14-registry-campaign-sequencing-audit]]'
---

# Replace the m303_annual_orden field on RegistrySnapshot and RegistryCatalogues with a generic modelo-keyed supplementary orden catalogue, delete the Modelo.M303 branch in generic authority construction, and sweep every consumer in one atomic relocation commit

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`
- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/`

## Description

This record documents work found already present, uncommitted, in the working
tree at the time of writing; it is written retrospectively from the code, the
diff against `HEAD`, and the reconciler output, not from having performed the
implementation.

- Replace the `m303_annual_orden: M303AnnualOrdenAuthority` field on
  `RegistrySnapshot` and `RegistryCatalogues` (`_schema.py`) with
  `supplementary_ordenes: Mapping[Modelo, M303AnnualOrdenAuthority]`.
- Add `src/cadrumo/domain/calculations/registry/_supplementary_orden.py`: a
  `Modelo`-keyed dispatch table pairing each registered modelo with a compiler
  (`SupplementaryOrdenCompiler` protocol) and a fingerprint collector, plus the
  generic fold `compile_supplementary_ordenes` and
  `collect_supplementary_orden_fingerprints` that iterate the table without
  naming a modelo. `Modelo.M303` is registered as the sole table entry today,
  pointing at the existing `load_m303_annual_orden_authority` /
  `collect_m303_annual_orden_fingerprints` M303-specific compiler, which is
  untouched.
- Delete the `if any(modelo.id == Modelo.M303 ...)` / `else` branch from
  `_construct_authority` in `_authority.py`; generic authority construction now
  calls `compile_supplementary_ordenes` unconditionally and folds whatever the
  table returns onto the shared catalogues.
- Sweep consumers in the same change: `_snapshot.py`'s
  `_build_validated_snapshot` and
  `_m303_orden_resolution.py`'s `supplementary_orden_authority(registry_snapshot.supplementary_ordenes, Modelo.M303)`
  read the new field; `test_m303_did_account_wire_isolated_authority.py`'s
  hand-built `RegistrySnapshot` fixture passes `supplementary_ordenes=` instead
  of `m303_annual_orden=`.
- Remove the stale `_authority.py` entry from
  `dev/registry/modelo_embed_classification.toml` (it classified `_authority.py`
  as `machinery` on the grounds of the now-deleted `Modelo.M303` branch) and add
  a new entry classifying `_supplementary_orden.py` as `machinery` — a dispatch
  table is a routing coordinate, not a regulatory value.

## Outcome

`_m303_orden_resolution.py` legitimately keeps its own `Modelo.M303` checks —
it IS the M303-specific resolver, not generic construction, so this is outside
the row's scope (which targets only `_authority.py`'s generic
`_construct_authority`).

Verification performed for this record:

- `uv run --no-sync python dev/registry/modelo_embed_classification.py` →
  `36 modelo-specific modules derived; 0 reconciliation failures`, confirming
  the ledger reconciles now that `_authority.py` is no longer derived as
  modelo-specific (it no longer carries the `Modelo.M303` branch that made the
  mechanical deriver pick it up) and that `_supplementary_orden.py`'s new
  `machinery` entry is not stale.
- `pytest src/cadrumo/domain/calculations/registry/tests/test_modelo_specific_embed_classification.py -n 0 -q`
  → `10 passed`.
- `pytest src/cadrumo/domain/calculations/registry/tests/test_m303_orden_anual_authority.py src/cadrumo/application/filing/tests/test_m303_did_account_wire_isolated_authority.py -n 0 -q`
  → `9 failed, 33 passed` in 265.78s. All 9 failures are
  `RegistryValidationError: modelo 303 revision ... is 'pending_review'; filing-grade
  snapshot requires operator_reviewed revision` on revisions `2025`,
  `2026-y-siguientes` and `2009-y-siguientes` — the tree-wide review-status
  collision this same day's registry-campaign-sequencing audit (linked in
  `related:`) already documents as blocking every filing-grade snapshot in
  `dev/registry/tests`, not
  a defect this row introduced. `test_m303_did_account_wire_isolated_authority.py`'s
  own tests are among the 33 passing, confirming the field-name sweep in that
  file works.

## Notes

This record documents work found already present on disk from a prior working
session and does not represent implementation performed by the agent writing
this record. The work is UNCOMMITTED at the time of writing (`git status` shows
`_schema.py`, `_authority.py`, `_snapshot.py`, `_m303_orden_resolution.py`,
`_supplementary_orden.py` and the swept test file as modified/new, unstaged).

This Step's deletion-inventory item is the `m303_annual_orden` field and its
generic-construction branch; both are gone from the shared types. The
M303-specific `_m303_orden_*` parsing modules and the
`M303AnnualOrdenAuthority` type itself survive deliberately, per the plan's own
"what survives deliberately" list — migrating the annual-orden content wholesale
into authoring-tree TOML is a named open question the ADR leaves to the
operator, not part of this row.

Full-tree `pytest --collect-only` was attempted for this record and failed
(exit 2) on the same review-status collision named above, tree-wide and
unrelated to this row's files; a scoped verification was used instead per this
project's guidance to re-run before blaming the code on a shared, actively
edited worktree.
