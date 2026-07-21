---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S26'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename MCP executable refusal and install hints

## Scope

- `src/cadrumo/entrypoints/mcp executable/refusal modules and focused real tests`

## Description

- Rename the MCP console executable guidance to `cadrumo-mcp` across its entrypoint and lazy SDK boundary.
- Rename the missing-SDK remedy to `pip install 'cadrumo[agent]'` and reject the former distribution hint in the refusal test.
- Launch the real installed `cadrumo-mcp` console entrypoint in the stdio client handshake.
- Preserve server names, tool prefixes, resource URI schemes, prompts, and human CLI subprocess wiring for W04.

## Outcome

Bare-core degradation now exits with code 3 and prints only the canonical Cadrumo agent-extra remedy. The installed-extra path reaches the real `cadrumo-mcp` console script and completes the stdio handshake. SDK adaptation remains lazy and succeeds when the extra is present.

Three focused integration tests passed: missing-SDK refusal, SDK adaptation, and real installed console-entrypoint stdio roundtrip. Ruff, formatting, exact residue, scoped wire-identity diff, and plan checks passed.

## Notes

The broader handshake file's in-process tool call still reaches the deferred human CLI subprocess spelling and failed with `WinError 2`; that wiring belongs to W04 and was not altered by S26. The real `cadrumo-mcp` stdio entrypoint test in the same file passed.

Formal review found no issue and confirmed that server name, tool prefix, resource scheme, prompts, and AEAT authority semantics remain unchanged.
