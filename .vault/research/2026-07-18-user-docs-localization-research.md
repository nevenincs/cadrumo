---
tags:
  - '#research'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
body_hash: 'sha256:eced3a5ca42af4f8b9db59848e2872c354f1795466d9f456f339ffd0a7a5798c'
related:
  - '[[2026-07-12-multilang-externalization-adr]]'
  - '[[2026-06-01-docs-educational-surface-adr]]'
---

# `user-docs-localization` research: `user documentation localization architecture`

Operator directive 2026-07-18: the user documentation must support Spanish,
Catalan, English, and Hungarian, with real localization infrastructure — not
line-by-line string substitution — and a holistic validity contract: a
documentation page counts as valid and complete only when every principal
language is actually present. This research grounds the current state via
`vaultspec-rag` (code + vault corpora) plus targeted source reads.

## Findings

### The language set is already law elsewhere

- `OutputLanguage` in `src/cadrumo/core/external_constants.py` is the closed
  BCP-47 set `es`, `en`, `ca`, `hu`, matched 1:1 by the runtime CLI catalogues
  `src/cadrumo/locales/{en,es,ca,hu}.yml` and their parity/honesty gates
  (`test_parity.py`, `test_locale_translation_honesty.py`,
  `test_locale_coverage_inventory.py`). Adding Hungarian to the docs surface
  therefore aligns docs with the existing runtime contract; no new language is
  introduced into the product.
- The accepted `multilang-externalization` ADR (2026-07-12) explicitly rules
  that documentation prose is NOT a runtime translation catalogue:
  "Documentation prose … has its own authoring, review, and localization
  workflow." Docs localization must not reuse the runtime YAML keys.

### The docs surface and its build

- User-facing docs are Sphinx + MyST Markdown under `docs/` (~57 pages outside
  the autodoc tree): `index`, `how-to/` (~25 pages), `explanation/` (7),
  `reference/` (7), `architecture`, `cli/` (generated reference), glossary,
  executed CLI sequences under `docs/_sequences/`, plus `disclaimer`,
  `updates`, `workstation-setup`, `authoring-guide`.
- `docs/conf.py` supports two build scopes via `CADRUMO_DOCS_SCOPE`: `full`
  (CI + deploy, includes ~1,150 autodoc stubs) and `user` (operator surface
  only, no app imports). The user scope is the localization target; the API
  autodoc tree is contributor-facing English by prior ADR and stays out.
- `docs/conf.py:116` already reserves the attachment point: "Additional
  languages attach here — set `language`, add `locale_dirs` and
  `gettext_compact`, and a gettext / sphinx-intl build matrix. Documentation
  translation must not reuse the runtime CLI translation catalogues."
- Build drivers: `python -m dev.docs.build` (justfile `docs`, `docs-page`,
  `docs-changed`), gates in `dev/docs/tests/test_docs_build.py` (nitpicky
  `-n -W` builds, scope-conditional config assertions), `just docs-check`
  (pytest `-m docs` + doc8). Generated surfaces (CLI reference, glossary from
  the Terminology Handbook, casilla/env references, Pagefind search index)
  are produced by `dev/docs/*.py` generators.
- The docs pin the CLI output language to English at build time (top of
  `docs/conf.py`) because executed CLI sequences and the generated CLI
  reference render live CLI output.

### Prior decisions that bind this campaign

- `2026-06-01-docs-educational-surface-adr`: Diataxis is binding; the
  educational surface launched English-only, "deferring localization to a
  separate, later decision" — this campaign is that decision. Single-source
  contract: docs must not re-author CLI flag/command help.
- `aeat-user-docs-hardening` + `aeat-documentation-workflow` rules: simple
  imperative instruction style, taxpayer-general terminology, command
  conformance and Sphinx build gates are mandatory.
- `aeat-spanish-stem-naming`: AEAT domain nouns keep Spanish stems
  (modelo, casilla, censo, justificante…) in every language.
- `glossary-concepts-are-taxpayer-facing` + `terminology-single-declaration`:
  the Terminology Handbook is the glossary authority; translations must not
  redeclare enrolled terms.
- `shipped-search-licence-clean`: the Pagefind index is regenerated per
  build, never committed; a localized site regenerates per-language search.

### Localization mechanism options observed

- Sphinx's first-party i18n: `make gettext` extracts POT templates
  per source page; `sphinx-intl` manages per-language `.po` catalogues under
  `locale_dirs`; building with `language=<lang>` substitutes translated
  paragraphs. Untranslated/fuzzy entries fall back to English silently —
  acceptable for incremental upstreams, but contrary to the operator's
  all-languages-present validity contract unless a coverage gate refuses
  fallback. `msgfmt --statistics` / `babel` expose per-catalogue
  translated/fuzzy/untranslated counts mechanically.
- Parallel per-language page trees (`docs/es/**` mirrors) would allow
  free-form whole-page translation but create a 4× structural drift surface
  (headings, anchors, toctrees, cross-references) with no mechanical parity
  primitive; every gate would be hand-built. Rejected by every prior sibling
  system in this repo (runtime locales, modelo locales) in favour of
  keyed catalogues with parity gates.
- The frontend (`frontend/src/i18n.tsx`) has a separate hand-rolled
  en/es/ca copy module without `hu`; it is not part of the user documentation
  surface and stays out of scope here (noted as a follow-up gap).

### Translation-quality context available to translators

- The Terminology Handbook (`src/cadrumo/_data/terminology/concepts/`) with
  approved taxpayer-facing concepts and the generated glossary.
- The runtime locale catalogues (`src/cadrumo/locales/*.yml`) as the
  authoritative translations for CLI-adjacent vocabulary the docs reference.
- The style rules above (imperative, simple, taxpayer-general) apply to every
  language, and Spanish-stem domain nouns are invariant across languages.
