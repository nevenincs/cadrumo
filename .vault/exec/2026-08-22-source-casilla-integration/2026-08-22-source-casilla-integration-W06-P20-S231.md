---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:20fa4d232b649c3bbb5907363abcf54aa28b3f7a7716222dd409c85a17239ae6'
step_id: 'S231'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - '[[2026-08-25-source-casilla-integration-modelo-840-source-and-repeated-row-owner-deferral-adr]]'
---
# Adjudicate Modelo 840 source and repeated-row value lifecycles independently from the generic CRLF transport bridge, then add only evidenced canonical bindings, provenance, and census dispositions without an M840-specific writer.

## Scope

- `.vault/research/`
- `.vault/adr/`
- `src/cadrumo/_data/source_connectivity/census.toml`
- `src/cadrumo/_data/registry/aeat/modelos/840/`

## Description

- Discover the governing source-connectivity decision, M840 registry and
  source-mesh surfaces, generic producer/terminator boundary, and prior M840
  record-extent reference before exact-symbol confirmation.
- Re-fetch the BOE order/form and AEAT procedure/design, record the published
  form and record-design hashes, and distinguish filing targets from source
  acquisition.
- Inspect the whole `2003-y-siguientes` registry lifecycle and exact-search for
  an M840 source owner, resolver, binding, row carrier, producer values, or
  census candidate.
- Record the factual result in model-scoped research and the normative
  `grounding_blocked` result in the accepted M840 ADR; preserve the independent
  generic CRLF transport owner.
- Correct the accidentally mixed blank scaffold from `eb732c9db9`, check S231
  through the approved CLI, regenerate the feature index, and run bounded
  registry/continuity and Vault checks.

## Outcome

S231 adds no source-connectivity candidate.  Official M840 artefacts establish
two real source familiesâ€”declaration/activity facts and individually repeated
`RelaciÃ³n de locales` factsâ€”but no authoritative, non-lossy encrypted owner
for either.  The accepted model-scoped ADR classifies both as
`grounding_blocked`, owned by `source-connectivity-campaign`, with no binding,
resolver, fixture, M840 writer, source-owned repeated-record export, registry,
or census change.

The existing informational registry targets, narrow secure IAE threshold
observation, and generic CRLF bridge retain their existing contracts.  None is
reclassified as a complete M840 source or direct/manual lifecycle.  Reopening
requires a family-specific authorized carrier, durable identity, full native
value/absence semantics, selected destinations, encrypted provenance and
replay/review route, plus separately grounded export proof if export is later
proposed.

## Notes

`eb732c9db9` was a shared mixed-worktree commit whose M763-labelled change set
inadvertently included blank S231 research/exec scaffolds and an unaccepted,
genericly named ADR scaffold.  Exact reference search found no inbound
references and no accepted decision in that erroneous file.  This step removes
only that scaffold, creates the correct model-scoped ADR, and records the
provenance rather than attributing the earlier mixed commit to S231.

The focused registry suite passed 10 tests and Ruff passed.  The five IAE
continuity tests fail before their assertions because shared validation now
refuses a `filing` snapshot for M840's declared `applicability` authority grade;
S231 changes no registry/runtime authority and does not mask that unrelated
failure.  The path-scoped Vault check has no errors: S231 frontmatter, schema,
ADR status, exec mapping, links, modified stamps, body sections, and
placeholders pass.  It reports 35 pre-existing feature warningsâ€”24 template
annotations, eight markdown-hygiene warnings, and three unrelated research
reference warningsâ€”none in S231.
