---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S122'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W05.P17.S122` Final blast-radius classification matrix

Step scope: `.vault/exec/2026-06-04-modelo-addressing-ux`.

## Classification Matrix

| Surface | Classification | Closure evidence |
| --- | --- | --- |
| `src/aeat/application/modelo/_selectors.py` | Natural-key selector boundary. Exact raw IDs retained as advanced addressing. | Selector tests and application lifecycle tests passed. |
| `src/aeat/application/modelo/_revision_persistence.py` | Current/filed pointer semantics. Internal IDs remain authoritative. | File-flow and export tests passed. |
| `src/aeat/application/modelo/_export.py` | Exportability policy and revision selection. Exact revision ID retained for machine/exact use. | Export application and CLI tests passed. |
| `src/aeat/application/modelo/_reconcile.py` | Evidence reconciliation service. Work unit identity remains internal service input. | Reconcile application and CLI tests passed. |
| `src/aeat/application/modelo/_history.py` | Lifecycle audit surface. Work unit ID retained for exact audit/history. | History application and CLI tests passed. |
| `src/aeat/application/modelo/_taxation_comparison.py` | Adjacent comparison service. Exact work-unit access retained for advanced comparison. | Taxation comparison tests passed. |
| `src/aeat/application/modelo/_result_summary.py` | Structured result summary. IDs retained for machine/audit output. | Covered through CLI modelo work/export payload tests. |
| `src/aeat/application/state_projection.py` | State-projection ID linkage. Internal IDs retained as projected state fields. | State projection tests passed. |
| `src/aeat/entrypoints/cli/_modelo.py` | Common operator path now resolves by active profile plus modelo/year/period. Exact IDs remain escape hatches. | Focused CLI and broader CLI abstraction tests passed. |
| `src/aeat/entrypoints/cli/_modelo_payloads.py` | Structured output contract. IDs retained for machine consumers and compatibility. | Payload tests passed. |
| `src/aeat/locales/*.yml` | Help and error text. Stale common-path raw-ID guidance removed; exact-ID help retained. | Locale stale-guidance scan and locale guard tests passed. |
| `docs/**/*.md` narrative docs | User education. Common path now teaches modelo/year/period targeting. | Exact raw-ID docs scan, strict page builds, and docs conformance tests passed. |
| `docs/cli/*.rst` generated reference | Live CLI reference. Raw ID arguments remain where commands still expose exact addressing. | Generated reference drift and conformance tests passed. |

## Outcome

The final blast-radius classification separates retained internal/exact-ID surfaces from the normal operator workflow. No remaining narrative docs or locale workflow guidance requires copying raw `work_unit_id` or `calculation_revision_id` values for calculate, verify, file, export, or reconcile.
