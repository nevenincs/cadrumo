---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:4a8ed06810c5282ff06b75f5184917358160b21396224d51039883647b1ba4e8'
step_id: 'S05'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Validate mapping bijection and require canonical identifiers, legal references, and source references to resolve through existing registry catalogues while constraining typed anomaly exceptions

## Scope

- `dev/registry/`

## Description

- Add a development-only validation boundary for one typed semantic map, one parser intermediate, and one target registry snapshot.
- Refuse mismatched modelo or design epoch, unpinned source metadata, duplicate parser or map anchors, and missing or extra anchors.
- Resolve canonical casilla and binding identities through the target revision and legal and source references through its catalogues.
- Constrain parser/source anomaly records to strict source-ref and SHA-256 metadata that cannot carry coordinates or waive any validation.
- Prove map-local export-field identifier uniqueness and independence from legacy export-layout membership.

## Outcome

Focused checks passed: 29 tests across the source-intermediate, semantic-map, and S05 validation boundaries; Ruff check and format check; and focused BasedPyright with zero errors or warnings. Independent review reported no CRITICAL, HIGH, MEDIUM, or LOW findings.

## Notes

The validator deliberately does not render or publish output and does not consult existing export layouts. Later generator Steps own deterministic generation, legacy-tree removal, and byte-level proof.
