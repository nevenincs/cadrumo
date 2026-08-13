---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:ae67ad22a0a3faa8f3075f4d065876434bc16bfc6b2738327095b50b6137145b'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
