---
tags:
  - '#adr'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
related:
  - "[[2026-07-12-multilang-externalization-adr]]"
  - "[[2026-06-01-docs-educational-surface-adr]]"
  - "[[2026-07-18-user-docs-localization-research]]"
---

# `user-docs-localization` adr: `docs localization via gettext catalogues with an all-languages completeness gate` | (**status:** `accepted`)

## Problem Statement

The user documentation (the Sphinx user-scope surface: how-to, explanation,
reference, index, glossary, sequences) is English-only, while the product's
operator surface is contractually four-language (`OutputLanguage`: es, en,
ca, hu). The educational-surface ADR deferred docs localization to a later
decision; the operator has now directed it: Spanish, Catalan, English, and
Hungarian documentation, built on real localization infrastructure, with a
holistic validity contract — a documentation page is valid and complete only
when every principal language is actually present. No such infrastructure
exists today (`language = "en"` is pinned in the Sphinx config).

## Considerations

- The `multilang-externalization` ADR forbids reusing runtime CLI YAML
  catalogues for docs prose; docs need their own localization workflow.
- The Sphinx config already reserves the attachment point: `language`,
  `locale_dirs`, `gettext_compact`, and a gettext / sphinx-intl build matrix.
- Sphinx gettext falls back to English for untranslated segments silently;
  the operator contract demands the opposite — absence must be a loud
  failure, never a silent fallback.
- The language set must not become a second hand-listed authority; it derives
  from `OutputLanguage` (en is the authoring source; es, ca, hu are
  translation targets).
- Generated surfaces (CLI reference, glossary, casilla/env references,
  executed CLI sequences) are English-sourced build products; their prose
  segments flow through the same gettext extraction as authored pages.
- Style and terminology rules apply per language: imperative
  taxpayer-general prose, Spanish-stem AEAT domain nouns invariant in every
  language, Terminology Handbook as the single glossary authority.
- Translation must read as native, idiomatic prose — reviewed per whole page
  with domain context — not mechanical segment substitution, even though the
  storage format is segment-keyed.

## Considered options

1. **Parallel per-language page trees** (`docs/es/**` mirrors). Whole-page
   freedom, but a 4× structural drift surface with no mechanical parity
   primitive; every gate hand-built. Rejected.
2. **Reuse runtime YAML locale catalogues for docs prose.** Already rejected
   by the accepted `multilang-externalization` ADR (different audience,
   lifecycle, review). Rejected.
3. **Sphinx gettext + sphinx-intl per-language builds with a
   coverage-refusal gate.** Canonical Sphinx i18n; POT extraction per source
   page, per-language `.po` catalogues, per-language builds; parity of
   structure is guaranteed by construction (one source tree), and
   completeness is mechanically measurable per catalogue. Accepted.

## Constraints

- `sphinx-intl` and `babel` join the docs dependency group; both are mature.
- Per-language `-W` builds multiply docs CI time; the user scope (minutes,
  no app imports) is the localized matrix, keeping the full autodoc build
  English-only.
- gettext fuzzy-matching on source edits marks entries fuzzy rather than
  failing; the completeness gate must count fuzzy as missing.
- The Pagefind search index and glossary generation must run per language at
  deploy; the index stays uncommitted (licence-clean rule).
- The docs build pins runtime CLI output to English for executed sequences;
  localized builds keep that pin (command output is evidence, not prose).

## Implementation

- **Extraction**: a `dev.docs` gettext step renders the user-scope POT
  templates into `docs/locales/pot/` (uncommitted build product), with
  `gettext_compact = False` so each source page owns one catalogue.
- **Catalogues**: committed per-language catalogues at
  `docs/locales/{es,ca,hu}/LC_MESSAGES/**/*.po`, managed by `sphinx-intl
  update`; English is the msgid source and has no catalogue.
- **Config**: `docs/conf.py` reads the build language from an environment
  switch validated against `OutputLanguage`; `locale_dirs = ["locales"]`.
  Default stays `en`.
- **Build matrix**: justfile targets to build one language and to build the
  full language matrix for the user scope; the deploy publisher emits
  per-language site roots (`/es/`, `/ca/`, `/hu/`, `/` = en) with a language
  switcher in the theme context.
- **Completeness gate** (the operator's validity contract, in
  `dev/docs/tests`): for every user-scope source page and every target
  language, the page's catalogue exists and carries zero untranslated and
  zero fuzzy entries — enumerated failures name page, language, and counts.
  A second gate asserts the docs language set equals `OutputLanguage`
  members exactly. A per-language nitpicky `-W` user-scope build completes
  the matrix. `just docs-check` runs all of it.
- **Translation workflow**: translators work per whole source page with the
  English page, the Terminology Handbook glossary, the Spanish-stem rule,
  and the runtime locale catalogues as context; the `.po` file is the
  storage format of the result, not the unit of thought.

## Rationale

Option 3 is the only design that satisfies all three binding constraints at
once: it keeps one structural source of truth (no drift surface), it is the
mechanism the docs config was explicitly built to attach, and its per-entry
catalogue statistics make the operator's "all languages present or invalid"
contract a mechanical gate instead of an honor system. The silent-fallback
weakness of stock gettext is inverted into a hard gate: fallback may exist
at render time, but CI refuses any catalogue with untranslated or fuzzy
entries, so a shipped page can never silently show English inside a Spanish,
Catalan, or Hungarian site.

## Consequences

- Every future English docs edit invalidates the touched segments in three
  catalogues; `docs-check` goes red until all three languages catch up. This
  is intended: docs changes now carry a four-language definition of done.
- ~57 pages × 3 languages of initial translation debt, staged per section
  with per-page completeness visible in the gate output.
- The frontend web app's separate i18n module still lacks `hu`; out of scope
  here, flagged as a follow-up.
- Docs CI grows three user-scope builds (each minutes, no app imports).
- Opens per-language deployment and, later, localized search relevance work.
