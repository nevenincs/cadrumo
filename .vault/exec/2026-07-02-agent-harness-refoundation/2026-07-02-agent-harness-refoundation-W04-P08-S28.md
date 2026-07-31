---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:be53263b4227329fbb2ec51f4d011aad9471850bf4c3dcb1c558b817cf361bd6'
step_id: 'S28'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Build the live subagent-persona harness substrate that starts the real server, drives a real client session, and captures the trajectory

## Scope

- `src/aeat/agent/eval/_live_harness.py`

## Description

- Author `src/aeat/agent/eval/_live_harness.py`: the ADR-R7 measurement
  substrate. Spawns the real console server as a stdio subprocess through the
  `mcp` client SDK (lazy, extra-gated import), initializes a real session,
  advertises the negotiated tool set to an injectable `PersonaDriver`, and
  captures every tool call, narration, and elicitation exchange verbatim into
  the typed `LiveTrajectory` (S30 models).
- Two drivers ship: `ScriptedPersonaDriver` (the deterministic, model-free
  CI floor) and `AnthropicPersonaDriver` (the live subagent persona — an
  extra-gated Anthropic tool-use loop seeded with the operator rules, persona
  document, and skill).
- Client-side elicitation is answered by an injectable responder
  (`decline_all_elicitations` default — fail-closed) and recorded for
  confirmation-honesty scoring.
- Hexagonal discipline preserved: the module never imports
  `entrypoints.mcp`; the tool-name→command-key mapping is caller-supplied.

## Outcome

FIRST LIVE ROUND-TRIP PROVEN: a real client session against the spawned
server completed initialize → tools/list (9 curated tools for the coordinator
persona, including the W02 `aeat_harness_load` floor tool and the W01
search/execute meta-tools) → a live `aeat_harness_load` call returning the
shipped operator rules text. Ruff clean. Commit `01740b64ac`.

## Notes

Two real defects found and fixed during the smoke: (1)
`StdioServerParameters.env` REPLACES the child environment — a bare
override dict strips PATH and the spawn hangs; the harness now merges
`os.environ`; (2) nesting the child under a second `uv run` layer is
hang-prone on this host — callers should spawn `sys.executable` directly.
At close, a peer campaign's uncommitted 124-line deletion in
`domain/modelos/_participation_index.py` transiently breaks the server's
import graph (HEAD is clean; verified by `git log`) — live calls that
route through the CLI tree fail until that peer lands; not absorbed here.
