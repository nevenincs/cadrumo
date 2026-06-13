---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S09'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the typed concept-oriented records (concept level: immutable Spanish-stem concept_id, closed domain enum, domain_refs, legal_refs, broader/related with narrower derived, lifecycle draft/approved/deprecated/retired, replaced_by, seed_provenance, dates

## Scope

- `language sections es/en/ca/hu: definition`
- `source citation`
- `scope_note`
- `required first-class short_description`
- `term sections: label`
- `term_status preferred/admitted/deprecated/forbidden`
- `hidden_search_forms`
- `grammatical fields) plus the strict TOML loader (ADR D2)`
- `src/aeat terminology package + src/aeat/_data/terminology tree`

## Description

- Ground the registry authoring-compiler house pattern via the resident RAG and `rg`; study `_loader.py` / `_schema.py` of the registry and the smaller-scale `user_profile` loader as the mirror.
- Create the committed authoring tree `src/aeat/_data/terminology/concepts/` with three worked exemplar fragments (`prorrata`, `prorrata-especial`, `casilla`) that double as the bundled loader fixtures.
- Author the new top-level package `aeat.terminology`: the closed-axis StrEnums (`_enums.py`), the build-tooling error hierarchy (`_errors.py`), the strict frozen pydantic v2 concept/language/term schema (`_schema.py`), and the strict TOML loader with the narrower-derivation and validation-hook seam (`_loader.py`), surfaced through `__init__.py`.
- Mirror the registry pipeline shape `TOML authoring tree -> loader/compiler -> strict schema objects`, reusing the canonical `read_toml` / `freeze_toml` / `to_str_keyed_dict` helpers and the `bundled_path` resource boundary.
- Reuse the canonical `OutputLanguage` core StrEnum for the four-language axis rather than redeclaring it; keep the Handbook-local axes beside the schema.
- Derive `narrower` as the inverse of authored `broader` edges across the whole concept set at load; reject any fragment that authors `narrower`.
- Write real-behaviour structural tests (round-trip with every defaultable field non-default, `narrower` derivation, frozen-record enforcement, and the validation-error matrix) under the package tests folder.
- Regenerate the apidocs stubs for the new package (`dev.docs.apidocs scaffold`) and stage only the terminology stubs plus the top-level subpackage toctree.

## Outcome

The concept-oriented Terminology Handbook schema and strict loader (ADR D2, the W02.P04 keystone) are implemented and green. Concrete deliverables:

- **Authoring tree.** `src/aeat/_data/terminology/concepts/{prorrata,prorrata-especial,casilla}.toml`. `prorrata` grounds its `legal_refs` against the real LIVA prorrata provisions already in the legal catalogue (`ley-37-1992:art-102`, `ley-37-1992:art-104`), carries all four language sections (es/en/ca/hu) with multiple `term_status` entries (preferred/admitted) and a `hidden_search_forms` variant, and is seeded with an IATE `seed_provenance` attribution. `prorrata-especial` declares `broader = ["prorrata"]` so the loader derives `prorrata.narrower = ["prorrata-especial"]`. `casilla` carries a `forbidden` English calque (`box`) to demonstrate the anti-recommendation surface.
- **Package `aeat.terminology`.** Schema records `ConceptRecord` (concept tier) -> `LanguageSection` (language tier) -> `TermSection` (term tier), all strict, frozen, `extra="forbid"`; the TBX `partOfSpeech` / `grammaticalGender` and SKOS `hiddenLabel` (`hidden_search_forms`) borrowings; `SeedProvenance` and `LanguageSource` sub-records. Closed axes `ConceptDomain` {concepto, modelo, casilla-namespace, regimen, periodo, cli-verb, legal}, `ConceptLifecycle` {draft, approved, deprecated, retired}, `TermStatus` {preferred, admitted, deprecated, forbidden}. The strict loader compiles the nested `[language.<code>]` / `[[language.<code>.term]]` authoring layout into records, rejects authored `narrower`, rejects duplicate `concept_id` across fragments, and derives `narrower` last over the full set.
- **Validation seam for S10.** `load_terminology_handbook(concepts_dir, *, validators)` accepts a sequence of `HandbookValidator` callables run against the assembled, narrower-derived `TerminologyHandbook` immediately before return. `TerminologyHandbook` exposes `concepts`, `by_id`, `broader_edges` (the pre-inversion authoring edges), and `concept(id)` so a validator can reason over the relation graph. S10 bolts id-uniqueness/legal-ref-resolution/relation-integrity/approved-completeness gates onto this seam without touching the loader body.
- **Tests.** `src/aeat/terminology/tests/test_loader.py`, 13 tests, all green: `test_full_fragment_round_trips_with_every_field_preserved` (every defaultable field non-default), `test_record_is_frozen`, `test_narrower_is_derived_from_broader_inverse`, `test_authored_narrower_is_rejected`, `test_retired_without_replaced_by_raises`, `test_two_preferred_terms_in_one_language_raises`, `test_duplicate_concept_id_across_fragments_raises`, `test_missing_short_description_raises`, `test_concept_without_language_section_raises`, `test_invalid_toml_raises_load_error`, `test_empty_concepts_dir_raises`, `test_validation_hook_seam_runs_supplied_validators`, `test_bundled_handbook_compiles_and_derives_narrower`.

Gates: `pytest src/aeat/terminology -q` 13 passed; `ruff check` / `ruff format --check` clean; `ty check` and `pyright` clean; `pytest --collect-only -q` clean across the whole suite; `dev.docs.apidocs scaffold --check` conformant.

## Schema decisions and their provenance

- **Concept-oriented three-tier model** (TBX / ISO 30042, research P4): one `ConceptRecord` owns one `LanguageSection` per language, each owning `TermSection`s. The term-first alternative breaks on multi-alias languages and missing locales; concept-first matches the registry one-fragment-per-entity compile pattern.
- **SKOS borrowings** (research P4): `term_status` from `prefLabel`/`altLabel` (at most one `preferred` per language section, enforced in the language-section model_validator); `hidden_search_forms` from `hiddenLabel`; `broader`/`related` authored shallow, `narrower` DERIVED at load (never double-authored - authoring it raises). `exactMatch` and cross-scheme match properties were skipped per P4.
- **Four-state lifecycle + tombstone** (research P4, SNOMED immutable-id pattern): `replaced_by` is required exactly when `lifecycle` is `retired` (a single biconditional check), never on a live concept; records are retired, never deleted. Concept lifecycle and per-term status are orthogonal (the TBX insight): the deprecated-regime exemplar in the round-trip fixture carries `preferred` and `admitted` terms under a `deprecated` concept.
- **`short_description` first-class and required** per language section (research P3, the gettext non-inference rule): never derived from the first paragraph of `definition`. `definition`, `scope_note`, and `source` are optional at the single-record boundary because the approved-concept completeness rule (a grounded es definition with a source citation, short_descriptions in every authored language) is the SIBLING step S10's gate, not a per-record invariant - a `draft` concept legitimately has an empty definition.

## Enum-home decision (coordinator ratification requested)

The Handbook-local closed axes (`ConceptDomain`, `ConceptLifecycle`, `TermStatus`, plus `PartOfSpeech` / `GrammaticalGender`) live in `aeat.terminology._enums` / `aeat.terminology._schema`, NOT in `aeat.core`. Rationale: `modelo-identifiers-use-core-enum` and the architecture-boundaries "type every constant-like axis" rule put closed AEAT axes in core because they are cross-cutting identifiers referenced across domain/application/CLI (`Modelo` has high import in-degree across layers). The terminology axes have the opposite shape: a concept's `domain` or a term's `term_status` is meaningful only inside the Handbook surface and has no consumer outside this package. Co-locating them with the schema they constrain keeps the closed set beside its single consumer, consistent with the `user_profile` package which declares `ProfileFieldType` / `ProfileSnapshotPolicy` etc. locally rather than in core. The one genuinely cross-cutting axis - the four output languages - is NOT redeclared: the schema reuses the canonical `aeat.core.external_constants.OutputLanguage`. Spanish-stem naming is applied to the `ConceptDomain` member values (concepto, modelo, casilla-namespace, regimen, periodo, legal); generic computing vocabulary (record, schema, loader, language, term) stays English.

## Error-hierarchy decision (coordinator ratification requested)

`TerminologyError` subclasses `ValueError`, NOT `aeat.core.errors.AeatError`. The `AeatError` hierarchy carries a registered `ErrorCode`, a translated message, and JSON-envelope redaction for OPERATOR-facing runtime failures routed through the CLI; a CI-blocking gate (`core/errors/tests/test_registry_enforcement.py`) walks every `AeatError` subclass and requires a declared code in the layer-partitioned error-code registry. The Handbook loader is build-time documentation tooling (the ADR places the compiler in the docs pipeline): a malformed fragment is a developer/CI stack-trace failure, exactly like the `pydantic.ValidationError` it most often wraps. Subclassing `ValueError` keeps the loader self-contained, lets pydantic treat schema-rule failures uniformly, and avoids enrolling a build-tooling error into the runtime error-code registry (which would also force a registry-layer-taxonomy decision for a package that sits in none of the existing domain/adapters/entrypoints/core/application buckets). If the coordinator prefers the `AeatError` family, the follow-up is mechanical: re-parent `TerminologyError`, pick a registry layer bucket, and declare the three codes.

## S10 validation seam left explicit

The loader runs the deterministic narrower-derivation and per-fragment schema compilation unconditionally, then runs every supplied `HandbookValidator` last over the assembled `TerminologyHandbook`. S10 supplies its four gates as validators: (1) id-uniqueness beyond a single load is already partly enforced (duplicate `concept_id` across fragments raises in the loader); the cross-load never-reused-id ledger is S10's; (2) `legal_refs` resolution reads the legal catalogue and confirms each `ConceptRecord.legal_refs` entry resolves; (3) relation-target existence walks `broader`/`related`/`replaced_by` against `handbook.by_id`; (4) approved-concept completeness checks the es grounded definition + source + per-language short_descriptions. The seam needs no loader change to add any of these.

## Notes

- Two cross-cutting gates fail on PRE-EXISTING peer work, NOT this step, and are out of scope: `test_codebase_size_budgets.py` flags `_calculation_actions.py`, `_modelo_m036_cli.py`, `_ledger.py`, `_modelo_payloads.py` and others (none under `terminology`; all peer modules); `test_docstring_core_struct_links.py` flags `aeat.application.live._justificante` (a peer file already modified in the worktree's initial git status). My terminology modules pass both gates.
- `dev.docs.apidocs scaffold` also generated stubs for a peer's pre-existing drift (`aeat.application.ledger._evidence_input`, committed in `983143078` without a stub). Those stubs are left UNCOMMITTED on disk - I committed only the `aeat.terminology.*` stubs and the `aeat.rst` subpackage toctree line that references my package. The ledger stub gap is the ledger author's to land.
- No scaffolds-left-in-code, no skips, no xfail, no mocks. The bundled-handbook test exercises the real committed fragments end to end; the tmp_path tests exercise the real loader against authored TOML.
