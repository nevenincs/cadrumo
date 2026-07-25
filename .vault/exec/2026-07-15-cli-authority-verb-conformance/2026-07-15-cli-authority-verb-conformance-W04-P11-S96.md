---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S96'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Restrict config switch to UUIDs and exact labels including canonical sandbox labels and reject bare sandbox names

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody.py`

## Description

Restrict profile selection to unambiguous UUIDs and exact operator labels, accept a
canonical `sandbox:<name>` label, and refuse a bare short sandbox name that would
have to be implicitly namespaced.

## Outcome

The step's action text names `config switch`, which no longer exists. The ADR
amendment note dated 2026-07-24 (`.vault/adr/2026-07-15-cli-authority-verb-conformance-adr.md:20`)
records that the accepted `2026-07-24-profile-login-session-adr` replaces
`aeat config switch NAME` with `aeat config login [NAME]` under an explicit operator
override, deleting `switch` rather than aliasing it. The requirement therefore lands
on `login`, and the retirement is asserted by
`src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py:305`
(`retired_verb = "switch"`) and `src/cadrumo/entrypoints/cli/tests/test_profile_lifecycle_verbs.py:213`.

`_register_login_command` (`src/cadrumo/entrypoints/cli/_config/_custody.py:117`)
registers `login` with the target as an optional positional `typer.Argument`
(`:123`), never a `--id` option, and delegates every resolution decision to the
single application resolver `login_profile` (`:150`). The CLI adds no second
resolver: the comment at `:155` records that login owns label resolution
internally. Bare-name and sandbox-label behaviour is proven at the grammar gate
`test_config_profile_sandbox_use_door_is_unmounted`
(`src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py:243`) and
`test_config_profile_use_bare_name_selector_is_unmounted` (`:256`).

Verified green in the coordinator's run of the W04 gate set:
`uv run --no-sync pytest <14 W04 files> -m "integration and not os_keychain"` →
`1 failed, 154 passed`, the single failure being the unrelated S112 control.

## Notes

The step action text is stale with respect to the 2026-07-24 amendment; it was
recorded against `switch` before `login` replaced it. The action text is left
unedited for identifier stability, as the Spanish-stem naming rule directs for
pre-amendment plan text, and this record names the verb that actually satisfies it.

`vaultspec-rag` was probed before this work and returned unrelated results: the code
index is truncated (~1027 chunks against ~4546 files) while reporting
`degraded_reasons: []`, so every finding here was confirmed with `rg` and direct
file reads.
