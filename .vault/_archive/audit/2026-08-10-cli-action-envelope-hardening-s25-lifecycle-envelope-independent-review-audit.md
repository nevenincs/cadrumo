---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:afc08f00153de672177937fe1a481d83fb0a51d7e3e7c09de251367e3cc4ec7f'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---
# `cli-action-envelope-hardening` audit: `S25 lifecycle envelope independent review`

## Scope

Independent review of `W04.P07.S25` after implementation. The review examined the lifecycle continuation producer, typed refusal registry, selector/addressing split, calculation and import consumers, CLI error transports, locale catalogue coverage, and real command journeys.

## Findings

### canonical-lifecycle-guard | high | discarded-state policy had consumer redeclarations

The earlier shape held discarded-state checks and refusal presentation in multiple calculation, aggregation, import, selector, and CLI routes. The resolved shape places state/addressability facts and calculate/import operation identity in `src/cadrumo/application/modelo/_work_lifecycle.py`; downstream consumers delegate rather than reproduce the predicate or recovery outcome. Semantic code search returned that guard and its operation mapping; targeted `rg` found production discarded-state predicates only in lifecycle ownership after remediation.

### typed-terminal-transport | high | adapters previously erased declared terminal verdicts

Calculate, filing-record import, rename, repeat-discard, and wizard paths can now rethrow typed lifecycle errors to the common error boundary. The boundary emits the same structured terminal action record in text and JSON. The review confirmed `REFUSED_MODELO_WORK_UNIT_ALREADY_DISCARDED` and `REFUSED_MODELO_WORK_UNIT_MUTATION_REFUSED`, category `REFUSED`, no default suggestion, and refusal exit family two.

### natural-key-addressability | high | discarded targets could be hidden before their refusal

Natural-key resolution is inclusive for status, history, and guarded calculation. Create-or-reuse uses the explicitly active natural selector, which proceeds to canonical create refusal for a discarded identity rather than treating the old record as reusable. This preserves audit visibility and makes the impossible next action explicit.

### locale-neutral-action-chain | medium | action prose could drift from executable schemas

The reviewed output has no application-level hardcoded command suggestion for these lifecycle refusals. Four catalogue locales render factual state messages while structured action data is sourced from declared precondition profiles and live operator schemas. Locale inventory contains calculate, import, and year-period mismatch keys.

### verification-boundary | medium | broad failures are not S25 evidence

The independent real CLI journey is green: three integration journeys passed in 100.68 seconds. Twenty-five related application and authority tests are recorded as passing in reviewer evidence. Targeted Ruff, formatting, compile, and owned selector/addressing basedpyright checks are green. The broader legacy CLI strict gate still has 70 established diagnostics, and unrelated `ErrorCode` default-suggestion churn can abort broad collection. Prior M303 revision, Justificante CSV, and M349 corpus failures remain external boundaries.

## Recommendations

- Keep future lifecycle verbs on the declared precondition profile and canonical lifecycle guard; do not add command strings or duplicate discarded-state predicates in adapters.
- Treat the broad CLI strict type lane and external registry/corpus fixture churn as follow-up work owned outside S25; do not weaken terminal-refusal schema requirements to accommodate them.
- Run equivalent real JSON and text journey checks whenever a lifecycle verb gains a new mutable state or a new transport.
