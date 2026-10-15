---
tags:
  - '#exec'
  - '#full-suite-repair'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:50613e514cb657820eea3262879044720a79c3ec02290cd10b0fd008adf44764'
related:
  - "[[2026-10-15-full-suite-repair-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `full-suite-repair` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S02` `M` `native/application-environment.toml`
- `S02` `M` `native/platform/src/launch.rs`
- `S02` `M` `dev/packaging/native/application_environment.py`
- `S02` `verify:` `native identity and launch metadata tests (196)` -> `pass`
- `S02` `verify:` `native launch probe tests (39)` -> `pass`
- `S02` `verify:` `publisher cache tests (6)` -> `pass`
- `S02` `verify:` `runtime and build client tests (32)` -> `pass`
- `S02` `verify:` `CMake rust_platform_consumer and platform.rust` -> `pass`
- `S02` `verify:` `scoped Ruff format lint and ty` -> `pass`
- `S02` `M` `src/cadrumo/core/config.py`
- `S02` `M` `src/cadrumo/core/config_google.py`
- `S02` `M` `dev/packaging/google_oauth.py`
- `S02` `M` `native/cmake/Contract.cmake`
- `S02` `M` `dev/packaging/native/environment_conformance.py`
- `S02` `M` `dev/packaging/native/generate.py`
- `S02` `M` `dev/packaging/native/cached_command.py`
- `S02` `A` `dev/packaging/native/tests/conftest.py`
- `S02` `A` `dev/packaging/native/tests/google_identity.py`
- `S02` `M` `dev/packaging/native/tests/test_application_environment.py`
- `S02` `M` `dev/packaging/native/tests/test_launch_profile_vectors.py`
- `S02` `M` `dev/packaging/native/tests/test_cached_command.py`
- `S02` `M` `dev/packaging/native/tests/stand_in_launch.py`
- `S02` `M` `dev/packaging/native/tests/test_environment_launch_probe.py`
- `S02` `M` `dev/packaging/native/tests/test_agent_image.py`
- `S02` `M` `src/cadrumo/adapters/outbound/google/tests/test_installation_client.py`
- `S02` `M` `.vault/adr/2026-10-04-google-app-identity-adr.md`
- `S02` `M` `.vault/adr/2026-10-04-canonical-environment-adr.md`
- `S02` `M` `native/CONTRACT.md`
- `S02` `verify:` `final application environment parser tests (33)` -> `pass`
- `S02` `verify:` `all-profile identity replacement correction (2)` -> `pass`
- `S02` `verify:` `final native build and platform.rust` -> `pass`
