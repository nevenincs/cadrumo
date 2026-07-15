---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S50'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Regenerate the marketplace manifest and Cadrumo plugin subtree from the changed authority

## Scope

- `packaging/marketplace generated output`

## Description

- Regenerate the marketplace manifest and ignored served-plugin tree from the committed S48 authority.
- Emit only the `plugins/cadrumo` identity with the pinned Cadrumo distribution and MCP launcher.
- Compare a clean temporary emission byte-for-byte and repeat the in-place emission to prove idempotence.
- Reject former plugin, distribution, executable, URI, and environment identities from generated output.

## Outcome

The checked-in marketplace manifest now points exclusively to
`./plugins/cadrumo`. The generated served plugin is Cadrumo `0.1.1`, launches
`cadrumo-mcp` from `cadrumo[agent]==0.1.1`, and exposes only `CADRUMO_MCP_*`
product environment keys. Fourteen focused generator tests and Ruff pass.

## Notes

The served `plugins/cadrumo` subtree remains intentionally ignored and
uncommitted under the marketplace packaging contract; it was regenerated for
the following live-validator step. Existing README and `.gitignore` working
changes were present before S50 and were preserved outside this commit.

## Contextual-casing continuation

The marketplace was regenerated through the live
`materialise_marketplace` authority after S48 and S49 separated sentence prose
from identity-context display values. The checked manifest retains `Cadrumo` in
its sentence description and now records `CADRUMO` in its owner identity. The
ignored served plugin likewise carries `CADRUMO` display and author identities,
`Cadrumo` sentence copy, lowercase `cadrumo` machine identifiers,
`cadrumo-mcp`, and only `CADRUMO_MCP_*` product environment keys.

A clean temporary materialisation matched the in-place generated tree
byte-for-byte across 58 files, and a second in-place generation produced the
same 58-file snapshot. All fourteen focused plugin and marketplace tests
passed, including checked-scaffold parity and live strict validation. Direct
strict validation also accepted both the marketplace and served plugin.

The existing marketplace ignore comment was carried into this Step because it
names the generator's Python import authority and correctly changes the removed
`aeat.agent` root to `cadrumo.agent`. The README remained untouched, and the
ignored served plugin tree remains validation evidence rather than committed
output.
