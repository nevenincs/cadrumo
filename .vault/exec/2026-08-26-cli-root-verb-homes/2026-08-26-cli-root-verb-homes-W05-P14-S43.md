---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:00c70d3ec6fbee6c4527b9a10f063844894277b144ddf910e9516bd2c50f838b'
step_id: 'S43'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Sweep the show->view rename through the surfaces S41 missed: 98 test invocations across 41 modules, two envelope identity expectations and the config storage bootstrap-exempt subtree

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` 41 test modules under `src/cadrumo/entrypoints/cli/`, `src/cadrumo/application/tests/` and `src/cadrumo/application/user_profile/tests/` (98 token replacements)
- `R` `src/cadrumo/entrypoints/cli/tests/test_ledger_counterparty_show_cli.py -> src/cadrumo/entrypoints/cli/tests/test_ledger_counterparty_view_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_audit_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_profile_authentication_gate.py`
- `M` `docs/_sequences/contracts/how-to/profile-setup/profile-setup-capabilities.seq`
- `M` 10 goldens under `docs/_sequences/how-to/profile-setup/`
- `M` `src/cadrumo/locales/{en,es,ca,hu}/cli.yml`
- `verify:` `pytest src/cadrumo/entrypoints/cli/ -p no:randomly -n0` -> `1426 passed, 28 peer-owned failures, none naming a CLI view or show verb`
- `verify:` `pytest test_bootstrap_exempt_entries_resolve.py test_documented_command_conformance.py -m integration` -> `pass`

## Notes

S41 swept the specs, handlers, payloads, locale catalogues and prose but not the
callers. Eleven `*_view_help` keys were referenced by code and absent from all
four catalogues, six `*_show_help` keys were left orphaned, and 98 test
invocations still addressed a token the graph no longer carries.

The locale gate did not catch the orphans on its own: `scaffold --check`
reported `extra=0` while ten unreferenced keys sat in the tree, and only
reclassified them once the `view` keys existed. Any bulk locale verb -
`remove`, `move-revision` - rewrites the shard from its own snapshot and drops
concurrent `set` values, so catalogue edits must end with the `set` pass, not
begin with it.

The bootstrap-exempt subtree for `config storage` still declared `show`. That
surface is named in `aeat-cli-contract` as one the gates do not scan, and it
fails open: a verb missing from the declared subtree drops out of the
profile-bound write guard.
