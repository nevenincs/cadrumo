---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:c9262efdb89a1577f496483971aa7504e0203c7f769c574b31efb10c0d29c567'
step_id: 'S14'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Build the generated legal reference surface rendering per-law pages with per-provision anchors from one shared slug authority, each entry carrying its BOE permalink and catalogue metadata

## Scope

- `dev/docs/`

## Description

- Add a registry-backed legal reference generator with one page per legal
  document, provision anchors, site-relative HTML targets, and BOE grounding.
- Hook legal-reference generation into the documentation builder and register
  the generated legal index in the root reference toctree.
- Fail closed on schema drift, unsafe authored text or links, reserved slugs,
  output collisions, and stale generated pages; accept omitted optional fields
  without inventing metadata.
- Re-review the final source against the accepted ADR and P05 plan.

## Outcome

The source implementation was delivered through commits
`289a3e1020e4d349a96d872f70ea7ae018c88006`,
`a71beada259b251af41cd3bdc2c59f3376bf2412`, and
`46d1a42d7d85a9f0cb32e809b57baefa6b483307`. The final formal review returned
PASS with no blocking source findings. `vaultspec-rag` semantic searches
grounded the accepted ADR, the active P05 plan, and the P05.S14 audit; exact
current source was then retrieved with `get_code_file`.

## Notes

The code-search MCP alias remains unavailable because the `codebase` source
alias is rejected; this is tracked in vaultspec-rag issue #350. No reindex or
bypass was attempted. No tests, builds, Pagefind runs, live probes, deployment,
or other runtime gates were run. S14 remains open for the authorized runtime
and documentation-build acceptance; P05.S15-S17 remain outstanding.
