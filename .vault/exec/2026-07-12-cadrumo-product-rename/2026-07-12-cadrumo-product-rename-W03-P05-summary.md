---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:4750a7d49cd2b83bae60039e3f7d235eedd937f2ebe112345abd5acdb72a272f'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename` `W03.P05` summary

Phase W03.P05 made the root project install and identify itself as Cadrumo across
distribution metadata, human CLI, MCP executable refusal, and optional-extra
remedies.

- Modified: `pyproject.toml`
- Modified: CLI registration, invocation, diagnostics, and direct structural tests
- Modified: MCP executable/refusal guidance and direct integration tests
- Modified: optional-extra authority, consumers, and degradation tests
- Created: S24 through S27 Step Records
- Modified: plan and rolling formal audit

## Description

The root distribution is `cadrumo`, selects `src/cadrumo`, and exposes only
`cadrumo` and `cadrumo-mcp`. Repository metadata points at the Cadrumo
project, self-referencing extras use `cadrumo[...]`, and root metadata already
names the future Cadrumo companion distributions without moving them early.

The human Typer surface, version/help rows, command paths, recovery diagnostics,
and invocation detector use `cadrumo`. The MCP executable refuses missing SDK
support with `cadrumo-mcp` and `pip install 'cadrumo[agent]'` while leaving
MCP server/tool/resource wire identities for W04. Optional Google, browser,
Anthropic, agent, search, and corpus remedies all map to declared Cadrumo extras.

Concurrent plan/source WIP briefly restored the former human command and reopened
completed rows. The accepted Cadrumo ADR supersedes that older naming intent; the
live source and canonical plan were reconciled without aliases, and completed
Step state was restored from existing records. The closure review inspected a
fresh wheel: Name `cadrumo`, 19,181 Cadrumo members, zero former import-root
members, and only the two canonical console scripts. No HIGH or CRITICAL findings
remain.

Verification includes TOML parsing, wheel metadata/member inspection, nine CLI
tests, three MCP refusal/stdio tests, 19 optional-degradation tests, focused
Ruff/format/compile checks, metadata consistency, and exact alias residue gates.
Lock regeneration and companion builds remain ordered in later P06/P07 Steps.
