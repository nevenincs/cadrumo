---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:8081a2093fe6723cd64906e6055ee1bf9dbc8aa3a23158d858ba893dc4c79670'
step_id: 'S89'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Apply the run-the-owning-gate rule to every artefact this campaign edits, which found all of them green, then re-test the root CLI tty cluster and split it: the interactivity refusal is in force through a richer construct that weighs stdout and the terminal type as well as stdin, and the entry's colour claim went stale when this campaign fixed the localised error path earlier while the prose kept the old sentence. The progress rule is waiting on a widget no entrypoint renders.

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` owning-gate sweep, all green -- `test_unreachable_module_ratchet_gate.py`
  29 passed, `test_unused_symbol_ratchet.py` and `test_symbol_ratchet_dispositions.py`
  11 passed, `test_unconsumed_export_ratchet.py` and `test_secure_store_write_path.py`
  27 passed, `test_reachability_classification.py` 9 passed, the three ledger
  gates 19 passed
- `verify:` module ratchet, secure-store gate, docstring ratchet exit 0;
  duplication 10 / 0.05%; dead code 0; unused 1038, exact 409
- `verify:` open symbol decisions 52 -> 50; clusters 120 -> 121

## Notes

The sweep found nothing, which is the point: the previous two steps' repairs
were the debt, and running every owning gate rather than the one just touched is
now the check that says so.

The tty cluster carried two claims and both were wrong, in different ways. It
said no command refuses a request needing interactivity when stdin is not a tty.
One does, through a construct that considers strictly more:
`detect_frontend_capability` returns `NON_INTERACTIVE` when stdin OR stdout is
not a real tty or the host advertises a dumb terminal, and `_tui_policy.py`
refuses on that verdict. A helper displaced by a richer rule looks identical to
a helper nobody wired.

Its other claim -- that the localised usage-error path passes Click's own
`show_color`, so the project colour settings reach nothing -- was true when
written and was fixed early in this campaign. `should_use_color` was removed
from the symbols list at the time; the prose was not. That is the second cluster
this campaign has found stale in exactly that way, and both times the gated half
stayed honest while the ungated sentence drifted.

Split rather than reclassified, because the two remaining symbols are different
classes: the refusal is superseded, while the progress rule is staged -- no
module under `entrypoints` constructs a rich progress widget at all, so the
question it answers is never asked, and it is the rule that would govern the
widget on the day one lands.

The citation gate refused the first draft for citing only the DISPLACING
constructs and never the subject's own home. That is the defect it was written
for, caught on my own prose.
