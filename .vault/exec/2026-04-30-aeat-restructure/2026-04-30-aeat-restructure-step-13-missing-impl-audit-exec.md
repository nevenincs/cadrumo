---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-research]]"
---

# 2026-04-30-aeat-restructure step-13 missing-implementation audit

## status

Step 13 audit complete. The new layout was scanned for the five gap
categories enumerated in the plan; findings disposition follows.

## audit methodology

- **Tool**: `Grep` (ripgrep-backed) for pattern-based gap detection
  + manual classification of every hit. Subagent did not use
  `Explore`-class semantic search because the gap signatures are
  syntactic (literal `raise NotImplementedError`, missing files
  matching naming patterns, enum-value declarations).
- **Scan depth**: Full `src/aeat/` tree under the new layered
  layout post-#493 keystone merge.

## gap-category findings

| category | findings | disposition | issue |
|----------|----------|-------------|-------|
| Hard gap (production-reachable `raise NotImplementedError`) | 4 sites; all documented intentional refusals | STRIKE | #500 (closed as STRIKE) |
| Coverage gap (modelo with no ruleset for required year) | Modelo 202 missing 2024 + 2026 | FILE | #498 |
| Casilla gap (catalogue-declared casilla without formula or input-only declaration) | 4 casillas in Modelo 303/2024 already locked under `_EXPECTED_GAPS` | FILE | #499 |
| Stub gap (empty function body + caller) | 0 found | n/a | n/a |
| Placeholder gap (enum value reserved + actively rejected by validator) | 0 found post-Phase-1 cleanup (SchemaSource slots removed in #482) | n/a | n/a |

## hard-gap detail (all STRIKE)

Every `raise NotImplementedError` in the new layout is an intentional
documented refusal, not a missing implementation:

| file:line | classification |
|-----------|----------------|
| `src/aeat/adapters/outbound/aeat/sede/_walker.py:204` | Guard: `fetch_justificante_pdf` is wrapped by `capture_justificante`; primitive exposed for testing only |
| `src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py:85` | Refusal: HTTPX_FALLBACK is verify-only by design; no browser path possible |
| `src/aeat/adapters/outbound/aeat/auth/_providers.py:329` | Refusal: CLAVE_PERMANENTE not offered by AEAT Sede Electrónica today |
| `src/aeat/adapters/outbound/aeat/auth/_providers.py:333` | Enum-fallback: defensive guard for future enum extensions |

## umbrella-issue cap audit

The plan caps Step 13 at 5 umbrella issues + N individual hard-gap
issues. Actual filing:

- 2 umbrella issues filed (#498 coverage gap; #499 casilla rollup)
- 1 hard-gap audit issue filed and immediately STRUCK (#500)
- 0 individual hard-gap issues required (no real hard gaps surfaced)

Total: 3 issues filed, well under the 5-umbrella cap.

## acceptance

The plan's Step 13 acceptance criteria:

- [x] Every gap has a disposition (STRIKE / FILE / FIX)
- [x] Every FILE-disposition gap has a GitHub issue link recorded
- [x] Issue board reflects the filed issues
