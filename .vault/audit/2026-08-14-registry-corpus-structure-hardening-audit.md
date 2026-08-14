---
tags:
  - '#audit'
  - '#registry-corpus-structure-hardening'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:0c338f0bb361de08b90c4cfd5f6268bc67da73b7ff3a4ae53dec62957356ddc8'
related: []
---

# `registry-corpus-structure-hardening` audit: fail-closed corpus topology and authority state

## Scope

The audit covered the complete modelo registry tree, legal catalogue loading,
fragment placement and filename grammar, persisted review state, and the runtime
boundary that turns compiled registry data into filing authority. Programmatic
inventory and mutation probes were used because schema validation alone cannot see
files omitted by discovery.

## Findings

### discovery-closed-world | high | unrecognized authored files could be silently ignored

Modelo discovery, legal catalogue discovery, and revision collection accepted only
recognized globs. Orphan modelo directories, wrong extensions, nested legal files,
and misspelled fragment folders could therefore evade both loading and schema tests.
The loader now rejects every unrecognized entry before cache lookup.

### fragment-ownership | high | directory names did not own fragment sections

Recursive fragment merging allowed a valid section beneath a misspelled or nested
folder. Revision fragments are now direct children of a canonical section directory,
must declare only that section, and must not be empty. Regression tests exercise the
real discovery and loading paths.

### persisted-provisional-state | high | synthetic M202 evidence was exposed as a production profile

The M202 declaration PDF extraction profile explicitly lacked a real specimen and
required review. It and its stale parser contract were removed. A whole-model test
prevents that profile identifier or declaration surface from reappearing in any
revision without a new grounded implementation.

### legal-review-provenance | high | free-text review state could imply filing readiness

Legal references now carry typed pending, agent-reviewed, or operator-reviewed state.
Pending entries forbid reviewer attestations; reviewed entries require them. Filing
snapshots reject any selected reference that is not operator-reviewed, while the
global compiler still permits honest catalogue backlog to be inspected and repaired.

### corpus-placement-and-naming | medium | canonical sections and lexical naming had drifted

M303 scalar metadata, M200 umbrella records, M349 export aliases, continuity folders,
verification predicate folders, underscore slugs, and duplicate numeric prefixes were
normalized. A content-hash inventory accounted for all moved or deleted blobs and
found no unexplained content loss.

### operator-review-backlog | high | 413 legal references are intentionally not filing-grade

The conservative migration promoted only 220 entries carrying an exact operator
attestation. The remaining 413 are honestly represented as agent-reviewed. Any
snapshot selecting one of them now refuses filing authority until a genuine operator
review is recorded.

## Recommendations

Maintain the closed-world topology tests as a required registry gate. Do not add
folder aliases or discovery allowlists; migrate authored data to the canonical owner.

Run an evidence-backed operator review campaign for the 413 agent-reviewed legal
references. Status must be upgraded only from an actual operator attestation, never
as a mechanical corpus cleanup.
