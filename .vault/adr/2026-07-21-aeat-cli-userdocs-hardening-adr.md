---
tags:
  - '#adr'
  - '#aeat-cli-userdocs-hardening'
date: '2026-07-21'
modified: '2026-07-21'
body_hash: 'sha256:f4982e171886e3a333a7068167d4d2c6fea087bc0aba85b73b7ae2f5debfb7c9'
related:
  - "[[2026-06-04-aeat-cli-userdocs-hardening-plan]]"
  - "[[2026-06-04-aeat-cli-userdocs-hardening-research]]"
  - "[[2026-06-10-aeat-cli-userdocs-hardening-audit]]"
  - "[[2026-06-04-aeat-cli-userdocs-hardening-reader-review-audit]]"
---

# `aeat-cli-userdocs-hardening` adr: `userdocs handbook corpus architecture (retroactive record)` | (**status:** `accepted`)

## Problem Statement

**This is a retroactive record**, authored 2026-07-21 to close a vault
lifecycle gap: the `aeat-cli-userdocs-hardening` campaign (L3 plan dated
2026-06-04, seven waves, executed through mid-July) ran under an approved plan,
session audits, and reader/code reviews, but the architecture it implemented
was never captured as an ADR. This record states the decisions the campaign
actually made and landed; it introduces no new choice.

The problem the campaign addressed: the user documentation was not a corpus a
non-technical operator could navigate. Pages mixed Diataxis types (tutorials,
recipes, explanation, and reference on one page), the landing route assumed
architectural knowledge, the monolithic glossary served as the primary
explanation path, troubleshooting started from subsystem internals rather than
user symptoms, and the generated CLI reference had drifted from the live CLI
(188 documented leaves against 193 live, omitting `ledger.doclink`,
`ledger.providers`, and the three M036 surfaces). Users could not rely on
examples when generated reference, runtime help, and next-action guidance
disagreed.

## Considerations

- A zero-context wireframe review warned that "quick-reference handbook" would
  blend Diataxis types unless the corpus is explicitly linked instead of
  merged (recorded in the plan's description and the reader-review audit).
- A non-technical reader review found the first-time path skipped ledger
  readiness, censo was buried, export/file/upload language confused, and
  troubleshooting started from internals (reader-review audit).
- The docs conformance gates (documented-command conformance, generated
  reference drift check, Sphinx nitpicky build) already existed and bind every
  page change; the campaign had to work inside them, not around them.
- Product gaps discovered during prose review must not be hidden by confident
  prose; they are logged as backlog findings.

## Considered options

1. One mixed quick-reference mega-document: rejected by the wireframe review —
   it blends learning, task, explanation, and lookup needs into prose that
   serves none of them.
2. A linked handbook corpus, one Diataxis type per page (accepted): tutorials
   for learning, how-to guides for tasks, explanation pages for mental models,
   generated reference for lookup, each page linking out for other needs.
3. Checking the generated CLI reference into git versus keeping it ignored
   build output: kept as generated build output regenerated from the live tree,
   with the drift gate reconciling leaf counts — a checked-in copy would add a
   second drift surface against the live CLI.
4. Glossary as the primary explanation path: rejected — replaced by inline
   first-use definitions and reference-backed lookup; escape-hatch routes that
   send general readers to a glossary, issue tracker, or backlog list were
   removed.

## Constraints

- Every page change passes the documented-command conformance gate against the
  live localized CLI help; command examples are verified with the real CLI in
  the documented language, and localization divergence is logged as backlog
  rather than papered over.
- Each new or rewritten page runs the full documentation pipeline as a
  single-document unit: wireframe, zero-context refinement, context gathering,
  isolated drafting, technical review against live CLI help, zero-context
  editorial review, final approval. Non-technical operator review is mandatory
  for the pages where implementation vocabulary most easily leaks.
- Terminology is normalized corpus-wide: DNI for Spanish citizens, NIE for
  foreign individuals, NIF/CIF for tax identifiers and legal entities, with
  DNI/NIE only where Cl@ve identity requires it.

## Implementation

Seven waves: audit and drift capture first (page inventory, generated-versus-
live reference comparison, reader-review baseline); then the handbook spine
(landing route rewritten for task-based navigation, route labels, target H1s,
and filenames normalized); Diataxis cleanup (mixed pages split, conceptual
detours replaced by links, reference restatement converted to stable links);
page families in parallel with disjoint write scopes (profile/censo, ledger,
modelo and manual inputs, verification/export); symptom-first troubleshooting;
and a continuous verification-gate wave. Documentation generators, build
helpers, and verifier tests moved out of production package code into
`docs/tools/` so production code does not own documentation generation.

## Rationale

The linked-corpus decision wins because each Diataxis type has a distinct
reader contract, and the campaign's own zero-context reviews demonstrated that
blending them is what made the prior docs unnavigable. Keeping the CLI
reference generated preserves one source of truth (the live command tree) with
gates instead of a second maintained copy. Symptom-first troubleshooting and
inline definitions follow from the same driver: the reader's vocabulary, not
the implementation's, orders the page.

## Consequences

- Non-technical operators get a navigable corpus: land, choose a task, follow
  one page, link out for depth; the full operator journey (profile through
  reconciliation) is documented end to end.
- The corpus is enforceable: conformance gates plus mandated technical and
  zero-context editorial reviews keep pages tied to the live CLI.
- The per-page pipeline is expensive by design; later campaigns (persona
  verification, localization) build on this corpus shape rather than revisiting
  it.
- Retroactive honesty: because this record postdates the work, it cannot have
  steered it; its value is that the vault now names the architecture the
  landed corpus and its audits already prove.
