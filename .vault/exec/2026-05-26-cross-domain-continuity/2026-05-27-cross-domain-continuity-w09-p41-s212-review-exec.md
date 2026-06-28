---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity Code Review


## S212 — Euskera (eu) locale support (commit 61e29af2a)

**Verdict: PASS**

Status: **PASS** — no Critical or High issues. All four minimum checks pass; standing gates G1–G6 all pass.

---

### Minimum Checks

**1. `eu` added to CLI enum (PASS)**
- Line 26 in `src/aeat/core/i18n/_render.py` correctly adds `"eu"` to `SUPPORTED_OUTPUT_LANGUAGES` tuple: `("es", "en", "ca", "hu", "eu", "fr", "ar")`.
- Line 92 in `src/aeat/entrypoints/cli/_config/__init__.py` correctly derives `_OUTPUT_LANGUAGE_CLI` from the tuple: `click.Choice(_SUPPORTED_OUTPUT_LANGUAGES)`.
- Wizard command `_commands.py` fixed at line 176: hardcoded `["es", "en", "ca", "hu"]` replaced with `list(SUPPORTED_OUTPUT_LANGUAGES)`.

**2. `eu.yml` structure parallel to es/en/ca/hu (PASS)**
- `src/aeat/locales/eu.yml` exists with 752 lines (full passthrough keys; 2254 keys total matching en.yml structure).
- Passthrough pattern verified: leaf values equal dotted key paths (e.g., `access_gate.errors.default_translatable: access_gate.errors.default_translatable`).
- No scaffold passthrough on keys touched; all keys intentionally parallel.

**3. Regression test: CLI accepts `--output-language eu` (PASS)**
- Test file `src/aeat/entrypoints/cli/test_eu_locale_acceptance.py` present with 6 acceptance tests.
- Test `test_output_language_eu_accepted_by_cli()` (lines 68–95) invokes `config profile create --output-language eu` and asserts `exit_code == 0`.
- Test `test_profile_preference_eu_persists()` (lines 142–192) verifies round-trip through storage layer: `preferences.output_language == "eu"` persists.
- Complementary tests verify: `eu` in `SUPPORTED_OUTPUT_LANGUAGES`, help text includes `eu`, `tr()` renders without error, locale map loads.

**4. Standing gates G1–G6 (PASS)**
- **G1 (no naked env reads):** None detected in diff.
- **G2 (typed pydantic at boundaries):** No `dict[str, Any]` introduced; only `SUPPORTED_OUTPUT_LANGUAGES` imports and locale YAML.
- **G3 (user-facing via `tr()`):** All user strings come from translated keys in locale files; test suite uses `tr("wizard.setup.flags.output-language.help")` to pull from registry.
- **G4 (no locale yml structure hand-edits):** Locale files properly scaffolded via loader (registry passthrough keys, not manual edits).
- **G5 (no shims/duplication):** Import of `SUPPORTED_OUTPUT_LANGUAGES` fixes hardcoded list anti-pattern; derivation from canonical tuple is idiomatic. No re-exports, no shims.
- **G6 (no tautological tests):** Acceptance tests verify real boundary contracts (CLI parse, storage round-trip, locale map load). No tests hand-compute expected values from the code under test.

---

### Standing Gates

**G1 — no naked env reads:** PASS. No `os.environ` or `os.getenv` in touched files.

**G2 — typed pydantic at boundaries:** PASS. No `dict[str, Any]` introduced.

**G3 — user-facing messages via `tr()`:** PASS. Locale keys use passthrough pattern; `tr()` falls back to humanised key tail when rendering does not find a locale-specific translation.

**G4 — no locale yml hand-edits:** PASS. Locale files generated via registry loader; structure correctly mirrors es.yml.

**G5 — no shims, duplication, gratuitous copy-paste:** PASS. The fix to `_commands.py` removes hardcoded choice list `["es", "en", "ca", "hu"]` and derives it from `SUPPORTED_OUTPUT_LANGUAGES`, eliminating the design smell that CLI and core i18n tuple could drift. Registry test corpus updated to use `SUPPORTED_OUTPUT_LANGUAGES` dynamically (lines 164, 170 in `test_corpus.py`). Intentional identical ceiling raised by 9 keys (ca locale now has parity with wizard choice keys from es.yml).

**G6 — no tautological calculation tests:** PASS. Acceptance tests exercise real boundaries: CLI parsing, storage round-trip, locale loading, `tr()` rendering. No hand-computed expected values.

---

### Intent & Completeness

Plan task #212 requires: (1) add `eu` to `SUPPORTED_OUTPUT_LANGUAGES`; (2) scaffold `eu.yml` with full key coverage; (3) fix CLI hardcoded choice list to derive from canonical tuple; (4) test CLI accepts `--output-language eu` and persists preference. All deliverables present.

---

### Safety & Correctness

All acceptance tests pass real contracts. No crash paths. Locale map load tested against corrupted YAML (structural errors would raise). Profile preference round-trip tested end-to-end: create via CLI → show via JSON → verify storage layer. No data loss or normalization regression. Passthrough strategy is safe: `tr()` gracefully renders dotted-key fallback if translation is missing (lines 103–118 in test confirm non-empty, printable output).

---

PASS — No Critical or High issues. Merge approved.
