---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s43-mcp-server-identity'
date: '2026-07-13'
modified: '2026-07-17'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s43-mcp-server-identity` audit: `Cadrumo product rename S43 MCP server identity audit`

## Scope

Independent formal review of commit
`4acbc5959954ef553c2457fd1234c2850490f05d` against the binding naming ADR
and `W04.P08.S43`. The review covered MCP protocol server identity, supervised
human-CLI subprocess argv, product-facing meta-tool prose, retained AEAT
authority language, real SDK and end-to-end subprocess tests, focused quality
gates, execution and plan truth, and commit path isolation.

## Findings

### server-name-bypasses-canonical-identity-authority | medium | The MCP server and its test duplicate the `cadrumo` literal instead of consuming `PRODUCT_IDENTITY.mcp_server`

`product_identity.py` is the accepted single runtime authority for the naming
tuple, and the agent workspace already derives its MCP server name from
`PRODUCT_IDENTITY.mcp_server`. The actual protocol server instead declares
`_SERVER_NAME = "cadrumo"`, while its test independently asserts
`server.name == "cadrumo"`. Those two matching literals prove only current
spelling, not projection from the canonical authority; either can drift from
the tuple without the focused gate failing. S43 already imports
`PRODUCT_IDENTITY` for the supervised human CLI, so the server identifier has
no architectural reason to remain a parallel declaration.

## Recommendations

Verdict: **FAIL** until the protocol server name consumes
`PRODUCT_IDENTITY.mcp_server` and its contract test asserts that authority
relationship rather than a duplicate literal.

The remaining S43 behavior is healthy. Supervised subprocess argv derives from
`PRODUCT_IDENTITY.cli_executable` and reaches the installed `aeat` command in a
real end-to-end `contract` meta-execution. Meta-tool descriptions use sentence
prose `Cadrumo`, not an `aeat` product label; AEAT remains in authority and
live-write safety language. The server advertises its real SDK capabilities and
the resource scheme is `cadrumo://`. Eighteen tests in the directly changed MCP
test module passed, including the server-name, SDK capability, copy, and real
subprocess cases. Ruff lint, Ruff format, Ty, and scoped whitespace checks
passed. The four-path commit is isolated to server typing, its direct tests,
execution record, and checkbox, with no documentation or unrelated leakage.
