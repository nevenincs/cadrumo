---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:46bd5e41dac0a4d1bd5f38b3c67ecf2d5a4e68458adf40fb1ffa3c9b5267766c'
step_id: '{S##}'
related: []
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# reachability-burndown <display-path>



## Changes

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

## Context

## Changes

- `M` `src/cadrumo/application/auth/sessions.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- Removed the uncalled `require_verified_aeat_session` branch and its export; all shipped live-auth callers already use the central `ensure_authenticated_aeat_session` owner required by the accepted custody-boundary ADR.
- Removed the `now` import that became unused with the dead branch.
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/auth/sessions.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/application/auth/tests/test_clave_credential_resolution.py src/cadrumo/application/auth/tests/test_blank_profile_identity_refusal.py src/cadrumo/application/auth/tests/test_live_provider_kind_resolution.py` -> `27 passed`
- `verify:` full auth suite under configured parallel execution -> `176 passed, 12 failed, 163 setup errors`; failures are dominated by shared scratch-path races and locks, so the focused serial owner tests above are the attributable gate.
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> live signal remains red as required, exact unused symbols reduced from 296 to 295, with 51 unreachable modules, 1 type-only module, and 4 orphan tests.
