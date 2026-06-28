---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S24'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Extend the Ctrl-K palette to query Pagefind with the progressive ladder - term cards first (short_description plus jump links to glossary anchor, casillas, legal corpus, how-tos), nav titles second, full text third - and replace the stock search page with the Pagefind surface via Furo template override (ADR D5)

## Scope

- `docs/_static/aeat-docs.js + docs/_templates + docs/conf.py`

Implements ADR D5: the Ctrl-K palette queries Pagefind with the progressive
ladder - term cards first, navigation second, full text third - the operator's
literal goal endpoint (semantic search via the command-K popup). Extends the
existing nav/TOC palette (does not rewrite it) and proves it works in a real
browser.

## Description

- Extend `initPalette` in `docs/_static/aeat-docs.js`: lazy-load Pagefind on
  first open, compose the three-tier ladder on each query, render term cards
  with kind badges, keep the nav tier, dedupe across tiers, preserve keyboard
  nav. Add minimal `aeat-docs.css` for the card badges/excerpt.
- Drive a real browser (Playwright over a built docs site WITH the Pagefind
  index + injection) to validate Ctrl-K -> "prorrata" -> a term card with the
  glossary deep link.
- Fix the two integration defects the browser smoke surfaced (per-language
  injection invisibility; dynamic-import path) so the headline actually works.
- Verify: the browser smoke green, the inject suite green, ruff/format/ty
  clean, docs conformance unaffected, collect-only clean.

## Outcome

### The palette ladder + dedupe

The query path composes the ADR-D5 tiers: (1) TERM CARDS from a Pagefind
search SORTED by the injected `weight` key - this returns ONLY the injected
records (the docs pages carry no weight key, so Pagefind drops them), ordered
by tier weight (concept 1.0 > cli 0.8 > casilla 0.7); (2) NAV titles from the
existing nav/TOC index (unchanged); (3) FULL TEXT from a normal relevance
search plus the "Search the docs for ..." handoff row. `compose()` dedupes by
href across tiers (a hit that is both a card and a page shows once, in its
higher tier) and caps at 18 rows. The palette paints nav+full-text
immediately (never blank) and re-paints with term cards when the async
Pagefind query resolves; a `queryToken` guards against an out-of-order
keystroke.

### Lazy-load + graceful fallback

Pagefind is dynamically imported on first palette open from the site-relative
`pagefind/pagefind.js` (resolved against `document.baseURI` so the specifier
is absolute - a bare/relative one is read as a package name and fails). If the
import fails (a dev preview built without the index pass), `loadPagefind`
resolves to `null` and the palette silently keeps its nav-only behaviour - the
palette never breaks.

### Term-card rendering

A CONCEPT card shows the term title, a "Term" badge with the concept domain,
the matched-description excerpt, and jumps to the glossary anchor deep link
(`glossary.html#term-<concept_id>`). A CASILLA card shows "Casilla · Modelo
<m> · <number>" and its deep link. A CLI card shows "Command · <command_path>"
and the CLI-reference deep link. The kind drives a coloured badge dot
(`aeat-palette-item--concept/casilla/cli`). All integrate with the existing
arrow/enter keyboard navigation.

### BROWSER VALIDATION RESULT (the headline)

DEMONSTRABLY WORKING. Built the full docs site (1776 pages) with the Pagefind
index + the concept injection, served it, and drove it with Playwright
(headless Chromium): Ctrl-K opened the palette, typing "prorrata" produced -
as the top two results, ABOVE the full-text pages - the term cards:

- `prorrata especial` (Term · concepto) -> `/glossary.html#term-prorrata-especial`
- `prorrata` (Term · concepto) -> `/glossary.html#term-prorrata`

followed by the full-text `_prorrata` module pages (third tier). Zero console
errors. Keyboard selection lands on the first card. A screenshot was captured.
This is the goal endpoint, proven in a real browser.

### Two integration defects found and fixed (the browser smoke earned its keep)

1. PER-LANGUAGE INVISIBILITY: S23 injected each record once per language
   section (es/en/ca/hu) into the matching language index. But Pagefind loads
   only the page's language index (the docs build pins `en`), so a concept
   whose Spanish description lived in the `es` index was invisible from an
   English page - the headline returned zero term cards. FIX (in
   `pagefind_inject.py`): inject each record ONCE into the primary (page)
   language with content combining the title and EVERY language's description,
   so the Spanish term, the English gloss, and the ca/hu forms are all
   matchable tokens in the one loaded index. Cross-lingual matching is
   preserved via the combined content rather than via a separately-loaded
   language index.
2. PAGE-RANK BURIAL + the dynamic-import path: a corpus query like "prorrata"
   matches ~1700 page fragments that outrank the one concept record, so a
   plain search buried it past any reasonable result window; and the relative
   import specifier failed to resolve. FIX: the palette uses the weight-sorted
   Pagefind search (returns only the weighted injected records) and resolves
   the import against `document.baseURI`.

### Stock search page

The S22 `docs/_templates/search.html` override already replaces the stock
Sphinx search with the Pagefind UI surface (the palette's full-text tier
hands off there). No conf.py change was needed: `aeat-docs.js` is already in
`html_js_files`, and the search-page template is already in `templates_path`.

### Filters

The injected records carry `kind`/`domain` and `weight`. Pagefind's filter
facet does not populate for custom records (`available_filters` is empty), so
client-side filtering by `meta.kind` is what the palette uses (the
weight-sorted card pass already isolates the injected kinds). A user-facing
kind/domain filter UI is deferred as polish (noted for follow-up).

### Tests + pass

`dev/docs/tests/test_pagefind_inject.py` - 9 green, including a new browser
integration test that drives real Pagefind WASM in headless Chromium and
asserts the weight-sorted search returns ONLY concept cards (no page noise)
with prorrata present - the durable proof of the palette's core mechanism.
S22's index test stays green; docs conformance stays 65 green. ruff/format/ty
clean; collect-only clean.

## Notes

- SCOPE FENCE honoured: S24 wires the palette to QUERY the index and renders
  term cards. The end-to-end prorrata SMOKE GATE is S28.
- DEEP-LINK PATH FLAG for S28: the injected concept target is
  `glossary.html#term-<id>`, but the S26 cutover moved the glossary to
  `_generated/glossary.html`. The card and its anchor render correctly; the
  `glossary.html` vs `_generated/glossary.html` path is in S17's committed
  `to_search_record` projection (not mine to change here). S28's smoke gate
  should confirm the deep link resolves to the built generated glossary, and
  if not, S17's target path needs a one-line update.
- The injection design change (one record per primary language) is in my own
  S23 module; I own that surface. The S23 exec record's per-language-split
  description is superseded by this discoverability fix.
- No PM wave/phase/step tokens in production JS/CSS/Python (ADR ids only here).
- Browser validation note: the headless Chromium binary was installed once
  (`playwright install chromium`) for the smoke; the durable browser test
  guards the mechanism in CI where a browser is available.
- Commit discipline: all verification ran first; staging and the commit are a
  single chained `git add ... ; git commit ...` over ONLY my explicit paths
  (the palette JS/CSS, the injection fix + its test, the exec record).

