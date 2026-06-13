---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S28'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Land the end-to-end smoke gate: the offline prorrata worked example returns the concept card, at least one M303 prorrata casilla record, and the relevant how-to page, plus four-language query checks (ADR D8)

## Scope

- `docs conformance test suite`

Implements ADR D8: the end-to-end prorrata smoke gate - the durable proof of
the whole documentation-search pipeline. Closes W04. First fixes the concept
deep-link path bug flagged in S24, then lands the browser-driven gate.

## Description

- STEP 1: fix the concept deep-link target path (the bug S24 flagged) and
  verify every kind's target resolves to a real built page.
- STEP 2: build the durable end-to-end smoke gate - a browser test that
  builds docs + the Pagefind index + the full injection, serves it, drives
  Pagefind in headless Chromium, and asserts the prorrata concept card +
  M303 casilla card + how-to page + four-language probes, with resolving
  deep links.
- Fix the cross-lingual gap the gate's four-language probe surfaced (term
  aliases were absent from the injected content).
- Verify: the deep-link fix resolves in a built site; the smoke gate green in
  a real browser; S17 resolution + inject tests stay green; ruff/format/ty/
  collect-only clean.

## Outcome

### Step 1 - the deep-link path fix (what was wrong, corrected, resolves)

The CONCEPT card target was `glossary.html#term-<id>`, but the S26 cutover
moved the glossary to `_generated/glossary.html` (the hand-written
`glossary.html` was deleted). So the cards rendered but their deep links would
404. FIXED in S17's projection (`dev/docs/terminology/_unified_record.py`):
added a `GLOSSARY_PAGE = "_generated/glossary.html"` constant and changed the
concept target to `{GLOSSARY_PAGE}#term-{concept_id}`. Verified in a fresh
build: `_generated/glossary.html` is emitted with `id="term-prorrata"` /
`id="term-prorrata-especial"` anchors, so the corrected target resolves (the
gate fetches it and asserts 200 + the anchor). The OTHER kinds were checked and
resolve: CASILLA targets `search.html?q=<modelo>+<number>` (the Pagefind
search-page handoff - search.html exists, so it resolves; casillas have no
rendered page of their own, so a search query is the intended surface); CLI
targets `cli/<family>.html#<anchor>` (the generated CLI reference - `cli/app.html`
builds). The committed relevance file carried one stale `glossary.html#term-
prorrata-especial` target (the sweep used the old projection); it was
mechanically re-pathed to `_generated/glossary.html#term-prorrata-especial` (a
one-line substitution the next re-sweep would also produce). The S17
resolution tests (`test_unified_record`, `test_sweep`, `test_relevance_data`)
were updated to the new path and stay green.

### The cross-lingual gap the gate found and fixed

The four-language probe initially failed on the English "pro rata" - the
injected content was title + descriptions, and the EN description ("the
deductible proportion ...") does not contain "pro rata". The concept's
declared term ALIASES (the EN "pro rata", the ca/hu forms, the unaccented
search variants) were absent from the searchable content. FIX: added a
`search_aliases` field to `SearchRecord`, populated in `to_search_record` from
the concept's every declared term label + hidden search form across all
languages, and folded into the Pagefind injection content. Now any declared
surface form finds the card - the cross-lingual matching the four declared
translations were meant to deliver.

### Step 2 - the smoke gate (what it asserts + that it PASSES)

`dev/docs/tests/test_prorrata_smoke_gate.py` (integration). It builds a
representative docs SUBSET (the generated glossary + a prorrata how-to + an
index) with Sphinx, injects the concept cards AND the M303 prorrata casillas,
runs the Pagefind index pass, serves the built site, and drives it with real
Pagefind WASM in headless Chromium. For "prorrata" it asserts: a CONCEPT card
appears (prorrata / prorrata-especial) AND its deep link is fetched from the
server and returns 200 with the `#term-prorrata` anchor present in
`_generated/glossary.html` (the Step-1 fix proof); at least one M303 prorrata
CASILLA card appears; the prorrata how-to PAGE appears in the full-text tier;
and FOUR-LANGUAGE probes (es "prorrata", en "pro rata", ca "prorrata sectors",
hu "aranyositas") each surface the concept card. It PASSES in a real browser
(17s). This is the end-to-end proof of the whole pipeline: preprocess ->
Handbook -> projections -> inject -> Pagefind -> palette card with a resolving
deep link.

### Scope / CI marking

The gate builds a docs SUBSET (glossary + how-to + index), not the full
1776-page site, so it runs in ~17s rather than minutes while still driving a
real browser and asserting resolving deep links (no mocks). It is
`integration`-marked: it builds docs + the index and runs Playwright, so it
runs in the browser-capable lane, not the default unit lane. The module
docstring documents how to run it.

### What is proven end-to-end vs residual gap

PROVEN end-to-end, in a real browser: a query surfaces the concept term card
(weight-sorted above full text), the casilla card, and the how-to page, and the
concept's deep link RESOLVES (200 + anchor) to the built generated glossary -
across four languages. RESIDUAL: the gate uses the same Pagefind query path the
palette's `searchPagefind()` runs (the basic-theme subset has no palette
trigger to keystroke), so the palette's keystroke-to-render wiring is proven by
the S24 browser smoke (full Furo theme) rather than re-driven here; the two
together cover the keystroke and the retrieval. The casilla deep-link is a
search-page handoff (`search.html?q=`) rather than a per-casilla page, which is
the intended design (casillas have no rendered page); a future enhancement
could deep-link to a registry/Diseno surface.

## Notes

- W04 IS COMPLETE with this Step: the feature is functionally done (the Ctrl-K
  palette delivers semantic term-card search with resolving deep links) and
  gated (the end-to-end smoke gate). Remaining: S21 (synonym mining infra) and
  W05 (ratchet, miss-rate, self-hosting vocab, honesty review + codify), plus
  the relevance-data refresh once the RAG service recovers.
- PEER-WIP discipline: the working tree carries peer changes to
  `dev/docs/build.py`, `cli_reference.py`, `apidocs/cli.py`, `serve.py`,
  `preprocess/_pdf.py`, `preprocess/_workbook.py`, and
  `tests/test_cli_reference_drift.py` that I did NOT touch or stage; only the
  files I actually changed are staged.
- The `search_aliases` addition and the concept-target fix are in S17's
  committed `_unified_record.py` (the shared projection); the change is
  behaviour-additive (a new defaulted field; the corrected target) and every
  consumer test was updated and stays green.
- No PM wave/phase/step tokens in production code (ADR ids only here). The two
  ty suppressions and the one S310 noqa in the smoke gate are justified inline
  (dynamic pagefind index; the loopback test-server fetch).
- Commit discipline: all verification ran first; staging and the commit are a
  single chained `git add ... ; git commit ...` over ONLY my explicit paths
  (the projection fix + alias field, the injection content, the relevance
  re-path, the updated resolution tests, the new smoke gate, the exec record).

