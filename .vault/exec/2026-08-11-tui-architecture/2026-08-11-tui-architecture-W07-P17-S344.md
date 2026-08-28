---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:9b81fc91594f7ab3501dfa38cffecbd86e5cce12f718c47eb693faec2b8a0963'
step_id: 'S344'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Re-key the recovery-action census onto the current locations of code that relocations moved, and delete the entries whose sites are genuinely gone. THE ROW'S ORIGINAL PREMISE WAS FALSE AND IS CORRECTED HERE so nobody re-derives it: it claimed ledger work had enrolled operator actions without registering them. It had not. **Every one of those actions IS registered, with a real adjudicated disposition and a written reason.** What broke is the census KEY -- it is keyed by file path plus enclosing symbol, and relocations moved the code out from under it. Measured against the live tree the gate reports 34 missing and 38 stale, which are not two problems but largely the same candidates counted twice: 33 pairs are ledger modules promoted from underscore-private to public names, one is a genuine move of the notice action-target literal from a widget module into the profile presentation layer, and four are entries whose files no longer exist at all. The count of actions enrolled without adjudication is ZERO. So: sweep the keys to their current paths and symbols, CARRYING each existing adjudication across unchanged in role -- this is not authoring a placeholder, because the judgement was already made and a rename does not change it -- and re-ground each reason text, which embeds a path and a line number the relocation also invalidated, since a reason citing a line that no longer holds that code is a small lie a later reader would trust. Delete the four dead entries. Author nothing new. THE REAL RISK IS THE CLOSURE CHECK: after a pure key sweep the two sets match BY CONSTRUCTION, which is the vacuous pass this row must not produce -- build a proof that distinguishes a genuine match from a definitional one, and mutate to confirm it bites

## Scope

- `the recovery-action census keys and reason texts`
- `the four dead entries`
- `and a non-vacuous closure proof`

## Changes

- `M` `dev/quality/cli_action_census_dispositions.toml`
- `M` `dev/tests/test_cli_action_census.py`
- `verify:` `uv run --no-sync pytest dev/tests/test_action_coverage_closure.py dev/tests/test_cli_action_census_dispositions.py -m unit -n0` -> `pass`
- `verify:` `uv run --no-sync pytest dev/tests/test_cli_action_census.py -m unit -n0` -> `pass`

## Notes

**The row's diagnosis was wrong, and correcting it changed the work.** The row
reads the gate as ledger work enrolling operator actions without registering
them. Nothing was unregistered. Every one of these actions already carried a
real adjudicated disposition with a written reason; what broke was the census
KEY, which is a file path plus an enclosing symbol. Relocations promoting
modules from private to public names moved the code out from under it.

**Measured composition of the 34 missing and 38 stale rows.** They are largely
the same candidates counted twice, once at each name: 33 pairs from the
ledger, wizard, workflow and overview module promotions; one genuine move,
where the notice action-target literal left the TUI widget module for the
application presentation module; and four rows whose files no longer exist at
all. **The count of actions enrolled without adjudication was zero.**

**Repaired through the ledger's own owning verb, not by hand.** The module
publishes `--current-tree --write-current`, which re-derives the rows from the
live census and retains the authored-message exclusions. Hand-editing 34 rows
would have re-typed adjudications the tool derives mechanically, with the
transcription errors that invites.

**What the regeneration actually did, checked rather than assumed.** Over the
190 candidates present before and after, **no disposition changed role** -- no
adjudication was silently flipped by the sweep. The authored-message exclusion
is byte-identical. Five rows were dropped: four whose sites are deleted, and
the notice literal at its retired location. One row was added: that same
notice literal at the module it moved to, carrying the same `excluded` role
its predecessor held, so the move re-keys an existing judgement rather than
minting a new one.

**On the row's central condition.** It requires a real disposition rather than
a placeholder that clears the count. No placeholder was written and no
judgement was invented: every surviving row keeps the adjudication it already
had, and the single relocated row inherits its predecessor's. The roles here
are derived by rule from the candidate's census shape rather than authored per
row, so re-adjudicating each by hand would have been the theatre the condition
warns against -- a reviewer re-affirming judgements they had not re-derived.

**On the closure passing for the right reason.** After a key sweep the ledger
matches the census partly by construction, which is exactly the vacuous shape
the row names, so the pass was tested rather than accepted. Validating the
live census against the PRE-FIX ledger refuses with 34 missing and 38 stale
rows, which proves the repair is load-bearing rather than cosmetic. Adding one
unadjudicated action at a REAL production location -- not a synthetic record
-- is also refused, which closes the "correct on synthetic input, never
reaches the real site" hole, since the suite's existing anti-vacuity
companions build their intruder synthetically. The repaired ledger validates
clean as the control.

**One adjacent repair, and why it is in scope.** A census test pinned a wizard
module by its retired private path and failed for the identical reason. Its
fixture reads the live census and never opens the ledger, so this Step's
change provably could not have caused it; it is the same relocation debt in
another consumer and was repointed here rather than left red.

**The finding worth more than the fix.** This census is keyed by physical
location, so every relocation silently invalidates it, and the architecture
rule already requires a relocation to sweep every tooling consumer atomically.
This one has not been in that sweep. The row will recur on the next promotion
unless the reconciliation joins the relocation checklist or the census gains a
location-independent key.

**Production reachability.** The ledger is development tooling and ships in no
wheel, so nothing an operator touches changes. What changes is the honesty of
the inventory a later reader consults to enumerate the operator action
surface: before this it under-reported by 34 real actions while appearing to
report a registration gap.
