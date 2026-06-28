---
tags:
  - '#adr'
  - '#quadlingual-i18n'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-04-12-trilingual-i18n-adr]]"
  - "[[2026-05-01-quadlingual-i18n-research]]"
  - "[[2026-05-01-quadlingual-i18n-reference]]"
---

# `quadlingual-i18n` adr: extending the contract from es/en/hu to es/en/ca/hu | (**status:** `accepted`)

## Problem Statement

The trilingual contract from 2026-04-12 (`es`, `en`, `hu`) covers the
canonical legal language, the project's working language, and Kent's
first language. It does not cover Catalan, which is co-official across
Catalunya, the Illes Balears, and the Comunitat Valenciana, and is the
day-to-day language of a non-trivial slice of the autónomo audience.

A second concern: the audit recorded in issue #377 found 27+ user-facing
CLI strings still hardcoded in English plus one call path that bypasses
`AEAT_OUTPUT_LANGUAGE` entirely. Nine `Translatable` literals carry the
identical English string in every slot — pseudo-translations that
silently revert to English. Adding `ca` is the right moment to close
those gaps, because the same call sites need a touch anyway.

## Considerations

Key factors:

- The existing trilingual ADR's six core decisions all hold. Adding
  `ca` is purely additive on the storage shape, the runtime
  primitives, the validation strategy, and the encoding policy.
- The corpus (`corpus/casillas/modelo_*` and `corpus/normatives/*`)
  already uses the nested-dict storage shape with `{es, en, hu}`
  keys. Adding a `ca` slot is a `total=False` extension; existing
  records remain valid until backfilled.
- The Generalitat de Catalunya, Agència Tributària de Catalunya
  (ATC), and DOGC publish Catalan-language tax forms that keep
  Spanish acronyms (`IVA`, `IRPF`, `IRNR`) intact rather than
  coining Catalan acronyms; the underlying instruments are state
  law, not autonomous law. Mirroring that convention keeps the
  output legally legible against published forms.
- Tax acronyms differ: Hungarian uses `ÁFA` for VAT and `SZJA` for
  personal income tax. The `hu` slots already recorded in the
  corpus follow this convention; `ca` slots will not.
- The user-facing CLI sees Spanish by default
  (`AEAT_OUTPUT_LANGUAGE=es`); the regression Kent reported is that
  many code paths fall back to English on his machine. Closing the
  audit gaps fixes the regression for `es` users specifically; the
  i18n contract widening is the architecture wrapper around it.
- A regression test that AST-scans `entrypoints/cli/` for bare
  string literals in user-facing emitters is the only way to
  prevent the same regression class from re-appearing as the CLI
  surface grows.

## Constraints

- The `Language` enum's `StrEnum` values must stay lowercase to
  match the storage shape and to round-trip through
  `normalize_language_code`.
- The fallback chain must put Spanish first in the default order;
  AEAT legal text is the canonical, and surfacing English ahead of
  Spanish on a partial record corrupts the user's mental model.
- The corpus backfill cannot regress any `definition_reviewed_at`
  metadata; the additive review pass bumps the date and records
  the reviewer (`human-codex`) explicitly.
- No build-step changes; the project does not use gettext / `.po`
  files and the trilingual ADR's tooling decision stands.

## Implementation

Architecture changes (additive, see the research doc for the
terminology rationale):

1. `src/aeat/core/i18n/__init__.py` — add `Language.CA = "ca"`,
   add the `ca: str` slot to the `Translatable` TypedDict, and
   replace the open-coded last-resort fallback list with a
   module-level `_HARDCODED_FALLBACK_ORDER = ("es", "en", "ca", "hu")`
   tuple consulted only after the configured chain is exhausted.
2. `src/aeat/core/config.py` — widen the `aeat_fallback_languages`
   default from `en,es` to `es,en,ca,hu`. Update the field
   docstrings to reference the four-language contract.
3. `env/.env.example` — update the i18n block with per-language
   commentary and the new fallback default.
4. `src/aeat/core/i18n/test_i18n.py` — add membership-closed test;
   add a `Language.CA` exact-match test; add a fallback test that
   confirms Spanish surfaces when `ca` is the target and only `es`
   is populated.
5. `src/aeat/entrypoints/cli/_i18n.py` — new module exposing
   `output_language()` and a thin `t(translatable)` shortcut that
   pre-binds the resolved language. Replace the four pre-existing
   local copies (`cli/filing/__init__.py`, `cli/profile/__init__.py`,
   `cli/financial/aggregate.py`, `cli/setup.py`) with imports from
   the new module.
6. CLI string migration per issue #377's punch list — every
   hardcoded English literal in the user-facing emitters is
   replaced with a `Translatable` literal carrying the four-language
   content from the legal glossary.
7. `src/aeat/application/review/_adapters.py` and
   `src/aeat/application/setup/_verifier.py` — replace the nine
   pseudo-translations (`{"es": text, "en": text, "hu": text}`
   where `text` is identical English) with real four-language
   `Translatable` literals.
8. `src/aeat/entrypoints/cli/test_no_hardcoded_user_strings.py` —
   new collection-time AST regression test that fails when any
   `typer.echo`, `_CONSOLE.print`, or `typer.BadParameter` call in
   `entrypoints/cli/` carries a bare string literal not routed
   through `Translatable` / `get_translation`.
9. `src/aeat/_corpus_ca_backfill.py` — one-shot maintenance
   script (deleted after the run) that walks every JSON under
   `corpus/casillas/` and `corpus/normatives/`, adds the `ca` key
   on every i18n map, sources the value from the legal glossary
   when a known lemma matches, falls back to the Spanish slot
   plus a `needs-native-review` provenance marker otherwise, and
   bumps `definition_reviewed_at` / `_by` to record the additive pass.

## Rationale

Why these specific decisions:

- **Catalan inclusion** — co-official across CAT/IB/VAL covers a
  meaningful subset of the autónomo audience the tool serves. The
  trilingual ADR's only reason to omit `ca` was the project's
  initial scope ceiling; that ceiling is now lifted.
- **Acronym retention for Catalan** — matches how the Generalitat,
  the ATC, and the DOGC themselves publish state-law instruments.
  Coining Catalan acronyms (`IVA` → `ITAV`?) would diverge from
  every published Catalan tax form and confuse users who cross-
  reference our output with the official documentation.
- **Spanish-first fallback chain** — the AEAT corpus is legally
  Spanish-canonical; surfacing English when Spanish is available
  corrupts the user's mental model of what a casilla actually says.
  The configured default (`es,en,ca,hu`) matches this priority.
- **Pseudo-translation prohibition** — the audit found nine
  literals where the same English string was duplicated across
  three slots. Without a regression test these will recur as the
  codebase grows; the test in `core/i18n/test_no_pseudo_translations.py`
  is short and targeted.
- **Collection-time CLI regression test** — preventing the same
  regression class is more valuable than fixing the current
  instances. AST scanning at collection time gives sub-second
  feedback during local pytest runs.
- **Backfill via maintenance script** — the corpus has 147+ JSON
  files and roughly 220 distinct lemmas. A script with explicit
  glossary lookups + per-record provenance is the only way to keep
  the diff auditable and re-runnable as future corpus drift adds
  records.

## Consequences

- Every record in the corpus gains a `ca` key, increasing per-file
  size by roughly 25%. Total corpus growth is bounded — under a
  megabyte across the catalogue.
- The CLI's user-visible strings stop drifting toward English
  defaults; Spanish-default users see Spanish on every code path,
  including the review queue. Catalan users see grounded Catalan
  on AEAT terminology and Spanish fallback (with the acronym
  intact) on records the glossary did not cover.
- A new CLI command faces a hard collection failure if a bare
  string is wired into `typer.echo` or any other user-facing
  emitter. This is intentional pressure to keep the i18n pipeline
  complete by construction.
- The audit issue #377 closes once the migration is complete; the
  regression test prevents the audit from needing a re-run.
- Native Catalan tax-terminology review remains a valuable
  downstream step. Records seeded by the backfill script carry an
  explicit `needs-native-review` marker on the `ca` slot, so a
  future native reviewer can sweep without first re-discovering
  which records are pristine versus seeded.
- The vault gains one extra reference document (the legal
  glossary) that future translators consult before adding a
  `Translatable` literal.
