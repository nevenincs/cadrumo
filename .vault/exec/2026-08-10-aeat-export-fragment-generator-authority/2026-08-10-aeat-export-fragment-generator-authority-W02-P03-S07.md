---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:8d9f50b50617ce4331288759cc2d11938b021676a2bc4a40d719d28ab85deb3b'
step_id: 'S07'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Implement fail-closed parser-to-semantic-map joining without fuzzy or positional matching

## Scope

- `dev/registry/`

## Description

- Add the frozen `JoinedRecordDesign` and `JoinedRecordDesignField` contracts.
- Validate map authority before direct exact-anchor indexing and retain parser sheet and field order unchanged.
- Add real-authority behavior tests for map-order independence, nearby-anchor refusal, and direct invalid-pair refusal.
- Add structural red guards that reject restored layout, derivative, approximate-match, positional, fallback, extracted-input, provenance, rendering, and export-loader surfaces.
- Resolve the independent review finding and rerun focused tests, lint, and static analysis.

## Outcome

The join produces one typed pair for every exact parser anchor only after source, scope, canonical-reference, and complete-bijection validation. Coordinates remain parser-owned and reviewed meaning remains map-owned. No output rendering or provenance behavior is included in this step.

## Notes

The initial independent review found a medium structural-guard gap for derivative inputs. It was corrected and re-reviewed as closed. Focused proof: 16 tests passed, Ruff passed, and basedpyright reported zero errors and zero warnings.
