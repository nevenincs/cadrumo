---
tags:
  - '#reference'
  - '#gate-integrity-adjudication'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:d0b0ec591ef181e744072b6c51e43cdd7dddd594973610ef0cd051a4837b6c41'
related:
  - "[[2026-09-02-gate-integrity-adjudication-research]]"
---

# `gate-integrity-adjudication` reference: `Pre-commit hook runtime`

This reference audits the installed `prek`, Ruff, and ty command surfaces, the
repository hook configuration, the current repair/type-check owners, and the
worktree-safety boundary relevant to commit-time mutation.

## Summary

### Runtime and configuration

- The locked tools are `prek@0.5.1`, `ruff@0.16.5`, and `ty@0.0.77` at
  `uv.lock:2612`, `uv.lock:3510`, and `uv.lock:4364`. The project declarations
  are lower bounds rather than exact pins at `pyproject.toml:435` and
  `pyproject.toml:468-469`.
- The Ruff hooks use a second environment pinned to `ruff-pre-commit@0.15.12`
  at `prek.toml:49-58`, so hook replay and project-local commands do not share
  one formatter/linter implementation.
- The configured ty hook is not path-scoped ty. It sets
  `pass_filenames = false` and calls the three-checker type harness at
  `prek.toml:61-71`; that harness runs ty, pyrefly, and BasedPyright over their
  governed scopes at `dev/quality/types.py:173-278` and
  `dev/quality/types.py:307-355`.
- The existing repair owner runs `ruff check --fix .` before `ruff format .`
  because lint fixes can create content needing final formatting:
  `dev/quality/fixes.py:35-42`.

### Commit-trigger behavior

- The accepted governing decision records that staged-content hook execution
  saves and restores unstaged changes independently of whether hook commands
  mutate: `2026-09-02-gate-integrity-adjudication-commit-time-mechanical-gates-adr:31-43`.
  A live `prek@0.5.1` invocation on 2026-09-14 emitted "Temporarily saving" and
  "Restored unstaged changes" before hook work.
- `prek` has no `run` option that disables this staged-content isolation. Its
  installed `run --help` exposes path/ref selectors but no no-stash mode.
- `prek` treats a changed file as a failed priority group even when the hook
  process exits zero. Multiple mutators in one priority group also have
  undefined results: https://prek.j178.dev/reference/configuration/.
- Child flags such as Ruff or ty `--exit-zero` can suppress diagnostic exit
  code 1, but cannot make a mutating `prek` run pass.

### Proposed command capabilities

- `ruff check --fix` applies safe fixes by default; unsafe fixes remain opt-in:
  https://docs.astral.sh/ruff/linter/.
- `ty@0.0.77` exposes both `check --fix` and `--exit-zero`. Its operational
  failures remain exit 2 and internal failures exit 101:
  https://docs.astral.sh/ty/reference/cli/ and
  https://docs.astral.sh/ty/reference/exit-codes/.
- `ruff format` mutates by default and `--check` is read-only. Ruff directs
  lint/import fixes to run before formatting:
  https://docs.astral.sh/ruff/formatter/.

### Installation state

- `prek.toml:3-18` intentionally declares the hook uninstalled, but its claim
  that verify-only hooks never stash contradicts the accepted decision and
  live runner behavior.
- `dev/init/hooks.py:73-108` would install a supplied hook config, but defaults
  to absent `.pre-commit-config.yaml` at `dev/init/hooks.py:124-129` and is not
  enrolled in `dev/init/plan.py:101-126`.
- The worktree has no active pre-commit script; its shared `core.hooksPath`
  names a missing path from an older worktree.

### Performance boundary

- Existing measurements put a change-scoped mechanical check near two
  seconds, versus approximately nine seconds for whole-tree formatting, four
  seconds for whole-tree style, five seconds for dependencies, and forty
  seconds for relative imports:
  `2026-09-02-gate-integrity-adjudication-research:106-117`.
- Warm one-file probes on 2026-09-14 were approximately 99 ms for Ruff format,
  95 ms for Ruff lint, and 140 ms for ty. The governed type harness is above
  that class because it ignores filenames and launches three checkers.
