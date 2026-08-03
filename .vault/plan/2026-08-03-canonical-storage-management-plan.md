---
tags:
  - '#plan'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_hash: 'sha256:a97908db79a1bebdf3f317b010f4d6bed070a2c2273c2f644296f50a9860724c'
tier: L3
related:
  - '[[2026-08-03-canonical-storage-management-adr]]'
  - '[[2026-08-03-canonical-storage-management-research]]'
  - '[[2026-07-13-data-output-standardization-adr]]'
---

# `canonical-storage-management` plan

Type every application-chosen on-disk location into one core authority, migrate every production and test site onto its accessor, and prove the burndown with a provenance gate rather than a census.

## Description

TODO

## Steps

## Wave `W01` - the typed authority in core, and the convergences that do not wait for it

Declares StorageCategory, StorageLocation, and STORAGE_TAXONOMY in cadrumo.core, moves the bucket and keystore names core-ward so the three duplicate literals become deletable, and replaces the derivation and materialisation machinery with taxonomy-derived equivalents while preserving the twelve migration invariants. Rulings R1, R2, R3, R10, and R13 govern this Wave. Every later Wave depends on the accessor contract frozen here. Its last Phase carries the semantic convergences that need no taxonomy at all and runs in parallel with the rest.

### Phase `W01.P01` - declare the typed taxonomy

Lands the closed enums, the frozen strict location model, and the single keyed mapping in core, with a transitional parity test proving every declared subpath is byte-identical to the shipped dict value.

- [ ] `W01.P01.S01` - Declare StorageNodeKind, StorageScope, StorageLifecycle, FingerprintParticipation, and StorageOverridePolicy as StrEnums in core, gated by a test asserting each member set is closed and an unknown value is rejected at model validation; `src/cadrumo/core/_storage_taxonomy.py`.
- [ ] `W01.P01.S02` - Declare ExternalPathRole as a StrEnum carrying the four escape roles plus OPERATOR_DIRECTED_OUTPUT, gated by a test asserting the five members and rejecting an undeclared role string; `src/cadrumo/core/_storage_taxonomy.py`.
- [ ] `W01.P01.S03` - Declare StorageCategory as a StrEnum naming every application-chosen location identified by scope and name together, gated by a test asserting the duplicated blobs and audit names resolve to distinct members; `src/cadrumo/core/_storage_taxonomy.py`.
- [ ] `W01.P01.S04` - Declare StorageLocation as a frozen strict pydantic model carrying subpath, node kind, scope, override policy, lifecycle, grouping, and fingerprint participation, gated by a test asserting extra fields are forbidden and mutation raises; `src/cadrumo/core/_storage_taxonomy.py`.
- [ ] `W01.P01.S05` - Declare STORAGE_TAXONOMY as the single mapping keyed by StorageCategory with each subpath copied verbatim from the shipped table, gated by a test asserting the mapping is total over the enum; `src/cadrumo/core/_storage_taxonomy.py`.
- [ ] `W01.P01.S06` - Add a transitional parity test asserting every key of the shipped derived-dirs dict has a taxonomy member whose subpath string is byte-identical, so the representation change cannot silently move a path; `src/cadrumo/core/tests/test_storage_taxonomy_parity.py`.
- [ ] `W01.P01.S07` - Export StorageCategory, StorageLocation, STORAGE_TAXONOMY, and the axis enums from the core package facade using the existing deferred-attribute pattern, gated by an import test from the package top level; `src/cadrumo/core/__init__.py`.

### Phase `W01.P02` - the accessor, the materialiser, and the twelve migration invariants

Replaces the derivation validator, the tree materialiser, and the override-settings rebuild loop with taxonomy-derived equivalents, deletes the untyped dict, and adds the root-permission test the research found missing.

- [ ] `W01.P02.S08` - Add storage_path returning the resolved absolute path for a root-scoped category, gated by a test asserting an absolute per-field override passes through unchanged with no containment rewrite; `src/cadrumo/core/_storage_taxonomy.py`.
- [ ] `W01.P02.S09` - Add the bucket-scoped and keystore-scoped accessor variant taking the bucket identifier, gated by a test asserting a root-scoped member passed to it refuses rather than silently resolving; `src/cadrumo/core/_storage_taxonomy.py`.
- [ ] `W01.P02.S10` - Add effective_storage_root to the paths module returning the caller override or the settings root, normalised, gated by a test asserting a relative override anchors to the platform user-data root one level above the storage root; `src/cadrumo/core/paths.py`.
- [ ] `W01.P02.S11` - Rewrite the derived-output validator to iterate the taxonomy instead of the dict while keeping the model-fields-set skip, gated by the existing explicit-override-wins test staying green; `src/cadrumo/core/config.py`.
- [ ] `W01.P02.S12` - Rewrite ensure_storage_tree to materialise the taxonomy-derived member set and delete the path-suffix file inference, gated by the existing file-valued-setting test asserting the parent is created and the leaf is not; `src/cadrumo/core/config.py`.
- [ ] `W01.P02.S13` - Preserve the occupied-by-a-file refusal message and its positive control through the materialiser rewrite, gated by the existing test asserting both the path substring and the occupied-by-a-file diagnosis appear; `src/cadrumo/core/config.py`.
- [ ] `W01.P02.S14` - Rewrite the override-settings root-change pop-and-rebuild loop against the taxonomy key space, gated by a test asserting a root override re-derives every non-overridden category under the new root; `src/cadrumo/core/config.py`.
- [ ] `W01.P02.S15` - Route the settings-cache pointer fingerprint's independent root read through the taxonomy resolver, keeping the deferred submodule-qualified pointer import, gated by a test asserting a profile switch invalidates the cached settings; `src/cadrumo/core/config.py`.
- [ ] `W01.P02.S16` - Add the missing root permission-bits test asserting the mode after ensure_storage_tree, with a positive control proving the assertion fails when the hardening is removed; `src/cadrumo/core/tests/test_ensure_storage_tree.py`.
- [ ] `W01.P02.S17` - Delete the untyped derived-dirs dict and the transitional parity test in one commit, gated by clean collection over the whole source tree immediately before the commit; `src/cadrumo/core/config.py`.

### Phase `W01.P03` - unify the bucket and keystore names in core and delete the duplicate literals

Moves the bucket-layout and keystore names into the core taxonomy so the namespace registry becomes a consumer, then deletes each of the four unpinned re-typed copies of the same two names.

- [ ] `W01.P03.S18` - Declare the bucket-layout and keystore members in the core taxonomy with fixed override policy and bucket-relative or keystore-relative scope, gated by a test asserting an operator override of a fixed member refuses; `src/cadrumo/core/_storage_taxonomy.py`.
- [ ] `W01.P03.S19` - Rewrite the namespace registry's filesystem-name constants as consumers of the core taxonomy while leaving the secure-object namespace definitions untouched, gated by a test asserting each constant equals its taxonomy member value; `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`.
- [ ] `W01.P03.S20` - Re-point bucket_paths onto the scoped accessor, gated by the existing bucket provisioning tests plus an assertion that no bare directory-name literal survives in the module; `src/cadrumo/adapters/persistence/storage/bucket/_layout.py`.
- [ ] `W01.P03.S21` - Re-point keystore_path onto the scoped accessor while preserving the keystore-separation validation, gated by the existing separation-refusal test; `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py`.
- [ ] `W01.P03.S22` - Delete the inline buckets and db literals in the bucket database path construction and read the taxonomy instead, gated by the route-classification suite; `src/cadrumo/core/config.py`.
- [ ] `W01.P03.S23` - Delete the inline buckets and db literals in the storage-route classifier's parts matching and read the taxonomy instead, gated by the route-classification suite; `src/cadrumo/core/_config_storage_route.py`.
- [ ] `W01.P03.S24` - Re-point the active-profile pointer filename onto its taxonomy member, gated by a test asserting the pointer round-trips through the taxonomy-resolved path; `src/cadrumo/core/_bucket_pointer_io.py`.
- [ ] `W01.P03.S25` - Collapse the twin reset-journal directory-name declaration onto the taxonomy member, gated by the existing parity pin rewritten to compare the application constant against the taxonomy rather than against a second constant; `src/cadrumo/application/_config_reset_repository.py`.
- [ ] `W01.P03.S26` - Re-point the Windows worst-case object-path suffix constant onto the now-core bucket-layout members, retiring the documented layering-wall literal, gated by the existing suffix-shape assertions in the layout and local-provider tests; `src/cadrumo/core/paths.py`.

### Phase `W01.P04` - semantic convergences independent of the taxonomy

Collapses four measured same-meaning-different-code clusters that need no taxonomy member and therefore run in parallel with the rest of this Wave: keystore sidecar paths, trash-rename deletion, directory byte totals, and filesystem retention selection.

- [ ] `W01.P04.S27` - Add keystore_sidecar_path validating keystore separation then joining the sidecar filename, and export it from the bucket package facade, gated by a test asserting an unvalidated separation refuses before any path is returned; `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py`.
- [ ] `W01.P04.S28` - Rewrite profile_session_path as a one-line caller of keystore_sidecar_path, gated by the existing persisted-session suite; `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py`.
- [ ] `W01.P04.S29` - Rewrite bucket_dek_path as a one-line caller of keystore_sidecar_path, gated by the existing master-key custody suite; `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py`.
- [ ] `W01.P04.S30` - Rewrite login_throttle_path as a one-line caller of keystore_sidecar_path, gated by the existing login-throttle suite; `src/cadrumo/adapters/persistence/storage/master_key/_login_throttle.py`.
- [ ] `W01.P04.S31` - Add trash_rename_and_remove in the bucket package beside the provisioning primitive, taking an explicit trash-cleanup error policy, gated by a test covering both the rename-succeeds and rename-fails branches; `src/cadrumo/adapters/persistence/storage/bucket/_layout.py`.
- [ ] `W01.P04.S32` - Rewrite remove_profile_bucket_directory as a caller of the shared trash-rename primitive passing the ignore policy, gated by the existing profile-deletion suite; `src/cadrumo/application/user_profile/_orchestration.py`.
- [ ] `W01.P04.S33` - Rewrite the profile repository's bucket-directory removal as a caller of the shared trash-rename primitive passing the raise policy, gated by the existing create-rollback suite; `src/cadrumo/application/user_profile/_profile_repository.py`.
- [ ] `W01.P04.S34` - Add directory_byte_total returning bytes and file count with optional stat-error tolerance, gated by a test that removes a file mid-walk and asserts the tolerant mode returns a partial total while the strict mode raises; `src/cadrumo/core/paths.py`.
- [ ] `W01.P04.S35` - Rewrite the observability run-directory byte total as a caller of the shared helper in tolerant mode, gated by the existing size-bound prune tests; `src/cadrumo/core/observability/_store.py`.
- [ ] `W01.P04.S36` - Rewrite the bucket-maintenance directory byte total as a caller of the shared helper in tolerant mode, gated by the existing disk-usage report tests plus a new race-tolerance assertion; `src/cadrumo/application/bucket_maintenance/_service.py`.
- [ ] `W01.P04.S37` - Add select_filesystem_retention_survivors as a pure function taking a timestamp projection, an optional cutoff, an optional count cap, and an optional total-byte ceiling, gated by tests covering each bound alone and composed; `src/cadrumo/core/paths.py`.
- [ ] `W01.P04.S38` - Rewrite the run-trace prune to delegate the survivor decision to the shared selector while keeping its own rmtree and newest-directory-never-size-pruned rule, gated by the existing prune suite; `src/cadrumo/core/observability/_store.py`.
- [ ] `W01.P04.S39` - Rewrite the wallet diagnostic dump prune to delegate the survivor decision to the shared selector, gated by the existing wallet diagnostic prune tests; `src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.
- [ ] `W01.P04.S40` - Rewrite the MCP telemetry prune to delegate the survivor decision to the shared selector while preserving its keep-newest-then-age disjunction, gated by a test asserting the disjunction not a conjunction; `src/cadrumo/entrypoints/mcp/_telemetry.py`.
- [ ] `W01.P04.S41` - Rewrite the stale registry pickle eviction to delegate the survivor decision to the shared selector, gated by the existing compiled-cache eviction tests; `src/cadrumo/domain/calculations/registry/_compiled_cache.py`.

## Wave `W02` - production consumer enrollment across every location-choosing site

Enrolls every remaining production location under the taxonomy: the cache and diagnostic surfaces, the nested subpaths written beneath already-enrolled categories, the effective-storage-root call sites, the optional-root CLI resolvers, and the fingerprint-participation axis. Rulings R5, R6, R16, and R17 govern this Wave. It depends on Wave W01's accessor contract and blocks the completeness proof in Wave W05.

### Phase `W02.P05` - cache, telemetry, and diagnostic surface enrollment

Enrolls or explicitly escapes every remaining root-anchored cache, telemetry, and diagnostic location, and widens the field selector so no path-valued setting can hide behind an inconvenient name.

- [ ] `W02.P05.S42` - Add a corpus-search category member and its settings field, delete the module-local index subdirectory constant and the local parent-mkdir workaround, gated by a test asserting the per-field environment override now resolves and the tree materialiser pre-creates it; `src/cadrumo/application/corpus_search/_runtime.py`.
- [ ] `W02.P05.S43` - Add an MCP session-telemetry category member and delete the module-local telemetry directory constant, gated by a test asserting the telemetry directory resolves through the accessor under an overridden root; `src/cadrumo/entrypoints/mcp/_telemetry.py`.
- [ ] `W02.P05.S44` - Govern the registry disk-cache name through a taxonomy member while leaving the field itself un-derived by the settings validator, gated by a test asserting the production branch resolves to the taxonomy subpath and the field default stays absent; `src/cadrumo/domain/calculations/registry/_loader_cache.py`.
- [ ] `W02.P05.S45` - Declare the registry disk-cache resolver's pytest-shared temporary branch as an explicit test-pinned exception on the member rather than an undeclared special case, gated by a test asserting the declaration exists and the branch still selects under pytest; `src/cadrumo/domain/calculations/registry/_loader_cache.py`.
- [ ] `W02.P05.S46` - Declare the Playwright browser root as a third-party-owned-cache escape carrying its role, gated by a test asserting the escape is declared and that the resolver still honours the vendor environment variable; `src/cadrumo/application/provisioning.py`.
- [ ] `W02.P05.S47` - Declare the LibreOffice executable field as an external-executable escape carrying its role, gated by the binding gate seeing it once the selector widens; `src/cadrumo/core/config.py`.
- [ ] `W02.P05.S48` - Widen the path-typed field selector from name suffix to annotation so no path-valued setting can hide behind an inconvenient name, gated by a test asserting the selector now returns the LibreOffice field; `src/cadrumo/core/config.py`.
- [ ] `W02.P05.S49` - Declare the wallet diagnostic dump directory as an operator-directed-output escape, gated by a test asserting the role and that the feature stays off when the field is unset; `src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.
- [ ] `W02.P05.S50` - Correct the wallet diagnostic field docstring so it stops overstating the capture scope relative to the implementation, gated by the generated environment reference regenerating without drift; `src/cadrumo/core/_config_integration_fields.py`.
- [ ] `W02.P05.S51` - Re-point the corpus-text cache read onto the accessor, gated by the existing corpus-text cache location test re-expressed against the taxonomy; `src/cadrumo/domain/calculations/registry/_validate_evidence.py`.
- [ ] `W02.P05.S52` - Re-point the validation-verdict cache read onto the accessor, gated by the existing verdict location test re-expressed against the taxonomy; `src/cadrumo/domain/calculations/registry/_validate_verdict.py`.
- [ ] `W02.P05.S53` - Re-point the observability run-trace directory read onto the accessor, gated by the existing run-store suite; `src/cadrumo/core/observability/_store.py`.
- [ ] `W02.P05.S54` - Re-point the default log file path onto the accessor, gated by the existing logging tests plus the rendered-help assertion naming the resolved log directory; `src/cadrumo/core/logging.py`.
- [ ] `W02.P05.S55` - Declare or escape the MCP certificate option's relative default so it stops naming a taxonomy-governed segment by literal, gated by the tools-and-dispatch tests re-expressed against whichever ruling applies; `src/cadrumo/entrypoints/mcp/_tools.py`.

### Phase `W02.P06` - nested subpath governance beneath enrolled categories

Declares every application-chosen segment written one and two levels beneath an already-enrolled category, closing the ungoverned depth the research measured.

### Phase `W02.P07` - effective storage root call-site migration

Migrates each of the six sites that re-derive the override-or-settings storage root onto the single core primitive, one file per Step so two lanes cannot collide on the same edit.

### Phase `W02.P08` - optional-root CLI resolver convergence

Collapses the copy-pasted optional-root Typer resolvers onto one parameterised helper so the bundled-default and settings-default families stop drifting apart.

### Phase `W02.P09` - fingerprint participation as a declared third axis

Rewrites the drift-fingerprint exclusion set to derive from the declared participation field, lands the deliberate registry-cache correction, and gates the axis with both halves of the property.

### Phase `W02.P10` - single-file stat cache-key convergence

Adds the path-keyed sibling of the existing filename-keyed stat fingerprint and converges the loader modules that each re-derived the identical stat-and-cache-key boilerplate.

## Wave `W03` - enforcement gates and the whole test-surface migration

Rewrites the lifecycle gate onto the taxonomy behind the peer-held fix, lands the provenance gate and its three supporting gates, retires fixture-level drift, re-expresses every pins-by-design test so it still defends its original property, and burns down the incidental literal corpus one test package at a time. Rulings R4, R9, R14, R15, and R18 govern this Wave. It depends on Wave W02 because a gate cannot go green over an unenrolled site.

### Phase `W03.P11` - the peer-held lifecycle gate rewrite

Confirms the peer's fix has landed and the gate is green at committed HEAD before any edit, then rewrites the five hand-maintained frozensets onto the taxonomy while keeping the gate enumerating path-typed settings fields rather than taxonomy members.

### Phase `W03.P12` - the provenance gate and its three supporting gates

Lands the structural gate whose property is that the storage root has exactly one reader, plus the materialisation-parity, binding, and liveness gates that keep the taxonomy honest, each proven by a mutation that reds it.

### Phase `W03.P13` - dormancy decisions the liveness gate forces

Turns the three declared-but-unwritten categories into an explicit wire-or-delete decision rather than an audit-discoverable condition.

### Phase `W03.P14` - isolation fixture drift retirement

Retires per-field overrides that duplicate the taxonomy at a call site, including the fixture pinning a category to a path that disagrees with the taxonomy, while leaving the two-tier root-redirection chain verbatim.

### Phase `W03.P15` - pins-by-design test re-expression

Re-expresses each test whose reason for existing is the on-disk name it asserts, so it still defends that property against the taxonomy rather than degenerating into an accessor-equals-itself tautology.

### Phase `W03.P16` - incidental test literal burndown by package

Burns down the mechanically re-pointable literal corpus one test package at a time, each Step gated by the provenance gate scoped to that package plus that package's own suite.

## Wave `W04` - the config storage operator surface, dev tooling, and documentation

Registers the config storage noun-group, authors its five verbs plus the refuse-and-instruct relocation response, wires locale keys and the regenerated reference, and sweeps the dev tooling, packaging manifest, and documentation that restate storage names outside the taxonomy. Ruling R7 governs this Wave. It depends on Wave W01 for the enum the CLI boundary renders and on Wave W03 for the gates the new leaf must pass.

### Phase `W04.P17` - the config storage noun-group and its verbs

Registers the lifecycle-operations-only noun-group and authors its five read and materialise verbs plus the refuse-and-instruct relocation response, each on the envelope spine with a registered strict schema.

### Phase `W04.P18` - operator-facing strings, reference, and conformance

Wires locale keys through the locales CLI in all four catalogues, regenerates the CLI reference, and clears the schema, documented-command, and reviewed-write gates the new leaf must pass.

### Phase `W04.P19` - dev tooling, packaging, and documentation sweep

Retires the storage names restated in dev scripts, the justfile, and the packaging manifest, adds the drift gate the manifest lacks, and rewrites the operator documentation the CRUD surface makes stale.

## Wave `W05` - completeness proof, honesty review, and closure

Proves the mandate rather than asserting it: mutation-proves each new gate, sweeps the tree for surviving unenrolled readers, resolves the open Playwright download measurement, runs a fresh-context honesty review before any completion claim, and reconciles the out-of-scope register. No ruling authorises skipping this Wave; the campaign is not complete until every Step here closes with a matching execution record.

### Phase `W05.P20` - gate mutation proofs and the tree-wide completeness sweep

Proves each new gate can actually fail by the smallest edit that should break its specific property, then sweeps the whole tree for surviving unenrolled readers and records the result as the mandate's completeness evidence.

### Phase `W05.P21` - open verifications inherited rather than authored

Resolves the one measurement this campaign ratified without proving: whether browser-mediated download bytes reach a filesystem path before cancellation fires.

### Phase `W05.P22` - honesty review and closure

Runs the mandatory fresh-context honesty review before any completion claim, tracks every item it surfaces, reconciles the out-of-scope register, and confirms one execution record per closed Step.

## Parallelization

TODO

## Verification

TODO
