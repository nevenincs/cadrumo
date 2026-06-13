---
tags:
  - "#audit"
  - "#codebase-health"
date: 2026-05-21
modified: '2026-05-21'
related: []
---

# cross-domain-handoffs swarm audit — 2026-05-21

Axis: cross-domain handoffs. READ-ONLY discovery pass against branch `chore/eliminate-shims` after six fix-waves of profile-lifecycle disaster recovery (#49/#55/#56/#58/#62 plus checkpoint fixes), concurrent schema-hardening (M100/M200 registry cluster), profile-UUID-identity cutover, and cli-workflow-redesign.

## Scope

Four handoff chains audited:

1. Registry authority → RegistrySnapshot → formula execution → CalculationRevision.observations → CLI emit (legal_refs / source_refs / formula_id provenance end-to-end)
2. Profile identity (UUID / display_name / label) across orchestration, repository, wizard persistence, CLI surfaces
3. Cross-domain routing tables — renta first-slice expense, CrossDomainSnapshotCheck registration
4. Modelo work-unit create → calculate → revision: registry validation gate, casilla completeness, observations persistence

---

## Findings

### F1 — CalculationRevision.observations survives model boundary but has no encrypted-storage roundtrip test with populated provenance

**Pathway:** `calculate_modelo_revision` → `CalculationRevision.observations` → `CalculationRevisionCatalogueRepository.save/load` → CLI emit `observations`

**File:line:**
- `src/aeat/domain/modelos/_calculation_revision.py:211` — `observations: tuple[CasillaObservation, ...] = Field(default_factory=tuple)`
- `src/aeat/domain/modelos/_calculation_repository.py:48` — `Envelope[CalculationRevisionCatalogue].model_validate_json(...)`
- `src/aeat/application/modelo/_actions.py:859` — `_build_typed_observations(...)` populates the field
- `src/aeat/entrypoints/cli/_modelo.py:1275-1286` — CLI correctly projects `obs.legal_refs`, `obs.source_refs`, `obs.formula_id`

**Data at risk / finding:** The field was added to `CalculationRevision` with `default_factory=tuple` for backward compatibility. The JSON roundtrip (`CasillaObservation.model_dump_json` ↔ `model_validate_json`) is covered by `test_cross_boundary_roundtrip.py`. The `CalculationObservationRepository` boundary has a full encrypted roundtrip + anti-tautology proof in `test_observations_repository_roundtrip.py`. However, **there is no dedicated encrypted-storage roundtrip test for `CalculationRevisionCatalogueRepository` that populates `observations` with real typed `CasillaObservation` entries (non-default, with `formula_id`, `legal_refs`, `source_refs` set).** The `test_secure_storage_roundtrip.py` in `domain/modelos/` explicitly notes it only covers the `WorkUnitCatalogueRepository` half ("CalculationRevisionCatalogueRepository is already covered by domain/filing/test_secure_storage_roundtrip.py"), but that filing test covers `ModeloDraftRepository`, not `CalculationRevisionCatalogueRepository`. A save-drops-observations regression in the `Envelope[CalculationRevisionCatalogue]` path would be invisible to the current test suite.

**Remediation:** Add a dedicated roundtrip test to `src/aeat/domain/modelos/test_secure_storage_roundtrip.py` (or a new `test_calculation_revision_repository_roundtrip.py`) that:
1. Builds a `CalculationRevision` in `BORRADOR` state with a populated `observations` tuple carrying `formula_id`, `legal_refs`, `source_refs`, and `operand_refs` set to non-default values.
2. Saves via `CalculationRevisionCatalogueRepository`.
3. Reloads and asserts strict pydantic equality.
4. Adds a companion anti-tautology proof: reach into the encrypted row JSON, delete `observations` entries, reload, and assert `ValidationError` or strict inequality.

---

### F2 — `ModeloDraft.subject_tax_id` and `snapshot_ref` are optional with `None` default — structural tests document but cannot enforce non-null population

**Pathway:** Filing schema provider → `build_draft` → `ModeloDraft` → encrypted storage → amendment / verification flows

**File:line:**
- `src/aeat/domain/filing/_schema.py:139` — `subject_tax_id: SubjectTaxId | None = None`
- `src/aeat/domain/filing/_schema.py:147` — `snapshot_ref: RegistrySnapshotRef | None = None`
- `src/aeat/domain/calculations/registry/test_cross_boundary_roundtrip.py:152-181` — structural tests assert the fields exist but cannot enforce that production code populates them

**Data at risk / finding:** `ModeloDraft.subject_tax_id` (a typed `SubjectTaxId` alias) and `snapshot_ref` (a typed `RegistrySnapshotRef` with modelo/revision/year/period coordinates) are optional with `None` default for backward compatibility with pre-migration persisted records. The production draft-builder path (`src/aeat/application/filing/runtime.py` via `build_draft`) must populate both fields for new drafts; if it does not, the filing chain silently loses the typed identity reference and the snapshot-grounding coordinates. The two structural tests in `test_cross_boundary_roundtrip.py` verify the fields exist on the model but assert nothing about whether the production path actually populates them for new drafts. The `test_filing_draft_survives_encrypted_storage_roundtrip` test in `src/aeat/domain/filing/test_secure_storage_roundtrip.py` explicitly populates both fields, which is correct, but the production path is untested.

**Remediation:** Add a contract test that calls the production `build_draft` function with a known registry snapshot and asserts that the resulting `ModeloDraft.subject_tax_id` and `snapshot_ref` are not `None`. If `build_draft` does not yet populate these fields, this is a pending wiring task; the test should be written to fail today and pass when the wiring lands.

---

### F3 — `_build_typed_observations`: registry_casilla is `None` for casillas absent from snapshot (silent empty grounding)

**Pathway:** `calculate_modelo_revision` → `_build_typed_observations` → `_casilla_observation_for` → `CasillaObservation(legal_refs=(), source_refs=())`

**File:line:**
- `src/aeat/application/modelo/_actions.py:1828-1836` — `legal_refs=registry_casilla.legal_refs if registry_casilla is not None else ()` / `source_refs=registry_casilla.source_refs if registry_casilla is not None else ()`

**Data at risk / finding:** When a casilla id appears in `engine_result.values` but is absent from `snapshot.revision.casillas` (i.e., `registry_casilla is None`), the observation is silently created with empty `legal_refs` and `source_refs`. This is a defensive fallback, but the architecture mandate requires every casilla observation to carry regulatory grounding. If the registry schema-hardening campaigns (M100/M200) introduce new binding-derived casillas that appear in `engine_result.values` but are not yet registered in `snapshot.revision.casillas`, they will produce ungrounded observations without raising. There is no assertion or warning log at this path. The `has_provenance` bucket-event flag (`src/aeat/application/modelo/_actions.py:933`) only signals whether the tuple is non-empty, not whether every observation has non-empty `legal_refs`.

**Remediation:** Either (a) add a warning log at `_casilla_observation_for` when `registry_casilla is None` so the drift is observable in the audit log, or (b) enforce with a test that asserts: after `calculate_modelo_revision`, every observation in the resulting revision carries non-empty `legal_refs`. This is a non-blocking finding for new M100/M200 bindings that may already be structurally correct; verify against the binding TOML data.

---

### F4 — Profile `display_name` (encrypted record) vs `label` (plaintext manifest) — rename atomicity depends on correct ordering but no cross-store integrity test post-rename

**Pathway:** `ProfileRepository.rename` → `ProfileLifecycleService.rename` (record update) → `write_manifest` (manifest label update) → `ProfileAggregate.label` ≠ `record.display_name` window

**File:line:**
- `src/aeat/application/user_profile/_profile_repository.py:440-449` — lifecycle service renames record first, then `write_manifest` updates manifest label
- `src/aeat/application/user_profile/_aggregate.py:79-102` — `_validate_cross_store_agreement` checks UUID and status match but NOT that `aggregate.label == record.display_name`

**Data at risk / finding:** The rename path mutates two stores sequentially: the encrypted record (`record.display_name`) first, then the plaintext manifest (`manifest.label`). A crash between these two writes leaves a manifest label that disagrees with the encrypted record's `display_name` — a torn state. The `ProfileAggregate._validate_cross_store_agreement` model validator checks `profile_id` and `status` agreement between stores but does NOT validate that `aggregate.label == record.display_name`. The `ProfileRepository.load` path loads both stores and constructs the aggregate, so a drifted label/display_name pair would construct silently. There is no cross-store label-agreement invariant enforced at load time. This was likely intentional (the manifest label is the operator-facing key and the record's display_name is encrypted; they should be equal post-rename but there is no enforcement) however the gap means a torn rename is undetectable.

**Remediation:** Add `aggregate.label == aggregate.record.display_name` to `_validate_cross_store_agreement`, or add a `verify_profile_integrity` check that surfaces label drift as a `ProfileIntegrityError`. Also add an anti-tautology proof test: build an aggregate with `label="A"` and `record.display_name="B"` and assert the constructor raises.

---

### F5 — `_resolve_default_actor` uses `record.display_name` (mutable label) as the actor attribution string — UUID never appears in actor attribution

**Pathway:** `_resolve_default_actor()` → `record.display_name` → bucket events `actor` field → audit trail

**File:line:**
- `src/aeat/entrypoints/cli/_modelo.py:91-110` — returns `record.display_name` as actor string; falls back to `active` (bucket UUID) if record absent
- `src/aeat/application/modelo/_actions.py:722-936` — actor is a plain string on `BucketEvent` and `CalculationRevision`

**Data at risk / finding:** The actor attribution uses the mutable `display_name` label, not the immutable `profile_id` UUID. A profile rename after calculation changes the actor label in future events without retroactively updating audit records that referenced the old label. This is documented behaviour (actor is a display label) but introduces a cross-domain inconsistency risk: audit reconstruction that joins by actor label will silently miss renamed profiles. The bucket UUID fallback (`active`) at line 107-109 is the UUID, so the fallback is UUID-keyed while the happy path is label-keyed — inconsistent attribution shapes in the event log.

**Remediation:** Standardise on the UUID for actor attribution in machine-readable event payloads, with the display label as a separate human-readable annotation. No change is strictly required if display-label attribution is an accepted product choice, but the inconsistency between the UUID fallback and the display-label happy path should be documented or eliminated.

---

### F6 — `CrossDomainSnapshotCheck` for renta first-slice routing depends on import-order side-effect registration — no guarded registration at `build_snapshot` call sites that construct M100 snapshots

**Pathway:** `aeat.domain.renta.__init__` → `register_cross_domain_snapshot_check` → `_check_cross_domain_snapshot_routing` at snapshot-build time

**File:line:**
- `src/aeat/domain/renta/_first_slice_routing_integrity.py:47` — `register_cross_domain_snapshot_check(check_first_slice_routing)` runs as import side-effect
- `src/aeat/domain/calculations/registry/_validate.py:2604-2611` — explicit guard: if modelo is 100 and `_CROSS_DOMAIN_SNAPSHOT_CHECKS` is empty, appends a failure message
- `src/aeat/domain/calculations/registry/test_cross_domain_snapshot_registration.py` — dedicated test

**Data at risk / finding:** The guard at `_validate.py:2604` correctly detects when the renta module was not imported and fails the snapshot build with a clear error message. The dedicated test in `test_cross_domain_snapshot_registration.py` further validates this. This chain is structurally sound. No gap found here.

---

### F7 — No encrypted-storage roundtrip test for `CalculationRevisionCatalogueRepository` that exercises `observations` with non-empty `legal_refs` and the `observations` field absent from the JSON (anti-tautology proof for the new field)

**Pathway:** Same as F1 — specifically the anti-tautology direction.

**File:line:**
- `src/aeat/domain/modelos/_calculation_repository.py:48` — loads `Envelope[CalculationRevisionCatalogue]` from bytes; `CasillaObservation` is a nested type with `default_factory=tuple` on the outer model
- `src/aeat/domain/modelos/_calculation_revision.py:211` — `observations: tuple[...] = Field(default_factory=tuple)`

**Data at risk / finding:** Because `observations` defaults to `()`, a serialiser that silently drops the field on write (or a schema migration that strips the field from persisted JSON) would be invisible: the loader would reconstruct an empty tuple matching the field default, and a strict equality check against a fixture built with the default `observations=()` would pass. The `test_observations_repository_roundtrip.py` covers the `CalculationObservationRepository` (AUDIT class) boundary correctly with an anti-tautology proof, but there is no equivalent proof for the `CalculationRevisionCatalogueRepository` (FINANCIAL class) boundary.

**Remediation:** This is the anti-tautology complement of F1. In the same new test module, add: persist a `CalculationRevision` with `observations=(CasillaObservation(...),)`, reach into the encrypted JSON row, delete the `observations` key from the inner JSON, reload, assert either the loaded revision's `observations` is non-empty (fails, surfaces the drop) or `loaded_revision != original` (strict inequality catches the regression).

---

## Recommendations

**Priority 1 (structural gap — no coverage):**
- F1 / F7: Add encrypted storage roundtrip test + anti-tautology proof for `CalculationRevision.observations` through `CalculationRevisionCatalogueRepository`. This is the highest-priority gap: the FINANCIAL boundary is the deepest persistence layer for formula provenance, and the `observations` field defaults to `()`, making silent field-drop regressions invisible.

**Priority 2 (non-null enforcement):**
- F2: Add a contract test asserting that `build_draft` populates `subject_tax_id` and `snapshot_ref` for new drafts. These fields exist and are typed; the gap is that production wiring is untested.

**Priority 3 (defensive grounding):**
- F3: Add a warning log or assertion at `_casilla_observation_for` when `registry_casilla is None` to surface ungrounded observations during M100/M200 schema-hardening expansion.
- F4: Add `label == record.display_name` to `ProfileAggregate._validate_cross_store_agreement`.

**No action required:**
- F5: Document actor attribution convention (display label, not UUID) if this is an accepted product choice; or backfill UUID as the canonical machine key and display label as annotation.
- F6: The renta first-slice cross-domain check registration is structurally sound with an explicit guard and a dedicated test.

**Overall health:** The primary handoff chain (registry authority → CalculationRevision.observations → CLI emit) is architecturally correct: `_build_typed_observations` populates full provenance; `CasillaObservation` carries all four provenance fields; the CLI projection is complete. The main gap is test coverage at the encrypted-persistence layer for the typed envelope, not a code defect. The profile-UUID/label decoupling is coherent; the UUID is the stable identity key throughout orchestration and repository layers.
