---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:eac9e3f432d122943c6115c0fbfaaa6648e01e15d4e63cacc835e50d254f8151'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename` `W04.P08` summary

Phase W04.P08 hard-cut the complete MCP wire identity to Cadrumo.

- Completed: S43 through S47 Step Records
- Renamed: server, subprocess executable, tool and client prefixes
- Renamed: resource schemes, prompt identities, and product-facing guidance
- Verified: tool-name budget, URI producer/resolver round-trip, and live stdio handshake
- Restored: packaging regression coverage lost in a shared-index collision

## Description

The MCP server now identifies as `cadrumo`, invokes the canonical `cadrumo`
human executable, exposes `cadrumo_` tools under the
`mcp__plugin_cadrumo_cadrumo__` client prefix, serves only `cadrumo://`
resources, and publishes the `cadrumo-empezar` orientation prompt. AEAT remains
only where it denotes the Spanish authority, its legal corpus, period codes, or
live-write boundary.

A real SDK stdio client initialized the `cadrumo-mcp` process, enumerated tools,
resources, templates, and prompts, called the safe harness floor, and shut down
cleanly. The final review proof set passed 28 tests with Ruff clean and found no
MEDIUM, HIGH, or CRITICAL issues; its sole low stale URI docstring was corrected.

Commit `6f2f22ab06` consumed peer-staged paths in addition to S46. History was not
rewritten. The rolling audit discloses the coupling, the S45 record and canonical
prompt/server bytes were restored explicitly, the corpus producer and elicitation
guidance leaks were remediated, and the dropped Docker probe regression test was
restored from the mixed commit's parent.
