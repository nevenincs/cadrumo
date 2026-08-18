---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:193240c9ef1a5746e04c07bfba19db6172daf5e0edc4ba821b10b469092c9c24'
step_id: 'S86'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---

# `aeat-design-relayout-boundary` execution record: `W04a.P12.S86`

Land the finished Modelo 184 export unit as its own commit.

## Executed

- The 184 authoring completed by the previous session landed as its own pathspec commit: the three 2025 mapping fragments (declarante, entidad, socio), the numeric-representation render profile, the three multi-id casilla fragments (87 casillas, 2 adjudicated export exemptions), the generated export tree with provenance, and the enrollment row in `test_generated_export_trees.py`.
- 184 is enrolled with NO `_CHECK_MODE_PENDING` entry: check mode passes fully, so the gate asserts the pass and a regression forces a pin rather than a soft state.

## Verification

- `dev/registry/tests/test_generated_export_trees.py`: 24/24 green, including the 184 row asserting full check-mode pass.
- Casilla coverage: all 85 mapping-referenced ids declared; the two declared-but-unmapped ids (`decl.tipo-declaracion`, `decl.persona-relacion`) carry their adjudication in-tree.
