---
tags:
  - "#exec"
  - "#trilingual-i18n"
date: 2026-04-12
modified: '2026-07-17'
body_hash: 'sha256:f28c8f5b2ca9b2387ea9fe0ef1118e950ad8be114f8da3338ad5fcc1f6c0999d'
related:
  - "[[2026-04-12-trilingual-i18n-plan]]"
---

# Add unit tests for i18n primitives

Added tests in `src/aeat/core/i18n/test_i18n.py`.
Tested exact matches, strict fallbacks, and dictionary injections.
Ensured no mocks, patches, fakes, or stubs were used. Tests run against the actual pure primitives.
