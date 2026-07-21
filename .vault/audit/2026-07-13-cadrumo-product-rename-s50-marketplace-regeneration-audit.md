---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s50-marketplace-regeneration'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-12-cadrumo-cli-executable-adr]]"
---

# `cadrumo-product-rename-s50-marketplace-regeneration` audit: `S50 marketplace regeneration review`

## Scope

Independently reviewed commit `0910ae716b9b8e9712f2ffd7d4c1daa2834ba669`
against the accepted product-identity tuple and S50 generation contract. The
review covered generator-only scope, clean-tree byte parity, repeated-generation
idempotence, exact contextual and machine identities, focused tests, direct
strict validators, the `.gitignore` authority correction, plan and execution
record truth, and exclusion of README and ignored served-plugin output. No
implementation fixes were made.

## Findings

No actionable findings.

## Recommendations

PASS. A fresh `materialise_marketplace` emission contains exactly 58 generated
files and matches the in-place marketplace manifest plus served plugin
byte-for-byte. A second emission into the same clean destination again contains
58 files with zero path or SHA-256 delta, independently proving idempotence.
The focused plugin and marketplace slice passes all 14 real-filesystem tests,
including checked-scaffold parity and the two live strict-validator tests.
Direct `claude plugin validate --strict` calls also accept both the marketplace
root and the served plugin.

The checked manifest uses sentence-prose `Cadrumo` and identity-context
`CADRUMO`. The ignored plugin uses exact `CADRUMO` display and author identities,
`Cadrumo` prose, `cadrumo` plugin and server identifiers, the
`cadrumo[agent]` distribution, `cadrumo-mcp`, and only `CADRUMO_MCP_*` product
environment keys. The `.gitignore` comment correctly names the public
`cadrumo.agent.materialise_marketplace` generation authority and retains the
contract that `plugins/` is generated, ignored, and never committed.

The pinned commit contains only the checked marketplace manifest, the valid
`.gitignore` authority correction, the S50 execution continuation, and the plan
checkbox. It contains neither README nor ignored served-plugin files and passes
scoped whitespace validation. The plan closes S50 while leaving S51 open. The
append-only continuation accurately records the current regeneration and
supersedes the earlier historical version and worktree notes without claiming
the ignored validation tree as committed output.
