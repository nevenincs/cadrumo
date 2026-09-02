---
tags:
  - '#research'
  - '#modelo-200-semantic-crosswalk'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:bfaf6999c5650d657b7b43937758afe968cde652f7d0697a7271a8652f99dd46'
related:
  - '[[2026-08-07-aeat-design-relayout-boundary-research]]'
  - '[[2026-08-08-aeat-design-relayout-boundary-modelo-200-partition-adr]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-adr]]'
---
# `modelo-200-semantic-crosswalk` research: `authority-safe reuse across the 2024 relayout`

Modelo 200's 2024 export can remain programmatically generated, but its missing
registry meanings cannot be recovered by copying the 2025 revision or by treating
text similarity as authority. The evidence supports a target-first workflow in
which the pinned 2024 design owns wire identity, exact same-revision templates can
support narrow repairs, cross-revision matches produce review candidates only, and
unmatched concepts require new 2024 adjudication. An ADR must settle the proof that
turns a candidate into reviewed semantic-map authority.

## Findings

### Wholesale sibling reuse is falsified as semantic authority

The conservative remediation screen refuses every one of the 156 current 2024
candidate identities: 141 have a different complete official field signature, 14
have no exact sibling parser/map anchor, and one has ambiguous segment ownership.
The accepted partition record's wholesale-copy premise therefore cannot establish
2024 meaning from the later-year tree. The reproducible measurement is at
`dev/registry/analysis/m200_2024_sibling_remediation.py:249` and
`dev/registry/analysis/m200_2024_sibling_remediation.py:355`; the premise being
tested is recorded at
`.vault/adr/2026-08-08-aeat-design-relayout-boundary-modelo-200-partition-adr.md:126`.

### Same-revision templates are narrow repair evidence, not a population generator

The restored-semantics audit accepts a repair only when one non-restored 2024 peer
has the same normalized description template and compatible wire type. Its measured
restoration cohort produced 9 uniquely repairable payloads and 147 unresolved ones.
The audit detects direct description/role contradictions instead of ranking a
nearest candidate; these contracts live at
`dev/registry/analysis/m200_restored_semantic_audit.py:107` and
`dev/registry/analysis/m200_restored_semantic_audit.py:235`. This option can
correct a reviewed proposal but cannot invent a semantic role for a unique concept.

### Cross-revision description matches are useful proposals but insufficient proof

A read-only join over the 147 same-revision-unresolved rows normalized only a
trailing bracket identity and explicit year, required equal AEAT type and length,
excluded identical parser anchors, and checked legal applicability to 2024. It
found 32 unique candidates, 13 conflicting candidate sets, and 102 with no
applicable match. Those counts are produced by
`dev/registry/analysis/m200_restored_semantic_audit.py`; they describe the
withdrawn restoration cohort and are not deployable registry data.

The governing generator authority separates concerns: the official binary design
owns wire facts, while the reviewed semantic map owns registry meaning.
Description, offset, neighboring fields, and a historical tree are diagnostics
rather than semantic-home authority. The exact-source, SHA, bijection, and
whole-design refusal requirements are at
`.vault/adr/2026-08-10-aeat-export-fragment-generator-authority-adr.md:55` and
`.vault/adr/2026-08-10-aeat-export-fragment-generator-authority-adr.md:82`.
A prior legal-grounding experiment also found that proximity joins can select
confident but wrong provisions; see
`.vault/audit/2026-08-26-registry-temporal-coverage-modelo-200-legal-grounding-and-revision-rename-audit.md:43`.

### Novel semantics remain review work even when coordinates are generated

For a meaning-changed or unmatched 2024 field, the currently authoritative route
is a new reviewed semantic declaration grounded in the 2024 design/manual and
applicable law. That does not require hand-authoring export fragments: once the
semantic map and render profile are reviewed, the generator derives the target
tree from the pinned binary source. The source-of-truth split is specified at
`.vault/adr/2026-08-10-aeat-export-fragment-generator-authority-adr.md:55` and
the atomic whole-tree posture at
`.vault/adr/2026-08-10-aeat-export-fragment-generator-authority-adr.md:90`.

### The decision must bind proposal, adjudication, and publication separately

The ADR must settle whether cross-revision matches may only create review records;
the exact admissibility proof for semantic reuse; how same-year repairs,
cross-revision candidates, and novel declarations are represented; and which
source-SHA, legal-window, reviewer-provenance, bijection, and unresolved-anchor
checks must pass before atomic publication. The evidence favors a constrained,
target-first crosswalk, but does not itself authorize one.

## Sources

- `dev/registry/analysis/m200_2024_sibling_remediation.py:249`
- `dev/registry/analysis/m200_2024_sibling_remediation.py:355`
- `dev/registry/analysis/m200_restored_semantic_audit.py:107`
- `dev/registry/analysis/m200_restored_semantic_audit.py:235`
- `.vault/adr/2026-08-08-aeat-design-relayout-boundary-modelo-200-partition-adr.md:126`
- `.vault/adr/2026-08-10-aeat-export-fragment-generator-authority-adr.md:55`
- `.vault/adr/2026-08-10-aeat-export-fragment-generator-authority-adr.md:82`
- `.vault/adr/2026-08-10-aeat-export-fragment-generator-authority-adr.md:90`
- `.vault/audit/2026-08-26-registry-temporal-coverage-modelo-200-legal-grounding-and-revision-rename-audit.md:43`
