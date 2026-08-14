---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:45dbb6c4a3d70f2e15377ade14498ad45158e33c265828321b2a257b707f8165'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `s63 implementation review`

## Scope

Read-only review of S63's core projection-reference taxonomy, IVA filing-row address, simplified projector, five M303 projection endpoint declarations, their focused tests, and the DP30302 matrix test against ADR commit `65952f0125`.

## Findings

No remaining findings. The four prior findings are closed:

1. Core and IVA fact addresses enforce the closed `sub_index` domain, Mesa requirements, and singleton rejection; the five source TOMLs and census preserve every reviewed epoch transition.
2. The selected-revision validator rejects invalid early/late horno shapes before application projection, with direct unit coverage.
3. Applicable projection requires one immutable calculation result before selecting any endpoint; the stale declared-quantity fixture now builds its real S76 result.
4. The five calculated fact members select only their matching immutable result; all other fact declarations correctly remain immutable row evidence. The amended ADR/TOML owner census confirms no annual-Orden fact partition exists; annual values remain on the module axis.

## Verification

- Core projection-reference tests: 28 passed.
- Filing S63 tests: 6 passed.
- Registry simplified projector tests: 8 passed.
- S63 path-scoped Ruff: passed.
- Diff whitespace check: passed.

## Conclusion

Approved. The S63 implementation conforms to the reviewed ADR amendment within this review scope.
