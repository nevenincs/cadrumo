---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S172'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S172 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Regenerate CLI reference pages from the live command tree and prove removed pages are absent and ## Scope

- `dev/docs/tests/test_cli_reference_conformance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Regenerate CLI reference pages from the live command tree and prove removed pages are absent

## Scope

- `dev/docs/tests/test_cli_reference_conformance.py`

## Description

- Regenerate and validate the CLI reference against the live materialised command tree.
- Prove docs-versus-tree completeness and that no documented path names a removed command.

## Outcome

The CLI reference pages are a build-time artefact: `docs/cli/` is not committed,
and the build regenerates it from the live tree through `generate_cli_reference`.
So regeneration is not a committed-file edit; the load-bearing deliverable is the
conformance gate, which materialises the live tree in a subprocess and asserts
every live leaf command is documented and every documented command path resolves
to a real leaf, plus schema-registry conformance. A removed page therefore cannot
survive: a documented path with no live leaf reds the gate. The gate is green.

The command tree was independently confirmed stable at 290 leaf paths with zero
duplicates, matching the coordinator's re-measurement, so the regenerated
reference reflects a stable surface rather than a shifting one.

Command: `uv run --no-sync pytest -p no:cacheprovider -n0 -m unit -o addopts=""
dev/docs/tests/test_cli_reference_conformance.py`. Collected 6, `6 passed in
45.13s`, exit code 0, at HEAD `b3fc6d22fb4b3567d01b97a05e97dfc147234303`.

## Notes

Execution was blocked for a period by an unrelated peer core refactor whose
uncommitted working-tree WIP (`core/_journal_repository.py` calling
`load_settings()` at import time) introduced a circular import that broke test
collection for every gate importing `cadrumo`. HEAD was clean throughout; the
break was working-tree only and was not touched. It cleared when the peer landed
their refactor, and the gate ran clean afterwards.
