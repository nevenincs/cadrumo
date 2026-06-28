---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase3 summary - parser and model unit tests

Phase 3 landed `src/aeat/status/test_site_health.py` exercising
every fixture through the real parser suite (mantenimiento, WAF,
rate-limited, OK) and validating the pydantic model shapes
(evidence bounds, retry-after lower bound, alert run-id bounds).
Zero mocks; headers are read from sibling `.headers.json` files.

Steps: 3-1. 38 parametrised tests green locally.
