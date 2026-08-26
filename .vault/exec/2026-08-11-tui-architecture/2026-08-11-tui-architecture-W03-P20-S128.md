---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2656750613cf29f8e8fdcb5ab98ed74d0ac9fd314e1bbdd7b51fff601c532b6c'
step_id: 'S128'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Implement the sole Workspace assembly and dispatch directly in the public application/modelo/workspace.py defining module by capturing WORK exactly once before REGISTRY exactly once, deriving the REGISTRY coordinate only from the captured ModeloWorkResolution, evaluating the independent requested and stored axes through the sole pure S159-backed assertion, then capturing locale-catalogue and field-manifest for static admission or all remaining public S126 registrations for graded admission, with epoch-v2 same-domain two-pass validation, contributor_epoch_digest-consistent process-incarnation-scoped baselines, facets, and typed cursors, bounded materialization, and no _workspace_projection.py path, pre-capture work read, owner reread, or registry grammar

## Scope

- `src/cadrumo/application/modelo/workspace.py and focused assembly/dispatch/admission/consistency tests`

## Changes

- `A` `src/cadrumo/application/modelo/workspace.py`
- `A` `src/cadrumo/application/modelo/tests/test_workspace.py`
- `M` `src/cadrumo/application/modelo/workspace_producers.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py -m integration -q` -> `pass` (5 passed)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (23 passed, no regression from the added `revision_id` property)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/workspace_producers.py src/cadrumo/application/modelo/tests/test_workspace.py` -> `pass`
- `M` `src/cadrumo/domain/calculations/registry/static_inspection.py` (separate commit `822642adbc`: enrolled `review_status` on `RegistryRevisionInspection`)
- `M` `src/cadrumo/application/modelo/workspace.py`, `workspace_producers.py`, `tests/test_workspace.py` (commit `be5384912c`: made revision-axis mismatch non-raising typed data; added `resolve_modelo_workspace_target` and `ModeloWorkspaceRegistryProjectionV1.review_status`)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (32 passed)
- `M` `src/cadrumo/application/modelo/workspace.py`, `workspace_producers.py`, `tests/test_workspace.py` (commit `a3db12320e`: locale summary, STATIC_INSPECTION capabilities, `catalogue_digest`)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (35 passed)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/workspace_producers.py src/cadrumo/application/modelo/tests/test_workspace.py` -> `pass`
- `M` `src/cadrumo/application/modelo/workspace.py`, `tests/test_workspace.py` (commit `e9fb1cf5fa`: `resolve_static_inspection_schema_identity`, `capture_modelo_workspace_target_captures`)
- `M` `src/cadrumo/application/modelo/workspace.py`, `tests/test_workspace.py` (commit `08a694e134`: evidence_horizon, contributors, work_review facet, baseline)
- `M` `src/cadrumo/domain/calculations/registry/static_inspection.py` (landed inside peer commit `daeb0594d1`: enrolled `family_dispositions`)
- `M` `src/cadrumo/application/modelo/workspace_manifest.py` (commit `9e90b62c26`: `_INSPECTION_ROOT_FIELDS` companion fix)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (66 passed)
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py -m "unit or integration" -q` -> `pass` (20 passed, 1 pre-existing skip)
- `M` `src/cadrumo/application/modelo/workspace_models.py`, `tests/test_workspace_models.py` (commit `16c56b2d5c`: S283, `legal_refs`/`constraints` `None`-vs-`()`)
- `M` `src/cadrumo/application/modelo/workspace.py`, `tests/test_workspace.py` (commit `d7528c1965`: CASILLA schema_facet + real pagination)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py -m integration -q` -> `pass` (24 passed)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_producers.py src/cadrumo/application/modelo/tests/test_workspace_models.py -m "unit or integration" -q` -> `pass` (73 passed, 1 pre-existing unrelated failure)
- `M` `src/cadrumo/application/modelo/workspace_models.py`, `tests/test_workspace_models.py` (commit `9699e5cd9a`: S284, `label` discriminated union)
- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md` (S284 amendment)
- `M` `src/cadrumo/application/modelo/workspace.py`, `workspace_models.py`, `tests/test_workspace.py` (commit `66fae65bb5`: remaining four schema_facet row kinds, `_BoundedLocaleKey`)
- `M` `src/cadrumo/application/modelo/workspace.py`, `tests/test_workspace.py` (commit `780b24c2e3`: complete `ModeloWorkspaceProjectionV1` assembly)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py -m integration -q` -> `pass` (32 passed)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m "unit or integration" -q` -> `pass` (74 passed, 1 pre-existing unrelated failure)
- `M` `src/cadrumo/application/modelo/workspace.py`, `tests/test_workspace.py` (commit `40c802ea31`: GRADED_SNAPSHOT `graded_snapshot_materialization_facet`)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/tests/test_workspace.py` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (108 passed, 1 pre-existing unrelated failure)
- `M` `src/cadrumo/application/modelo/workspace_models.py`, `tests/test_workspace_models.py` (commit `c03f834da4`: S291, `ModeloWorkspaceLedgerIssueSubjectV1` discriminated union)
- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md` (S291 amendment)
- `M` `src/cadrumo/application/modelo/workspace.py`, `tests/test_workspace.py` (commit `dfc8a9f19c`: `graded_snapshot_readiness` pass-through)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/workspace_models.py src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_models.py` -> `pass` (only pre-existing unrelated diagnostics)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (110 passed, 1 pre-existing unrelated failure)
- `M` `src/cadrumo/domain/modelos/_calculation_revision.py`, `application/modelo/_calculation_actions.py`, `application/modelo/workspace.py`, `tests/test_workspace.py`, `adapters/persistence/profile/tests/test_source_mesh_revision_roundtrip.py` (commit `8b6f04125a`: S290, `CalculationSourceRef.source_casilla_ids`, `graded_snapshot_provenance_facet`)
- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md` (S290 amendment)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_producers.py src/cadrumo/domain/modelos/tests/test_calculation_revision.py src/cadrumo/adapters/persistence/profile/tests/test_source_mesh_revision_roundtrip.py -m "unit or integration" -q` -> `pass` (177 passed, 1 pre-existing unrelated failure)

## Notes

Partial landing; Step NOT checked. Only the WORK-then-REGISTRY
capture-and-assertion core is built and tested:
`capture_modelo_workspace_target_axes` captures WORK exactly once through
`ModeloWorkspaceWorkPortV1`, derives the REGISTRY coordinate solely from the
captured `ModeloWorkResolution`'s `(modelo, filing_year, period)` (never from
the target's own operands, which for an exact-work-unit target carry none),
captures REGISTRY exactly once through `ModeloWorkspaceRegistryPortV1`, and
judges the requested and stored revision axes independently against that one
capture through the existing pure `assert_work_target_revision`. Covered by
real integration tests over actual encrypted-SQL-backed repositories and the
bundled registry authority, including a genuine stale-stored-revision refusal
(constructed the same way `test_work_addressing.py` reproduces a
generation-superseding write, since `create_work_unit` itself re-confirms the
law-selected pairing at write time and refuses a hand-picked mismatch).

Added `ModeloWorkspaceRegistryProjectionV1.revision_id` (workspace_producers.py)
to read the law-selected revision uniformly off either admission shape
(`RegistryRevisionInspection.revision_id` or `RegistrySnapshot.revision.id`)
without a second registry read.

Update: the `review_status` gap is resolved. Team lead ruled against sourcing
it from a second structural read off `ModeloDefinition` (a fresh
`authority.validate_modelo(...)` is a second, unsynchronized observation of
registry state -- the exact inconsistency the epoch/ABA capture machinery
exists to rule out, even though it would have been cheap). Instead
`RegistryRevisionInspection` was enrolled with the field itself (own commit
`822642adbc`, kept separate from assembly work per instruction): it is a
governance stamp, not filing-grade content, so it stays in scope for a static
inspection. `RegistryRevisionInspection` is constructed only through
`from_revision()` across the tree, so no consumer needed updating.

While building on top of this, self-caught a second real defect before it
shipped: the axis computation originally re-raised
`assert_work_target_revision` on any mismatch, which would have destroyed the
per-axis `MISMATCHED` disposition the moment a caller tried to build
`ModeloWorkspaceRevisionMismatchRefusalV1` from it -- that refusal is built
FROM the mismatched axes, not from a caught exception. Corrected to always
return typed data; the pure assertion remains available, unused by the
non-raising path, for a caller that wants the canonical raised text (proven by
a dedicated test). `resolve_modelo_workspace_target` now assembles the full
`ModeloWorkspaceResolvedTargetV1`, including a resolved mismatch case.

Update: landed part of the STATIC_INSPECTION vertical (commit `a3db12320e`).
`capture_modelo_workspace_locale_summary` resolves the revision's own
`revision_locale_key` display key through the LOCALE_CATALOGUE port,
requested -> Spanish -> suppressed. Self-caught a real bug first: the draft
used the port's `present` field to decide EXACT vs fallback, but `present`
means catalogue MEMBERSHIP, which the locale parity gate guarantees for every
key in every locale -- checking modelo 130's real catalogue directly showed
`present=True` even for its null (untranslated) English label. The real
signal is `value is not None`; fixed before landing, tested against modelo
130's actual ES/EN catalogue content.

`static_inspection_modelo_workspace_capabilities` returns the closed 5-member
set for STATIC_INSPECTION: SCHEMA_INSPECTION `AVAILABLE`, the other four
`NOT_APPLICABLE`, both read off `RegistryRevisionInspection`'s own stated
scope, never inferred. GRADED_SNAPSHOT's dispositions are untouched and
unanswered.

Added `ModeloWorkspaceLocaleCatalogueProjectionV1.catalogue_digest`
(workspace_producers.py) -- the envelope was dropping the native capture's
real content digest, leaving only the opaque, process-nonce-salted
`comparison_domain` as a wrong substitute; reported and fixed as a small
mechanical addition, same shape as `review_status`.

Two further specification gaps surfaced and reported rather than
worked around, both now tracked as their own Steps rather than inferred here:
`W03.P20.S277` (schema-record per-row join semantics -- `formula_operands`,
`relation_endpoints` etc. have no consumer or spec anywhere in the tree to
derive the join from) and `W03.P20.S278` (the FIELD_MANIFEST generator is
hard-typed to `RegistrySnapshot` and has no root for
`RegistryRevisionInspection`, so `schema_identity`/`baseline` -- which both
require `field_manifest_digest` -- are blocked for STATIC_INSPECTION until
that resolves).

One incidental note: the landing commit's git-add picked up an already-staged,
content-neutral peer rename (`m303_orden_projection_compiler.py` ->
`_m303_orden_projection_compiler.py`) alongside the intended 3 files. Checked
before assuming harm: two consumers already imported the underscored name at
the prior HEAD while the file itself had not moved yet, so the tree was
already broken there; the accidental inclusion completed that peer's
in-flight rename rather than introducing a break. Reported to team lead for
attribution; not claiming credit for it here.

Update: S277, S278, S279 all landed (own decision commits, reported
separately). With all three settled, resumed the STATIC_INSPECTION vertical:

- `resolve_static_inspection_schema_identity` (commit `e9fb1cf5fa`):
  `schema_fingerprint` over the inspection's own casilla/binding id sets;
  `field_manifest_digest` from the S278 inspection-rooted manifest. Also
  generalized the capture flow: `capture_modelo_workspace_target_captures`
  now returns the full stamped-and-epoched WORK/REGISTRY captures (not just
  their bare projections) so baseline assembly can fold in their stamps and
  epochs without a second capture of either;
  `capture_modelo_workspace_target_axes` becomes a thin wrapper preserving
  every existing caller's shape.
- `static_inspection_evidence_horizon`, `static_inspection_contributors`,
  `STATIC_INSPECTION_WORK_REVIEW_FACET` (fixed `UNMEASURED`/`None`, per
  S279), `resolve_static_inspection_baseline` (commit `08a694e134`) --
  baseline digests the CALLER's already-captured stamps/epochs and performs
  no capture of its own, deliberately: a baseline that re-captured would
  reintroduce the second-observation hazard S279/S128's REGISTRY-capture
  reasoning exists to rule out.

**Pattern worth recording rather than three isolated fixes**: `review_status`
(commit `822642adbc`), then `family_dispositions` (commit `9e90b62c26`) are
the second and third fields the shared Workspace records require that
`RegistryRevisionInspection` did not carry. `RegistryRevisionInspection` was
built for a narrower consumer (verifying generated static artefacts) than the
Workspace shared shapes assume, so a fourth gap of the same shape should be
expected, not treated as another one-off surprise.

The `family_dispositions` enrolment landed inside a peer's unrelated
`daeb0594d1` commit via the shared working tree (verified byte-identical to
the intended change before building on it); the matching
`workspace_manifest.py` `_INSPECTION_ROOT_FIELDS` addition, committed
separately as `9e90b62c26`, itself accidentally absorbed that same peer's
follow-on deletion of the two now-superseded public module names
(`validate_references.py`/`verdict_cache.py`) via the same shared-index
mechanism as the earlier `m303_orden_projection_compiler.py` incident.
Verified zero remaining references to the deleted names and clean imports
before treating it as harmless; reported to team lead for attribution both
times, not claiming credit here.

**Stopped again, not inferring**: the schema_facet walk surfaced a FOURTH
and materially larger gap of the same pattern before any code was written.
`RegistryRevisionInspection.casilla_ids` / `.binding_ids` are bare id sets,
never `CasillaDefinition` / full binding objects -- so a CASILLA row has no
source for `legal_refs`, `constraints`, or per-casilla family membership at
all, unlike the FORMULA/BINDING/RELATION/PARAMETER rows, which the inspection
already carries as rich definitions. This is a bigger surface than a single
scalar/mapping field, so it was reported with three options (enroll the
richer casilla/binding data; scope STATIC_INSPECTION's schema_facet to the
identity kinds it can fully back plus bare casilla references with an
explicit not-yet-measured disposition on the missing fields; or open it as
its own decision Step like S277/S278/S279) rather than picked unilaterally.
Holding for a ruling before writing any schema_facet code.

Update: S283 landed (own decision commit `16c56b2d5c`, reported separately)
-- bounded a STATIC_INSPECTION casilla row to identity alone, and gave
`ModeloWorkspaceSchemaRecordV1.legal_refs`/`.constraints` a `None`-vs-`()`
absence distinction. With all four decisions settled, landed the CASILLA
schema_facet (commit `d7528c1965`):

- `static_inspection_casilla_schema_records`: one row per casilla identity,
  sorted for stable pagination, `formula_operands`/`relation_endpoints`
  consuming the S277 join functions directly, `legal_refs`/`constraints`
  always `None` per S283.
- Extracted `_resolve_locale_summary_and_value` as the shared per-key locale
  fallback helper (requested -> Spanish -> suppressed), reused by both the
  revision-level summary and per-casilla label resolution -- one rule, not
  two independently-drifting copies.
- `paginate_static_inspection_schema_facet` treats the cursor as a real
  contract: proved round-trip across all 7 pages of a real 20-casilla result
  (modelo 130/2026/1T, page_size=3), and proved `ModeloWorkspaceStaleCursorError`
  fires when resumed against a baseline whose `contributor_epoch_digest` has
  moved, rather than silently returning a different page.

**Stopped a fifth time, same discipline**: before building BINDING/FORMULA/
RELATION/PARAMETER rows, checked `modelo_localization.py` for their
locale-key convention and found none exists -- only `modelo`, `revision`,
`construct`, and casilla occurrence/continuity/alias keys are defined.
`ModeloWorkspaceSchemaRecordV1.label` is required with `min_length=1` and no
None-capable escape like S283 gave `legal_refs`/`constraints`, so there is no
established, non-inventive way to populate it for these four row kinds.
Reported three options (these identities have no real display text and
`label` needs its own S283-shaped absence ruling; a locale-key convention
for them is a genuine gap in `modelo_localization.py` to close; or
something else) rather than fabricating a label convention. Holding.

Update: S284 landed (own decision commit `9699e5cd9a`, reported separately)
-- `ModeloWorkspaceSchemaRecordV1.label` became the discriminated
`ModeloWorkspaceRecordLabelV1` (localized text or
`ModeloWorkspaceTechnicalLabelV1`). With all five decisions settled
(S277/S278/S279/S283/S284), completed the schema_facet walk (commit
`66fae65bb5`): `static_inspection_binding_schema_records`,
`_formula_schema_records`, `_relation_schema_records`,
`_parameter_schema_records` cover the remaining four reference kinds, all
fully backable (their definitions carry `legal_refs` directly, unlike a
bare casilla id). A FORMULA row's `formula_operands` is its own complete
operand set -- the same S277 join as a CASILLA row's, walked from the
opposite end. `static_inspection_schema_records` assembles all five kinds
into one deterministic sequence, proven identical across two independent
calls. Fixed a real bound violation the walk surfaced against actual data:
modelo 303's base32hex-encoded casilla ids produce locale keys up to 143
characters, past `_BoundedCode`'s 128-char limit; added a dedicated
`_BoundedLocaleKey` (max 256) rather than widening the shared type.

Then assembled the complete projection (commit `780b24c2e3`):
`resolve_static_inspection_result` is the sole STATIC_INSPECTION entry
point, wiring every landed piece into one validated
`ModeloWorkspaceStaticInspectionResultV1` -- proven to perform exactly one
WORK read across the whole call (asserted directly against the real
work-unit-catalogue debug log, not inferred). `static_inspection_family_dispositions`
projects only the families `inspection.family_dispositions` actually
declares `NOT_APPLICABLE`; most schema families (constructs,
deadline_windows, verification_expectations, and others) have no
corresponding data on `RegistryRevisionInspection` at all, so reporting an
unrepresented family as `POPULATED` or `BLOCKED_PENDING_EVIDENCE` would
assert a fact the inspection has no basis for -- consistent with every
prior absence ruling this Step made. Proved the full assembly round-trips
through JSON and satisfies every cross-field validator the projection and
result models already enforce.

**This closes the STATIC_INSPECTION vertical.** GRADED_SNAPSHOT remains
completely unbuilt: request/admission dispatch for that admission,
materialization/provenance facets, readiness/closure integration, and the
runtime capability-disposition computation S279 deliberately left out of
scope. S128 stays unchecked until GRADED_SNAPSHOT is sized and addressed.

Sized GRADED_SNAPSHOT per direction and opened the capability-disposition
computation as its own ninth gap (S287), confirmed unimplementable as
written; capability dispositions stay untouched pending that ruling. Of
the three remaining mechanical pieces, built and tested
`graded_snapshot_materialization_facet`: groups scalar
`casilla_values` and repeated `row_casilla_values` into typed
`ModeloWorkspaceMaterializationRecordV1` rows, keying every repeated-row
group by its `DirectRowMaterializationProvenance.source_binding_id` (never
a re-derived identity), and refuses (`ValueError`) a row casilla value
carrying no `row_casilla_provenance` entry -- proved against a real
`CalculationRevision` built the same way `test_source_mesh_revision_roundtrip.py`
builds one, plus a `model_construct`-bypassed defensive-only proof, since
`CalculationRevision`'s own validator already forecloses that shape from
ever reaching the facet through normal construction.

Found and held, rather than guessed around, two further gaps while sizing
the remaining two pieces:
- `graded_snapshot_provenance_facet`: `CalculationSourceRef` (the sole
  source of `CalculationRevision.source_provenance`) carries no field
  naming the casilla or binding it explains, but
  `ModeloWorkspaceProvenanceRecordV1.subject` requires exactly that
  identity. `CasillaObservation.source_refs` is a different, unrelated
  concept (legal-catalogue `SourceRefId`s) from `CalculationSourceRef.source_ref`
  (a resolver-mesh string), so there is no shared key to join on. Not
  built.
- readiness/closure pass-through: `ProjectionModeloReadiness`,
  `ProfilePreflightRequirement` and `ProjectionModeloBindingRequirement`
  map 1:1 onto their Workspace equivalents and are safe to build, but
  `LedgerPreflightIssue.transaction_id: TransactionId | Literal["__period__"]`
  has no representable arm in the required
  `ModeloWorkspaceLedgerIssueV1.transaction_id: TransactionId` for a
  period-level (not one-transaction) issue. Not built.

Landing commit `40c802ea31` also carries an unrelated, pre-staged registry
relocation continuing `dd44ea6a1a` (`RelationDefinition` consolidation into
`schema.py`, consumer repoints) that was already staged in the shared
worktree index when this commit ran; verified harmless (`ty check` clean,
108 workspace tests pass, the only red collection is the pre-existing
`.baseline-source-snapshot` fixed-point failure and unrelated
`cadrumo_harness.mcp` collection errors reproducing independently of this
change) and disclosed rather than unwound.

S291 (`W03.P20.S291`, decided and closed separately, own exec record) and
the readiness pass-through both landed (commits `c03f834da4`, `dfc8a9f19c`).
`graded_snapshot_readiness` projects `ProjectionModeloReadiness` onto
`ModeloWorkspaceReadinessV1` as a pure axis-preserving pass-through --
`ledger_issues` is the one axis needing a shape change, routed through the
new `ModeloWorkspaceLedgerIssueSubjectV1` discriminated union so a
period-level `LedgerPreflightIssue` (`transaction_id == "__period__"`) is
represented as itself. Proved with a real `ProjectionModeloReadiness`
carrying one of each row kind (profile requirement, binding requirement,
a transaction-scoped and a period-scoped ledger issue) and asserting every
field survives the projection unchanged. This completes all three
GRADED_SNAPSHOT mechanical pieces authorized (materialization, ledger-issue
subject, readiness).

S290 (`W03.P20.S290`, decided and closed separately, own exec record)
landed (commit `8b6f04125a`): `CalculationSourceRef.source_casilla_ids`
carries the subject identity through from `CalculationSourceProvenance`
(which already held it) at the `_source_provenance_refs` boundary --
verified first that the omission was a boundary gap, not the docstring's
documented `legal_refs`/`source_refs` anti-duplication choice, which does
not extend to a subject identity. `graded_snapshot_provenance_facet` fans
one ref out into one record per linked casilla; an unlinked ref (most
resolvers today) produces zero records rather than a fabricated subject.
Deliberately does NOT backfill the 16 `CalculationSourceProvenance`
construction sites across 7 files that leave the field at its `()` default
-- a separate undertaking.

This lands all three GRADED_SNAPSHOT mechanical pieces plus the S290
provenance-subject decision. Still held: the runtime
capability-disposition computation (S287, confirmed unimplementable as
written). S128 stays unchecked until S287 is ruled on.
