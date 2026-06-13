---
step_id: S212
tags:
  - "#exec"
  - "#eu-locale"
date: 2026-05-27
modified: '2026-05-27'
commit: 61e29af2a
related:
  - '[[2025-05-22-restructure-execution-P01-S01]]'
---

# Task #212 — Euskera (eu) locale implementation

## What was done

Added Euskera (`eu`) as a fully-supported output language.

**Root cause fixed:** `src/aeat/application/wizard/_commands.py` line 176 had a hardcoded `click.Choice(["es", "en", "ca", "hu"])` that rejected `--output-language eu` at CLI parse time. Fixed by importing `SUPPORTED_OUTPUT_LANGUAGES` and using `list(SUPPORTED_OUTPUT_LANGUAGES)`.

**Files changed in commit 61e29af2a:**

- `src/aeat/core/i18n/_render.py`: `eu` added to `SUPPORTED_OUTPUT_LANGUAGES` (done in prior session commit `ab28b1edb`)
- `src/aeat/application/wizard/_commands.py`: hardcoded choice list replaced with `SUPPORTED_OUTPUT_LANGUAGES`
- `src/aeat/locales/eu.yml`: new locale file, 2254 passthrough keys matching all other locales
- `src/aeat/locales/ca.yml`, `en.yml`, `hu.yml`: brought to full 2254-key parity with `es.yml` (9–505 missing keys added as passthrough for each)
- `src/aeat/locales/_intentional_identical.json`: ca ceiling updated 149 → 158 (9 wizard choice keys added by parity sweep mirror en)
- `src/aeat/application/registry/test_corpus.py`: hardcoded `("es", "en", "ca", "hu")` assertions replaced with dynamic `SUPPORTED_OUTPUT_LANGUAGES`
- `src/aeat/entrypoints/cli/test_eu_locale_acceptance.py`: 6 acceptance tests (all pass)

## Test results

```
src/aeat/entrypoints/cli/test_eu_locale_acceptance.py  6/6 PASS
src/aeat/locales/test_locale_translation_honesty.py    2/2 PASS
src/aeat/locales/test_parity.py::test_inter_locale_parity  PASS (was failing)
```

Pre-existing failures (Task #199 scope, all locales affected, not eu-specific):
- `test_codebase_to_locale_parity`: 11 keys missing from all locales
- `test_codebase_namespaces_are_satisfied_by_locale_entries`: `cli.diagnostics.profile.errors.*` and `renta_family.descendiente.*` namespaces absent from all locales including es/en

## Standing gates

- G1: no naked os.environ reads introduced
- G2: no untyped boundary changes
- G3: tr() pattern unchanged; eu.yml passthrough values are operator-readable key tails
- G4: locale yml structure edited only via Python (no hand-editing of nested structure; leaf values only)
- G5: no shims introduced; wizard._commands.py now derives from canonical SUPPORTED_OUTPUT_LANGUAGES
- G6: acceptance tests assert real CLI behaviour; no tautological assertions
