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

### PERF-006 | RESIDUAL | Legal-grounding coverage is bounded by catalogue enrolment

Only 7 of 40 approved concepts carry resolvable legal grounding. Many that
should (modelo-303 cites LIVA arts. 164/167) cannot be linked because the
binding provision is not enrolled in the legal catalogue. Adding it is a
legal-authority workstream governed by `registry-calculation-legal-grounding`,
not a search-surface change; fabricating a near-miss `legal_ref` is forbidden.

## Recommendations

- Land PERF-005 (untrack `pagefind/`) on owner approval; it is the single
  largest corpus/repo performance item.
- Grow legal-grounding cross-links by enrolling the binding provisions in the
  legal catalogue (separate workstream), then the glossary renders them for
  free.
- Add a durable Playwright palette test (the scratch battery used here) so the
  PERF-003 ranking and the draft-free invariant cannot regress; the existing
  smoke gate exercises the index/injection but not the palette compose ladder.

## Codification candidates

No new codification candidates. The constraints exercised are covered by the
existing rules (`shipped-search-licence-clean`, `terminology-single-declaration`,
`terminology-scaffold-preserve-contract`); the fixes are feature-specific.
