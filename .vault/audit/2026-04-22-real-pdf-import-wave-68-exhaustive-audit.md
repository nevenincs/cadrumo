---
tags:
  - "#audit"
  - "#real-pdf-import"
date: 2026-04-22
modified: '2026-04-22'
related:
  - "[[2026-04-22-real-pdf-import-wave-48-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-53-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-58-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-60-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-62-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-64-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-66-exhaustive-audit]]"
---

# real-pdf-import — wave 68 exhaustive audit

> **Note (retroactive, wave 70)**: Wave 68 shipped its fixes without
> producing a standalone audit doc. Wave 70 stream 4 flagged the
> contract gap. This doc is reconstructed from the four stream
> reports captured at execution time (see
> `C:\Users\hello\AppData\Local\Temp\claude\...\tasks\a*.output`).

## Scope

Eighth cycle of the exhaustive-audit pattern. Four parallel streams
verified wave 67 (commit `29a537e`) and probed for residuals.

Commit audited: `29a537e`.

| Stream | Verdict | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| 1 wave 67 remediation verification | PASS | 0 | 0 | 0 |
| 2 RIRPF art. 100 structure definitive | DEFINITIVE | 1 | 0 | 0 |
| 3 structural citation-error prevention | RECOMMENDATION | — | — | — |
| 4 deferral-tracking + audit-trail + ruleset drift | REVISION REQUIRED | 2 | 2 | 1 |

## HIGH findings

### H1 (stream 2) — RIRPF art. 100 has NO sub-letter structure

WebSearch against BOE-A-2007-6820 + iberley + supercontable confirmed:

- **art. 100.1** — 19% rate on arrendamientos urbanos
- **art. 100.2** — 60% Ceuta/Melilla reduction

No `.3`, no letters `.a` / `.b` / `.c`. The prior wave-29 audit's
acceptance of `100.3.a` was factually wrong. Corrected in
**wave 67g** (`fe8fa85`) — coordinated cross-file fix across 5 files.

### H2 (stream 4) — Exec-record deferral not tracked

Wave 65d ADR deferral section named an artefact path but no GitHub
issue. Wave 66 H1 flagged as "structurally soft". Confirmed in wave
68 stream 4.

**Closure**: wave 68c (`fe8fa85`) filed [issue #313](https://github.com/wgergely/aeat/issues/313).

### H3 (stream 4) — Modelo 131 production `_CITATIONS` stale

Wave 65a fixed the Modelo 131 test docstrings (art. 110.2 → 110.1.c,
art. 110.4 → 110.1.b) but the production ruleset's `_CITATIONS`
tuple was never swept. Same cross-cutting concern as wave 67g
flagged for 115/180 production `_CITATIONS`.

**Closure**: wave 68a (`fe8fa85`) swept production + 131_2024 clone.

## MEDIUM findings

- **M1 (stream 4)**: Wave 60 + Wave 62 audit docs lack Closure
  status tables. Same anti-pattern wave 66 H2 flagged on wave 64.
  **Closure**: wave 68b (`fe8fa85`) added both tables.
- **M2 (stream 4)**: Wave 64 stream 2 L2 (9 uncovered sub_op chains)
  tagged "wave 65e+" but dropped silently. **Closure**: wave 68c
  filed [issue #314](https://github.com/wgergely/aeat/issues/314).

## LOW findings

- **L1 (stream 4)**: modelos.md row 15 Modelo 130 declaración-import
  cell corrected previously (wave 63c). No action.

## Stream 3 recommendation (non-finding)

Stream 3 proposed a hybrid CITATION_TITLES registry + KNOWN_BAD
blocklist to mechanically prevent future miscites. Positive-registry
half deferred (populating it is subject to the same error mode);
**blocklist half landed as wave 69** (`4fa75da`) with ADR
`.vault/adr/2026-04-22-citation-blocklist-adr.md`.

## Closure status (wave 70)

| Finding | Status | Closing wave |
|---|---|---|
| H1 RIRPF 100 sub-letter structure | CLOSED | wave 67g (`fe8fa85`) |
| H2 exec-record deferral untracked | CLOSED | wave 68c (`fe8fa85`) — issue #313 |
| H3 Modelo 131 production drift | CLOSED | wave 68a (`fe8fa85`) |
| M1 wave 60/62 closure tables missing | CLOSED | wave 68b (`fe8fa85`) |
| M2 9 uncovered sub_op chains untracked | CLOSED | wave 68c (`fe8fa85`) — issue #314 |
| L1 modelos.md row 15 drift | CLOSED | wave 63c |
| Stream 3 structural recommendation | CLOSED | wave 69 (`4fa75da`) |
