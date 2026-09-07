---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:d58fdd3c9a3c6d2c7912e9c3f0b12a1189f6eaf5f59a61c4c1eedc0f8bc16842'
step_id: 'S92'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the five execution-policy declarations the config package does not use, and correct the entry that called them a displaced canonical home: the module holding them is leading-underscore and therefore private to config, so the modelo specs declaring their own is the correct shape rather than a displacement, and the five are simply declarations with zero in-package consumers where their siblings carry between two and twenty-six each. Record the two spent symbol-ratchet entries this and the output-language wiring left behind.

## Scope

- `src/cadrumo/entrypoints/cli/config/_spec_policies.py`
- `src/cadrumo/entrypoints/cli/config/tests/test_spec_policies.py`
- `dev/quality/unused_symbol_ratchet.toml`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/entrypoints/cli/config/_spec_policies.py`
- `M` `src/cadrumo/entrypoints/cli/config/tests/test_spec_policies.py`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.audit.unreachable_code` unused 1038 -> 1033,
  exact 409 -> 404; none of the five still reported
- `verify:` `pytest .../config/tests/test_spec_policies.py` 8 passed,
  `.../cli/tests/test_command_specs.py` 16 passed
- `verify:` symbol ratchet left with only the two peer regressions after the two
  spent entries were removed; module ratchet exit 0; ledger gates 19 passed
- `verify:` `ruff check` and `ty check` clean
- `verify:` open symbol decisions 51 -> 46

## Notes

The entry said the canonical home had been displaced by private copies in the
modelo command specs. That was the wrong reading and checking the boundary rule
settled it: `config/_spec_policies.py` is a leading-underscore module, so it is
private to the config package and was never a legitimate source for the modelo
package. The modelo specs declaring their own is CORRECT, not a displacement.

What the five actually were is declarations the config package does not use.
The comparison that made it obvious is in-package consumer counts: the module's
other policies carry between two and twenty-six each, and these carried zero.

Their only reader was a hand-listed inventory asserting that profile-bound
policies declare custody authority. That test still covers the seven policies
that are used, so deleting the five costs no coverage -- an inventory test over
a module's own declarations shrinks with the module by construction.

Five symbols in one step, the largest movement in many, and it came from
re-reading a ledger entry rather than from finding new debt. A wrong framing had
made the cluster look like an architecture question when it was a deletion.

The symbol ratchet then showed two spent entries: this deletion, and the
output-language hint wired two steps ago whose entry I never lowered. Removed
both. That is the second time this campaign has owed the ratchet bookkeeping for
work already done, which is the argument for finishing it in the same step.
