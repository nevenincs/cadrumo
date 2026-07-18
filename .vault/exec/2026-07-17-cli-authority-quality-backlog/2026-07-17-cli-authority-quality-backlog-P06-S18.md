---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S18'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-quality-backlog with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-07-17-cli-authority-quality-backlog-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The GATED (blocked until the mcp-call-latency plan completes): make the MCP server direct dispatch path call gate_refusal() once so a refused call is not composed twice into the envelope and ## Scope

- `src/cadrumo/entrypoints/mcp/_server.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# GATED (blocked until the mcp-call-latency plan completes): make the MCP server direct dispatch path call gate_refusal() once so a refused call is not composed twice into the envelope

## Scope

- `src/cadrumo/entrypoints/mcp/_server.py`

## Description

- Route the direct per-verb call handler through the single shared persona-scope / handoff / permanent-live-write gate `gate_refusal`, replacing the inline `persona_scope_refusal` plus `is_handoff_denied` / `handoff_denial_message` composition in `_call_tool`; `src/cadrumo/entrypoints/mcp/_server.py`.
- Import `gate_refusal` from `_meta_tools` and drop the now-unused `handoff_denial_message` import.
- Add `test_direct_dispatch_gate_composition.py` driving the real server `tools/call` handler: a scope-refused and a handoff-denied verb each compose exactly one refusal, byte-identical to the shared gate, not a doubly-wrapped envelope, and identical to the `execute` meta-path.

## Outcome

Root cause: the direct dispatch path re-derived the scope / handoff / live-write refusal inline, composing the same decision a second time alongside the shared `gate_refusal` the `execute` meta-path already ran. The two compositions were kept in lock-step only by a parity test (a band-aid), and the live-write branch diverged in message text between the paths. The fix makes both entry points resolve the refusal from one `gate_refusal` call, so a refused call carries exactly one refusal and the two surfaces cannot fork.

Behaviour is preserved for every reachable case: `gate_refusal` returns byte-identical scope and handoff messages (proven by the existing parity and handoff tests, still green). The only delta is the permanent-live-write BLOCK message, which is unreachable on the direct path (no live-write tool is ever advertised, so it never resolves through `_call_tool`); after the change the direct path would use the same short BLOCK message the meta-path already uses, making the two paths consistent rather than divergent.

Gates: `pytest src/cadrumo/entrypoints/mcp` gate/identity/dispatch/hitl suites green; CLI `test_json_schema_conformance.py` green (149); ruff and ty clean; `import cadrumo.entrypoints.mcp` clean.

## Notes

There was no runtime double-nesting of a refusal inside another envelope; the "composed twice" was the duplicated composition of the gate decision across the inline direct path and the shared `gate_refusal`. The fix collapses it to one composition site. `persona_scope_refusal` remains defined and exercised by tests as the reference implementation the shared gate is asserted equal to.
