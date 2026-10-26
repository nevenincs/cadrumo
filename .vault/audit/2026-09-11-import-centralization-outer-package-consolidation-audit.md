---
tags:
  - '#audit'
  - '#import-centralization'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:bf93571f5fa8f2a2e5007cc032caa66ae31a109f809b5d28eb650a991513f7c9'
related:
  - "[[2026-09-11-import-centralization-import-authority-drift-audit]]"
---

# `import-centralization` audit: `Outer-package consolidation and canonical imports review`

## Scope

The review covered the outer-package consolidation and canonical-import work for
the relocated outbound LLM adapter, the separately shipped harness, adapter
facades, CLI/TUI boundaries, package initializers, and literal dynamic targets.
It was grounded in the import-centralization ADRs, the approved W07 plan, and
the import-authority drift audit.

## Findings

### harness-entrypoint-dependency | high | The retained harness still consumes CLI entrypoint implementation

The retained MCP composition root has supported behavior and is therefore the
correct hard disposition, but its production modules still import
`cadrumo.entrypoints.cli` contracts and adapter composition, while harness tests
still reach `cadrumo.tests`. The independent composition-root disposition is not
closed until LANE 1 supplies inward command/schema/policy and adapter-composition
contracts and the harness consumers move to them.

### llm-error-registry | high | The relocated LLM errors are not yet registered at their canonical paths

The old `cadrumo.llm` implementation is deleted and the target package imports
from its new canonical modules, but the core error-code registry still lacks the
relocated `cadrumo.adapters.outbound.llm.errors` entries. Importing the CLI's
LLM-dependent command graph therefore fails closed with the registry's missing
entry error. LANE 1 owns the inward registry and application/shared consumers.

### deferred-target-absolute-paths | medium | Finite dynamic command targets still use the old absolute representation

The owned literal `import_module` and raw first-party `__import__` probes were
converted to package-anchored relative targets and the command-schema probe now
uses the shared resolver. The remaining command graph contains 437 literal
`DeferredTarget` first-party module strings whose representation is absolute and
whose resolver has no package anchor. LANE 3 owns the closed resolver/checker
support and must migrate this finite target population without a compatibility
path.

### external-consumer-residue | medium | Repository-only tooling still names retired outer paths

Development packaging/evaluation consumers still refer to the deleted
`cadrumo.llm` namespace, the retired adapter package facades, and the former
`cadrumo_harness.mcp:main` target. Those consumers are outside this lane's
permitted edit set and require LANE 3/tooling-owner migration before the global
residue and installed-artifact gates can reach exact zero.

### entrypoint-imports-outside-root | high | Application and shared-test modules still reach entrypoint modules

The resolved-import audit found 13 imports from outside `cadrumo.entrypoints`
into `cadrumo.entrypoints.operation_composition` or CLI modules. They are
concentrated in application tests and shared CLI helpers; they are not part of
the owned outer-package rewrite and require LANE 1 to move the exercised
contract inward or relocate the test seam.

## Recommendations

Close `harness-entrypoint-dependency` by replacing the listed CLI and adapter
composition imports with the inward contracts supplied by LANE 1; keep the MCP
console script as the independent outer root.

Close `llm-error-registry` by registering the canonical relocated error classes
and repointing all inward consumers in one atomic handoff.

Close `deferred-target-absolute-paths` and `external-consumer-residue` through
the authoritative dynamic resolver and tooling migration, then rerun the exact
zero import and installed-wheel checks.

Close `entrypoint-imports-outside-root` by handing the shared operation and CLI
contracts inward and removing the application/test reaches in the same lane
graph migration.
