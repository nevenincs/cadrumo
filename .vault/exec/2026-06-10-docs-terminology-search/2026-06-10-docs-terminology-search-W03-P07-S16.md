---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S16'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the CLI-surface record emitter (every command and option with locale-resolved help across the four languages) and the concept-card emitter (definition, short_description, four-language alias sets, legal grounding links) (ADR D4)

## Scope

- `dev docs terminology compiler`

## Description

Implements ADR **D4** record kinds (a) concept cards and (c) CLI surface
records — the two emitters the Ctrl-K command palette surfaces as first-class
"term cards" (concept meaning + legal grounding) and CLI-surface results.
Casilla projection (b) is the sibling S15; doc pages (d) come from Pagefind in
W04.

Two new build-time modules under `dev/docs/terminology/` (alongside
`cli_reference.py` / `apidocs` — build tooling, emitting an UNCOMMITTED
artifact consumed by the later Pagefind injection):

- **`_cli_projection.py`** — `project_cli_search_records()` walks the LIVE
  materialised Typer/Click command tree via the house pattern
  (`typer.main.get_command(app)` after `_force_lazy_imports`, reusing
  `dev/docs/cli_reference.py`'s `_collect_commands` / `_normalise_command_path`).
  CLI help strings are `tr()` values baked to plain strings at module-import
  time, so the original translation keys are NOT recoverable from the
  materialised tree; the four-language help is gathered by walking the tree
  FOUR times, once per language, each in a fresh subprocess with
  `AEAT_OUTPUT_LANGUAGE=<lang>` (the same clean-interpreter guarantee
  `generate_cli_reference_in_subprocess` uses). Emits one `CliSurfaceRecord`
  per leaf command and one `CliOptionRecord` per option/argument; each carries
  a `descriptions: dict[OutputLanguage, str]` (es invariant, en/ca/hu where
  the help differs from the Spanish — an identical string is treated as
  untranslated and omitted, never duplicated) plus a `target` anchor
  `cli/<family>.html#<docutils-slug-of-command-path>`.

- **`_concept_cards.py`** — `project_concept_cards()` loads the REAL bundled
  Terminology Handbook via `load_terminology_handbook(validators=default_handbook_validators())`
  (the full ADR-D8 gate inventory runs, so a malformed Handbook fails here, not
  half-mapped) and emits one `ConceptCardRecord` per concept (drafts included,
  lifecycle-flagged). Each card carries the per-language `short_description`
  (the `descriptions` map), per-language `LocalisedDefinition` (definition +
  scope_note), the four-language `TermAlias` set (every term `label` by status,
  with `hidden_search_forms`), and resolved `LegalGroundingLink`s — each
  `legal_ref` resolved through `bundled_authority().catalogues.legal` (the SAME
  catalogue the calculation engine grounds against, per
  `aeat-registry-authority-flow` / `aeat-calculation-grounding`) into the BOE
  `permalink` + anchored `corpus_ref` + `document_id` + `notes`. An unresolved
  ref is reported in `stats.unresolved_legal_refs`, never echoed as a dead
  link.

Both records extend the shared `SearchRecordBase` / `SearchRecordKind`
authored by S15 in `_search_record.py` (imported READ-ONLY — the parallelism
fence; the base's docstring explicitly anticipates the S16 emitters extending
it), reusing the `kind` discriminator (`SearchRecordKind.CLI` /
`SearchRecordKind.CONCEPT`) and the four-language localised-description map.
Strict-frozen pydantic v2 throughout; closed axes are StrEnum
(`OutputLanguage`, `ConceptDomain`, `ConceptLifecycle`, `TermStatus`).

## Outcome

Landed (one atomic commit, see Notes for hash). Verification proofs:

- **CLI emitter:** 209 `CliSurfaceRecord`s + 830 `CliOptionRecord`s; 0
  untranslated commands; command-record `registry_key` set == the independent
  house-walk live leaf set (exact parity); every `target` anchor equals
  `docutils.nodes.make_id(command_path)` (the slugger Sphinx itself uses —
  verified against the built `docs/_build/html/cli/*.html` section ids).
- **Concept-card emitter:** 95 cards == 95 bundled concepts (20 approved + 75
  draft, lifecycle-flagged); the approved `prorrata` card carries es+en+ca+hu
  short_descriptions, its alias set (en preferred "pro rata", es admitted
  "prorrateo"), and 2 resolvable BOE legal links (`ley-37-1992:art-102/104`);
  0 unresolved refs against the real catalogue.

Tests (14, all real-behaviour, no mocks) under
`dev/docs/terminology/tests/`:
- `test_cli_projection.py` (7): `test_command_records_cover_the_live_leaf_set`,
  `test_every_command_record_carries_a_spanish_description`,
  `test_prorrata_relevant_command_is_fully_translated`,
  `test_every_target_anchor_resolves_to_the_cli_reference_shape`,
  `test_option_records_attach_to_their_command_and_carry_help`,
  `test_required_amount_option_is_marked_required`, `test_records_are_frozen`.
- `test_concept_cards.py` (7): `test_one_card_per_bundled_concept`,
  `test_card_count_matches_curation_split`,
  `test_approved_prorrata_card_is_fully_populated`,
  `test_every_card_has_a_spanish_short_description`,
  `test_all_legal_refs_resolve_against_the_real_catalogue`,
  `test_legal_link_resolution_reports_a_missing_ref` (anti-tautology: a
  synthetic catalogue missing `art-104` must report it unresolved, not
  fabricate a link), `test_card_records_are_frozen`.

Gates green: `pytest dev/docs/terminology/tests/ -q` (14 passed);
`pytest --collect-only -q dev/docs/terminology/` (clean); `ruff check` /
`ruff format --check` clean; `ty check` clean (pyright scope is `src/aeat`
only, so `ty` is the authoritative gate for `dev/docs`).

## Notes

- **S17 reconciliation (ADR D4/D6):** S16 (CLI + concept) and S15 (casilla)
  records share `SearchRecordBase` / `SearchRecordKind` but are NOT yet
  unified into one index schema or exported together from the package
  `__init__.py`. To honour the parallelism fence I did NOT edit
  `_search_record.py`, `_casilla_projection.py`, or the package `__init__.py`
  (all S15-authored, untracked WIP at the time of this Step). My modules and
  tests import the records directly from their submodule paths
  (`dev.docs.terminology._cli_projection` / `._concept_cards`), not via
  `__init__.py`. S17 owns the `__init__.py` re-export reconciliation and the
  single unified index schema across all four record kinds.
- **Shared package marker:** `dev/docs/terminology/tests/__init__.py` (empty
  package marker) was created by S16 because the tests dir existed without it;
  it carries no logic and is idempotent if S15 also adds it.
- **pyproject:** added `dev/docs/terminology/_cli_projection.py` to the `S603`
  per-file ruff ignore (the controlled-argv subprocess pattern, exactly as
  `dev/docs/cli_reference.py` is allowlisted).
- **Locale-key gaps:** none observed — every leaf command and the sampled
  options resolved help in all four languages (`commands_untranslated = 0`).
  The emitter's design tolerates a gap gracefully: a missing/identical
  non-Spanish help is omitted (es stays the invariant) rather than failing.

