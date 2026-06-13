---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S10'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the loader validation gates: unique never-reused ids, every legal_ref resolves in the legal catalogue, relation targets exist, lifecycle/replaced_by integrity (retired requires replacement), approved concepts carry a grounded es definition with source citation and short_descriptions in every authored language section (ADR D2/D8)

## Scope

- `terminology loader + its tests folder`

## Description

- Ground the legal-catalogue resolution authority via the resident RAG and `rg`; study the registry `verify_legal_catalogue` and the `bundled_authority().catalogues.legal` mapping keyed by legal-ref id.
- Read the core-authority ADR the architecture-boundaries rule cites to resolve the S09 enum-home tension definitively (gate 6).
- Implement the five validation gates as `HandbookValidator` factories in a new `_validators.py` module on the seam S09 exposed - the loader body is untouched.
- Correct the S09 `replaced_by` per-record obligation from a too-strict biconditional to the ADR D2 rule (required-when-retired, optional-when-deprecated, forbidden-when-draft/approved) so a deprecated concept may name a live successor.
- Resolve every concept's `legal_refs` against the same registry legal catalogue the calculation engine grounds against, via the validated authority accessor, with an injectable id-set for unit isolation.
- Write real-behaviour passing + failing tests per gate (anti-tautology), exempting draft concepts from completeness, and prove the bundled exemplars pass the full inventory against the real 262-entry catalogue.
- Run ruff / ty / pyright / pytest green; regenerate apidocs stub for the new module.

## Outcome

The five loader validation gates (ADR D2 / D8) are implemented as `HandbookValidator` callables on the seam designed in S09, with the loader body unchanged. Deliverables:

- **`_validators.py`** - five gate FACTORIES, each returning a closure over the assembled `TerminologyHandbook`, plus `default_handbook_validators(legal_ref_ids=None)` assembling the inventory in loader-run order:
  - `id_uniqueness_validator()` - no duplicate `concept_id` across the handbook (gateifies the loader's per-fragment dedupe as an explicit, independently testable member; the never-reuse contract holds because a retired concept persists as a tombstone occupying its id, so a re-minted live concept under that id trips this gate).
  - `legal_refs_resolve_validator(legal_ref_ids=None)` - every `legal_ref` on every concept resolves in the legal catalogue. Defaults to the bundled authority's catalogue keys; accepts an injected id-set for unit isolation.
  - `relation_integrity_validator()` - every `broader`, `related`, and `replaced_by` target is an existing `concept_id`.
  - `lifecycle_replaced_by_validator()` - a `retired` concept's `replaced_by` points at a NON-retired concept; a `deprecated` concept's declared `replaced_by` likewise must be live; the `replaced_by` graph is acyclic.
  - `approved_completeness_validator()` - an `approved` concept carries an es `definition` AND an es `source` citation, and EVERY authored language section carries a non-empty `short_description`. Draft/deprecated/retired are exempt (the draft asymmetry is the curation-backlog signal W05.P13 ratchets).
- **Schema correction (in-scope).** S09's `ConceptRecord` per-record validator enforced a biconditional (`replaced_by` set exactly when retired), which rejected a `deprecated` concept naming a successor. ADR D2 and research P4 say `replaced_by` is mandatory WHEN retired - not forbidden on deprecated. Corrected to: required when retired, optional when deprecated, forbidden when draft/approved. The S09 round-trip and `test_retired_without_replaced_by_raises` tests still pass (the message still contains `replaced_by`). The cross-record successor checks (existence, non-retired-target, acyclicity) stay handbook-level gates, not per-record invariants.
- **Public surface.** The five factories and `default_handbook_validators` are exported from `aeat.terminology`. The registry import in the legal gate is deferred (function-body `import`) so `import aeat.terminology` does not drag the registry into light consumers.
- **Tests.** `src/aeat/terminology/tests/test_validators.py`, 18 tests, all green; combined package suite 31 passed. Per-gate passing + failing pairs (anti-tautological), plus the bundled-exemplar full-inventory gate and the default-catalogue legal-resolution gate.

Gates: `pytest src/aeat/terminology -q` 31 passed; `pytest --collect-only -q src/aeat/terminology` 31 collected clean; ruff check / format clean; ty and pyright clean; importlinter shows zero terminology involvement (the one broken layered contract is pre-existing peer drift, no terminology edge).

## Legal-catalogue authority resolved against

The legal gate resolves against `bundled_authority().catalogues.legal` - the `RegistryCatalogues.legal` mapping (`Mapping[LegalRefId, LegalReference]`, keyed by legal-ref id), reached through the registry's publicly exported `bundled_authority()` LRU-cached accessor. This is the SAME catalogue the calculation engine and the registry's own `verify_legal_catalogue` ground against, satisfying the registry-authority-flow rule (consume through the validated authority, never re-parse the legal TOML). The S09 exemplar `prorrata` legal_refs (`ley-37-1992:art-102`, `ley-37-1992:art-104`) were verified to resolve in the live 262-entry catalogue. The cross-layer import (terminology -> domain.calculations.registry) is sanctioned by core-authority ADR Rule 2 Exception A (registry surfaces importable by any layer per the registry-authority-flow precedent) and matches the `aeat.locales` precedent of a top-level package consuming lower layers.

## Enum-home verdict (gate 6 - resolved, ADR-cited)

VERDICT: package-local placement of `ConceptDomain` / `ConceptLifecycle` / `TermStatus` in `aeat.terminology._enums` is CORRECT and sanctioned by the cited ADR - no relocation to `core/`.

The architecture-boundaries rule's "closed value sets ... MUST be declared as StrEnum in `core/`" is qualified by the ADR it cites: `2026-05-31-core-authority-adr`. That ADR's **Rule 1 (placement principle)** is explicit: "A definition used only within its own package stays in that package. A definition consumed by more than one non-owning layer moves to core/." Its **Rule 4 (module pattern)** names the home directly: "Enum declarations: `_enums.py` within the owning package, OR core/ for cross-layer enums." The discriminator is cross-layer consumption (clause a: imported outside the declaring layer). `OutputLanguage` IS cross-layer (CLI, application, core i18n all consume it) - so it lives in core, and the schema correctly reuses it rather than redeclaring. `ConceptDomain` / `ConceptLifecycle` / `TermStatus` are consumed ONLY inside `aeat.terminology` (the schema, the loader, the validators - one package) - so Rule 1 places them in the owning package's `_enums.py`, exactly where they are. This mirrors the `user_profile` precedent cited in S09 (`ProfileFieldType` / `ProfileSnapshotPolicy` declared package-local) and the `iva` / `renta` / `modelos` packages, all of which carry domain-local StrEnums under Rule 4. The tension S09 flagged is therefore resolved in favour of local placement, on the ADR's own placement rule - not left open.

## S10 seam usage (no loader change)

All five gates are `HandbookValidator` callables passed to `load_terminology_handbook(..., validators=...)` - the seam S09 exposed. The loader runs the deterministic narrower-derivation and per-fragment compilation unconditionally, then runs the validators last over the assembled handbook. `_validators.py` adds no line to `_loader.py`; the only `_loader.py`-adjacent change is none (the schema correction is in `_schema.py`, a per-record obligation fix, not a seam change).

## Notes

- One in-scope schema correction: the S09 `replaced_by` biconditional was too strict for the gate-4 spec; corrected to the ADR D2 obligation. This is the only S09 file touched, and it is a genuine spec-conformance fix surfaced by writing the deprecated-points-at-live test - not scope creep.
- Two cross-cutting gates fail on PRE-EXISTING peer files, NOT this step: `test_codebase_size_budgets.py` (peer modules `_calculation_actions`, `_modelo_m036_cli`, `_ledger`, `_modelo_payloads`, none under terminology) and `test_docstring_core_struct_links.py` (peer files `aeat.application.live._justificante`, `aeat.application.modelo._calculation_actions` - both already-modified in the worktree's git status). My terminology modules pass both gates.
- apidocs `scaffold` generated the `aeat.terminology._validators` stub and updated the package toctree; the peer `aeat.application.ledger._evidence_input` drift stub is again left UNCOMMITTED (not mine). Committed only my `_validators` stub and the regenerated `aeat.terminology.rst` toctree.
- No mocks, skips, xfail, or tautological assertions. The synthetic legal id-set is real data passed to the real gate (not a mock); the bundled-exemplar test exercises the real registry catalogue end to end.
