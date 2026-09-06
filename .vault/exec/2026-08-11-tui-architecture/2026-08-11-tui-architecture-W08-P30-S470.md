---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:14aecd521e233c31fbde48075746a2a708085c13b26b7ede0e728f6980e1bd64'
step_id: 'S470'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Restore the static frame reasons gate to running, promoting the live AEAT token helper to the public name its cross-package consumer and the packages own docstring already use and recovering the unconverted baseline an import refactor deleted alongside it

## Scope

- `dev/docs/sequences/runner.py`
- `dev/docs/sequences/tests/test_runner.py`
- `dev/docs/tests/unconverted_static_baseline.json`

## Changes

`dev/docs/tests/test_static_frame_reasons.py` runs again: 6 passed, where
before it could not be COLLECTED at all.

I OPENED THIS FIRING BY CLAIMING EVERY GATE WAS CLOSED OR BLOCKED. That was
wrong, and I only found out by sweeping instead of asserting it: `dev/`
excluding `dev/locales` reports 29 failures and one collection error. The claim
had been true of the surfaces I had been working and I generalised it to the
repository.

TWO DEFECTS, BOTH FROM ONE SIBLING COMMIT. `23eadb3884`
("refactor(imports): close the private-to-public module promotion at zero")
left this suite unable to import and deleted the baseline it reads.

* `runner.py` defined `_live_aeat_tokens` while `dev/docs/tests` imported the
  PUBLIC `live_aeat_tokens`. The package's own initialiser docstring names it
  publicly, beside `refuse_live_frames`, so the public name is what this
  package says it exposes -- the definition was the half left behind. Renamed
  atomically across the definition, its two internal call sites, the private
  import in the sequences' own `test_runner`, and `__all__`, with a sweep
  confirming the private name survives nowhere.

* `unconverted_static_baseline.json` was deleted in the same commit while the
  two tests that read it stayed. Recovered with `git show <commit>^:<path>`,
  which writes nothing to the working tree of another contributor's files.

THE RESTORED BASELINE STILL MATCHES REALITY. That is the part worth checking
rather than assuming: had it been stale, the honest move would have been to
report it, since regenerating a baseline from the implementation it is meant to
constrain proves nothing. It matched, which also confirms the deletion was
collateral rather than a deliberate retirement of the ratchet.

Teeth: two defects, each restored by copy -- re-privatising the symbol returns
the collection error, and removing the baseline fails both tests that read it.

## Notes

`refuse_live_frames` is documented publicly and still defined as
`_refuse_live_frames`, but nothing outside `runner.py` imports it, so promoting
it is not what this failing gate needed and I left it. Stated here rather than
done quietly.

A THIRD DEFECT OF THE SAME CLASS, FOUND NOT FIXED.
`dev/docs/sequences/tests/test_runner.py::TestAmbientEnvNeutralisation` fails
with `ImportError: cannot import name 'probe_subprocess_providers' from
'cadrumo.application.provisioning'`. Another consumer importing a name the
promotion sweep did not leave in place. It cannot be caused by this step's
rename, and it is the obvious next target.

THE SWEEP'S OTHER FAILURES, for the next firings: 23 of the 29 are one
parametrised case,
`dev/registry/tests/test_generated_export_trees.py::test_committed_tree_is_reproducible_and_check_mode_refuses_only_for_its_named_reason`,
across m151/m184/m185/m202/m222/m296/m303/m322/m347/m390 -- one root cause is
likely. `dev/audit/tests/test_unreachable_code.py::test_the_live_reference_walk_read_every_file`
is the remaining one.

Unchanged: the three operator decisions -- the 125 `cli.*` extras, the 5
`application.*` extras, and the `direction` spelling.
