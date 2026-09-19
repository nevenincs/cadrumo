---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:016e33504d7f5df56b5e6cdecb707976cafe6bc55dcbb96383309a92193156a0'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S35 retired authority import gate review`

## Scope

Read-only re-review of the S35 remediation against the accepted facts-registry authority decision, the retirement commits, current canonical IVA and convenio paths, and the full AST import census across `src` and `dev`.

## Findings

### dynamic-and-nested-import-evasion | medium | Resolved: literal runtime imports, alias access, and descendants now refuse

The remediated detector rejects literal `importlib.import_module` and `__import__` targets, including their builtins-qualified forms; it rejects literal `getattr` access to retired convenio symbols through direct, child, and ancestor module aliases; and it treats every descendant of a fully retired module as retired. The mutation test separately proves each route with distinct findings, including parent-module and relative imports plus wildcard access to a partially retained module. The same detector keeps the canonical `convenio_authority_from_facts`, technical external constants, canonical IVA projection, and the explicitly pending IVA grounding path legal.

## Recommendations

Final verdict: CLEAR. Keep the source-and-development AST census in the quality suite. The gate fails closed if an enumerated module cannot be parsed and derives the retired statutory declaration set from its existing ledger; it now provides discriminating proof for every S35 retirement route in scope.
