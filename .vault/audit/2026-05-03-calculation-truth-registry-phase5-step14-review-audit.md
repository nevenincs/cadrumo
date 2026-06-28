---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step14-exec]]'
---

# `calculation-truth-registry` Code Review

Review result:

- Initial review found one low-severity issue: public-facing docstrings still
  described the deleted Python extractor registry as if it existed.
- Fixes applied:
  - Parser, schema, error, and detection docstrings now describe
    `TemplateRevision` as identity/diagnostics.
  - Extractor dispatch is documented as fail-closed pending validated registry
    snapshots.
  - Supported-triple enumeration and live Python registry binding wording was
    removed.
- Follow-up review result: no remaining findings.
- Second follow-up review result: no findings after the corpus coverage tests
  were updated to stop importing `_REGISTERED_CLASSES` / `_REGISTRY`.

Verification reviewed:

- ruff passed on touched declaration files and deletion gates.
- ty passed on `src\aeat\adapters\inbound\declaracion` and deletion gates.
- Focused pytest passed with 34 passed.
- Full `ty check` passed after removing the remaining corpus-test imports of
  the legacy registry constants.
- `rg` confirmed removed registry anchors are absent from implementation code.

Residual risk:

- Concrete extractor modules still exist and can be imported directly, but the
  public dispatch and inspection paths are fail-closed and no longer treat them
  as registry authority.
