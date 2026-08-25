---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f4598be5ad5743fe8f67c21ef6b142e47f7104ce5b8ff339948abf4880ed6c92'
step_id: 'S247'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Resolve changed-surface Ruff import order and partition every remaining type diagnostic to its owning implementation or fixture until the scoped global proof is clean

## Scope

- `src/cadrumo/ and src/cadrumo-harness/ and dev/`

## Description

- Trace campaign quality ownership with Vaultspec RAG, the W06.P12 plan scopes, execution records, and the exact Python paths changed by their commits.
- Run Ruff and ty over the broad product, harness, and developer-tool trees to partition current diagnostics by campaign and concurrent owner.
- Prove the exact 41-file campaign surface, including profile custody, observability, sequence parsing and comparison, CLI action census, and harness MCP paths.
- Narrow masked sequence envelopes through runtime mapping checks before structural comparison.
- Narrow schema-derived regex metadata through a runtime string check before returning it from the parser test helper.
- Declare every campaign census AST visitor override explicitly through the standard typing contract.
- Run focused behavioral suites and submit the bounded repair for independent formal review.

## Outcome

The exact 41-file W06.P12 Python surface passes Ruff and ty with no diagnostics. Sequence comparison now proves both recursively rebuilt mask results remain mappings at runtime before canonicalisation and path diffing, while the schema-pattern test proves Pydantic metadata supplies a string before returning it. Every campaign-owned AST visitor override is explicitly declared without casts, ignores, configuration exclusions, or diagnostic baselines. The focused behavioral lanes pass 91 tests.

## Notes

- A broad diagnostic inventory over `src/cadrumo`, `src/cadrumo-harness`, and `dev` reported 22 Ruff findings and 942 ty diagnostics. Ruff findings belong to the active uncommitted TUI-secret relocation; the remaining ty inventory spans unrelated repository fixtures, entrypoints, registry, and agent-evaluation surfaces. None is on the exact campaign file set after this repair.
- The reproducible surface is the sorted, existing `.py` union from `git show --pretty= --name-only` over campaign implementation commits `67b72d4afd`, `022da104e0`, `2ec2921fd1`, `f7694d3ae2`, `98f34aa7b01`, `2be1f36529`, `6e9b859b3f`, `c3ecef84dd`, `c890ecea4b`, and `a2393b74ee`. This yields 41 files. The commits respectively own S237 harness guidance, S238 profile deletion, S239 golden masking, S240 parser/result expectations, S241 comparison, S245 quality/harness recovery, and S246 watchdog lifecycle.
- The shared worktree commit `04ea7186d0` captured three S247 implementation files alongside independently owned CI and locale work while verification was running. This is recorded as concurrent split provenance; the closing commit owns the corrected S240 parser-test narrowing and S247 lifecycle records and does not rewrite or revert the shared commit.
