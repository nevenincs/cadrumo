---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S112'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove passphrases, mnemonics, and secret-input values are absent from help and examples

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_help_without_secrets.py`

## Description

Prove that passphrases, mnemonics, and secret-input values never appear in help
output or examples, and keep that proof falsifiable by showing the secret is still
genuinely required to execute a real verb.

## Outcome

This was the only step in W04 that required a code change; the rest of the Wave was
already satisfied and merely unrecorded.

The module's anti-tautology control was failing. It ran `app ledger list` in an
environment carrying a placeholder `CADRUMO_ACTIVE_PROFILE` and asserted the refusal
named `CADRUMO_SECRET_PASSPHRASE`; the CLI instead refused earlier with "No active
profile". Investigation found the deeper defect: `CADRUMO_ACTIVE_PROFILE` is severed
from environment selection by `_NON_ENVIRONMENT_SELECTION_NAMES` in `core/config.py`
— selection belongs to the active-profile pointer file and the in-process `--profile`
channel — so the placeholder configured nothing and had only ever produced a
cold-start refusal. The control was already close to vacuous before it went red.

Repairing it by relaxing the assertion was rejected: the module's help assertions are
only meaningful while the secret remains load-bearing, so a weakened control would
have made every assertion above it unfalsifiable.

`test_data_verb_still_refuses_without_passphrase` is now a differential over exactly
one variable. It provisions a REAL encrypted profile in an isolated root through the
real console script, then runs the SAME data verb twice against that profile: once
with the passphrase on its sanctioned environment channel, once without. The unlocked
run must exit 0 with non-empty output; the refused run must exit non-zero and must not
reproduce the listing. The paired successful run is the load-bearing half — it proves
the profile and root are usable, so the refusal cannot be explained away by a broken
fixture. If the passphrase gate were ever removed, the second run would exit 0 and the
test would fail, which is what makes the control genuinely falsifiable.

A second control, `test_store_writing_verb_still_demands_the_passphrase`, preserves
the original "names the variable" assertion on `config profile create`, a
store-writing verb that does reach master-key resolution from a cold start. Naming the
variable is what attributes the refusal to the secret rather than to some other
cold-start precondition.

Two environment properties were pinned to stop the controls passing for the wrong
reason: the passphrase variable is explicitly removed so an exported developer value
cannot satisfy the gate, and the secret-store backend is pinned to `file` because
under the default `auto` a machine with a usable OS keychain can serve the master key
with no passphrase at all.

Verified independently by the coordinator, not on the implementing agent's report:
`uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_help_without_secrets.py
-m "integration and not os_keychain" -n0 -q` → `13 passed in 58.47s`. Clean collection
confirmed at `14390/17707 tests collected` immediately before commit.

## Notes

No prose is asserted anywhere in the repaired control. The refusal wording is free to
change — a session door now fronts the key gate on this route — while the secret's
necessity is the invariant. The `_PASSPHRASE_ENV_VAR` name is spelled as a literal
rather than imported from the master-key adapter that emits it, since importing the
producer's own constant would assert the code against itself.

The existing distinction in `_PASSPHRASE_VALUE_LEAK_PATTERN` is preserved: naming the
variable in operator help is legitimate, materializing a `KEY=value` assignment is the
genuine leak. Both controls assert the value never appears.

Pinning the backend to `file` also keeps these cases runnable under an agent SSH
logon, where OS-keychain access fails with `WinError 1312`; nothing here carries the
`os_keychain` marker.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
findings were confirmed with `rg` and direct file reads.
