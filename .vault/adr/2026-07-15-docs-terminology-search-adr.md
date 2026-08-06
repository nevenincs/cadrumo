---
tags:
  - '#adr'
  - '#docs-terminology-search'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:7038f7eec4ee9efd7d4fef9b4b7d92d2b314842d89c5b69f3eb3232d081e55d4'
related:
  - '[[2026-06-10-docs-terminology-search-adr]]'
  - '[[2026-06-15-docs-terminology-search-adr]]'
  - '[[2026-06-15-docs-terminology-search-audit]]'
---

# `docs-terminology-search` adr: `precompiled search-result contract: destinations and representation` | (**status:** `accepted`)

## Problem Statement

Three of the four shipped search-record kinds deep-link to destinations that
do not exist, and no gate can see it. The unified search index injects four
record kinds (`SearchRecordKind`: CONCEPT, CASILLA, CLI, PAGE) whose `target`
is the URL a palette card jumps to. Audited against the built site:

- **CONCEPT** targets `_generated/glossary.html#term-<anchor>` and resolves --
  the one healthy kind, because PERF-001 gave it a shared anchor derivation
  plus a lock-step parity gate (`test_glossary_anchor_parity.py`).
- **CLI** targets were built from a stale structural assumption: the target
  builder hardcoded `cli/<family>.html#<anchor>` while the CLI reference had
  been restructured into per-GROUP pages (`cli/app/ledger.html`, ...). The
  family landing pages carry ZERO command anchors, so the overwhelming
  majority of the 323 command records landed on a generic landing page with a
  dead fragment; only the ~9 `config` direct-child leaves happened to resolve.
  Option records reuse their command's target verbatim and inherited the
  break. (A repoint through the renderer's own routing authority is landing
  as in-flight peer work at HEAD; this ADR ratifies its contract.)
- **CASILLA** targets were never a destination at all:
  `search.html?q=<modelo>+<casilla_id>` is a search-for-itself hand-off -- a
  closed loop whose top hit is the card the operator just clicked. Until the
  recent `?q=` fix the loop was also broken outright (the search page ignored
  the parameter).
- **PAGE** records carry Pagefind's own full-text URLs and are fine.

The through-line is architectural, not per-kind: **nothing verifies that a
shipped record's target resolves to a real page and a real anchor in the
built site.** The nitpicky `-n -W` Sphinx gate validates Sphinx's OWN
cross-references but is blind to injected record targets -- that asymmetry is
the hole. Each kind broke invisibly for a different reason (a stale docstring
assumption, a punt to a search page, a draft-404 class already fixed once),
which is exactly why per-kind spot fixes keep recurring.

The operator widened the defect further: the search PAGE itself was never a
working surface. `docs/_templates/search.html` is a stock `PagefindUI` drop
with its own ranking and rendering -- a second, divergent search
implementation beside the Ctrl-K palette that actually implements the D5 tier
ladder, the PERF-003 relevance tie-break, and result dedupe. The stock page
was not merely unpolished: its `bundlePath` rendered to a bare module
specifier the browser refuses to resolve, so full-text search on the page
returned zero results for every reader (fixed at HEAD, commit `f4891c78`).
Two search implementations, where the good one is modal-only and the broken
one owned the URL, is the architectural defect behind the operator's "the
search page has never been worked on".

The defect has a second half beyond the deep link: the RESULT-ITEM
REPRESENTATION. Every record kind is a precompiled element derived from our
own schema and bundled corpus data -- registry casilla definitions with
`legal_refs`/`source_refs`, Handbook concepts with legal-catalogue grounding
that resolves to BOE permalinks and corpus anchors, the introspected CLI
tree. That provenance is projected into `SearchRecordMetadata`, then DROPPED
at the injection seam: `_meta_for` (`dev/docs/pagefind_inject.py`) ships only
`kind`/`tier`/`title`/`summary`/`weight` plus bare identity fields, and the
palette card (`cardFromPagefind`) renders only title, crumb, summary, and one
href. The parent ADR promised "every result linked to its legal grounding";
no shipped surface can render that link, because the data never reaches the
index. A result is therefore not tied to anything the reader can look at:
the card shows a label, and (for three kinds) even its one link was dead.

This ADR supersedes the prior audit's PERF-004 acceptance ("casilla cards
hand off to the search page -- VERIFIED"): a search hand-off is a fallback
contract, not a destination.

## Considerations

- **Verified state at HEAD (fast-moving; peers are landing fixes).** The
  `?q=` hand-off contract works (`search.html` reads
  `URLSearchParams(...).get('q')`, gated behaviourally by
  `test_search_page_query_param.py`, deliberately written
  surface-independent); the page's dead `bundlePath` is fixed; the palette
  loading state landed. The CLI target repoint through
  `cli_reference_page_for_command` (the routing authority the CLI-reference
  generator itself renders against) is implemented in working-tree peer WIP,
  with its parity gate in flight. The casilla destination and the
  kind-agnostic gate do not exist.
- **The projected casilla corpus is 6,330 records, not 15,745.** The registry
  declares 15,745 casilla rows across revisions;
  `project_casilla_search_records` collapses each `(modelo, casilla_id)` to
  the latest revision: 6,330 deduplicated records across 73 modelos
  (established by running the projection at HEAD; 3,381 carry a non-Spanish
  label). Heavily skewed: Modelo 200 has 3,250, Modelo 100 has 2,258 --
  together 87 % -- median modelo 5. A casilla record carries the official
  label, localised labels, `number`, `segmento`, `section` path,
  `semantic_role`, `legal_refs`/`source_refs`, `source_revisions`: a
  reference table row -- more than an anchor, less than a page.
- **Resolvability alone would not have caught the casilla punt.**
  `search.html?q=...` resolves as a page; the defect is that a query-string
  hand-off is not a destination. The contract must therefore constrain target
  SHAPE (page + optional fragment, no query strings), not just existence.
  Symmetrically, the `bundlePath` break was a runtime browser error no
  Python/Sphinx gate can see -- that class belongs to the behavioural
  (Playwright) gates, not to static resolvability.
- **The second-order lesson from the CLI break:** the target builder
  duplicated a structural fact (which page renders a command) that the
  renderer owned; when the renderer restructured, the duplicate silently
  rotted. Destination routing must be DERIVED from the renderer's own
  authority, never re-hardcoded -- the docs-side instance of the
  one-aggregation-path discipline.
- **The committed light data pins target shapes.** The laundered
  `relevance.json` carries exactly 28 casilla targets in the
  `search.html?q=` form (zero CLI targets, so the CLI repoint strands no
  committed data). The target-resolution gate
  (`dev/docs/terminology/tests/test_relevance_data.py`) validates the current
  query-string pattern and must move with the contract.
- **Palette-vs-page convergence surface.** The palette (`initPalette`,
  `docs/_static/cadrumo-docs.js`, ~460 lines of the 1,256-line file) builds a
  `<dialog>` and calls `showModal()`; its search core (Pagefind loading,
  card/page search, the compose ladder, painting, keyboard selection) is
  closure-scoped to three inner nodes (`input`, `list`, `status`) plus the
  dialog for busy-state classes. The genuinely modal-specific code (dialog
  construction, `showModal`/close/backdrop/Esc, trigger buttons, global
  keydown) is roughly 50-80 lines; the rest is shell-agnostic once the node
  references are parameterised.
- **Rule reconciliation.** Casillas are an explicitly taxpayer-facing concept
  class under `glossary-concepts-are-taxpayer-facing`; a casilla reference
  page is a projected surface that never enrolls in the Handbook (parent ADR
  D4: projected, never curated), so `terminology-single-declaration` is not
  breached. Generated pages under `docs/_generated/` are uncommitted build
  outputs (`shipped-search-licence-clean`); `aeat-docs-scaffolding-cli`
  governs the apidocs stubs, not builder-inited pages.
  `aeat-calculation-grounding` is strengthened: casilla pages become an
  operator-facing surface for `legal_refs`/`source_refs`. Retiring the stock
  PagefindUI page keeps one implementation per responsibility
  (`no-legacy-compatibility`: delete the divergent surface, no bridge).
- **Where grounding can render.** The bundled normatives corpus is not
  shipped as docs pages; corpus-derived grounding reaches a reader only
  through the legal catalogue's BOE permalinks. The generated glossary
  already renders "Legal basis" permalink lines per entry; the CLI reference
  renders each command's options; casillas have no destination yet (D3
  creates one). So every kind either has, or gains under this ADR, a
  DESTINATION surface capable of rendering its full provenance -- the
  question is whether grounding renders on the card, the destination, or
  both.
- **Revision collapse.** A casilla's meaning changes across revisions; the
  projection already resolves this (latest revision authoritative,
  `source_revisions` audits the collapse). The destination page must render
  from the same projection or card text and landing text drift.

## Considered options

Per axis, at the same level of abstraction.

**Axis 1 -- the target contract and its gate:**

- **O1a -- Universal destination contract + two-layer gating** (per-kind
  renderer-derived parity gates, plus one kind-agnostic built-site sweep).
  **Chosen.**
- **O1b -- Per-kind parity gates only** (generalise
  `test_glossary_anchor_parity.py` kind by kind, no built-site sweep).
  Rejected as sufficient-looking but leaky: a parity gate validates the
  producer against the renderer's RST-level inventory; it cannot catch
  Sphinx-slug drift, template restructures, or a page dropped from the
  toctree -- the CLI break was precisely a restructure that one generator's
  RST-level view could not see.
- **O1c -- Built-site sweep only.** Rejected as sole layer: it runs against a
  full docs build (slow, integration-lane) and localises failures poorly; the
  fast per-kind gates are what a coder runs in the loop.
- **O1d -- Extend the `-n -W` gate.** Rejected: injected records are not
  Sphinx references; there is no Sphinx seam where they exist. The sweep gate
  is the `-n -W` ANALOGUE for the injection seam, not an extension of it.

**Axis 2 -- CLI targets:**

- **O2a -- Route the target through `cli_reference_page_for_command`, the
  renderer's own routing authority.** Chosen; ratifies the in-flight peer
  implementation. Option records keep their owning command's anchor --
  coarse but real; per-option anchors would require the renderer to emit
  1,000+ additional ids for marginal navigation value. Accepted coarseness,
  revisitable.
- **O2b -- Re-hardcode the group map in the projection.** Rejected: exactly
  the duplication that broke.

**Axis 3 -- casilla destination:**

- **O3a -- Per-modelo generated casilla reference pages with per-casilla
  anchors** (73 pages under `docs/_generated/casillas/`, target
  `_generated/casillas/<modelo>.html#casilla-<slug>`). Mirrors the glossary
  precedent (typed authority -> builder-inited page -> parity gate).
  **Chosen.**
- **O3b -- Per-casilla pages** (~6,330). Rejected: a casilla is a table row,
  not a page; ~6,330 near-empty pages would roughly quadruple the Sphinx page
  count for no informational gain over an anchor on a shared page.
- **O3c -- Keep the (now working) search hand-off.** Rejected as end state:
  a self-referential destination rendering none of the card's provenance;
  also violates the new target-shape contract (no query-string targets).
- **O3d -- Drop casilla cards.** Rejected: parent ADR D4/D5 make casillas a
  first-class navigation namespace; the 6,330 records are what answers
  "which casillas does prorrata touch". The defect is the destination, not
  the card.

**Axis 4 -- the search page:**

- **O4a -- The search page becomes a palette-hosted inline surface**: extract
  the palette's search controller from its modal shell and mount it inline on
  `search.html`, reading `?q=`; retire the stock PagefindUI drop. **Chosen.**
- **O4b -- Keep two implementations, polish PagefindUI toward the ladder.**
  Rejected: duplicates the compose ladder, tie-break, and dedupe in a second
  codebase that has already proven unowned (it shipped dead); a permanent
  drift surface.
- **O4c -- Redirect `search.html` to open the modal palette over the
  referring page.** Rejected: a URL-addressable, shareable search surface is
  the point of a search PAGE; a modal cannot be deep-linked into and leaves
  the page beneath it arbitrary.

**Axis 5 -- result-item representation:**

- **O5a -- Lean card, grounded destination.** The card renders identity
  (title, kind crumb, one-line summary) and its resolvable target; the FULL
  provenance (legal_refs as BOE permalinks, source_refs, segmento, revision
  history, options) renders at the destination the target points to.
  **Chosen.** Requires the destination-grounding assertion in the per-kind
  parity gates (the destination MUST render the provenance the record
  carries), and a small meta widening only where the crumb needs it.
- **O5b -- Fat card: ship grounding in the Pagefind meta and render
  legal-basis links on every result row.** Rejected: duplicates the
  destination's rendering responsibility into a second surface (the exact
  divergence class Axis 4 retires), bloats the index meta for 6,330+
  records, and a result list is the wrong reading surface for provenance --
  the reader needs it when they LAND, not while scanning.
- **O5c -- Status quo (drop metadata at the injection seam, no destination
  requirement).** Rejected: this is the defect -- the parent ADR's
  "every result linked to its legal grounding" stays unimplementable.

**Axis 6 -- result differentiation and ordering (operator directive):**

- **O6a -- Closed display-class taxonomy in the injected meta + one declared
  weight table.** Chosen: the class is derived once in Python where the
  typed record is available, shipped as data, rendered by the one shared
  controller; ranking stays a single auditable table.
- **O6b -- Derive the class in the JS renderer from URL/metadata
  heuristics.** Rejected: re-derivation in a second language from partial
  data is the hardcoded-structural-assumption failure mode again (the CLI
  break), and it drifts the moment a path convention changes.
- **O6c -- Re-rank in the JS compose pass with hardcoded per-kind bumps.**
  Rejected: ranking policy would then live in two places (Python weight
  table + JS bumps); the compose ladder already consumes the shipped weight,
  so policy belongs in the one table.

## Constraints

- **Gate honesty limits.** Static resolvability (page exists, fragment id
  present) is necessary, not sufficient: it cannot see runtime browser
  failures (the `bundlePath` class -- owned by the behavioural Playwright
  gates) and it would pass a query-string punt (owned by the target-shape
  ban). All three layers are needed; none subsumes another.
- **Sphinx `-n -W` stays green.** Every generated casilla page joins a
  toctree; every emitted anchor is unique per page. Casilla ids carry
  characters HTML ids cannot (`DP200014:00562`, `decl.ejercicio`,
  `contraparte.clave-operacion`), so an explicit shared slug function is
  required and a post-slug collision within a page is a build failure, never
  a silent merge.
- **Committed-data sweep.** The 28 casilla targets in the committed
  `relevance.json` are rewritten mechanically from each record's
  `(modelo, casilla_id)` metadata in the same commit as the target change --
  no GPU re-sweep (precedent: the deprecated-concept rederivation).
- **Docs build weight.** 73 additional generated pages, two large (~3,250
  and ~2,258 entries). The generated casilla pages are excluded from the
  Pagefind full-text pass -- the 6,330 injected custom records already cover
  casilla search; indexing the pages would duplicate every record.
- **Modal-extraction cost (honest estimate).** `initPalette` is ~460 lines;
  the extraction parameterises the search controller on a host node set and
  leaves the dialog shell as one of two hosts. Roughly 50-80 lines are
  modal-specific; the risk is closure-variable untangling (busy-state classes
  toggle on the dialog, `endBusy` writes the status node, `open()` seeds
  render). Estimate: 1-2 focused coder-days including re-pointing the
  behavioural `?q=` gate at the new host and re-running the Playwright
  palette-ranking gate; the `?q=` gate is written surface-independent and
  should survive with selector updates only.
- **Parent-feature stability.** The projection compilers, the unified-record
  funnel, the builder-inited generation seam, the Pagefind injection, and the
  palette compose ladder are landed and stable. The CLI repoint and its
  parity gate are in-flight peer work this ADR ratifies, not re-assigns.

## Implementation

Eight rulings, D1-D8.

**D1 -- The destination contract.** Every shipped search record's `target` is
a site-relative page path plus an optional fragment
(`<page>.html[#<anchor>]`). A query-string hand-off is forbidden as a record
target (search is where a reader comes FROM, not where a card sends them).
The page and anchor MUST be derived from the same authority that renders the
destination -- the generator's routing/slug functions -- never re-hardcoded
in a projection. Every record kind names its destination-owning renderer:
CONCEPT -> the glossary generator; CLI -> the CLI-reference generator's
`cli_reference_page_for_command` + heading slug; CASILLA -> the casilla
reference generator (D3); PAGE -> the built page itself.

**D2 -- Two-layer target-resolvability gating.**
(i) *Per-kind parity gates*, the `test_glossary_anchor_parity.py` shape
generalised: each destination-owning generator exposes its anchor inventory
at the RST/render level, and a fast gate proves every projected record's
target is in it (CLI gate in flight as peer work; casilla gate lands with
D3). (ii) *A kind-agnostic built-site sweep* in `dev/docs/tests/`: walk the
unified projection (all kinds), assert each target's page exists under the
built `docs/_build/html/` tree and, where a fragment is present, that an
element with that id exists on the page; assert zero query-string targets.
It reuses the built tree the docs-build gate already produces
(integration-lane, like `test_pagefind_index.py`). This is the `-n -W`
analogue for the injection seam -- the single gate whose absence let all
three breaks ship. The `relevance.json` target-resolution gate's casilla
pattern moves to the D3 form (page+anchor membership, not query-string
shape).

**D3 -- Casilla destination: per-modelo generated reference pages.** A new
`dev/docs/casilla_reference.py` (sibling of `glossary_reference.py`) calls
`project_casilla_search_records()` -- the same projection the search records
use, so page and card cannot disagree on revision collapse or labels --
groups by modelo, and renders one RST page per modelo plus
`_generated/casillas/index.rst` (toctree; one toctree line added to
`docs/index.md`, the glossary's one-time edit). Each casilla renders an
explicit RST label target then its entry: number + Spanish label heading,
localised labels, segmento, section path, semantic role, `legal_refs` as BOE
permalinks where the legal catalogue resolves them (reuse the
`_legal_permalinks` read), `source_refs`, `source_revisions` latest-first.
Entries group by registry `section` path so M200/M100 stay navigable. Wired
as `_generate_casilla_reference` in `docs/conf.py` beside
`_generate_glossary_reference`. One shared slug function
`casilla_page_anchor(modelo, casilla_id)` (beside `_glossary_anchor.py`)
feeds both the generator and `_from_casilla`, which retargets to
`_generated/casillas/<modelo>.html#casilla-<slug>`. The `search.html?q=`
form disappears from casilla records entirely (no dual-target bridge).

**D4 -- CLI targets route through the renderer's routing authority.**
Ratifies the in-flight peer implementation: `_command_target` resolves its
page through `cli_reference_page_for_command`, exported by
`dev/docs/cli_reference.py` as the single routing authority both the page
generator and the projection consume. Option records keep the owning
command's anchor (accepted coarseness; a per-option anchor scheme is a
revisitable follow-up, not part of this ruling).

**D5 -- The search page becomes the palette-hosted search surface.** The
palette's search controller (Pagefind loading, card+page search, the D5
compose ladder, tie-break, dedupe, painting, keyboard selection) is
extracted from the modal shell into a host-parameterised controller in
`cadrumo-docs.js`; the Ctrl-K `<dialog>` and an inline mount on
`search.html` become its two hosts. The inline host reads `?q=`, seeds the
input, renders the same tiered results, and updates the URL as the query
changes (shareable searches). The stock `PagefindUI` drop -- CSS, UI bundle
reference, and its divergent ranking -- is retired from `search.html` in the
same change. The palette's own full-search escape row keeps targeting
`search.html?q=...` (a NAVIGATION surface, not a record target; the D1 ban
governs injected record targets, not the palette's own hand-off row). The
peer's behavioural `?q=` gate re-points at the inline host; the Playwright
palette-ranking gate is unaffected.

**D6 -- The result-item representation contract.** A shipped result item is
a lean pointer: identity (title, kind/tier crumb, clean one-line summary)
plus its D1-conformant target. The record's full provenance -- `legal_refs`
resolved to BOE permalinks, `source_refs`, `segmento`, `source_revisions`,
command options -- MUST render at the target's destination, at parity with
what the record carries: the glossary entry's legal-basis lines (already
live), the casilla page entry (D3 renders the full provenance block), the
CLI reference command section. The per-kind parity gates therefore assert
destination-grounding coverage, not just anchor existence: a record carrying
`legal_refs` whose destination entry renders none of them is a gate failure.
The injected Pagefind meta widens only where the card's crumb needs it
(casilla records add `segmento` beside the existing `modelo`/`number`);
grounding data itself stays out of the index meta. This implements, and
makes gateable, the parent ADR's until-now-unimplemented "every result
linked to its legal grounding".

**D7 -- Result display-class taxonomy and iconography.** Every shipped
result item carries a `display_class` from a closed set, derived
deterministically at the injection seam (one derivation authority, shipped
in the Pagefind meta -- the JS renderer never re-derives it heuristically):
`casilla` (box icon; CASILLA records), `modelo` (document icon; CONCEPT
records whose Handbook domain is `modelo`), `cli` (terminal icon; CLI
records and full-text hits under `cli/`), `technical` (code icon; full-text
hits under `api/` and any dev-machinery surface), and `doc` (question-mark
icon; user-documentation pages and general-fact concept cards). The shared
search controller (D5) renders one inline-SVG icon plus a class-scoped style
per display class -- hand-authored SVG, no icon-font or external icon-set
dependency (`shipped-search-licence-clean`). A record that maps to no class,
or a class with no icon, is a unit-gate failure.

**D8 -- User-first ranking ladder.** The base-weight table moves from
per-kind to per-display-class, declared as ONE data table at the injection
seam: general-fact concept cards, then `modelo`, then `casilla`, then `cli`,
then user-documentation pages, then `technical` pages last. This amends the
parent ADR's D5 ladder in two ways only: within the navigation tier the
order becomes modelo > casilla > cli (previously cli > casilla), and the
full-text tier splits so `technical` (api/dev) pages rank strictly below
user-documentation pages. Term-cards-first and the PERF-003 within-tier
tie-break (exact > prefix > substring, relevance fallback) are retained
unchanged. The Playwright palette-ranking gate gains assertions for the two
new orderings (casilla above cli on a mixed query; how-to page above api
stub on a mixed query).

## Rationale

- **Why a contract + gate rather than three spot fixes:** each kind broke
  invisibly for a different reason; only the missing invariant is common.
  Stating the contract (D1) and gating it kind-agnostically (D2) is what
  makes the NEXT restructure -- of any destination surface -- a loud CI
  failure instead of 300 silently dead cards. The glossary kind proves the
  pattern: it is the one kind that never re-broke, and it is the one kind
  that had a parity gate.
- **Why derivation from the renderer's authority:** the CLI break was a
  duplicated structural fact rotting out of sync -- the docs-side instance
  of the one-aggregation-path discipline. Routing through
  `cli_reference_page_for_command` (and the casilla generator's own slug
  function) makes producer/renderer divergence structurally impossible.
- **Why per-modelo casilla pages:** the corpus statistics decide it (median
  modelo 5 casillas; a casilla is a reference row). 73 pages with 6,330
  anchors gives every record a rendered home at ~1 % of the page cost of
  per-casilla pages, and the destination renders what the card cannot: the
  full provenance chain (`aeat-calculation-grounding` reaching one more
  operator-facing surface) and the neighbouring casillas of the same modelo
  section -- how an operator actually reads a modelo.
- **Why display classes as shipped data with one weight table:** the
  operator's need is visual scanability (box vs document vs command vs code
  vs question mark) and user-first ordering; both are POLICY, and policy
  that lives in two implementations or two languages is what this ADR
  exists to eliminate. One derivation, one table, one renderer.
- **Why lean cards and grounded destinations:** provenance is read at the
  destination, not scanned in a result list; rendering it twice re-creates
  the two-implementations drift Axis 4 retires. Making destination-grounding
  a gated parity property is what converts the parent ADR's promise from
  prose into CI.
- **Why palette-hosts-the-page rather than page-grows-its-own:** the palette
  already implements everything the prior ADR and PERF-003 decided (tier
  ladder, tie-break, dedupe); the page's independent implementation shipped
  broken and stayed broken because nothing owned it. One controller, two
  hosts eliminates the divergence class; the extraction cost is bounded and
  small against maintaining a second ranking implementation forever.

## Consequences

- All four record kinds gain verified destinations; the palette becomes
  trustworthy end to end, and the search page inherits the palette's ranking
  quality while becoming URL-addressable. PERF-004's acceptance of the
  casilla search hand-off is superseded.
- The docs build grows by 73 generated pages, two large (M200 ~3,250, M100
  ~2,258 entries): seconds-scale Sphinx time and ~1-2 MB of built HTML on the
  two big pages, mitigated by section grouping and Pagefind full-text
  exclusion (index size stays flat).
- The built-site sweep gate adds an integration-lane test tied to the docs
  build artefact; it will fail loudly on any future destination restructure
  until the restructuring change also updates the routing authority --
  that is its purpose, and it is the cost of never re-living this defect.
- The committed `relevance.json` diff (28 target rewrites) is one-time and
  mechanically derived. Casilla reference quality in en/ca/hu stays bounded
  by registry locale coverage (3,381 of 6,330 records localised) -- registry
  locale work, outside this feature.
- The controller extraction touches the shipped palette JS: a regression
  there degrades BOTH search surfaces at once. Compensating controls: the
  Playwright palette-ranking gate and the behavioural `?q=` gate both drive
  the real shipped surfaces.
- Destination pages become the provenance surface of record: the casilla
  pages (D3) and the existing glossary/CLI pages carry the grounding the
  cards deliberately do not. A destination redesign now has a gate telling
  it what it must keep rendering.
- Result rows become visually self-classifying (box / document / terminal /
  code / question mark), and dev-technical hits stop outranking taxpayer
  documentation. Cost: the ranking change invalidates memorised result
  orders and the palette-ranking gate expectations; both updated in the same
  change.
- Pathways opened: a per-option CLI anchor scheme (D4 follow-up), a
  revision-history rendering on the casilla pages (the projection's
  `source_revisions` is already on the page), and retiring the palette's
  duplicated nav-index fallback into the unified controller.

## Implementation sequencing (for the executing coders)

1. **Already landed / in flight (do not duplicate):** the `?q=` contract and
   `bundlePath` fix; palette loading state; CLI repoint through
   `cli_reference_page_for_command` + CLI parity gate (peer WIP -- let it
   land; D4 ratifies it).
2. **Casilla destination (one atomic commit):** `casilla_reference.py` +
   `casilla_page_anchor` + `conf.py` wiring + `docs/index.md` toctree line +
   `_from_casilla` retarget + the 28 `relevance.json` rewrites + the casilla
   parity gate (anchor existence AND destination-grounding coverage per D6)
   + updates to `test_relevance_data.py` and `test_unified_record.py`.
   Destination and target change must never split.
   The D6 meta widening (`segmento` in `_meta_for`) and the
   destination-grounding assertions for the glossary and CLI kinds ride the
   same commit or a small follow-up -- they are additive and low-risk.
3. **Built-site sweep gate (after 2, else it is born red on casillas):** the
   kind-agnostic resolvability + no-query-string gate in `dev/docs/tests/`.
4. **Search-page palette host (parallel with 2-3; disjoint files):**
   controller extraction in `cadrumo-docs.js`, inline host + PagefindUI
   retirement in `search.html`, re-point the behavioural `?q=` gate.
5. **Display classes + user-first ranking (D7/D8; after or with 4):** the
   Python side (display-class derivation, `_meta_for` shipping, the one
   weight table, unit gates) is independent and can land any time; the icon
   rendering and ranking assertions land in the shared controller so they
   ship once for both hosts -- coordinate with the step-4 owner on
   `cadrumo-docs.js` (pathspec commits, diff before edit).
