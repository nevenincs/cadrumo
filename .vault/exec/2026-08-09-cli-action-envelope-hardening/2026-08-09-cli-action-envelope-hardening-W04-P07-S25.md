---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:c70bc6eb72f56bc221707f470afc1497dc1d8334df2f10a3b3dd15b13c0c0528'
step_id: 'S25'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Replace lifecycle suggestion construction with resolved typed action notices

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`

## Description

- Grounded the action-envelope change with semantic vault and code searches, then confirmed declarations, consumers, and rejected-state predicates with targeted `rg` and AST-oriented authority checks.
- Replaced lifecycle-only continuation and refusal guidance with application-owned `PreconditionVerdict` records and schema-resolved terminal outcomes.
- Centralised discarded work-unit addressability and refusal facts in `src/cadrumo/application/modelo/_work_lifecycle.py`; calculation, aggregation, and filing-record import delegate to that guard.
- Made natural-key reads inclusive for status, history, and guarded calculation while keeping create-or-reuse explicitly active-only, so a discarded target reaches its canonical terminal refusal instead of being hidden or reused.
- Preserved typed lifecycle refusals through calculate, import, rename, repeat-discard, and wizard CLI adapters; kept genuine not-found handling as parameter validation.
- Reclassified terminal lifecycle errors as canonical `REFUSED_*` registry outcomes without a default suggestion and removed stale raw-action census debt.

## Outcome

- The action chain is derived from declared profiles and live schemas; terminal states carry `action: null`, empty bindings, exact evidence, and `no_recovery_outcome: terminal` rather than command prose.
- Three isolated real CLI integration journeys passed in the independent reviewer run in 100.68 seconds. They cover discarded status and history by natural key, direct and natural calculate, retry-create, rename, repeated discard, filing-record import, locale rendering, terminal wire DTOs, and unchanged persisted state.
- Twenty-five related application and authority tests passed in the reviewer evidence set. Targeted Ruff, formatting, compile, and the owned selector/addressing basedpyright lane passed.
- Locale handling is catalogue-backed and locale-neutral: the four supported output locales render factual terminal messages while action metadata remains schema-derived.

## Notes

- The broader legacy CLI strict basedpyright lane remains red with 70 pre-existing private-import and unknown-type diagnostics outside this step's reviewed changes.
- A separate global `ErrorCode` registry churn requires `default_suggestion` on unrelated registrations and can abort broad import/test collection. Earlier unrelated blockers also include stale M303 revision fixtures, invalid Justificante fixture CSV text, and M349 corpus validation. These boundaries are recorded rather than masked, bypassed, or reclassified as S25 success.
