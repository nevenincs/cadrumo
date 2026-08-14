---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:a4526de88138ef3cdbb13fae1f5c3f13e5091a3257e12bd07eed06f4e1157603'
related: []
---

# `tui-architecture` audit: `s15 review`

## Scope

Independent review of `W02.P03.S15`, limited to the claimed fixed-point census across production operation definitions, canonical recovery actions/catalogue, and exposed frontend projections.

## Findings

### fixed-point-scope | critical | A hand-built singleton cannot prove the mandated production fixed point

D8 requires a census joining operation definitions, TUI actions, CLI and MCP projections, executor factories, direct mutation/outbound sites, and exclusions, with every exposure and claim joined exactly once. The test constructs one synthetic `OperationDefinition` for a cherry-picked filed-history action and asserts its self-declared frontend enum set. It enumerates none of the production catalogue, recovery-action producers, exposed surface inventories, operation definitions, direct mutation sites, or exclusions. The execution record explicitly acknowledges that no production operation-definition catalogue exists, which means the fixed point cannot yet be proved; narrowing the step to a representative row contradicts the plan and ADR.

### mirrored-operation-fixture | high | The test invents the future operation and executor contract it claims to verify

`FiledHistoryRequest`, `FiledHistoryResult`, `FiledHistoryExecutor`, its factory, capabilities, phases, reconciliation, and projection permissions are all locally authored test substitutes for the W03 production definition. This is a minimal executor shortcut and mirrors future business/registration facts instead of importing the production authority. Consequently the green assertion proves only that the test's own declarations agree with themselves.

### mutation-completeness | high | Only unknown catalogue identity is refused

The sole mutation changes the synthetic definition to an unknown action and checks two catalogue lookups. There is no production-set mutation for orphan action, missing operation definition, duplicate mapping, missing recovery producer, missing CLI/MCP/TUI projection, projection claim without a real surface, or executor-factory/direct-mutation bypass. The test cannot detect the fixed-point failures D8 lists.

### gates | low | Two passing tests are honest only for the narrow sample

Ruff, basedpyright, and two focused pytest cases are green. They do not compensate for absence of the production census or mutation-sensitive coverage.

## Recommendations

- Do not close S15 until a production-owned operation-definition inventory exists; if plan ordering makes that impossible, amend the authorizing plan rather than weakening the fixed-point claim.
- Build the census from production authorities and their complete identity sets, without local request/result/executor/capability mirrors.
- Add independent planted mutations for every missing/orphan/duplicate projection, action, definition, recovery, factory, mutation-site, and exclusion edge required by D8.
- Rerun exact gates against the resulting real-tree census.
