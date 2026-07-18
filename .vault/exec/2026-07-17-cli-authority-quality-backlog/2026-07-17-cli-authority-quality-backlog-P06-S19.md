---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S19'
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
     The S19 and 2026-07-17-cli-authority-quality-backlog-plan placeholders are machine-filled by
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
     The GATED (blocked until the mcp-call-latency plan completes): add a per-verb CLI-versus-MCP schema-parity diff proving every operator verb exposes the same request and response schema across both surfaces and ## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_inprocess_envelope_parity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# GATED (blocked until the mcp-call-latency plan completes): add a per-verb CLI-versus-MCP schema-parity diff proving every operator verb exposes the same request and response schema across both surfaces

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_inprocess_envelope_parity.py`

## Description

- Add a per-verb CLI-versus-MCP schema-parity diff to `test_inprocess_envelope_parity.py`, enumerating every operator verb from the live operator-surface manifest (`command_schema_refs` filtered by `is_exposable_command`) so a newly-mounted verb is covered automatically.
- Assert the operator verb set is identical across the CLI surface and the MCP descriptor set (a verb on one surface but not the other fails).
- Assert every verb's MCP request schema equals the schema projected from that verb's own live CLI click parameters (rebuilt via `build_verb_input_schemas`).
- Assert every verb's MCP response schema embeds exactly the CLI-registered result model (`SCHEMA_REGISTRY` + `thin_output_schema`) inside the shared envelope, with a non-vacuous floor on grounded verbs.
- Add a runtime cross-surface proof: run the `contract` read verb through the real CLI in-process and assert its emitted envelope satisfies the MCP-advertised output schema spine.

## Outcome

Design: both surfaces single-source their per-verb schemas from the CLI authority - the request schema from the live Typer/click command tree, the response schema from the `SCHEMA_REGISTRY` result model wrapped in the shared envelope. The MCP tool builder derives from these; the parity diff proves the MCP surface has not forked from the CLI for any verb. The diffs are genuine and non-vacuous: injecting a request property or flipping a response `additionalProperties` is detected, and all 288 exposable verbs carry a registered result model (the grounded floor of 100 is comfortably met, so no verb falls through to the generic-object fallback). A future hand-authored MCP schema, a divergent thinning, a stale result model, or a verb exposed on one surface only fails the corresponding test for that exact verb.

Gates: `pytest src/cadrumo/entrypoints/mcp/tests/test_inprocess_envelope_parity.py` green (7); ruff and ty clean; `import cadrumo.entrypoints.mcp` clean.

## Notes

The request-side diff shares the `build_verb_input_schemas` builder with the MCP surface by construction (the MCP request schema IS the projection of the live CLI command), so its value is catching a descriptor whose advertised input schema drifts from the live command; the response-side and verb-set diffs are the load-bearing fork detectors. No mocks, skips, or tautological assertions.
