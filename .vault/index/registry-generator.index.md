---
generated: true
tags:
  - '#index'
  - '#registry-generator'
date: '2026-09-09'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:d958143bea20ad5d68cde3ca7ad6e5dea94a83767c9e5767b4839f54fd909e94'
related:
  - '[[2026-09-09-registry-generator-W04-P17-S75]]'
  - '[[2026-09-09-registry-generator-W04-P17-S76]]'
  - '[[2026-09-09-registry-generator-W04-P17-S77]]'
  - '[[2026-09-09-registry-generator-W04-P17-S78]]'
  - '[[2026-09-09-registry-generator-W04-P17-S79]]'
  - '[[2026-09-09-registry-generator-adr]]'
  - '[[2026-09-09-registry-generator-consumer-behaviour-reference]]'
  - '[[2026-09-09-registry-generator-corpus-provenance-research]]'
  - '[[2026-09-09-registry-generator-divergence-evidence-research]]'
  - '[[2026-09-09-registry-generator-plan]]'
  - '[[2026-09-09-registry-generator-signal-coverage-research]]'
---

# `registry-generator` feature index

Auto-generated index of all documents tagged with `#registry-generator`.

## Documents

### adr

- `2026-09-09-registry-generator-adr` - `registry-generator` adr: `a dependable, reproducible registry and the signals that keep it honest` | (**status:** `accepted`)

### exec

- `2026-09-09-registry-generator-W04-P17-S75` - Recompute the root manifest aggregate from the per-modelo manifests without fetching, so the only repair path for a purely local number no longer runs across the network; the check exits 1 on `main` today recording 247 artefacts against 248 held and M270 as 1 against 2
- `2026-09-09-registry-generator-W04-P17-S76` - Declare the 161 manifested artefacts that are expressible under the static-files base but named by no required entry, matching each declaration URL to the manifest URL or alias so the pull stays additive
- `2026-09-09-registry-generator-W04-P17-S77` - Add a declaration locus for the off-host class beside `historical_exclusions.json`, carrying per-artefact provenance and the disposition recording why a BOE document sits in an AEAT-indexed tree; five M184 and one M270 Orden PDFs as record designs, the M186 anexo image as a form spec
- `2026-09-09-registry-generator-W04-P17-S78` - Add the converse invariant to the offline check once the authority set is total: every manifest artefact resolves to exactly one declared authority, either a required entry or an off-host declaration
- `2026-09-09-registry-generator-W04-P17-S79` - Prove the invariant has teeth by planting an undeclared artefact on a temporary corpus tree and asserting the check refuses it, with the normal path passing in the same suite

### plan

- `2026-09-09-registry-generator-plan` - `registry-generator` plan

### reference

- `2026-09-09-registry-generator-consumer-behaviour-reference` - `registry-generator` reference: `how the consuming application behaves on an incoherent registry`

### research

- `2026-09-09-registry-generator-corpus-provenance-research` - `registry-generator` research: corpus provenance
- `2026-09-09-registry-generator-divergence-evidence-research` - `registry-generator` research: divergence evidence
- `2026-09-09-registry-generator-signal-coverage-research` - `registry-generator` research: signal coverage
