---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:2a59e54a1d4a8248c2322c5e4ab1dd30e1ae07727d246f48fda7d3f89eeaf92e'
related: []
---

# `aeat-export-fragment-generator-authority` audit: `s54 sector source taxonomy review`

## Scope

Reviewed the S54 implementation against the governing differentiated-sector taxonomy decision, the secure-storage atomicity contract, the no-legacy rule, and the repository's real-behavior test constraints. The review covered canonical enum ownership, lossless provenance, legal category and flow combinations, reciprocal Bienes linkage, secure migration, aggregation call paths, and legacy caller fallout.

## Findings

### s54-sector-source-taxonomy-review | high | Cross-namespace cutover was initially incomplete

The first implementation migrated transaction and Bienes namespaces independently. Remediation introduced one explicit target set, complete semantic validation, and one compare-and-swap batch across transaction index, transaction rows, and the persisted Bienes register. Real conflict tests prove every row remains at schema v1 when any revision races.

### s54-sector-source-taxonomy-review | high | Default backfill and in-memory old-schema reads remained

The first upgrader supplied missing authority axes through defaults and generic lineage could return upgraded bytes without persisting the cutover. Remediation deleted those defaults, made historical migration explicit and evidence-bound, and made ordinary reads refuse non-current S54 rows.

### s54-sector-source-taxonomy-review | medium | Legal combination validation was incomplete

Rectification originally bypassed category, flow, and rate checks, while REAGP was underconstrained. Remediation validates rectification against the corrected domestic, import, or intra-EU source combination, refuses exempt rectification, and restricts REAGP to its exact category, supported-input flow, and exempt tier.

### s54-sector-source-taxonomy-review | medium | A public aggregation bypass remained

The low-level public aggregator originally admitted investment-bearing facts without profile or register authority. Remediation made all authority parameters mandatory, performs reciprocity validation inside that boundary, and migrated every caller without compatibility defaults.

### s54-sector-source-taxonomy-review | low | Final review found no residual defect

The third independent review passed with zero critical, high, medium, or low findings. Caller census found no unguarded production path. Evidence-less fixtures assert strict refusal rather than infer or mirror fiscal classification.

## Recommendations

- Keep S49 dependent on the immutable S54 outputs and do not recreate deduction classification in export projection.
- Preserve the cross-namespace migration coordinator as the sole v1-to-v2 cutover path.
- Keep old-schema ordinary reads and evidence-free classifications as hard failures.
