---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S173'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Regenerate the static CLI tree from the live command tree and verify exact accepted paths

## Scope

- `dev/docs/tests/test_cli_tree.py`

## Description

- Regenerate and validate the static CLI-tree projection against the live command tree.
- Verify the projection covers every live node and that documented paths are present.

## Outcome

The static CLI tree (`_static/cli-tree.json`) is a build-time artefact, not a
committed file, generated from the live tree by `write_cli_tree`. The gate proves
the projection generates, is byte-deterministic across two builds, and covers
every node an independent second materialisation of the live Click tree yields --
a coverage assertion between two independent walks, not the projection against
itself -- and that a documented command path absent from the projection fails
loudly. Green.

The independent leaf walk resolved 290 leaf paths, zero duplicates, so the
regenerated projection matches the stable surface. No leaf appeared or vanished
under regeneration.

Command: `uv run --no-sync pytest -p no:cacheprovider -n0 -m unit -o addopts=""
dev/docs/tests/test_cli_tree.py`. Collected 15, `15 passed in 31.51s`, exit code
0, at HEAD `b3fc6d22fb4b3567d01b97a05e97dfc147234303`.

## Notes

Same peer core-import block as the sibling reference Step delayed the run; it
cleared when the peer's refactor landed and the gate ran clean. The peer WIP was
not touched.
