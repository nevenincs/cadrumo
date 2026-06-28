---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S584
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W11.P42.S584`

Verified `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py` — all 3 `"utf-8"` sites are hashlib hash-protocol sites.

- No code change required.

## Grep post-condition

Lines 228, 243, 562 each contain `hashlib.sha256(html.encode("utf-8")).hexdigest()`.
All 3 are on the `_HASH_ALLOWLIST_TOKENS` (`sha256`, `hashlib`) exempt list.
Non-hash bare `"utf-8"` count: 0 (before and after — no change needed).

Allowlist criteria: any encode call whose result feeds directly into a `hashlib` or `hmac`
digest on the same logical line is protocol-mandated and exempt from `UTF_8_ENCODING` enrollment.
