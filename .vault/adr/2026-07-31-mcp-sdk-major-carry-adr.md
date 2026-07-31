---
tags:
  - '#adr'
  - '#mcp-sdk-major-carry'
date: '2026-07-31'
modified: '2026-07-31'
body_schema: 'body-v1'
body_hash: 'sha256:0331197e8fbc1f8f02e6032410c3ebc26a2a7eb8151725ec3bae25836f90fe91'
related:
  - "[[2026-06-30-agent-harness-adr]]"
  - "[[2026-06-15-dependency-provisioning-adr]]"
  - "[[2026-06-28-product-packaging-adr]]"
  - "[[2026-07-31-mcp-sdk-major-carry-reference]]"
---

# `mcp-sdk-major-carry` adr: `Harness dependency floor carries the shipped MCP SDK to its 2.x major` | (**status:** `accepted`)

## Problem Statement

`2026-06-30-agent-harness-adr` put a real MCP server behind the `agent` extra
of the published `cadrumo` wheel: `entrypoints/mcp/` runs on the `mcp` SDK and
ships the `cadrumo-mcp` console script, and `cadrumo[agent]` pinned
`mcp>=1.12,<2`. Separately, this project's own `.vault/` document corpus is
authored through `vaultspec-core`, a contributor-only CLI declared in the
`dev` dependency group that `src/cadrumo/` never imports. `vaultspec-core`
0.1.55 is the first release that understands the `body_hash` frontmatter
fingerprint the corpus now carries; an older CLI silently drops that stamp on
rewrite (nevenincs/vaultspec-core#299), so the operator directed the harness
floor to track latest. Raising it collided immediately: `vaultspec-core`
0.1.55 declares `mcp` as an unconditional base dependency requiring
`>=2.0.0`, with no extra to opt out of, while `cadrumo[agent]` still required
`mcp<2`. Because `agent` and `dev` resolve inside the one project `uv.lock`,
the two disjoint `mcp` ranges are a hard resolver conflict, not a soft skew
two separate lockfiles could tolerate. A prior pass, recorded at the pin
itself, hit exactly this and deliberately held the floor at 0.1.25 rather
than force the collision. This record decides how the harness floor is
allowed to move now that the operator has directed it to move regardless.

## Considerations

- `agent` is a real `project.optional-dependencies` extra of the published
  wheel; `entrypoints/mcp/_server.py` imports `mcp.server.Server` at runtime
  (deferred, per the project's lazy-import discipline) to build
  `cadrumo-mcp`. A version bump here is a product-facing SDK migration, not a
  tooling bump.
- `dev` is a PEP 735 dependency group; `vaultspec-core` and `vaultspec-rag`
  are contributor tooling with zero import sites in `src/cadrumo/`, confirmed
  by a project-wide search before this record was written.
- `vaultspec-rag`'s own `[mcp]` extra is already demoted out of its base
  dependency set for the adjacent reason: dev tooling's own optional MCP
  capability must not bleed into a shipped wheel. `vaultspec-core`'s `mcp`
  requirement is not similarly optional; it ships as an unconditional base
  dependency of `vaultspec-core` itself, so there is no upstream extras
  boundary to hide behind.
- The universal resolution `uv.lock` performs across every extra and group
  in one project is what turns two independently reasonable pins into one
  hard conflict; nothing about the `agent` extra or the `dev` group in
  isolation is wrong.

## Considered options

- **Decouple**: keep `cadrumo[agent]` on `mcp<2` and move `vaultspec-core`
  off this project's dependency graph entirely (install it as a standalone
  `uv tool` on PATH, or declare `agent` and `dev` mutually conflicting so
  each locks independently and the two are never installed together).
  Preserves the shipped SDK version and defers the 2.x migration
  indefinitely. Rejected: it relocates the forcing function rather than
  resolving it. `vaultspec-core` will keep shipping releases, the
  `body_hash` hazard is already live today, and the identical collision
  reopens on the next contributor-tooling floor bump regardless.
- **Hold the floor** (the prior posture): keep `vaultspec-core` at 0.1.25,
  accept the silent frontmatter-stamp loss on a mixed-version corpus, and
  revisit later. Rejected by direct operator instruction: the harness tracks
  latest.
- **Fix forward** (chosen): raise `cadrumo[agent]`'s `mcp` pin to `>=2,<3`
  alongside the `vaultspec-core>=0.1.55` floor, absorbing the SDK major into
  the shipped `cadrumo-mcp` server and every call site it touches.

## Constraints

- `mcp` 2.0.0 removed decorator-based handler registration from
  `mcp.server.Server` entirely; verified against the installed 2.0.0 wheel,
  the class exposes no `list_tools`/`call_tool`/etc. methods at all. The
  constructor now takes `on_list_tools`, `on_call_tool`, and their siblings
  as keyword callbacks over a `ServerRequestContext`. At the time of this
  record, `entrypoints/mcp/_server.py`'s `build_server()` still registers
  every handler through the removed `@server.list_tools()`-style decorators
  and does not instantiate against the installed SDK; rewriting it to the
  constructor-callback shape is the load-bearing follow-up this decision
  requires, tracked outside this record.
- The `mcp_types` family renamed camelCase attributes to snake_case
  (`isError` to `is_error`, `structuredContent` to `structured_content`,
  `serverInfo` to `server_info`, `inputSchema` to `input_schema`,
  `requestedSchema` to `requested_schema`). The rename is attribute-only: a
  site that also treats the old spelling as a wire key or a pinned-digest
  input must keep that string literal and rename only the attribute access
  feeding it, or the digest silently moves under a change that reads as pure
  cleanup.
- The SDK also relocated or removed public composition helpers, not only
  attributes. `mcp.shared.memory.create_connected_server_and_client_session`,
  the pre-2.0 helper that started a real in-process server and handed back an
  already-initialized client session, no longer exists as a standalone
  function; the maintained composition is now `mcp.client.Client` in
  `mode="legacy"` over the still-shipped in-memory transport, and a consumer
  of the removed helper has no drop-in replacement.

## Implementation

`cadrumo[agent]`'s `mcp` pin moves from `>=1.12,<2` to `>=2,<3`; the `dev`
group's `vaultspec-core` floor moves from `>=0.1.25` to `>=0.1.55`. Every
call site touching a renamed `mcp_types` attribute is swept to the
snake_case spelling, scoped to genuine attribute access; the one site
building a pinned inventory digest off a wire-shaped path segment
(`dev/packaging/verify_distribution_identity.py`) keeps its `"inputSchema"`
string label and changes only the attribute read behind it, with an inline
note explaining why the string does not move alongside the attribute.
`entrypoints/mcp/_server.py`'s `build_server()` is rewritten from decorator
registration to the SDK's constructor-callback shape. The removed
`create_connected_server_and_client_session` composition is reimplemented
once, in `cadrumo.tests.mcp_session`, on top of `mcp.client.Client` in
`mode="legacy"`, and every in-process MCP test and the packaging
serving-path benchmark consumes that one shared implementation instead of
independent reimplementations.

## Rationale

The decoupling option was genuinely available: `src/cadrumo/` does not
import `vaultspec_core` anywhere, so nothing structurally forced the two
dependency surfaces to share a resolution. It was rejected because it does
not resolve the forcing function, it only defers it outside the one project
the operator directed to track latest, and every future `vaultspec-core`
floor bump reopens the identical collision until `cadrumo[agent]` eventually
needs its own unrelated reason to move past `mcp<2`. Absorbing the major now,
while the SDK 2.0.0 blast radius is fresh and traceable to one cause, is
cheaper than absorbing it later entangled with a second, unrelated
product-driven SDK requirement. `2026-06-30-agent-harness-adr` never asserted
`mcp<2` as a durable product commitment, only as the version available when
the harness shipped, and nothing in that record or in
`2026-06-15-dependency-provisioning-adr`'s capability-mapped extras
discipline requires the SDK pin to trail contributor tooling rather than
lead it.

## Consequences

Gains: the harness stops silently corrupting `body_hash` stamps on rewrite,
and `cadrumo-mcp` moves onto a maintained SDK line before the migration is
forced by an unrelated deadline.

Costs, observed directly against the working tree at the time of this
record: `build_server()` does not currently instantiate against the
installed SDK, so the shipped `cadrumo-mcp` server does not currently run
until its decorator registration is rewritten; twelve files under
`entrypoints/mcp/tests/` needed the snake_case attribute sweep; the
release-readiness verifier `dev/packaging/verify_distribution_identity.py`,
the clean-install proof `2026-06-28-product-packaging-adr` established, and
the installed-CLI oracle `dev/packaging/installed_mcp_oracle.py` both broke
on the same renames, so the blast radius reached release tooling, not only
test coverage; the packaging serving-path benchmark and the agent eval
live harness (`src/cadrumo/agent/eval/_live_harness.py`) each needed a
separate fix for a relocated or removed SDK symbol.

A hazard this decision surfaces for future SDK majors: an attribute rename
that happens to share its old spelling with a wire key or a digest input is
not safe to rename blindly. The distribution-identity verifier's
`"inputSchema"` label is deliberately not renamed alongside the
`tool.input_schema` attribute read that now feeds it, because the label is a
path segment baked into a committed inventory digest; a future SDK rename
sweep must check every digest-adjacent string literal against this same
hazard before applying a mechanical find-and-replace.

The precise count of MCP test failures this migration caused before the
in-flight fix could not be independently reproduced for this record without
reverting the attribute-rename work already applied, which the standing
prohibition on destructive git operations forbids. What is independently
confirmed against the installed `mcp` 2.0.0 wheel and the current
working-tree diff is the root cause (decorator-API removal, attribute
renames, a removed composition helper) and the file-level blast radius
enumerated above.
