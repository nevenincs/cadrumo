---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-09'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:9dd3ef60cd9b281f4aadaadb2bc60cd93b4b6a918c64762292f02f53189b3459'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: filename and frontmatter, scaffolded by
     `vaultspec-core vault exec log`; never hand-edit. Add no
     frontmatter fields. Wiki-links belong in `related:` only, never in the body.

     ONE ledger per plan, replacing one document per Step. The Step identity
     the plan's ids provide moves from the filename into the row's first
     column, so a Step still maps to a real artifact. -->

# `registry-edition-authoring` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one line per path touched per Step:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose, no sentences: the Step
     row states the intent and the commit carries the diff. Example:

       - `S01` `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `S01` `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `S02` `D` `src/legacy/shim.py`

     Optional per-Step check line:
       - `S01` `verify:` `<command>` -> `pass` | `fail`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered; a `## Notes` section is added ONLY on
     exception (data loss, skipped work, a scaffold left in code, a persistent
     failure) and is otherwise omitted. -->
- `S67` `M` `src/cadrumo/core/modelo.py`
- `S67` `M` `src/cadrumo/core/tax_domain.py`
- `S67` `A` `src/cadrumo/core/tests/test_fact_backed_bootstrap_validation.py`
- `S67` `verify:` `uv run --no-sync pytest -q -n0 --confcutdir=src/cadrumo/core/tests src/cadrumo/core/tests/test_fact_backed_bootstrap_validation.py` -> `pass`
- `S67` `by:` `Codex Luna/max registry fleet`
- `S68` `M` `dev/test_runs/tests/test_lanes.py`
- `S68` `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `S68` `verify:` `uv run --no-sync pytest -q -n0 dev/test_runs/tests/test_lanes.py dev/registry/conformance/tests/test_lifecycle_cli.py` -> `pass`
- `S68` `by:` `Codex Luna/max registry fleet`

## Notes

- `S67` 13 focused tests passed; a combined focused run before concurrent artifact drift passed 27 tests.
- `S67` 6b14eeb144 replaced nine Modelo and one TaxDomain bootstrap ValueError raises with CoreValidationError; 2b6053e9f3 pinned the registered code.
- `S67` Native TOMLDecodeError remains unmasked so syntax failures retain exact identity.
- `S67` Shared-worktree commit 6b14eeb144 also contains concurrent profile work; history was not rewritten.
- `S68` 11 focused tests passed; the combined focused run passed 27 tests.
- `S68` 229128e3d8 added the failed-preflight matrix; ec34052bcc typed the planted registry-validation failure.
- `S68` Lane runner remains domain-agnostic; typed error identity is asserted at the registry lifecycle producer.

