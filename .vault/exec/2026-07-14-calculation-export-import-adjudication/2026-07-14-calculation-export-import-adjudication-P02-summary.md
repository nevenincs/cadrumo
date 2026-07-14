---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# `calculation-export-import-adjudication` `P02` summary

Phase P02 adjudicated every outbound export-layout candidate without admitting
production implementation. Across 25 separately windowed candidates, 21 are
`mandate-gated`, three are `not-mandated`, and one is `retired`. No candidate
passes all four backlog-admission conditions, so the phase authorizes no
registry layout, binding, renderer, parser, or test implementation.

- Created: the 13 P02 Step Records, `P02.S03` through `P02.S15`.
- Created: this P02 phase summary.
- Modified during Step closure: the parent plan and rolling adjudication audit.
- Unchanged: production source, tests, and registry data.

## Description

The phase reconciled legacy outbound wording with exact registered authority
windows, current registry state, available real evidence, and the canonical
generic export path. A filing link, parity reference, bundled record design, or
missing optional layout was not treated as a product mandate. Every active
candidate lacks a real golden outbound payload and a mutation-sensitive
round-trip for its exact window. That evidence gap remains relevant, but the
taxonomy stops most candidates earlier at the missing mandate.

### Disposition and window coverage

| Step | Candidate window or variant | Exact authority finding | Disposition |
|---|---|---|---|
| `P02.S03` | Modelo 036, `alta`/`modificacion`/`baja`, `2025-02-03` to open end | Definitive `DR036v43.xlsx` covers the window; v42 remains provisional | `mandate-gated` |
| `P02.S04` | Active Modelo 037 outbound support, `2025-02-03` to open end | Suppression authority makes Modelo 036 the active successor | `retired` |
| `P02.S05` | Modelo 184, `2025-01-01` to open end | `aeat-dr-184-2025` covers the window | `mandate-gated` |
| `P02.S05` | Modelo 184, `2015-10-30` through `2024-12-31` | No registered machine-file authority; the 2025 design cannot be projected backward | `mandate-gated` |
| `P02.S06` | Modelo 190 annual `0A`, `2025-01-01` to open end | `aeat-dr-190-2025` covers the window | `mandate-gated` |
| `P02.S06` | Modelo 190 annual `0A`, `2024-01-01` through `2024-12-31` | A 2024 design is bundled and was found structurally identical to 2025, but is not registered exact-window authority | `mandate-gated` |
| `P02.S07` | Modelo 193 annual `0A`, `2025-01-01` to open end | `aeat-dr-193-2025` covers the window | `mandate-gated` |
| `P02.S07` | Modelo 193 annual `0A`, `2024-01-01` through `2024-12-31` | 2024 designs are bundled but not registered, and no accepted 2024/2025 structural-parity finding exists | `mandate-gated` |
| `P02.S08` | Modelo 308 AD-HOC, `2019-01-01` to open end | `aeat-dr-308-2019` covers the window | `mandate-gated` |
| `P02.S08` | Modelo 308 AD-HOC, `2009-01-01` through `2018-12-31` | No exact machine-file authority; form authority does not prove a layout | `mandate-gated` |
| `P02.S09` | Modelo 309 AD-HOC, `2023-01-01` to open end | `aeat-dr-309-2023` covers the window, but no outbound mandate exists | `not-mandated` |
| `P02.S09` | Modelo 309 AD-HOC, `2004-01-01` through `2022-12-31` | No exact machine-file authority and no outbound mandate | `not-mandated` |
| `P02.S10` | Modelo 322 monthly, `2026-01-01` to open end | `aeat-dr-322-2026` covers the window | `mandate-gated` |
| `P02.S10` | Modelo 322 monthly, filing years 2008 through 2025 | No registered exact-window design; the 2026 design cannot be projected backward | `mandate-gated` |
| `P02.S11` | Modelo 347 annual, `2025-01-01` to open end | `aeat-dr-347-2025` covers the window | `mandate-gated` |
| `P02.S11` | Modelo 347 annual, `2011-12-13` through `2024-12-31` | `aeat-dr-347-2011` covers the window | `mandate-gated` |
| `P02.S11` | Modelo 347, exercises 2008 and 2009; registry revision begins `2008-10-23` | A distinct 2008-2009 design is bundled but lacks reviewed registered applicability | `mandate-gated` |
| `P02.S11` | Modelo 347, exercise 2010 | A distinct 2010 design is bundled but lacks reviewed registered applicability | `mandate-gated` |
| `P02.S12` | Modelo 353 monthly, `2026-01-01` to open end | `aeat-dr-353-2026` covers the window | `mandate-gated` |
| `P02.S12` | Modelo 353 monthly, filing years 2008 through 2025 | No registered exact-window design; the 2026 design cannot be projected backward | `mandate-gated` |
| `P02.S13` | Modelo 360, `2010-04-01` to open end | `aeat-dr-360-2010` covers the window, but no outbound mandate exists | `not-mandated` |
| `P02.S14` | Modelo 369 Esquema Union, quarterly, `2021-07-01` to open end | Shared `aeat-dr-369-2021` authority covers this distinct regime | `mandate-gated` |
| `P02.S14` | Modelo 369 Esquema Importacion, monthly, `2021-07-01` to open end | Shared `aeat-dr-369-2021` authority covers this distinct regime | `mandate-gated` |
| `P02.S14` | Modelo 369 Esquema Exterior, quarterly `EXT-1T` through `EXT-4T`, `2021-07-01` to open end | Shared `aeat-dr-369-2021` authority covers this distinct regime | `mandate-gated` |
| `P02.S15` | Modelo 840, `2003-09-19` to open end | `aeat-dr-840` aligns with the registry window | `mandate-gated` |

### No-duplicate-code decision

The current codebase already owns outbound behavior through
`ValidatedRegistryAuthority`, `resolve_export_layout`, `export_draft`, and
`parse_export_payload`. These shared paths select registry data and fail closed
when an applicable revision exposes no layout. The phase therefore records
optional registry-data gaps without proposing a second authority, schema store,
Modelo-specific renderer, submitted-file parser, or archive format. If a
future candidate first gains a proven mandate, exact authority, and real golden
evidence, the only permitted implementation shape is reviewed registry data
plus real-behavior coverage through these existing engines.

### Verification results and limitations

- Intent-first `vaultspec-rag` and exact source inspection grounded the phase
  in the live registry and existing generic engines. Semantic search results
  were treated only as discovery pointers; unrelated hits and timed-out queries
  were not promoted to evidence.
- `P02.S03` records the only completed focused pytest result in this phase:
  the two named Modelo 036 registry/source tests passed, `2 passed in 16.00s`.
- `P02.S04` targeted four real-behavior retirement/refusal tests, but the
  command exceeded 30 seconds before pytest emitted a result. No pass or fail
  is claimed.
- `P02.S05` targeted Modelo 184 registry/window/source tests and the generic
  real round-trip suite, but likewise exceeded 30 seconds without a pytest
  result. No pass or fail is claimed.
- `P02.S06` through `P02.S15` record source, registry, corpus, and test-inventory
  inspection but no completed pytest result. Their adjudication conclusions are
  therefore evidence-backed reconciliation findings, not new executable proof.
- Existing mutation-sensitive fichero round trips cover Modelos 130, 303, and
  390. They prove the generic engine shape but do not prove any P02 candidate's
  exact layout or payload. No P02 record claims otherwise.

### Review corrections

- `P02.S09` was initially committed with an unrelated P03 record and closed
  before independent review completed. The rows were reopened through the
  canonical CLI, the substantive `not-mandated` outcome was accepted, and the
  step was reclosed after review.
- `P02.S11` originally combined the early Modelo 347 gap. Independent review
  established that the corpus contains distinct 2008-2009 and 2010 designs, so
  the final record preserves two separate authority-gap rows. Neither bundled
  design is treated as registered exact-window authority.
- `P02.S14` was corrected to identify Orden HAC/610/2021 article 1 as the
  applicability selector for all three regimes. Article 2 remains a shared
  legal reference, not the selector. The Union, Importacion, and Exterior
  candidates remain separate despite sharing one record-design source.

### Step and commit coverage

All 13 phase rows are checked and all 13 Step Records exist. Commit coverage is
complete, but the history is not uniformly compliant with the plan's
one-Step/one-commit rule:

| Step coverage | Record or closure commit | Traceability assessment |
|---|---|---|
| `P02.S03` | `9fae0e2b8f7` | Dedicated adjudication, audit, and closure commit |
| `P02.S04` | `dd95adfc811` | Dedicated adjudication, audit, and closure commit |
| `P02.S05` | `c26e2c567d3` | Dedicated adjudication, audit, and closure commit |
| `P02.S06` | `8a9e2137d12` | Dedicated adjudication, audit, and closure commit |
| `P02.S07` | `88f1a49e382` | Dedicated adjudication, audit, and closure commit |
| `P02.S08` | `d0393699d6c` | Dedicated adjudication, audit, and closure commit |
| `P02.S09` | `3b814f986ee`, reviewed by `54d8826e63a` | Initial record commit also contains `P03.S22`; review/closure commit also changes the shared audit |
| `P02.S10` through `P02.S15` | `bba1a5c59d5` | Six Step Records share one commit; this violates the one-Step/one-commit execution contract |
| `P02.S11` and `P02.S14` corrections | `45ce61e6ec4` | Review corrections share a commit with audit and P04 corrections |
| `P02.S10` through `P02.S15` closure | `262c1e6e8eb` | Six plan rows were reclosed together after a stale-read reopen |

The grouped history is disclosed rather than normalized retroactively. It does
not change the substantive phase outcome, but it is a process limitation and
must not be represented as 13 clean one-Step/one-commit executions.
