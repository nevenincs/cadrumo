---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S178'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run passphrase and recovery lifecycle suites against real encrypted vaults and secure input channels

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/`

## Description

- Run the passphrase and recovery lifecycle suites under an explicit execution-marker selection covering both lanes.
- Read the failing set rather than the summary line alone, and re-run sequentially before triaging any failure as a regression.
- Reduce the failure to the smallest reproducing invocation and establish whether it is a parallel-worker artefact or an order dependence that survives without workers.
- Collect the OS-keychain remainder for the same scope.

## Outcome

Verdict: FAILED, on an order dependence inside the scope rather than on the passphrase and recovery behaviour itself.

Parallel command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/entrypoints/cli/_config/tests`.

Collected 131, passed 123, failed 8, skipped 0. Exit line: `8 failed, 123 passed, 6 warnings in 52.31s`, exit code 1. HEAD at run time was `5eaf4b0ee6213f8d8d7845eabafb2a5c3afe79bd`.

Serial command over the same scope: `24 passed, 131 deselected in 33.54s`, exit code 0. The OS-keychain selection collected nothing.

All eight failures are in one module, the auth round-five surface module, and every one raises the same error: the profile-key registry reports that no keys are registered and instructs the caller to import the wizard catalogue so the compiled keys are pushed before the registry is read.

The failure is NOT a parallel-worker race. Running the whole scope with no workers passes 155 of 155, but running that single module alone with no workers fails 8 of 13 in nine seconds. The module therefore passes only when some other module in the same process has already imported the wizard package, whose import is what seeds the registry. Whole-scope sequential runs mask this because another module imports the wizard first; file-scoped work distribution exposes it because the module lands alone on its worker.

The project already recognises this hazard on the domain side, where a package-local test-fixture module imports the wizard specifically so those tests are not order-dependent on broader suite startup. The equivalent protection was never extended to this CLI configuration scope.

Attribution: owner surface. The failing module is committed and clean at HEAD; the uncommitted peer work in this area does not remove a wizard import, so the order dependence is a property of the committed tree rather than of another agent's in-flight edit.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. Every claim here is bound to a pytest exit line or a direct read of the source.

The parallel run also emitted a held-serial warning naming 24 serial-marked cases that did not execute in that pass; those were covered by the separate serial pass, which was green.

This finding shares a root cause with the MCP identity failures recorded against the MCP dispatch and identity Step, where the same unregistered-profile-keys error reaches a real subprocess server. The CLI-side symptom is a test-isolation defect; the MCP-side symptom is operator-facing.

## Re-measurement at HEAD `1437055950`

Verdict: SATISFIED.

The root cause closed before this re-measurement. Commit `6b2edc7301` registers wizard catalogue keys at the point of use inside `list_profile_key_records` via a function-local import, eliminating the order-dependent side-effect requirement. All eight auth-round-five failures now pass regardless of module execution order.

Parallel command: `uv run --no-sync pytest -q -p no:cacheprovider -n auto --dist=loadfile --tb=no -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/entrypoints/cli/_config/tests`.

Collected 182, passed 182, failed 0, skipped 0. Exit line: `182 passed, 6 warnings in 54.07s`, exit code 0. HEAD at run time was `1437055950f5b8f4082d323578294fc32ad1d9fe`.

Serial command: `uv run --no-sync pytest -q -p no:cacheprovider -n0 --tb=no -m "serial and not os_keychain and not external_tool and not perf" src/cadrumo/entrypoints/cli/_config/tests`. Collected 24, passed 24. Exit line: `24 passed, 182 deselected in 45.12s`, exit code 0. The OS-keychain selection collected nothing.
