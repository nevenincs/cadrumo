---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - '[[2026-06-10-docs-terminology-search-adr]]'
  - '[[2026-06-10-docs-terminology-search-plan]]'
  - '[[2026-06-14-docs-terminology-search-audit]]'
---

# `docs-terminology-search` audit: `search corpus performance and result-quality drive`

## Scope

A driving pass over the SHIPPED search experience, not the test surface: compile
the corpus, exercise it with real operator queries against the live Pagefind
WASM in a headless browser, and audit performance, coverage, draft pollution,
deep-link resolution, ranking, and documentation cross-linking. Findings are
acted on in the same pass.

## Findings

### PERF-001 | FIXED | Draft concepts shipped as placeholder dead-link cards

The Handbook carries 115 concepts but only 40 are approved; the other 75 are
scaffold-empty drafts (`(sin curar) draft pendiente de definicion`, empty
English). The Pagefind injector and the sweep resolver shipped all 115 as
first-class cards, so 65 % of concept search results were placeholder cards
whose `_generated/glossary.html#term-<id>` deep link 404s (the glossary is
approved-only), and 8 draft targets had leaked into the committed relevance
sweep. Both consumers now surface APPROVED concepts only; the re-swept
`relevance.json` carries zero draft leaks. A live 14-query battery confirms no
draft card appears in any result.

### PERF-002 | FIXED | Concept relations were invisible (no cross-linking)

The Handbook declares SKOS `broader`/`related` relations, but they rode only on
search-record metadata and were rendered nowhere. The generated glossary now
renders them as `:term:` cross-references (approved targets only, so the
`-n -W` build stays green -- validated by the throwaway-Sphinx-build gate),
turning the glossary into a navigable concept graph. High-traffic modelo and
core navigation concepts (modelo-303/390/100/130, casilla, autoliquidacion,
declaracion, iva, recargo-equivalencia) gained curated `related` cross-links to
existing approved concepts. The page now renders 35 relation cross-reference
lines and 9 legal-grounding links; the loader confirms every relation target
resolves.

### PERF-003 | FIXED | Exact-term concept did not rank first

Every injected concept card carries the flat tier-one weight (1.0), so the
palette's weight-sorted card pass tied all concepts and returned them in
Pagefind's internal (non-relevance) order. The live battery exposed the
consequence: `iva` surfaced VIES first with the IVA concept off the visible
head; `casilla` led with "proyeccion de busqueda"; `borrador` with "verificado
completo". The palette now carries each result's relevance rank from the
relevance pass and breaks within-tier ties by it -- the tier still keeps cards
above full-text pages, but the best textual match leads its tier. Re-running the
battery: `iva`->IVA, `casilla`->casilla, `borrador`->borrador,
`autoliquidacion`->autoliquidacion, `irpf`->IRPF, `modelo 303`->modelo 303 all
now return the exact-match concept as the top card. Cross-lingual matching holds
(`aranyositas` -> prorrata especial; `pro rata` -> prorrata).

### PERF-004 | VERIFIED | Deep links resolve; tiering correct

Every concept card target resolves to a real `_generated/glossary.html#term-<id>`
anchor in the built site. CLI cards deep-link to `cli/*.html#<command>` anchors;
casilla cards hand off to the search page. The tier order holds: a concept card
outranks CLI commands outranks casilla namespaces outranks full-text pages
(`censo` returns the concept card first, then the `aeat config profile censo *`
commands).

### PERF-005 | RESIDUAL (owner decision) | A 63 MB compiled index is committed to git

`pagefind/` at the repository root is tracked: 16,339 files, ~63 MB, NOT
gitignored. This is a compiled Pagefind index -- exactly the uncommitted,
regenerated-every-build artifact ADR D5 specifies (the `docs/_build/html/pagefind`
copy IS correctly gitignored). It was committed by a peer campaign
(`f57a1bcf6`), is stale relative to the current corpus, and bloats every clone.
The fix is `.gitignore += pagefind/` plus `git rm -r --cached pagefind/`
(non-destructive to the working tree). Deferred to an owner decision because it
untracks 16k peer-committed files.

### PERF-006 | FIXED | Tax-concept legal-grounding coverage driven to 100%

Only 7 of 40 approved concepts carried resolvable legal grounding. The binding
framework articles for the rest were not enrolled in the legal catalogue. Thirteen
provisions were enrolled in a dedicated `tax-framework.toml`
(separate from the calculation legal files a peer campaign is actively editing):
LIVA arts 1/148/164, LIRPF arts 1/96/98, LGT arts 5/98/99/213, RGAT arts 3/18,
Ley 39/2015 art 38. Each carries the verified BOE permalink; the three whose
verbatim text was fetched ship a corpus excerpt + a `required_text` the strict
corpus gate verifies, the rest use the supported staged-annotation state. Legal_refs
were added to 19 concept fragments; the loader confirms every ref resolves and all
13 entries pass `corpus_strict`. Result: glossary legal-basis links 9 -> 28, with
26/26 TAX concepts grounded. The 14 still-ungrounded approved concepts are
search/calc INFRASTRUCTURE terms (barrido-rag, proyeccion-busqueda, mapa-relevancia,
work-unit, ledger, ...) with no AEAT legal basis -- correctly left ungrounded, never
fabricated.

### PERF-007 | FIXED | The palette ranking + draft-free invariants are now gated

The PERF-003 ranking fix lacked a test (the prior smoke gate exercises
`pf.search`, not the compose ladder). A durable Playwright gate
(`test_palette_ranking.py`) now drives the SHIPPED palette: it opens Ctrl-K,
types "iva", and asserts the IVA concept is the first row, ahead of VIES. Driving
the real palette exposed that the relevance-only tiebreak was fragile over a thin
corpus, so a deterministic title-match signal (exact > prefix > substring) was
added as the primary within-tier key, with relevance as the cross-lingual
fallback.

### NOTE | Terminology module relocation absorbed

Mid-campaign a peer relocated the `src/aeat/terminology` Python module to
`dev/docs/terminology_handbook` (production-code vs documentation-tooling boundary).
The docs-search consumers this campaign owns were swept to the new import path and
re-verified; the data fragments under `src/aeat/_data/terminology/` are unaffected.

## Recommendations

All three residuals from the first pass are now closed: PERF-005 (`pagefind/`
untracked + gitignored), PERF-006 (tax-concept legal grounding to 100%), and
PERF-007 (durable Playwright palette gate). Remaining follow-ups, lower priority:

- Ingest the corpus excerpts for the 10 staged legal provisions
  (`required_text` pending) so they graduate from permalink-only to
  corpus-verified grounding, matching the calculation legal catalogue.
- Consider demoting the 14 search/calc INFRASTRUCTURE concepts (barrido-rag,
  proyeccion-busqueda, work-unit, ...) out of the taxpayer-facing glossary: they
  document the system, not AEAT surfaces, and a taxpayer would never look them
  up. This is a curation decision, not a grounding gap.

## Codification candidates

The two lower-priority follow-ups below were promoted to project rules during the
follow-up plan: `glossary-concepts-are-taxpayer-facing` (new) and the
committed-light-data-not-heavy-index boundary folded into
`shipped-search-licence-clean`. The other existing rules
(`terminology-single-declaration`, `terminology-scaffold-preserve-contract`)
remain unchanged.

## Follow-up plan closure

The two follow-ups recommended above were actioned to completion under the
`2026-06-15-docs-terminology-search` plan (L2, 28/28 steps closed), backed by the
`2026-06-15-docs-terminology-search` ADR (D1-D3). Per-phase verification evidence:

- **Legal grounding (P01).** The 10 staged provisions were graduated from
  permalink-only to corpus-verified: verbatim BOE text fetched via the Open Data
  API, corpus excerpts written, `required_text` added. Fetching surfaced a real
  grounding error - the sede electronica article is Ley 40/2015 art. 38, not Ley
  39/2015 art. 38 - which was corrected (entry, corpus, and the
  `sede-electronica` concept ref). All 13 `tax-framework.toml` entries pass the
  strict corpus gate.
- **Glossary cleanup (P02).** The 11 internal-machinery concepts were demoted to
  `deprecated` with internal-marker scope_notes; approved concepts dropped 40 ->
  29 and the glossary excludes all 11. The S31 self-hosted-vocabulary test was
  updated to assert the deprecated, non-glossary-facing state.
- **Artefact boundary (P03).** `pagefind/` is gitignored and untracked (0 tracked
  files); the light `relevance.json` plus the Handbook fragments stay committed.
- **Codify + verify (P04).** Both rules authored and synced to the provider
  dirs. The sweep's `enumerate_query_vocabulary` now enumerates approved concepts
  only; the committed `relevance.json` was rederived from the failed=0 approved-era
  sweep by excluding the deprecated concepts (no degraded re-retrieval), leaving
  72 queries / 29 concepts / failed=0. The relevance-drift, miss-rate,
  concept-cards, sweep, glossary, and pagefind gates are green.
