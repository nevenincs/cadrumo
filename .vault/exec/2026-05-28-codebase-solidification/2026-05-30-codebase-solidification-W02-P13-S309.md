---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-07-17'
body_hash: 'sha256:f580a0c3fe78b337bf9f43205d6396fe84aedb1b159c60553d0855173c3a12b9'
step_id: 'S309'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W02.P13.S309`

Added `CAST-RATIONALE-SANITIZER-PIKEPDF-OPERANDS` and `CAST-RATIONALE-SANITIZER-PIKEPDF-ARRAY-ELEMENT` inline comments at the two cast sites in the PDF sanitizer stream processor.

- Modified: `src/aeat/adapters/inbound/sanitizer/_streams.py`

## Description

Both pikepdf cast sites now carry `CAST-RATIONALE-*` markers in the immediately preceding comment block. The first (operands cast) explains that `_ObjectList` is a private QPDF runtime-sequence type not statically typed as `Sequence[...]`. The second (array element cast) explains that the operand union cannot express the `pikepdf.Array` narrowing at the static level.

## Tests

Covered by `src/aeat/test_cast_rationale_inventory.py` — the inventory test walks the AST and confirms both cast sites carry their markers.
