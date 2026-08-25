---
tags:
  - '#adr'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:8e20e8ab7a99de543c4b238a4cec11d940ff32984487abd4aee165c3686b5b0a'
related:
  - "[[2026-08-25-source-casilla-integration-m390-2021-annual-value-arrival-grounding-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Amend vs supersede: refinements and concretization rewrite the accepted
     record's body in place (modified: carries the revision); a new ADR with
     supersession is only for a major pivot. One accepted record per
     decision.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `source-casilla-integration` adr: `m390 2021 source owner deferral` | (**status:** `accepted`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

## Problem Statement

The accepted source-connectivity framework requires a model-scoped source-owner
decision before a source domain, binding, producer, or layout is authored. The
exact Modelo 390 2021 annual surface is grounded in
`2026-08-25-source-casilla-integration-m390-2021-annual-value-arrival-grounding-research`,
but no complete pre-filing value owner is. This ADR decides the bounded 2021
outcome without changing the parser or importing later M390 behavior.

## Considerations

- `2026-08-22-source-casilla-integration-adr` governs the disposition
  vocabulary and requires a non-lossy, encrypted, provenance-carrying lifecycle
  before a source claim can be connected.
- `2026-08-25-source-casilla-integration-m390-2021-annual-value-arrival-grounding-research`
  distinguishes the official 2021 annual record from the ten parser
  observations, read-only filed evidence, and later M390 implementation.
- `2026-06-02-m390-annual-autoconsumo-promotor-source-adr` and
  `2026-06-21-m390-iva-carry-boxes-adr` retain their narrow, later M390
  aggregation decisions; neither supplies complete 2021 source ownership.

## Considered options

### Connect the parser, filed declaration, or later routes now

Rejected. Each is either a post-filing observation or a partial/later route; none
is the non-lossy 2021 fact owner the framework requires.

### Treat the complete annual surface as not applicable

Rejected. The official 2021 annual record is genuine and required; absence of a
source owner is a grounding gap, not an inapplicability determination.

### Hold the exact annual surface at a model-scoped grounding boundary

Accepted. Preserve genuine parser observations, filed-declaration read evidence,
and independent later-model routes, while refusing to claim they are a complete
2021 source connection.

## Constraints

- The decision applies only to Modelo 390, filing year 2021, period `0A`; it
  neither extends to another M390 revision nor changes any legal temporal
  selector.
- Parser coordinates, export fields, static-layout evidence, and post-filing
  observations remain inadmissible as proof of a pre-filing value owner.
- Existing encrypted filed-declaration custody is read-only historical evidence;
  it neither supplies absent facts nor substitutes for the calculation-revision
  source lifecycle.
- No runtime, source taxonomy, binding, producer, registry, census, or layout
  change is authorized by this decision.

## Implementation

<!-- A high-level overview (not a plan!) of HOW and WHAT will be implemented. Focus on condensed but clear prose that describes functionality layering.

Do not add code; code references must be persisted in a separate `{reference}` document. Important `{reference}` snippets must be summarized and referenced explicitly. -->

## Rationale

<!-- Why this option wins against the drivers: a knockout criterion or a
     clear edge over the alternatives. Cite `{research}` findings and
     grounding `{reference}` by stem; do not restate them. A new fact
     surfacing here first belongs in the grounding document. -->

## Consequences

<!-- Gains, but framed honestly. Difficulties. Pathways this feature opens. Pitfalls. -->
