---
tags:
  - '#audit'
  - '#renta-calculation-pipeline-coverage'
date: '2026-05-08'
modified: '2026-05-08'
related: []
---

# `renta-calculation-pipeline-coverage` audit

Baseline coverage report for the registry's calculation pipelines as
of 2026-05-08, captured before the renta-cuota-integra-autonomic-scale
work continues to land per-CCAA bracket schedules. Numbers below reflect
the registry tree at the audit timestamp.

## Headline numbers

| metric                                    | count  |
| ----------------------------------------- | ------ |
| modelos in the registry                   | 25     |
| total formulas declared                   | 1 027  |
| total parameter declarations              | 87     |
| total bindings declared                   | 904    |
| total relations declared                  | 38     |

Formula op distribution:

| op                | count  |
| ----------------- | ------ |
| `sum`             | 507    |
| `subtract`        | 184    |
| `percent`         | 72     |
| `copy`            | 65     |
| `max`             | 64     |
| `min`             | 62     |
| `if_then_else`    | 31     |
| `add`             | 30     |
| `lookup_bracket`  | 12     |

The 12 `lookup_bracket` formulas are the IRPF state-scale wirings
landed across Modelo 100 revisions 2020-2025 (2 per revision × 6
ejercicios). The autonomic counterpart (`lookup_bracket_by_ccaa`) ops
appear only in unit tests today; the per-CCAA per-year formulas have
not yet landed (tracked in `#33`-`#40`).

## Coverage status per modelo

Three coverage signals carried by every revision:

- `workbook_parity_refs` — pin the revision's calculation against the
  AEAT-published workbook (cent-level oracle).
- `verification_expectations` — declare scenario-level invariants the
  formula evaluator must satisfy.
- formula count — proxy for calculation density.

| modelo  | revisions | formulas | bindings | parameters | relations | workbook_parity | verification |
| ------- | --------- | -------- | -------- | ---------- | --------- | --------------- | ------------ |
| 100     | 6         | 918      | 48       | 72         | 9         | yes (per rev)   | none         |
| 111     | 1         | 2        | 0        | 0          | 0         | yes             | yes          |
| 115     | 1         | 2        | 0        | 1          | 0         | yes             | yes          |
| 123     | 2         | 7        | 0        | 0          | 0         | yes (per rev)   | yes (per rev)|
| 130     | 1         | 10       | 1        | 2          | 0         | yes             | yes          |
| 131     | 4         | 24       | 298      | 8          | 0         | yes (per rev)   | yes (per rev)|
| 180     | 2         | 6        | 6        | 0          | 6         | yes (per rev)   | yes (per rev)|
| 184     | 1         | 0        | 0        | 0          | 0         | yes             | yes          |
| 190     | 1         | 3        | 19       | 0          | 19        | yes             | yes          |
| 193     | 1         | 3        | 3        | 0          | 3         | yes             | yes          |
| 200     | 1         | 1        | 1        | 1          | 1         | yes             | none         |
| 202     | 3         | 35       | 0        | 3          | 0         | yes (per rev)   | none         |
| 232     | 2         | 0        | 434      | 0          | 0         | yes (per rev)   | yes (per rev)|
| 303     | 1         | 3        | 5        | 0          | 0         | yes             | none         |
| 308     | 1         | 0        | 0        | 0          | 0         | yes             | none         |
| 309     | 1         | 1        | 2        | 0          | 0         | yes             | none         |
| 322     | 1         | 3        | 5        | 0          | 0         | yes             | none         |
| 347     | 1         | 0        | 0        | 0          | 0         | yes (×2)        | yes          |
| 349     | 1         | 0        | 17       | 0          | 0         | yes             | none         |
| 353     | 1         | 3        | 5        | 0          | 0         | yes             | none         |
| 360     | 1         | 0        | 0        | 0          | 0         | yes             | none         |
| 369     | 3         | 3        | 5        | 0          | 0         | yes (per rev)   | none         |
| 390     | 1         | 3        | 8        | 0          | 0         | yes             | none         |
| 720     | 1         | 0        | 43       | 0          | 0         | yes             | yes          |
| 840     | 1         | 0        | 0        | 0          | 0         | yes             | yes          |

## Findings

### 1. Verification-expectations coverage gap

11 modelos carry zero `verification_expectations` even when they
declare formulas: 100, 200, 202, 303, 308, 309, 322, 349, 353, 360,
369, 390. Modelo 100 in particular carries 918 formulas with only
workbook parity as the cent-level gate; verification expectations
would catch chain-shape regressions (e.g. cuota integra ≥ 0,
deducciones ≤ cuota, base liquidable ≤ base imponible). Tracked as a
follow-up audit-driven task.

### 2. IVA cuota chain depth is shallow

Modelos 303 / 322 / 353 / 369 / 390 each carry only 3 (or 1) formulas.
The IVA cuota chain is inherently simpler than IRPF, but this depth
suggests the IVA modelos are wired only at the cuota-totals layer
without intermediate breakdown formulas. A separate stream is the
right place to assess whether deeper formula coverage is needed for
parity with AEAT's published cuota chain.

### 3. Modelo 232 + 720 are pure-binding modelos

232 declares 434 bindings, 0 formulas. 720 declares 43 bindings, 0
formulas. Both are informational declaration modelos (no cuota
calculation). Workbook parity + verification expectations are present
on both, which is appropriate for declaration-only modelos.

### 4. Autonomic-scale chain pending (already tracked)

Casillas 0529 and 0531 across Modelo 100 revisions 2020-2025 are
manual-input today because the per-CCAA bracket parameters and the
`lookup_bracket_by_ccaa` formulas have not yet landed (the runtime
op landed at `2e964ff7`; per-CCAA wiring tracked in tasks
`#33`-`#40`). 90 (15 CCAA × 6 ejercicios) bracket parameters and 12
(2 casillas × 6 ejercicios) formulas need to land to close this
chain.

### 5. Modelo 100's workbook_parity_refs are single-coverage per revision

Every Modelo 100 revision carries exactly one workbook_parity_ref —
an aggregate cuota-chain-authority pin. Per-formula breakouts (e.g.
"this specific 0532 subtract closure") are not pinned individually.
That is structurally appropriate for the cuota chain (the chain only
makes sense end-to-end), but it means a formula-level regression
that produces a compensating downstream error would not be caught by
parity alone. The chain-behaviour scenario tests partly cover this
gap; expanding scenario coverage is the natural next stream.

## Pending work captured as backlog tasks

- `#33`-`#40` — autonomic-scale chain (15 CCAA × 6 ejercicios)
- `#42` — this audit (the present document)
- new `#43` — verification-expectations coverage (modelos 100 / 200 /
  202 / 303 / 308 / 309 / 322 / 349 / 353 / 360 / 369 / 390)
- new `#44` — Modelo 100 chain-behaviour scenario expansion
  (per-CCAA scenarios, per-deduction-stream scenarios)

## Method

Per-modelo formula / binding / parameter / relation counts were
collected by loading the registry tree via
`aeat.domain.calculations.registry.load_registry_tree` and inspecting
each `ModeloRevision`'s declared collections. Op-distribution counts
walk every formula's `expression.op`. Workbook parity and
verification counts read `revision.workbook_parity_refs` and
`revision.verification_expectations`. The audit was produced
mechanically from the live registry; numbers reflect the registry
tree at commit `328900d0`.
