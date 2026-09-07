---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:139d7a321b097d1cbbeb565269f213228b89863e3e10b0a029c7439933cbf88f'
step_id: 'S489'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Close the codebase to locale parity gate by narrowing the removal manifest against the four authorities the first sweep missed, since the wizard descriptor walk and the identity contract read keys the source scan cannot see, then teach the manager to discover the wizard flow help key it builds by interpolation and retire the google profile option sample whose option the live command specs no longer declare

## Scope

- `dev/locales`
- `src/cadrumo/locales`

## Changes

M dev/locales/manager.py
M dev/locales/wizard_translation_audit.py
M dev/locales/tests/test_dynamic_prefix_registry_coverage.py
M dev/locales/tests/test_audit.py
M dev/locales/tests/test_parity.py
M src/cadrumo/locales/ca.yml
M src/cadrumo/locales/en.yml
M src/cadrumo/locales/es.yml
M src/cadrumo/locales/hu.yml

    663 passed in 331.31s   the whole dev/locales suite, 0 failed

The parity gate opened this campaign at 228 missing and 463 extra. The missing
side reached zero when the ledger writer adopted the direction state spelling.
The extras closed here.

FIRST ATTEMPT WAS WRONG AND IS PART OF THE RECORD. Applying the prepared
manifest removed 528 leaves, turned parity green and broke four other gates. The
prepared verdict "not declared by the live authority owning its namespace" was a
claim about THREE authorities that happened to be queried, not about every
resolver. The wizard descriptor walk and the identity contract both read keys
that sweep called orphaned. Restored from a copy backup taken beforehand; the
tree returned byte-identical to committed, and no destructive git was used.

Narrowing the manifest against those authorities left 130 of the 132 safe. What
survived was not a deletion question at all but two authorities disagreeing.

`cli.config.setup.help` is built by interpolation at
wizard_translation_audit.py:45, `f"cli.config.{flow.id}.help"`, so no source scan
can see it while the wizard audit requires it to resolve in every locale. Closed
by `wizard_descriptor_keys()`, a public derivation wrapping the audit's own walk,
consumed as a seventh discovery path in `get_codebase_keys`.

`cli.config.google.profile_help` is residue of a retired option: the command-spec
registry declares 22 keys under the live `config google` family and that is not
among them, while sibling `profile_help` keys under `cli.root` and
`cli.config.repair` are declared. Removed from four catalogues with its two
identity-contract entries and two parity assertions.

## Notes

ONE GATE'S EXPECTATIONS WERE EDITED, deliberately and once. Retiring the google
sample removed a naming-contract example whose option no longer exists. The
contract keeps its other samples and google coverage survives through three
`adapters.google.*` entries; no assertion with a live subject was relaxed. Called
out here because editing a gate to make it pass is otherwise indistinguishable
from this.

TEETH. Removing the discovery path reds the new gate against 35 wizard descriptor
keys with a message naming the regressed path; restoring manager.py by copy
returns it to green. Both arms observed in this session.

A `ruff format` pass reflowed an unrelated fixture in the shared test file and
introduced the only E501. The file was rebuilt from `git show HEAD:<path>` plus
the two intended additions, leaving a two-hunk diff. The remaining E501 is in the
committed baseline.

NOT COMMITTED. The catalogue prune and five source edits sit uncommitted with
copy backups in scratch; committing needs the operator.
