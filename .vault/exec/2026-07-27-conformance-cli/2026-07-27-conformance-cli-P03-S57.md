---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S57'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# compare a recorded baseline against the committed one and surface every counter moving in the weakening direction, and re-anchor the seed invariant to a freshly measured ceiling so the first genuine operator signoff does not red it

## Scope

- `dev/registry/conformance/manager.py`
- `dev/registry/conformance/cli.py`
- `dev/tests/test_registry_conformance_cli.py`

## Description

- Add the pure `baseline_weakenings` fold, naming every ceiling that would rise and every
  floor that would fall against the baseline on disk.
- Refuse a capture carrying any weakening unless it is explicitly accepted, and name each
  moved counter with its direction in the refusal.
- Wire the acceptance as an option on the audit verb so the escape hatch is a recorded act
  rather than a hand edit of the baseline.
- Re-anchor the seed invariant onto a freshly measured ceiling and give it a message that
  sends a reader to re-record.
- Add four tests: the raised-ceiling refusal, the lowered-floor refusal with its direction
  separation, the strengthening capture passing untouched, and the acceptance flipping the
  real verb's exit code.

## Outcome

### Every guard on the capture described the report, none described the movement

`record_baseline` checked three things: the read was not degraded, the report had rows,
and a note was supplied. All three describe the report in isolation. Nothing compared the
capture against the baseline it was about to overwrite, so `--record` accepted a raised
ceiling or a lowered floor without a word. The note requirement looks like a guard and is
not one: it proves a sentence was typed, never that the sentence describes the movement,
and its own field documentation says the note exists because a capture in a shared
worktree is a snapshot of a MOVING tree.

The two directions fail differently and only one of them heals. A raised ceiling is loud:
the backlog it now permits shows on the census and the coverage screen, and the next
honest capture pulls it back down. A lowered floor is silent forever. A capture taken
while a peer's half-landed change has removed revisions permanently lowers
`composed_revisions`, and from that moment a genuinely half-read tree passes the
anti-vacuity check that exists to catch exactly that. The guard that would have caught the
disarming is the one that was disarmed.

The capture is now diffed against the baseline on disk, every weakened counter is named
with its direction, and taking one requires saying so. The refusal also asks for the note
to name the counter, which is what makes the acceptance auditable rather than merely
permitted.

The escape hatch is deliberate. A refusal with no sanctioned way past it teaches the next
author to hand-edit the baseline JSON, which is the unrecorded act the guard exists to
remove, so the flag is wired through to the shipped verb and proved there.

### The seed test encoded a census fact and would have died on its first success

`test_the_committed_baseline_seeds_the_operator_backlog_at_its_true_value` asserted the
operator ceiling equalled the `composed_revisions` floor. Those two numbers are equal only
because nothing in the tree carries an operator signoff. The first genuine signoff makes
the honest ceiling 89 against a 90 floor, and the test fails for a reason having nothing to
do with seeding — at the exact moment the campaign succeeds, with a message pointing at
nothing actionable. The cheapest fix available to whoever met that failure is to delete it.

It is re-anchored to a fresh measurement taken through the real recording path. The
invariant that survives is the one worth keeping: the committed ceiling equals what the
tool measures. Above the measurement is headroom, and a revision can lose its signoff
inside it without the gate noticing; below it the gate is already red. Both readings resolve
to the same instruction, which the assertion message now gives.

### Verification

The comparison is proved by disabling it in production code. Three cases flip and the
strengthening case correctly does not:

```
FAILED ...::test_recording_refuses_a_capture_that_raises_a_ceiling
FAILED ...::test_recording_refuses_a_capture_that_lowers_a_floor
FAILED ...::test_an_accepted_weakening_is_written_and_the_acceptance_reaches_the_real_verb
3 failed, 2 passed in 46.94s
```

The lowered-floor case seeds a report that STRENGTHENS two ceilings while weakening one
floor, and asserts the fold reports exactly the floor:

```
('floor composed_revisions would fall from 90 to 89, demanding less measurement',)
```

so a guard refusing any movement at all would fail it rather than pass it.

The re-anchored seed test is proved by bumping the committed operator ceiling by one and
running it:

```
AssertionError: the committed operator ceiling has drifted from the measurement;
  re-record the baseline
assert 91 == 90
```

The committed baseline file was captured to the scratchpad before the bump and restored
byte-identically after, verified by comparison.

Real verbs and both dev gates:

```
uv run --no-sync python -m dev.registry.conformance audit --check  -> exit=0
uv run --no-sync python -m dev.registry.conformance coverage       -> exit=0
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
62 tests collected / 62 passed in 67.57s
uv run --no-sync pytest dev/tests/test_registry_conformance_gate.py -m integration -q --no-header
2 passed in 116.44s
```

The gate module carries the `integration` marker, so a bare path invocation DESELECTS both
its tests and reports "no tests collected (2 deselected)" while exiting cleanly. It was run
under its own marker rather than left as a green-looking no-op.

Style and lint:

```
uv run --no-sync ruff format --check ...  -> 6 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator direction; the
service is stopped and its index is broken. Grounding was by whole-file reads and `rg`.

The comparison fires only when a baseline already exists at the resolved path, so a first
capture to a new path is unaffected and every existing test that captures to a fresh
temporary file is untouched by it.

The bump-and-restore probe also surfaced that the committed `declared_grounding_claims`
floor stands at 58 against a live measurement of 59, left by the peer step that landed the
M303 prorrata percentage as an enforced oracle. A floor RISE is a strengthening, so the new
guard is silent on it and the committed floor still passes; it is recorded here because the
next capture will fold it in, and a reader comparing the two numbers should know why they
differ.

### Fifth-hole sweep, carried forward

Recorded here because the S53 and S54 records forward-reference it. Every item below was
MEASURED, not reasoned, and none is fixed: each needs its own Step, and landing a fix
outside a Step would produce a commit with no plan row and no execution record.

**H1, HIGH. The same byte defect S54 fixed is still live in the other dev-side writer.**
`record_baseline` writes through `write_text`, so on Windows every capture leaves the
committed baseline CRLF while git stores it LF under `eol=lf`, and `git diff` reports
nothing:

```
HEAD blob     CRLF 0  / LF 28 / 1932 bytes
working tree  CRLF 28 / LF 28 / 1960 bytes
identical: False
git diff sees a change: False
```

This is the state of the tree right now, not a hypothetical. The fix is the same one-line
change: encode and `write_bytes`. It matters more than it looks, because the baseline is
the artefact the gate reads, so its on-disk bytes and its committed bytes silently differ
for every reader that is not git.

**H2, MEDIUM. A reviewer-only restatement inherits the previous reviewer's date.** With no
date supplied, the merge carries the declared `reviewed_at` forward, so a new claim is
recorded against an old claim's date:

```
stamp --review-status agent_reviewed --reviewed-by agent:first --reviewed-at 2026-01-15
stamp --reviewed-by agent:second
-> agent_reviewed | agent:second | 2026-01-15
```

The CLI's today-defaulting fires only when the status is explicitly supplied, so it does
not cover this path either. In the one axis that is declared rather than derived, that is a
provenance smear: the record states a person reviewed a revision on a day they did not.
Either default the date whenever the reviewer changes, or refuse a reviewer change that
does not restate the date.

**H3, MEDIUM, structural, and the most likely place round five lands.** The
effective-status guard reads the status from the MANIFEST TEXT. The compiled revision is
the authority, and `_assert_revision_is_compiled` already loads it and discards it. The two
agree today only because the loader refuses governance keys declared in fragments — the
laundering path that refusal exists to close. If that refusal ever regresses, or a future
governance source appears that the manifest does not carry, the guard falls through to
"nothing declared" and permits the write. Reading the declared status off the compiled
revision is free and strictly stronger.

**H4, LOW. A branch marked unreachable is reachable.** `_apply_governance` carries
`# pragma: no cover - _declared_governance proves the table exists` on its header lookup.
`_declared_governance` proves the TABLE exists in parsed TOML, never that the literal
header line matches the one exact spelling the lookup compares against. Two valid
alternatives parse to the same table and miss it:

```
"[revisions.'2019-y-siguientes']"   -> tomllib key ['2019-y-siguientes'] | exact-line match: False
'[ revisions."2019-y-siguientes" ]' -> tomllib key ['2019-y-siguientes'] | exact-line match: False
```

It fails safe, so the cost is a hand-authored manifest in either spelling being unstampable
with a confusing message — plus a comment that tells the next reader a branch cannot
happen when it can.

**H5, LOW. The `stamp` verb cannot be exercised without writing to the shipped registry.**
`stamp_revision` takes `registry_root`; the Typer command never passes one. So the only
CLI-level stamp coverage that can exist is a refusal caught at the parse boundary, and the
CLI layer's own logic — the today-defaulting of `reviewed_at`, the `StampError` to
`BadParameter` translation — has no end-to-end test at all. A `--registry-root` option
would close it; the containment check is already relative to whatever root it is given.

**H6, LOW. `--accept-weakening` is silently ignored without `--record`.** The verb already
refuses `--check` with `--record` and `--no-validate` with either, so the precedent for
naming a meaningless combination is set.

**H7, LATENT. The line editor's table-end scan can be fooled.**
`_apply_governance` ends the revision table at the first following line starting with `[`,
so a hand-authored multi-line array with an element beginning at column zero would truncate
the table early and the governance lines would land inside the array. No shipped manifest
has that shape, and the post-write reload catches it, so it fails safe. Noted because it is
a second genuine post-write-failure trigger: the S54 record defers refusing control
characters in an identity until a replacement trigger for the rollback proof exists, and
this is a candidate.
