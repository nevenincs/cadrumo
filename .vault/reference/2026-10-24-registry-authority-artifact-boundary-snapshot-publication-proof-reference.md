---
tags:
  - '#reference'
  - '#registry-authority-artifact-boundary'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:197173795fac74bbe0238b4657a252ba898e7fb2253b52d17210d37fe9c445b1'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]"
---
# `registry-authority-artifact-boundary` reference: `snapshot cross-check placement and publication proof surface`

How the runtime builds a validated `RegistrySnapshot` from the published indexed authority, which of its checks read only generation content, which read runtime inputs, what publication already proves, and how a generation is admitted. Read on 2026-10-24 against the `feature/tui` working tree and the published generation `98c4d66f…` (`.authority/`, `cadrumo-authority-sqlite-v4`, 118,390,784 bytes). Measurements are warm-cache, one loaded workstation, Python 3.13, repository on `Y:`; a probe replaced `build_validated_snapshot` with a timing wrapper and changed nothing else.

## Summary

### Runtime path

- `PinnedAuthorityOperation.snapshot()` (`src/cadrumo/domain/calculations/registry/authority.py:694-738`) loads the modelo directory, selects revision metadata, loads the revision with its export layouts, materializes the modelo, loads every referenced legal and source declaration, then calls `build_validated_snapshot` (`src/cadrumo/domain/calculations/registry/snapshot.py:245-342`) on every call. The indexed path has no snapshot memo; the operation carries only `_fact_resolutions` (`authority.py:745-757`).
- The eager `ValidatedRegistryAuthority` memoizes per `(modelo, year, period, on, revision_id, grade)` with 1024-entry FIFO eviction (`authority.py:384-417`), under a governed-fact scope bound to itself (`authority.py:404`).
- `IndexedRegistryAuthority.operation()` binds the governed-fact scope to the pinned operation (`authority.py:906-911`); `lease_operation()` deliberately does not, and long-lived hosts pair it with a per-task scope (`authority.py:913-925`). Checks that read governed facts resolve through `require_governed_fact_authority`, which refuses without a scope (`governed_fact_scope.py:108-119`).

### What `build_validated_snapshot` does, by input dependence

Generation content only (the selected revision, its modelo directory, the referenced legal/source declarations, snapshot globals):

- Revision selection given `(filing_year, period)` with `on=None` and `revision_id=None` (`snapshot.py:273-280`) and its temporal resolution (`snapshot.py:281-286`).
- Grade ladder against the revision's declared grade (`snapshot.py:345-390`), review status for filing (`snapshot.py:393-416`), Orden applicability and revision reference identity (`snapshot.py:184-213`).
- Export-layout derivation from bindings (`snapshot.py:302`) and materialized record-family validation (`snapshot.py:165-181`, `:303-304`); filing capability for the filing grade (`snapshot.py:419-455`).
- Revision-scoped legal and source windows (`snapshot.py:316-317`, bodies at `:585` and `:817`); the source-window check reads the modelo directory for continuity and structural-succession endpoint context (`snapshot.py:899-1045`).
- `RegistrySnapshot` model validators (`schema.py:1243-1262`) and `check_all_id_references` (`snapshot.py:341`, `reference_checks.py:80`).

Runtime inputs:

- `on`: changes revision selection (`temporal.py:688-721`, projected reference date) and the legal-review filing date, `on or date(filing_year, 12, 31)` (`snapshot.py:225-243`, `:483-502`), which keys known-bad citation lookup (`legal.py:34-54`, `citation_blocklist.py:150-198`). Eight production call sites pass a non-null `on` (for example `adapters/inbound/declaracion/parser.py:576`, `application/modelo/binding_readiness.py:96`, `domain/calculations/registry/queries.py:658`).
- `revision_id`: an explicit revision override (`authority.py:713-719`); production callers pass it, for example `adapters/persistence/profile/calculation_revision_override_migration.py:157` and `application/calculations/cross_period_clean_state.py:185`.
- Caller grade: selects which checks run; a lower grade is a narrower claim (`snapshot.py:258-266`).
- Wall clock: two checks resolve governed mapping facts at `today_madrid()`, not at the filing coordinate: the legal source-kind vocabulary used by known-bad citation lookup (`setup_profile_bindings.py:28-53`, `:107-114`) and the M130 retenciones route used by a registered cross-domain check (`domain/renta/retenciones_routing_integrity.py:36-48`). The perceptor-clave cross-domain check uses the period's end date instead (`domain/modelos/perceptor_clave_scope.py:92-101`).
- Governed-fact scope: the ambient scope, not necessarily the pinned operation, supplies those facts; a `lease_operation()` caller without a scope fails those checks.
- No profile facts or taxpayer values enter `build_validated_snapshot`.

### Selector set of the current generation

A read-only probe over the published generation enumerated every modelo directory, supported filing year and declared period with `on=None`:

- Support envelope: floor 2022, horizon 2026, no hard ceiling. Years above the horizon are admitted and projected from the horizon-year edition, so the year axis is open upward; the sweep covered 2022-2026.
- 58 modelos and 161 revisions in the generation; 1,258 `(modelo, year, period)` cells select a revision, reaching 141 distinct revisions (1 to 85 cells each, 8.9 mean). Periods are declared tokens (`0A`, quarters, months, `1P`-`3P`, `EXT-nT`, event kinds) plus one symbolic `EVENT-N`, which also admits any concrete `EVENT-<digits>` request (`period_selector_match.py:8-18`), so the request space for that selector is unbounded.
- `on` changed the selected revision in none of the 1,258 cells (about 70 dates per cell, including every revision boundary), and no cell had a second revision reachable by `revision_id`. In this generation `on` can only narrow or refuse; `on=None` selects uniquely everywhere. That is a property of today's data, not of the selector code.
- All three grades for every cell: 3,774 calls, 2,908 succeed, 866 refuse. Every refusal is the grade-ladder refusal for a grade above the revision's declaration (381 applicability-declared cells refusing calculation and filing, 104 calculation-declared cells refusing filing). No review-status, legal-review, window, identity or cross-domain failure occurs, and outcomes are uniform per `(modelo, revision, grade)` across all 423 combinations.
- Whole sweep in one process: 22.8 s wall, about 18 s inside `build_validated_snapshot`, per call median 1.3 ms, p95 30 ms, maximum 253 ms, peak RSS about 351 MB, once process-level projections are warm. A cold first M100 spends about 0.12 s of 0.52 s in the cross-checks and a four-snapshot workload about 0.41 s; decode is about 0.40 s of the first M100. cProfile inflates the cross-checks about 2.6x; disabling cyclic GC moves repeat M100 from 0.18 s to 0.075 s.

### Publication today

- `publish_sqlite_authority_candidate` (`dev/registry/pipeline/authority_publication.py:527-563`) compiles in a canonical child interpreter (`:273-332`), runs complete registry validation through `compile_validated_authority(..., complete_validation=True)` ending in `RegistryValidator.validate_registry` (`dev/registry/compiler/authority.py:248-310`), loads every component through a clean reader (`authority_publication.py:665-669`), checks currency and switches the descriptor (`:672-673`).
- Publication never calls `build_validated_snapshot` or `.snapshot(` for any selector. Snapshot-level checks run in development only through conformance and tree validation (`dev/registry/conformance/coverage.py:676`, `:1248`; `dev/registry/pipeline/_tree_validation.py:439`, `:470`) and in `dev/registry/diagnostic_classification.py:172`. `_tree_validation.py:27` imports `build_snapshot` from a test-support module.
- Compile-time validation overlaps only partly: it derives export layouts (`dev/registry/compiler/_validate_revision_sections.py:87`), checks revision identity (`dev/registry/compiler/revision_definition.py:50`) and endpoint source context (`dev/registry/compiler/validate_revision_closure.py:134`), but not per-selector grade, legal/source windows over the snapshot slice, known-bad citations at a filing date, or registered cross-domain checks.

### Generation identity and admission

- Logical generation is the digest of legal inputs only (`authority_publication.py:477-488`, identity schema `cadrumo-authority-candidate-identity/v2` at `:112`). A compiler or validator change republishes a new physical file under the same logical generation (`authority_publication.py:21-23`).
- The physical SHA-256 covers every table (`dev/registry/compiler/authority_database.py:86-91`). Schema: `authority_manifest` (format, logical generation, component count), `components` (kind, key, codec, payload SHA-256, retained weight, payload), `dependencies` (`authority_database.py:370-401`). Store format `cadrumo-authority-sqlite-v4` (`authority_store.py:34`), codec `cadrumo-authority-component-v1`.
- Admission: canonical descriptor read (`authority_store.py:76-118`), full-file digest or per-user receipt keyed by device, inode, size, mtime and ctime (`authority_store.py:198-241`, `:425-477`), manifest format and logical-generation equality (`authority_store.py:403-423`). Per lease the file identity is restated (`authority_store.py:479-503`); uncached component loads verify payload digests (`authority_store.py:363-374`).
- Existing runtime-trusts-publication statements: `legal.py:22-23` (corpus provenance), `authority_store.py:404-413` (structural integrity), `authority_database.py:96-101` (acyclic graph), `authority_store.py:377-380` (retained weight).

### Mapping to a publication proof

- Fits: the success/refusal outcome of a `(modelo, year, period, grade)` cell with `on=None` and no `revision_id` is a pure function of generation content, the validator code, the date used for wall-clock fact lookups and the period-end date. The 3,774 cell-grade set is small enough to sweep at publication in well under a minute, and a new table is covered by the physical digest. Adding one changes the published schema, which the indexed-storage decision's earlier amendments handled by advancing the store format under refusal and republication.
- Does not fit without more work: non-null `on`, explicit `revision_id`, concrete `EVENT-n` beyond the symbolic selector, years projected above the horizon, and the two `today_madrid()` fact lookups. The proof also certifies a validator version, which the logical generation deliberately does not identify, so a proof must be bound to the validator contract the runtime runs, not only to the generation.
