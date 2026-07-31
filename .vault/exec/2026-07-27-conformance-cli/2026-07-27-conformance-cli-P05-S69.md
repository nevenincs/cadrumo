---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:fd759939831e18d28aaccb67ccee0e707cab064b5338b2c0202d0bf5b6b57592'
step_id: 'S69'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# measure and gate the tree-wide terminator drift where over a thousand tracked files carry on-disk bytes differing from their committed bytes while git diff stays silent, so the class is bounded rather than known only anecdotally

## Scope

- `dev/audit/checkout_drift.py`
- `dev/audit/checkout_drift_baseline.json`
- `dev/audit/tests/test_checkout_drift.py`
- `justfile`
- `pyproject.toml`

## Description

- Build the measurement: every tracked path at HEAD, minus the paths git
  reports modified, hashed on its raw disk bytes against its committed blob.
- Reimplement git's object naming so the comparison bypasses the input filters
  that hide the class, and check that reimplementation against git itself.
- Refuse a walk that found no tracked files, and separately a walk that hashed
  none.
- Record a shrink-only ceiling with per-tree counters, written with a pinned
  terminator so the screen's own baseline cannot enter its own worklist.
- Add the ratchet comparison and the `--check` exit, defaulting to the screen
  posture.
- Resolve the git executable rather than relying on argv shorthand, and
  register the remaining subprocess lint under the established per-file entry.
- Wire the screen into the task runner and into the aggregate advisory run.

## Outcome

### Re-measured, because the reported figure was hours old

The brief carried 1458 CRLF-bearing files, 1155 of them drifted. That number
had moved, and the peers landing continuously are why. Measured fresh at live
HEAD `a58bee2c1f`:

```
tracked files at HEAD: 37817
files git reports modified: 723
candidates (tracked, git-clean, present): 37094

SILENTLY DRIFTED: 1142
  of those carrying CRLF on disk: 1142
  src 542 | docs 309 | .vault 203 | dev 78 | packaging 3 | .github 2
  plus 5 root files
```

Two findings the earlier figure did not state.

First, the class is entirely ONE mechanism. All 1142 carry CRLF; not one is
drifted for any other reason. So this is not a general "disk differs from
commit" population with a terminator subset — terminator translation IS the
population, which is what makes a single fix at each writer a complete remedy
per artefact.

Second, and this is what decided the posture, the composition by file type:

```
.py 430 | .json 245 | .md 212 | .toml 145 | .seq 87 | .po 9 | .html 7
```

That is overwhelmingly hand-edited source. It is produced by contributors'
editors, not by any generator this repository controls. The number also moves
under observation: across this session's runs it read 1142, 1137, 1141 and
1136 as peers landed and as ordinary edits moved files in and out of the
git-modified exclusion.

### Screen, not gate, and the reason is attribution rather than size

RULING: a screen. The default run always exits 0.

Size alone would be a weak argument — a large worklist is exactly what a
shrink-only ratchet exists to hold. The decisive property is that the
population is NOT OWNER-ATTRIBUTABLE. A ceiling pinned at 1136 goes red the
moment any contributor opens any of 37000 files in an editor that writes
platform terminators. That contributor did not create the defect, cannot see
it, and has no way to tell their red from a real one. It is the failure mode
this campaign already recorded twice in its own governance ceilings: a
population pin forces an operator to assert they are weakening a ratchet in
order to land an honest change.

So the teeth exist but are not wired. `--check` applies the shrink-only
ceiling and exits 1 with a per-tree growth report; nothing invokes it in a
blocking lane. Growth is made VISIBLE rather than fatal, which is the property
the class actually lacked — it was never that the number was too high, it was
that no number existed at all. The module states the promotion condition
outright: wire `--check` when contributor tooling writes LF and the ceiling
sits near zero, at which point a red is a real event.

The ceiling carries per-tree counters, not only a total, and a tree absent
from the ceiling is compared against zero. Without that, an entire new tree
could drift while the total moved too little to notice.

Mass-normalisation was considered and refused. It would rewrite every
concurrent contributor's working tree in one sweep and buys nothing durable
while the tooling that produced the drift is unchanged.

### Verification

Four mutations, each flipping a different mechanism.

Normalising the bytes before hashing — that is, making the instrument blind in
exactly the way every other reader in the tree is blind — collapses the finding
set to empty:

```
E   AssertionError: assert () == ('module.py',)
E   AssertionError: assert () == ('translated.py',)
E   AssertionError: assert {} == {'pkg': 1}
3 failed, 5 passed
```

This is the sharpest of the four. The screen has value only because it does
not normalise, and this is that claim as an executable statement.

Dropping the git blob header from the object naming produces the opposite
failure, a false positive on everything, and the git-agreement case names the
cause rather than leaving a reader to infer it from the noise:

```
E   AssertionError: assert ('.gitattribu..., 'module.py') == ('module.py',)
E   AssertionError: object name disagrees with git for lf.txt
4 failed, 4 passed
```

That case exists because the reimplementation is the single point where the
whole instrument could be systematically wrong while every other assertion
still passed. Checking it against git rather than against a remembered
algorithm is the difference between a measurement and a guess.

Removing the git-modified exclusion turns every contributor's live work into a
finding:

```
E   AssertionError: assert ('edited.py', 'translated.py') == ('translated.py',)
1 failed, 7 passed
```

Removing the second vacuity floor:

```
E   Failed: DID NOT RAISE SystemExit
FAILED ...::test_measure_refuses_when_every_tracked_file_is_excluded
1 failed, 7 passed
```

The two floors are separate on purpose. A tree with no tracked files and a
tree whose every tracked file is excluded both report zero drift, and zero
drift is what a healthy repository reports. Only one of the two is caught by
an emptiness check on the tracked set.

Every mutation was reverted and the module diffed byte-for-byte against a
pristine copy taken before the first one.

The ratchet was also proved end to end rather than only through its unit, by
seeding an artificially low ceiling on the real tree:

```
python -m dev.audit.checkout_drift --check
checkout drift: FAIL - a counter moved in the weakening direction.
  total 1137 exceeds the recorded ceiling 5
  .vault/ 196 exceeds the recorded ceiling 0
  docs/ 309 exceeds the recorded ceiling 0
  src/ 544 exceeds the recorded ceiling 0
EXIT=1
```

and exit 0 after re-recording the honest ceiling. A ratchet never observed
refusing is not a ratchet.

Final state:

```
uv run --no-sync pytest dev/audit/tests/test_checkout_drift.py -q
8 passed in 4.55s

uv run --no-sync pytest src/cadrumo/tests/test_dev_tree_lane_coverage.py -q
4 passed

just audit-checkout-drift                     -> exit=0
python -m dev.audit.checkout_drift --check    -> exit=0 (within the ceiling)
```

Style, lint and types:

```
uv run --no-sync ruff format --check ...  -> 2 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
uv run --no-sync ty check ...             -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator
direction; the service is stopped and its index is broken. Grounding was by
whole-file reads and `rg`.

The one lint suppression here is scoped, and half of it was refused. Ruff
flagged both a subprocess call and a partial executable path. The partial path
was FIXED rather than suppressed — the executable is resolved, which also turns
a missing git into one plain sentence instead of a file-not-found traceback
from inside a measurement. Only the subprocess rule is registered, under the
entry the sibling audit runners already use, with the reason stated.

The screen reads the tree through git twice and hashes 37000 files in about
ten seconds. That is acceptable for an advisory run and is why it is wired into
the aggregate advisory recipe rather than into a per-commit lane.

INCIDENT, and it is the same self-inflicted one this Step measures. Editing
`pyproject.toml` translated 1031 terminators in it. It was caught by running
the very screen this Step adds, and normalised before the commit. Two of the
three hand-edited files this session touched drifted this way. That is the
mechanism reproducing itself under observation, and it is the concrete evidence
for the posture ruling above: if the tooling in use by the agent writing the
instrument drifts a file per session, a population ceiling is not something any
contributor can hold.

A residual `.git/index.lock` blocked staging twice during this work. It was
diagnosed by handle probe rather than by elapsed time, moved aside rather than
deleted the first time, and waited out the second. No destructive git operation
was run.
