---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S102'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove exact sandbox labels work through switch while sandbox use and bare names are absent

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_profile_sandbox.py`

## Description

Prove that an exact canonical `sandbox:<name>` label selects a sandbox through the
profile-selection verb, while the `sandbox use` door and bare short-name selection
are both absent.

## Outcome

`src/cadrumo/entrypoints/cli/tests/test_config_profile_sandbox.py` exercises the
canonical label against real persisted sandbox state: creation emits
`label\tsandbox:bakeoff` (`:74`) and `show` renders the same canonical
`display_name` (`:80`), so the label the operator is given back is the label
selection accepts. Selection runs through `config login` (`:85`, `:112`, `:139`),
which is the verb that replaced `switch` per the 2026-07-24 ADR amendment; listings
render canonical labels (`:127`, `:133`), and profile edit addresses a sandbox by
its exact `sandbox:lab` label (`:105`).

Absence of the removed doors is asserted in the grammar gate rather than by
inference: `test_config_profile_sandbox_use_door_is_unmounted`
(`src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py:243`) and
`test_config_profile_use_bare_name_selector_is_unmounted` (`:256`).

Both modules passed in the coordinator's W04 gate run
(`uv run --no-sync pytest <14 W04 files> -m "integration and not os_keychain"` →
`1 failed, 154 passed`), the single failure being the unrelated S112 control.

## Notes

The step action text says "through switch"; `switch` was deleted and replaced by
`login` under the 2026-07-24 amendment, so the proof runs through `login`. The action
text is left unedited for identifier stability.

These are `integration`-marked modules. The repository default `addopts` selects
`-m 'unit and not external_tool and not os_keychain'`, so a bare `pytest <path>` here
collects zero tests and exits green — the marker above is required for the run to
mean anything.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
all findings were confirmed with `rg` and direct file reads.
