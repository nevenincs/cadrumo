---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:443e35f741bb067a6680a42a739567f69afaf210c1a1fba670645b36c0380cb3'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# `tui-architecture` reference: `graded snapshot assembly sizing`

## Summary

Sizing for `resolve_graded_snapshot_result`, the still-unbuilt GRADED_SNAPSHOT
counterpart to `resolve_static_inspection_result` (`workspace.py:1179`), which
S128 needs to close. Written after `CALCULATION_UNAVAILABLE` landed
(`workspace_models.py`, commit `47cc1b3496`) and before starting the assembly
itself, per direction: trace and record, do not build under time pressure.

Each item below states CONFIRMED (read against the tree) or INFERRED (reasoned
but not yet verified) explicitly.

### CONFIRMED: the grade-insufficiency path is real, not decorative

`AUTHORITY_GRADE_UNAVAILABLE` has a genuine trigger. Traced the full call
chain: `ModeloWorkspaceRegistryPortV1.capture_projection_with_epoch()` ->
`ValidatedRegistryAuthority.capture_law_selected_projection(grade=...)`
(`authority.py:867`) -> `self._cached_snapshot(..., grade=grade)`
(`authority.py:832`) -> `_build_validated_snapshot(..., grade=grade)`
(`snapshot.py:276`) -> `_check_snapshot_authority_grade(modelo, revision,
requested_grade=grade)` (`snapshot.py:368`).

`_check_snapshot_authority_grade` RAISES `RegistryValidationError`
(`registry/errors.py:92`) in two cases:
- the revision declares no `authority_grade` at all (`revision.is_graded` is
  `False`);
- the revision's declared grade is below the requested one, compared via
  `tuple(RegistryAuthorityGrade)` enum declaration order.

The raised error carries a typed `registry_failure: RegistryFailureClassification`
property (`errors.py:73`) with `condition=RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT`
and a `facts` dict (`modelo`, `revision_id`, `requested_authority_grade`,
`declared_authority_grade` or `authority_grade_declared=False`). The catch
point for the assembly is around the REGISTRY port capture call: catch
`RegistryValidationError`, check `exc.registry_failure is not None and
exc.registry_failure.condition is RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT`
before treating it as `AUTHORITY_GRADE_UNAVAILABLE` -- re-raise anything else,
since `RegistryValidationError` is a broad type and other conditions must not
be silently absorbed into the grade-unavailable refusal.

### CONFIRMED: `declared_grade`'s real source

`ModeloRevision.effective_authority_grade` (`schema.py:1153`) is the property:
returns `self.authority_grade` when declared, else
`UNDECLARED_REGISTRY_AUTHORITY_GRADE` (the lowest rung) as a fail-closed
default. This is exactly the value `ModeloWorkspaceSnapshotScopeV1.declared_grade`
should read from `snapshot.revision.effective_authority_grade`.

### INFERRED, NOT YET CONFIRMED: `effective_grade`'s relationship to `required_grade`/`declared_grade`

Since `_check_snapshot_authority_grade` only enforces `declared >= requested`
and never truncates, a snapshot that is successfully returned always has
`declared_grade >= required_grade`. My working assumption is `effective_grade
= declared_grade` (the full authority the revision actually carries, not
clamped down to what was asked) -- but I have not found anywhere in the
codebase that actually computes or names an "effective grade" distinct from
`declared_grade` for this purpose, so this is a guess to verify, not a traced
fact, before wiring `ModeloWorkspaceSnapshotScopeV1` construction.

**This has two readings, and the next pass must establish which before
touching this field, not guess.** Either (a) `effective_grade` is genuinely
always equal to `declared_grade` and the field is a harmless, mildly
misleading redundant restatement of it -- in which case the assembly simply
mirrors `declared_grade` into both fields -- or (b) `effective_grade` is a
designed-but-unimplemented axis: the model declares a three-way distinction
(`required`/`declared`/`effective`) that no code anywhere actually computes,
which would be a genuine contract gap of the same kind as the other thirteen
found this session, not ordinary unexplored implementation surface. The
answer changes whether the assembly computes anything for this field at all
or simply copies `declared_grade`. Resolve this FIRST in the next pass,
before starting `resolve_graded_snapshot_result`.

### CONFIRMED: what still needs building, and why it cannot reuse the static functions as-is

1. **Graded-admission equivalents of three STATIC_INSPECTION-only functions,
   all currently typed to `RegistryRevisionInspection`:**
   - `resolve_static_inspection_schema_identity` (`workspace.py:770`) reads
     `inspection.modelo_id`, `.revision_id`, `.casilla_ids`, `.binding_ids`.
     The graded equivalent reads `snapshot.modelo.id`, `snapshot.revision.id`,
     and derives casilla/binding id sets from `snapshot.revision.casillas`/
     `.bindings` (full `CasillaDefinition`/`DataBindingDefinition` tuples, not
     bare id sets -- confirmed in the S296 sizing work).
   - `static_inspection_evidence_horizon` (`workspace.py:799`) reads
     `inspection.source_ref_ids` (a `frozenset[SourceRefId]`).
     `RegistrySnapshot.sources: Mapping[SourceRefId, SourceReference]`
     (confirmed field, `schema.py:1434`) is the graded equivalent source --
     `frozenset(snapshot.sources)` gives the same shape.
   - `static_inspection_contributors` (`workspace.py:808`) hardcodes exactly
     4 contributors (WORK, LOCALE_CATALOGUE, FIELD_MANIFEST, REGISTRY). The
     graded admission reads a 5th: CALCULATION. A `graded_snapshot_contributors()`
     naming all 5 is needed; it cannot reuse the static one by parameter,
     since the static function's docstring asserts an exact ADR-quoted set of
     4 and is itself a proof artifact for that admission's boundary.

2. **`resolve_graded_snapshot_baseline`, not a parameterization of the
   existing one.** CONFIRMED: `resolve_static_inspection_baseline`
   (`workspace.py:834`) takes exactly 4 named `(stamp, epoch)` pairs
   (`work_stamp`/`work_epoch`, `registry_stamp`/`registry_epoch`,
   `locale_stamp`/`locale_epoch`, `field_manifest_stamp`/`field_manifest_epoch`)
   as positional/keyword arguments, not a generic collection -- it cannot
   accept a 5th (CALCULATION) pair without a signature change or a sibling
   function. A sibling `resolve_graded_snapshot_baseline` with the same
   `content_hash_hex` digesting shape over 5 stamps/5 epochs is the
   lower-risk option (mirrors S296's principle: only build what is
   genuinely new, but the STATIC function's arity IS the boundary here,
   unlike the S296 record builders where the underlying types were already
   identical).

3. **`ModeloWorkspaceGradedSnapshotScopeV1` / `ModeloWorkspaceSnapshotScopeV1`
   construction** -- `required_grade` is the caller's input parameter;
   `declared_grade` = `snapshot.revision.effective_authority_grade`
   (confirmed above); `effective_grade` is the one open inferred item above;
   `snapshot_scope_digest` needs a `content_hash_hex` shape decision (not yet
   sized -- likely digesting the three grade values plus the selected
   revision id, mirroring `schema_fingerprint`'s shape, but not confirmed
   against any existing precedent).

4. **Readiness/closure ports** (`ModeloWorkspaceReadinessPortV1`,
   `ModeloWorkspaceClosurePortV1`) remain genuinely OPTIONAL on
   `ModeloWorkspaceProjectionV1` (`readiness: ... | None = None`,
   `registry_closure_limbs: ... = ()` -- confirmed, no validator requires
   either non-empty for a graded result, only `materialization_facet` and
   `provenance_facet` are required non-`None`). A first landing of the
   assembly can validly omit both and add them as a follow-on without
   reopening the core assembly, since their absence is a modelled, legal
   state.

### Not yet traced at all

- Whether `capture_law_selected_projection`'s `on`/`revision_id` optional
  parameters need any graded-specific handling versus the static path (used
  identically by both today via the shared
  `capture_modelo_workspace_target_captures(..., grade=...)`, so likely
  fine as-is, but not independently re-verified for this note).
- The exact `content_hash_hex` payload shape for `snapshot_scope_digest`.
- Whether `ModeloWorkspaceCalculationPortV1`'s single-read/epoch discipline
  composes cleanly with the WORK-then-REGISTRY ordering when
  `work_unit.current_calculation_revision_id` is present (mechanically
  should: capture WORK, refuse early if no calculation id, else capture
  REGISTRY(graded) then CALCULATION by id) -- not yet built or tested.
