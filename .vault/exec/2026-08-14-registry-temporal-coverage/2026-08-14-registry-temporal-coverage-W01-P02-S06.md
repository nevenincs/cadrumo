---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:d94004607a2c493a9e0e5ff17d50cc0a63e7981ce768727a1171a707dd1da07d'
step_id: 'S06'
related:
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-14-registry-campaign-sequencing-audit]]'
---

# Add a structural gate refusing any modelo-named field on a generic registry schema type and any modelo branch in generic authority construction, proven by a planted field observed red then removed

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`
- `dev/`

## Description

This record documents work found already present, uncommitted, in the working
tree at the time of writing; it is written retrospectively from the code and an
independent runtime bite proof performed for this record, not from having
performed the implementation.

- Add `test_generic_schema_modelo_naming.py`: derives the canonical modelo code
  set from the `Modelo` enum, then two AST-derived properties over the registry
  package's production modules — no modelo-named annotated field on a class
  whose own name carries no modelo code, and no `Modelo.M###` attribute
  reference inside `_authority.py` or `_snapshot.py` (the two generic
  authority/snapshot construction modules).
- A per-modelo-named class (e.g. `M303FilingEnvelopeDefinition`) is exempt from
  the field check by construction — its fields are its own business.
- Add a keyed allowlist, `_ALLOWLIST: dict[tuple[path, class, field], reason]`,
  for deferred live violations, plus two anti-tautology tests: one fails a
  stale entry that no longer names a live violation, one fails an entry whose
  stated reason is under 40 characters.
- Add `test_the_registry_package_is_actually_scanned`, proving the scan reaches
  real modules (including confirming `_supplementary_orden.py` exists) so a
  green verdict on the two derived-property tests is not vacuous.

## Outcome

`pytest src/cadrumo/domain/calculations/registry/tests/test_generic_schema_modelo_naming.py -n 0 -q`
→ `5 passed`.

One live deferred violation is currently on the allowlist:
`ExportLayoutDefinition.m303_filing_envelope` in `_schema_exports.py`. Its
stated reason: the Modelo 303 export layouts are regenerated wholesale from
their official binaries by a separate campaign, so this field moves with that
regeneration rather than ahead of it. Per the plan's own
`aeat-agent-orchestration` rule — "beside every scope-narrowing note, write
what the standing goal still asks for that it excludes" — what the standing
goal ("no generic registry type carries a modelo-named field at all") still
asks for that this excludes: `ExportLayoutDefinition` genuinely carries a
Modelo-303-named field today, and the gate reports that population as clean
only because the allowlist masks this one entry. This is the same finding this
same day's registry-campaign-sequencing audit (linked in `related:`) records
independently ("second-divergence-instance"), which additionally notes
the gate fails if this exemption ever outlives the defect it covers — the
`test_every_allowlisted_site_is_still_a_live_violation` test is exactly that
tripwire, and it currently passes because the field genuinely still exists.

**Bite proof, independently reproduced for this record.** The row requires the
gate to be "proven by a planted field observed red then removed." No committed
test file performs this plant — the committed suite is entirely AST-derived
static analysis over the real registry package, with no monkeypatch-and-restore
test. To verify the claim rather than assume it, this record built its own
runtime plant from outside the repo: a script
(`monkeypatch.object(gate, "_registry_items", return_value=(...))`, in-process
only, no tracked file written or mutated) fed the module's own detector
functions (`_modelo_named_fields_on_generic_types`,
`_modelo_branches_in_generic_construction`) a synthetic AST tree carrying (1) a
modelo-named field on a generically-named class, (2) a `Modelo.M303` reference
inside a fake `_authority.py`, and (3) a control case — a per-modelo-named
class's own field, which must NOT be flagged. All three assertions passed:
both plants were detected, the control was correctly exempt, and the real
(unpatched) scan was unaffected once the patch context exited. This is closer
to the row's own "planted field observed red then removed" language than the
committed AST-only suite alone demonstrates, and it is reported here as
independently-obtained evidence rather than inferred from the static tests.

## Notes

This record documents work found already present on disk from a prior working
session and does not represent implementation performed by the agent writing
this record. The work is UNCOMMITTED at the time of writing (`git status` shows
`test_generic_schema_modelo_naming.py` as untracked).

This row's deletion-inventory consumption is none — it adds a gate and an
allowlist, it deletes nothing.
