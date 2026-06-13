---
tags:
  - "#exec"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-self-healing-sync-plan]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
---

# step 8 — live opt-in smoke

- `test_live_sync.py` — `@pytest.mark.live` smoke test gated by
  `pytest.importorskip("aeat.adapters.outbound.aeat.auth.certificate")` and
  `pytest.importorskip("aeat.corpus")`. The default `just test`
  invocation deselects it via `-m 'not live'`; `just test-live`
  opts in. The body calls `pytest.fail` after the import gate so
  the moment #8 and #17 rebase in, the failure forces the engineer
  to wire the real end-to-end flow rather than silently pass.

`pytest src/aeat/application/sync/` reports `54 passed, 1 deselected`.
