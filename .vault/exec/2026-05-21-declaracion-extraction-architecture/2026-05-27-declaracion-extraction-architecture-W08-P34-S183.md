---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: "2026-05-27"
modified: '2026-05-27'
step_id: "S183"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-27-declaracion-extraction-architecture-audit]]"
---

# declaracion-extraction-architecture W08.P34.S183

## Step

Audit calculation-completeness manifests for the 5 modelos with `target_casillas` REMOVED (M036/M720/M184/M232/M347) to verify removed casillas are marked `input_kind = "informational"` or otherwise non-extractable.

## What was done

Inspected casilla definitions for each removed casilla in each affected modelo:

| Modelo | Casilla removed from target_casillas | input_kind in registry | Verdict |
|--------|--------------------------------------|------------------------|---------|
| M036 | `decl.vigencia-2025` | `"informational"` | CLEAN — already marked per task #45 commit |
| M720 | `decl.tipo-declaracion` | `"informational"` | CLEAN — positions 121-122 are two flag bytes, not a printed label+value pair |
| M184 | `decl.tipo-declaracion` | `"informational"` | CLEAN — same EDI flag structure |
| M347 | `decl.tipo-declaracion` | `"informational"` | CLEAN — same EDI flag structure; documented inline in 347.toml comment |
| M232 (2016-2017) | `decl.cnae` (pattern fix) | `"informational"` | CLEAN — not a removal but a pattern correction; casilla correctly informational |
| M232 (2018+) | `decl.cnae` (pattern fix) | `"informational"` | CLEAN — same |

All five modelos' removed casillas have `input_kind = "informational"` in their registry definitions. No casilla is expected-extractable but unextracted. The cumulative completeness manifests are consistent: informational casillas do not participate in extraction coverage.

The parity coverage manifest (`test_modelo_parity_coverage.py`) passes cleanly after all changes.

No code changes required for this unit — the audit finding was clean.

## Files changed

None (audit-only, all casillas confirmed as informational).

## Test result

`test_modelo_parity_coverage.py`: 1 passed in 30.09s
