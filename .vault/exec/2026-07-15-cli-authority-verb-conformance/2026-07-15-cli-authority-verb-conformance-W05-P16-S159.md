---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:92c5926aa5cfc9a016bfe429a5de37d1db8fbb21963cd5eadf689f5110b2fc06'
step_id: 'S159'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove generated MCP input schemas for every accepted changed command

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_input_schema.py`

## Description

- Read what the existing sweep actually binds, finding it iterates whatever is exposable rather than a named set.
- Establish that a command dropping out of that set removes itself from the sweep without failing it.
- Name the eight accepted changed commands and assert each is exposable before asserting its shape.
- Assert each derives a typed non-bag schema at its resolved nested path.
- Read one family for its real parameters, since a correct path proves nothing about the contents.
- Correct a guessed contrast after the test caught it, using the measured parameter sets.

## Outcome

The row's commands were covered incidentally and are now covered by name.

The existing sweep asserts a shape over every exposable key and floors the count at two hundred. That is real but it does not bind these commands: it iterates whatever happens to be exposable, so a command silently dropping out removes itself from the sweep, and the floor absorbs the loss without a failure. Measured, all eight accepted keys do derive typed non-bag schemas today, at correctly resolved three-segment paths.

The membership assertion is the addition that matters. Each of the eight is asserted exposable BEFORE its shape is asserted, so disappearance becomes a red test rather than a smaller corpus.

A second case reads one family for its contents, because every assertion in the sweep holds for a schema that resolved the right path and read none of its parameters. The reset family discriminates itself: an operation id addresses an EXISTING operation, so `status` and `resume` take one while `start`, which creates the operation, does not. A derivation emitting one parameter set for the whole group fails this.

That case is also where this step's own error was caught, and the correction is worth recording. The first version asserted `config.reset.status` takes no operation id, on an assumption from a parameter COUNT rather than a reading of the names. The test failed immediately. Measured, `status` takes exactly `operation_id`, and it is `start` that takes none. The assertion was rewritten from the measured parameter sets. A guess that had happened to be true would have shipped as a pinned fact.

`uv run --no-sync pytest` over the three modified modules reported `46 passed in 24.36s`, and the full MCP suite under an explicit marker expression reported `285 passed, 6 warnings in 83.02s`. `ruff check`, `ruff format --check` and `ty check` all reported clean.

## Notes

The source-side row is satisfied by a generic derivation, and the two are worth keeping distinct. The module names none of these families because it walks the real command tree, which is why a hand-enumerated schema cannot drift here. The test naming them is not a duplicate of that: derivation makes the schemas correct by construction, membership makes their PRESENCE non-optional, and only the second catches a command leaving the surface.

The mutation proof for the membership assertion used a key that is not registered, and it failed as intended.

Not verified: that the derived schemas match what the CLI would accept at runtime for these eight commands. The schemas are read from the same click tree the CLI dispatches on, so the parameters agree by construction, but no invocation was made.
