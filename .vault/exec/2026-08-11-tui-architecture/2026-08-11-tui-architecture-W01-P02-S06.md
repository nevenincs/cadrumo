---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b37320b52a4b326237caa2a14d6e2640e98820bba61a0bfb4a159fcd6469827c'
step_id: 'S06'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
---
# Implement the closed operation lifecycle, terminal, effect, durability, cancellation, deadline, close-policy, event, and interaction axes

## Scope

- `src/cadrumo/core/operations.py`
- `src/cadrumo/core/tests/test_operations.py`

## Description

- Ground the generic operation vocabulary in the accepted TUI architecture decision and research through semantic RAG, then confirm the exact closed sets from the lifecycle, settlement, capability, event, interaction, and close-policy clauses.
- Establish one frontend-neutral core module containing value types only and importing no application, adapter, entrypoint, domain, persistence, or presentation layer.
- Keep domain-specific reset, workflow, sync, and presentation lifecycles in their existing canonical homes rather than redeclaring or merging them into the generic operation contract.
- Prove every accepted token hydrates to its exact `StrEnum` member, serialises without translation, and rejects unknown frontend-invented state.

## Outcome

`cadrumo.core.operations` is now the sole canonical home for nine generic operation axes: lifecycle, terminal condition, committed effect, durability, cancellation, deadline, close policy, event kind, and interaction kind. The module contains only closed `StrEnum` value sets plus its explicit module export list. It has no dependency on an outer architectural layer and introduces no state machine, model shell, compatibility path, or duplicate domain lifecycle.

The concurrently modified `cadrumo.core` package facade was deliberately left untouched. S06 owns the canonical module itself; facade promotion can occur only through an authorized step after the shared facade is clean.

## Notes

Canonical-home and duplication adjudication:

- Configuration-reset and workflow lifecycle enums remain operation-specific authorities, not substitutes for the three independent generic operation axes.
- Observability retains log-capture and diagnostic-envelope authority; `OperationEventKind` classifies safe operation facts without creating a second logging system.
- Deadline-domain types retain tax-calendar meaning; `OperationDeadline` expresses only the supervisor capability guarantee.
- Apply and reject remain typed interaction presentation families; no callback, request model, or response-token implementation was pulled forward from later plan steps.

Focused verification:

- `uv run --no-sync ruff check src/cadrumo/core/operations.py src/cadrumo/core/tests/test_operations.py` - all checks passed.
- `uv run --no-sync pytest -q -n 0 src/cadrumo/core/tests/test_operations.py` - 18 passed in 0.86 seconds.
- `uv run --no-sync basedpyright src/cadrumo/core/operations.py src/cadrumo/core/tests/test_operations.py` - 0 errors, 0 warnings, 0 notes.
- `uv run --no-sync lint-imports` - exit 1 before contract evaluation because three unrelated stale ignored-import declarations no longer match: `_prorrata_regularizacion`, `_renta_ledger`, and `_iva_ledger` to `cadrumo.adapters.persistence.profile.prorrata_register`. S06 adds no ignored import and its production module imports only `enum.StrEnum`.

Standing status: focused unit, lint, and type gates are green. The repository import-linter command remains red on unrelated pre-existing stale ignore configuration. S06 remains open and uncommitted pending independent review.

Mechanical closeout verification:

- `uvx vaultspec-core vault check all` - exit 0 in 25.4 seconds with 1,315 warnings and no errors. The warning inventory was one S06 audit-template annotation warning, two Markdown warnings, eight feature-index or missing-ADR warnings, 54 execution-mapping warnings, 1,220 body-section warnings, 29 schema warnings, and one unrelated modified-stamp warning. The two generated comment blocks identified in the S06 audit were stripped afterward through the sanctioned vault edit path; all other warnings are outside this Step.
