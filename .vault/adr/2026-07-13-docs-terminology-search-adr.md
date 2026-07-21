---
tags:
  - '#adr'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-17'
related:
  - "[[2026-07-13-docs-terminology-search-research]]"
  - "[[2026-06-10-docs-terminology-search-adr]]"
  - "[[2026-06-15-docs-terminology-search-adr]]"
---

# `docs-terminology-search` adr: `next wave: upstream hook wiring, corpus coverage, and the rung-2 gate` | (**status:** `accepted`)

## Problem Statement

The precompiled semantic-search architecture (2026-06-10 ADR, D4-D8) shipped:
the dev vaultspec-rag sweep, the typed chunk-to-target resolution, the
committed laundered relevance data, the Pagefind injection, and the Ctrl/Cmd-K
palette. An operator status review on 2026-07-13 (the sibling research
document) surfaced four unsettled follow-ons the original ADRs deferred or
adjudicated on facts that have since changed:

1. Upstream vaultspec-rag now SHIPS the pre-index preprocess seam
   (`.vaultragpreprocess.toml` rules; `preprocess list / check / run-one`;
   versioned `PreprocOutput` contract, `extra="forbid"`, per-file skip on
   validation error). The D6 interim — committed `*.extracted.md` sidecars —
   was adjudicated when the walker had no hook. This repo carries zero rules.
2. The shipped relevance mapping covers 72 queries over 29 approved concepts;
   the bundled legal corpus and the modelo/casilla registry offer a far larger
   derivable query surface whose coverage has never been measured.
3. The rung-2 decision (client-side int8 term-embedding matrix) was deferred
   behind a miss-rate measurement that has never been taken, and "material
   miss-rate" was never given a number, so the gate cannot fire.
4. The reader-side entry point was a static link list; the palette was
   undiscoverable from the landing page (closed 2026-07-13, ratified here).

## Considerations

- The dev box hosts the resident RAG service (port 8766, healthy) and the GPU;
  CI and the docs build have neither, so everything shipped stays precompiled
  committed data — the D6 licence-laundering discipline (rankings and target
  ids only, never vectors or sparse weights) is unchanged and non-negotiable.
- The upstream rule loader is deliberately CPU-only, degrades to zero rules on
  malformed config outside `preprocess check --strict`, and threads matched
  rules into spawn workers; a project rule therefore must be a self-contained
  command invocation, not an importable callable.
- The repo's `dev/docs/preprocess` extractors (BOE HTML article-aware
  splitting, Diseños workbooks, corpus PDFs, text tail) already produce a
  versioned `PreprocessOutput` designed as a forward-compatible precursor of
  the upstream schema; the migration is a serialization adapter, not a rewrite.
- The terminology chunk-to-target resolver maps `*.extracted.md` PATHS to
  search targets; hook-fed indexing surfaces chunks under SOURCE file paths
  (`.html`, `.pdf`, `.xlsx`), so resolver path rules and the sidecar
  retirement are one coupled change, never two.
- The sweep and its consumers treat generated-but-committed data as reviewed
  diffs; a widened vocabulary must not bypass the synonym ratification
  ratchet (antonym/co-hyponym intrusion risk stands).

## Considered options

- Hook wiring: (a) adapter command per source kind reusing the existing
  extractors — CHOSEN (one extraction truth, mechanical schema map);
  (b) reimplement extraction inside rule commands — rejected (duplicates the
  hardened extractors); (c) stay on sidecars indefinitely — rejected
  (committed derived bytes, staleness-by-hand, upstream seam exists).
- Sidecar retirement: (a) atomic with resolver retarget + parity proof —
  CHOSEN; (b) keep both paths "for safety" — rejected (dual-format assessment
  hazard; the registry-format campaign's lesson); (c) retire before parity —
  rejected (silent index regression risk).
- Rung-2 trigger: (a) numeric gate on the held-out miss-rate — CHOSEN;
  (b) operator vibes per release — rejected (unfalsifiable, the gate never
  fires); (c) implement rung 2 unconditionally — rejected (the 2026-06-10 ADR
  already rejected paying the cost without evidence of misses).

## Constraints

- Upstream `vaultspec-rag v0.2.28` is the grounded surface; the rule-file
  format and `PreprocOutput` major version are pinned by `preprocess check`
  in strict mode, which becomes a repo gate so an upstream major bump fails
  loudly here rather than degrading to zero rules silently.
- Sweep and miss-rate runs REQUIRE the resident service and warm models; they
  are dev-box operations producing committed reports, never CI steps.
- The shared-worktree discipline applies: every landing is an explicit-path
  commit; the sidecar retirement is one atomic commit spanning rules file,
  resolver path rules, deleted sidecars, docstring correction, and gates.

## Implementation

Four decisions, ratified together:

**D1 — Wire the shipped upstream hook.** A repo-root `.vaultragpreprocess.toml`
maps the four corpus source kinds (normatives HTML, Diseños workbooks, corpus
PDFs, unsupported-text tail) to adapter commands that run the existing
`dev/docs/preprocess` extractors and emit the upstream `PreprocOutput` JSON.
`preprocess check --json` (strict) becomes a fast repo gate. Per-kind parity
is proven with `preprocess run-one` against a representative source: the
hook-emitted unit text must equal the committed sidecar text for the same
file. Only after parity holds for every kind does ONE atomic change retarget
the terminology resolver path rules from `*.extracted.md` to source-file
paths, delete the committed sidecar tree, correct the stale
`dev/docs/preprocess/__init__.py` docstring, and prove a post-change sweep
resolves an equal-or-superset target set.

**D2 — Measure, then widen, the query vocabulary.** A coverage report derives
the candidate query surface from the casilla labels and sections of
calc-grade revisions and from the legal catalogue's provision vocabulary,
then lists every derivable target with no inbound entry in the committed
relevance mapping. The widened vocabulary re-runs the sweep through the
resident service (explicit incremental reindex first), flows through the
existing typed resolution and laundering, and lands as a reviewed diff of the
committed mapping. Synonym candidates keep the human ratification ratchet.

**D3 — The rung-2 gate gets a number.** The held-out real-query set is run
through the shipped mapping via the existing miss-rate machinery, before and
after the D2 widening. Material is defined as: MORE THAN 10 PERCENT of
held-out queries whose intended target is absent from the top five shipped
results after widening. Above the line, rung 2 (the ~1-3 MB int8
term-embedding matrix over the closed vocabulary, client-side cosine) is
implemented; at or below it, rung 2 stays deferred and the measurement is
committed as the standing baseline re-taken each sweep cadence. Either way
the measurement report is committed, so the gate is falsifiable.

**D4 — The palette is the reader's search front door.** The landing page
teaches Ctrl/Cmd-K instead of a link list (landed 2026-07-13). No
hand-authored glossary exists or returns; the generated glossary remains the
D7 projection of the approved-tier Handbook, and the Handbook remains the
single vocabulary authority feeding sweep, palette, and glossary alike.

## Update 1 (2026-07-13): D1 sidecar retirement rescinded; cutover re-scoped

Execution of the cutover surfaced a fact the decision missed: the committed
`*.extracted.md` / `*.extracted.json` sidecars are no longer only the dev-RAG
interim. They are PRODUCT data — the shipped offline corpus search builds its
lexical index from the bundled `*.html.extracted.json` triples
(`src/cadrumo/application/corpus_search/_lexical_index.py`), the
manual-oracle grounding anchors (`raw_evidence_locator`) cite line ranges
inside `*.extracted.md`, and the wheel content boundary deliberately ships
the extracted text WHILE EXCLUDING the source binaries, so inside the wheel
the sidecars are the only corpus text that exists. Deleting the tree would
break the shipped search and the verification-grounding evidence chain.

D1 is therefore amended: the hook wiring, rule file, parity gates, and the
strict `preprocess check` gate stand as ratified; the sidecar tree is NOT
retired. The sidecars remain the committed product corpus payload with their
freshness gate, and the hook-vs-sidecar parity gate becomes a PERMANENT
lock (one extraction truth feeding both the product payload and the dev
index) instead of a transition aid. The dev-index side of the cutover
becomes: exclude `*.extracted.md` and `*.extracted.json` from the dev
walker via `.vaultragignore` (the hook now feeds the same text under source
paths, so indexing both would double-count every corpus document), retarget
the terminology resolver path rules from sidecar paths to source paths, and
prove the equal-or-superset sweep target set. The stale
`dev/docs/preprocess/__init__.py` docstring is corrected to describe the
dual role. Plan step W02.P02.S07 is re-scoped to match.

## Update 2 (2026-07-13): the D3 gate, de-tautologized, fires implement-rung-2

The close honesty review (the sibling audit) found the D3 gate could not
fail as first built: the held-out set was all in-vocabulary with the
concept's own seeded card as an expected id, the CI test pinned zero misses,
the enforced threshold was 0.20 against the ratified 0.10, and the top-five
bound was unimplemented. All four defects were remediated in-session: the
held-out corpus now carries a gate-enforced out-of-sample class evaluated by
palette-style lexical containment over the precompiled tiers, the module
default equals the ratified 0.10, the top-five bound applies, and CI pins
the adjudication's consistency, never its verdict. The remediated
measurement over the widened mapping reads 32 cases / 26 hits / miss-rate
0.1875 - ABOVE the line - so per this decision's own rule the gate fires
IMPLEMENT-RUNG-2. Rung 2 is committed follow-up scope in its own pipeline
(research, ADR, plan under a new feature), bounded by the 2026-06-10 ADR's
rung-2 scoping (~1-3 MB int8 matrix, closed vocabulary, client-side cosine)
and the licence-clean shipping rule; the offline measurement's stated caveat
(precompiled tiers only, upper bound on shipped misses) is the first
question that follow-up research must sharpen.

## Rationale

The sibling research grounds every fact: the shipped pipeline inventory, the
zero-rules `preprocess check` probe, the 72/29/0 relevance data state, the
untaken miss-rate measurement, and the stale downstream docstring that
mis-reported the upstream seam as missing. D1 follows the no-dual-format
lesson (one on-disk truth, loud gates); D2 extends an accepted mechanism
rather than inventing one; D3 converts a deferred decision from folklore to a
falsifiable number; D4 ratifies the operator's discoverability correction.

## Consequences

- The committed sidecar tree — derived bytes under version control — retires,
  and corpus indexing freshness stops depending on hand-run extraction.
- The resolver retarget is the risky edge: chunk paths change shape for every
  hook-fed source; the parity-then-atomic-cutover sequencing and the
  equal-or-superset sweep proof exist precisely to catch a silent resolution
  regression before it ships.
- Widening the vocabulary grows the reviewed-diff burden on the relevance
  mapping; the score floor and ratification ratchet are the noise dams.
- If the miss-rate lands above 10 percent, rung 2 becomes committed scope —
  a real client-side asset with size and licence-cleanliness obligations the
  2026-06-10 ADR already scoped.
- An upstream schema major bump now reds a repo gate instead of silently
  disabling rules.
