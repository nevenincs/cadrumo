---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S68'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W04.P06.S68` getting-started natural-key lifecycle rewrite

Step scope: `docs/getting-started.md`.

## Description

- Keep the getting-started lifecycle path addressed by modelo, year, and period.
- Remove residual copied-ID wording from the first filing flow.
- Verify that educational-doc commands and relative links resolve against the live CLI.
- Check that the getting-started guide no longer contains raw ID placeholders or 64-character ID examples.

## Outcome

The getting-started guide now tells the reader to create, calculate, verify, and export a Modelo 130 filing with natural-key command flags. Internal IDs are framed as ignorable metadata for this guide, not as values carried between commands.

Verification passed with `uv run pytest -m docs src/aeat/entrypoints/cli/test_educational_docs_conformance.py`.

## Notes

The docs conformance test emitted existing Click deprecation warnings from the CLI entrypoint; no documentation failures were reported.
