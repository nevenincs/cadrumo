---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s54-mcpb-real-behavior'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:543e99a21e365c6168ac9860c3e005e151c12bd37a2569080c8166d8e06e2232'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-12-cadrumo-cli-executable-adr]]"
---

# `cadrumo-product-rename-s54-mcpb-real-behavior` audit: `S54 MCPB real-behavior review`

## Scope

Reviewed commit `817be90b6e` against the S54 plan contract, the accepted naming ADR, and the repository's real-behavior test rules. The review inspected the production loader, builder, committed manifest, test diff, execution record, and plan closure; verified the exact executable, environment, tool-name, display, archive-member, filename, and version assertions; searched the scoped test for fake, mock, patch, monkeypatch, skip, and xfail shortcuts; observed the actual host signer state; and reran the focused tests plus Ruff, formatter, and Ty gates.

## Findings

### s54-format-gate | low | The changed test does not pass the repository formatter

`ruff format --check` exits non-zero for `packaging/mcpb/tests/test_build.py` and would collapse the three-line `captured.err.startswith` assertion to one line. The parent revision passes the same stdin formatter check, so this is introduced by S54 rather than inherited drift. Ruff lint and Ty pass, but the changed Python surface is not fully gate-clean.

## Recommendations

FAIL pending the single formatting correction and a clean formatter rerun. No implementation or test-semantics change is required.

The substantive S54 behavior is otherwise sound. All six focused tests pass and use the real production loader, script entry point, filesystem, zip writer, and host signer availability; the scoped files contain no prohibited substitute or bypass mechanism. The current host has no `mcpb` executable, so the test truthfully proves the explicit unsigned branch and does not claim a configured signing identity, installation, or publisher verification. The manifest contract pins `cadrumo-mcp`, the exact `CADRUMO_MCP_PERSONA` mapping, the exact six tool names, `Cadrumo` display prose, `cadrumo.mcpb`, a single verbatim embedded manifest member, and version parity. The commit changes only the S54 test, record, and plan checkbox; its record accurately reports six passing tests and an unavailable real signer.
