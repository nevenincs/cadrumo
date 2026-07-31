---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:52d30baee6d8bac1b4f2d5294ad4a21774f7ad63f0ddb425f6a2e31584e66d07'
step_id: 'S23'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

# incorporate approved reference feedback

## Scope

- `dev/docs/cli_reference.py`

## Description

Operator feedback on the generated CLI reference: the app/config pages were
mechanical command dumps with no structure, and asked for the CLI to be
separated by verb, with each major verb starting with its actual verb help
output rather than a single flat dump.

- Restructure the generator so each top-level family page (`docs/cli/app.rst`,
  `docs/cli/config.rst`) becomes navigation only: a grid linking to each major
  verb group's own page, plus any command mounted directly on the family root
  with no intervening group (`config check`, `config lock`, etc.), rendered
  inline on the family page since they have no group of their own.
- Derive the verb-group set from the live Typer tree's first-level subgroups
  under each family root (`app ledger`, `app modelo`, `app live`, `app
  overview`, `config profile`, `config auth`, `config google`, ...), ordered
  by the canonical `RootSurface.required_children` sequence rather than
  alphabetically.
- Give each verb group its own page under `docs/cli/<family>/<group>.rst`
  (e.g. `docs/cli/app/ledger.rst`). The page opens with that group's real
  `--help` rendering (usage, description, options, subcommand summary),
  captured via Click's classic `Command.format_help` called directly on the
  Typer-produced command object (bypassing Typer's Rich-based override, which
  both subclass) — Rich's box-drawing style auto-detects the host console's
  legacy/VT capability and differs between an interactive terminal and a
  headless subprocess, so the classic formatter is used instead for a
  byte-stable rendering, with `terminal_width`/`max_content_width` both pinned
  to make the wrap width deterministic across machines.
- Walk each group's subtree recursively: a nested subgroup (`ledger rule`,
  `ledger invoice catalogue`) gets its own captured `--help` block before its
  children; a leaf command gets the existing full section (description,
  parameters, output schema). Heading depth is chosen purely from tree depth
  (a shared `_heading_char_for_depth` table), never from the leaf/group
  distinction, so a direct leaf and a nested subgroup at the same depth render
  as RST siblings.
- Fixed `generate_cli_reference_in_subprocess`'s read-back to `rglob` (was
  `glob`, non-recursive) so the new per-group pages under family
  subdirectories are picked up.
- Preserved every existing content guarantee: all leaf commands still
  documented (registry-key parsing in the dev/docs conformance gate scans all
  rendered pages regardless of nesting), envelope/schema references intact,
  automation/schemas pages untouched.

## Outcome

- `docs/cli/app.rst` / `docs/cli/config.rst` are now pure navigation pages (a
  "Choose a command group" grid plus any direct commands); `docs/cli/app/*.rst`
  and `docs/cli/config/*.rst` carry one page per major verb group, each led by
  that group's real `--help` output.
- `docs/cli/` is gitignored (not a committed surface); only the generator
  source changed. Regenerated on disk locally and verified against every gate.
- Gates green: `dev/docs/tests/test_cli_reference_drift.py`,
  `dev/docs/tests/test_cli_reference_conformance.py`,
  `dev/docs/tests/test_cli_tree.py` (22 passed);
  `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m
  integration` (69 passed); `dev/docs/tests/test_docs_build.py::test_sphinx_nitpicky_build_is_clean`
  (1 passed, full nitpicky `-n -W` Sphinx build clean); `python -m
  dev.docs.apidocs scaffold --check` and `python -m cadrumo.locales scaffold
  --check` both clean (unaffected by this change).

## Notes

None. No skipped work, no scaffolds left in code, no data loss.
