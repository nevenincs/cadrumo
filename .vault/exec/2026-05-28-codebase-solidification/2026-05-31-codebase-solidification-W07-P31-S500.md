---
tags:
  - "#exec"
  - "#codebase-solidification"
date: "2026-05-31"
modified: '2026-05-31'
step_id: "W07.P31.S500"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-adr]]"
---

# codebase-solidification W07.P31.S500 — CertificateLoadError tr-positional regression fix

## Outcome

Replaced two `raise CertificateLoadError(tr(...))` positional-tr calls at
`_authenticator.py:1241,1251` with `translated_message=` keyword form.
Grep-post-condition: zero `raise CertificateLoadError(tr(` in the file (before: 2, after: 0).

## Files touched

- `src/aeat/adapters/outbound/aeat/auth/_authenticator.py` — S500 fix
