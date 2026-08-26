---
generated: true
tags:
  - '#index'
  - '#declarations-register-pagination'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:a1c77fb1aa49ffb79f482ac2c7503ad03b41dfd5b587b42e39697ae39f29c9a8'
related:
  - '[[2026-08-07-declarations-register-pagination-adr]]'
  - '[[2026-08-07-declarations-register-pagination-plan]]'
  - '[[2026-08-07-declarations-register-pagination-reference]]'
---

# `declarations-register-pagination` feature index

Auto-generated index of all documents tagged with `#declarations-register-pagination`.

## Documents

### adr

- `2026-08-07-declarations-register-pagination-adr` - `declarations-register-pagination` adr: `Detect AEAT declarations register pagination truncation` | (**status:** `accepted`)

### exec

- `2026-08-07-declarations-register-pagination-S01` - 2026-08-07-declarations-register-pagination-S01
- `2026-08-07-declarations-register-pagination-S02` - 2026-08-07-declarations-register-pagination-S02
- `2026-08-07-declarations-register-pagination-S03` - 2026-08-07-declarations-register-pagination-S03
- `2026-08-07-declarations-register-pagination-S04` - 2026-08-07-declarations-register-pagination-S04
- `2026-08-07-declarations-register-pagination-S05` - 2026-08-07-declarations-register-pagination-S05
- `2026-08-07-declarations-register-pagination-S08` - 2026-08-07-declarations-register-pagination-S08
- `2026-08-07-declarations-register-pagination-S06` - Add a minimal purely-additive optional register-injection seam to list_filed_data_bulk and capture_filed_data_bulk, defaulting to today's behaviour so every existing caller and signature is unchanged. Its purpose is SESSION-RESOLUTION bypass, not browser avoidance. Route interception makes the browser reachable with no production change at all, but both bulk paths first call active_verified_session, which runs AeatAccessGate.require_live_read. Under pytest that refuses unless CADRUMO_LIVE_TESTS_ENABLED is the literal 1, and it then drives ensure_authenticated_aeat_session, the central live-session writer needing an active bucket and real credentials. Satisfying that gate rather than bypassing it would ARM real AEAT access, so the seam is what lets the test never request live access in the first place. This is also why the existing navigation-timeout test needs no seam: it drives _drive_search with its own page and never resolves a session. Gate: a test passes a REAL DeclaracionesRegisterSession, never a stub or a patched production path, over route-intercepted synthetic fixtures with no AEAT contact, arranges one query pair truncated and another complete, and asserts the truncated pair becomes a FiledDataCaptureFailureRow while the complete pair still yields rows. Gate on the property, never on a pair count. This closes a gap wider than truncation, since no failure kind currently has coverage of the sweep continuing past a failed pair
- `2026-08-07-declarations-register-pagination-S07` - Cover the register walk end to end offline, closing the browser-shell exclusion S02 records. The chain is reachable because nothing in it must behave like the ZK app, only be present, visible and clickable: route interception fulfils the real listing URL so the post-Buscar landing assertion still sees an AEAT url, a static composite fixture carrying the Modelo and Ejercicio labels, the combobox buttons, visible comboitem texts, a Buscar button and the listbox satisfies the form-render check and both combobox drives, and the Buscar click needs no response because the same document already carries the result rows. Gate: a test drives the real walk entry point against that fixture through a real headless browser with no AEAT contact and asserts the truncation refusal surfaces from walk itself, plus a companion asserting the real no-pager capture returns its rows. The new fixture declares synthetic_generated provenance in its sidecar
- `2026-08-07-declarations-register-pagination-S09` - 2026-08-07-declarations-register-pagination-S09

### plan

- `2026-08-07-declarations-register-pagination-plan` - `declarations-register-pagination` plan

### reference

- `2026-08-07-declarations-register-pagination-reference` - `declarations-register-pagination` reference: `Declaraciones register pagination blindness`
