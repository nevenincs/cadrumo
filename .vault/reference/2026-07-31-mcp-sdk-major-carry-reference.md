---
tags:
  - '#reference'
  - '#mcp-sdk-major-carry'
date: '2026-07-31'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:5af1682a4f4974208bd8ddf5d1abb6d7a9118b90f3cd5de9e56219b9092c9828'
related: []
---

# `mcp-sdk-major-carry` reference: `MCP SDK 2.0.0 API surface and blast radius verified against the working tree`

Grounds `2026-07-31-mcp-sdk-major-carry-adr`. Every claim below was checked
directly, either by reading the current working-tree diff (`git diff`,
uncommitted at the time of writing), by reading `uv.lock`, or by introspecting
the installed `mcp` 2.0.0 wheel at runtime; none is taken from the dispatch
brief on trust.

## Summary

### Dependency graph

`pyproject.toml`'s `agent` extra (`[project.optional-dependencies]`) pinned
`mcp>=1.12,<2` prior to this change; `dev` (`[dependency-groups]`) declared
`vaultspec-core>=0.1.25`. `uv.lock`'s `vaultspec-core` package block (version
0.1.55) lists `mcp` inside its plain `dependencies = [...]` array with no
extras marker, i.e. an unconditional base dependency, not gated behind an
optional feature. `uv.lock`'s resolved `mcp` package block moved from
`1.29.0` to `2.0.0`, pulling in two new transitive dependencies
(`mcp-types` 2.0.0, `httpx2`/`httpcore2` as a vendored HTTP stack) that did
not exist in the 1.x resolution. `entrypoints/mcp/_server.py` imports
`mcp.server.Server` inside function bodies (deferred, at least at lines 151
and 247), the project's lazy-import pattern for optional-extra SDKs; a
project-wide search for `import vaultspec_core` / `from vaultspec_core` /
`import vaultspec_rag` / `from vaultspec_rag` under `src/cadrumo/` returned
zero hits, confirming the harness tooling has no runtime import site in the
shipped product.

### Server API: decorator registration removed

Introspecting the installed `mcp.server.lowlevel.Server` class: it exposes no
`list_tools`, `call_tool`, `list_prompts`, `get_prompt`, `list_resources`,
`list_resource_templates`, `read_resource`, or `completion` attributes at
all (`hasattr` false on every one). `mcp.server.Server.__init__`'s signature
instead accepts `on_list_tools`, `on_call_tool`, `on_list_resources`,
`on_list_resource_templates`, `on_read_resource`, `on_subscribe_resource`,
`on_unsubscribe_resource`, `on_subscriptions_listen`, `on_list_prompts`,
`on_get_prompt`, `on_completion`, `on_set_logging_level`, `on_ping`,
`on_roots_list_changed`, and `on_progress` as keyword callbacks, each typed
`Callable[[ServerRequestContext[LifespanResultT], <ParamsT>],
Awaitable[<ResultT>]]`; `ServerRequestContext` is imported from
`mcp.server.context` in the installed wheel.

At the time of writing, `entrypoints/mcp/_server.py`'s `build_server()`
(defined at line 575) still registers every handler through the removed
decorator style: `@server.list_tools()` (line 772), `@server.call_tool()`
(line 784), `@server.list_prompts()` (line 1008), `@server.get_prompt()`
(line 1023), `@server.list_resources()` (line 1052),
`@server.list_resource_templates()` (line 1064), `@server.read_resource()`
(line 1109), `@server.completion()` (line 1127). Because the installed SDK's
`Server` carries none of these methods, `build_server()` does not currently
instantiate against the installed `mcp` 2.0.0 wheel; the shipped
`cadrumo-mcp` server does not currently run. The same file already imports
`ServerRequestContext` under `TYPE_CHECKING` (line 152) for unrelated
standalone-function type annotations, so the constructor-callback rewrite
this decision requires is anticipated but not yet applied to `build_server`
itself.

### `mcp_types` attribute renames (camelCase to snake_case)

Confirmed via the working-tree diff, each a Python-attribute rename with the
same semantic field:

- `result.isError` to `result.is_error`
- `result.structuredContent` to `result.structured_content`
- `initialized.serverInfo.name` to `initialized.server_info.name`
- `tool.inputSchema` to `tool.input_schema`
- `params.requestedSchema` to `params.requested_schema`

This is the one site in the diff where a naive global camelCase-to-snake_case rename would have silently changed a pinned digest.

### Removed and relocated composition helpers

`mcp.shared.memory.create_connected_server_and_client_session`, the pre-2.0 helper that started a real in-process `Server` on the SDK's memory transport and returned an already-initialized `ClientSession`, does not exist as a standalone function in the installed 2.0.0 wheel.

`mcp.shared.context.RequestContext` relocated to
`mcp.client.session.ClientRequestContext`; `_live_harness.py`'s elicitation
callback signature was updated to the new type and its
`KWARGS-ANY-RATIONALE-MCP-REQUEST-CONTEXT` inline rationale comment (for a
generic-over-`Any` parameter that no longer applies to the concrete
`ClientRequestContext`) was removed in the same hunk.

### File-level blast radius observed in the working tree

### What could not be verified from this position

The specific count of MCP test failures attributed to the SDK bump could not
be independently reproduced: doing so would require running the test suite
against the pre-fix attribute names, which would mean reverting the
already-applied rename commits/working-tree edits under
`src/cadrumo/entrypoints/mcp/tests/`. The standing prohibition on destructive
git operations in this shared worktree forbids that.

A `pytest` run against `src/cadrumo/entrypoints/mcp` under this project's
default `addopts` (`-m 'unit and not external_tool and not os_keychain'`)
passed 16 tests with 18 more held as serial-only. That default marker
excludes the large majority of the 297 test functions across the directory's
42 files, so this run is evidence the already-fixed subset stayed green, not
a measurement of the original failure count or a broad confirmation that the
rename sweep is complete; most of the directory's coverage, including
whatever exercises `build_server()` directly against a live SDK instance,
was not exercised by this run.
