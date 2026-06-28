---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step13-exec]]'
---

# `calculation-truth-registry` Code Review

Review result:

- No findings.
- The runtime boundary is coherent: `filing_profile_from_autonomo` now strips
  the loaded profile down to identity and returns `applicable_modelos=()`.
- The static supported-modelo tuple and `applies_to` dependency are gone.
- `build_runtime_schema_provider` remains fail-closed.
- Public exports remain coherent.

Verification reviewed:

- ruff passed on `src\aeat\application\filing\runtime.py` and the deletion
  gates.
- ty passed on `src\aeat\application\filing\runtime.py` and the deletion
  gates.
- Focused pytest passed with 59 passed.
- `rg` confirmed removed runtime anchors are absent from implementation code.

Residual risk:

- Registry-backed obligation/modelo applicability is still absent, so runtime
  profile loading intentionally cannot answer filing obligations until that
  authority exists.
