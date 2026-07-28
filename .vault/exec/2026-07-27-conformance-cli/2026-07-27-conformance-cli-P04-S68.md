---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S68'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# write the two sibling audit baselines and the generated api stubs through explicit newline handling, and fix the stub drift check which reads with universal newlines so a translated stub compares equal to the writer that translated it

## Scope

- `dev/docs/apidocs/manager.py`
- `dev/docs/apidocs/tests/test_manager.py`
- `dev/docs/tests/test_api_stubs.py`
- `dev/audit/complexity.py`
- `dev/audit/tests/test_complexity_baseline_capture.py`

## Description

- Extract the stub comparison into one named predicate and compare BYTES, so
  the terminators survive to the comparison instead of being folded away by
  the read.
- Pin the stub writer's terminator with an explicit newline, matching the
  sibling generators in the same package family that already did.
- Pin the complexity baseline capture's terminator the same way.
- Record at each change site what the previous shape did, with the measurement.
- Add the planted-drift proof, the writer proof, and the rewrite proof for the
  stubs, and the capture and two-scope proofs for the baseline.
- Add two gates that read the real committed artefacts rather than files a
  test just wrote.
- Rewrite the 60 drifted stubs and the two drifted baselines to their
  committed bytes.

## Outcome

### The check was blind to its own writer, on the live tree

Measured before touching anything. Every number below is from the committed
tree as it stood:

```
dev/audit/complexity_baseline.json
  disk CRLF=660 LF=660 bytes=66087
  HEAD CRLF=0   LF=660 bytes=65427   identical=False
dev/audit/size_budget_baseline.json
  disk CRLF=74  LF=74  bytes=7985
  HEAD CRLF=0   LF=74  bytes=7911    identical=False
docs/api: 1240 stubs, 60 carrying CRLF on disk

python -m dev.docs.apidocs scaffold --check
Stub tree is conformant. No drift detected.   -> exit=0
```

Sixty generated files whose on-disk bytes differed from their committed bytes,
and the dedicated drift check for exactly those files reported the tree clean.
Two independent normalisations were folding the difference away: the check read
through a universal-newline text open, and the repository normalises to LF on
the index side, so `git diff` was silent on the same files. Every reader the
system had was blind, and the writer that introduced the drift was the checker's
own.

The fix is one comparison on bytes plus an explicit terminator on both writers.
Neither is novel here; the sibling generators in the same package family — the
CLI reference, the glossary reference, the casilla reference, the download
matrix, the pagefind injector — already write this way. The hazard was known in
the family and had not been swept into these two.

### The gates were RED on the live tree before the restore

This is the half that matters. A capture proof only measures files a test just
wrote, so it would have left the real artefacts drifted forever. Reading the
committed files is the read nothing in the campaign performed, and both gates
failed on the tree as found:

```
FAILED dev/docs/tests/test_api_stubs.py::test_every_source_module_has_a_stub
E   Stubs whose content differs from the generator (60): cadrumo.adapters.inbound.tui ...

FAILED dev/docs/tests/test_api_stubs.py::test_the_committed_stub_tree_carries_untranslated_terminators
E   AssertionError: 60 of 1240 committed stubs carry translated terminators, so their
    on-disk bytes differ from their committed bytes and no diff can show it
2 failed in 4.23s
```

The correspondence gate had been passing on this tree for as long as the drift
existed; the byte comparison is what turned it red. The restore was then the
writer proving itself:

```
python -m dev.docs.apidocs scaffold
Scaffolded 60 changed stubs, left 1180 unchanged, removed 0 stale stubs.

stubs scanned         : 1240
carrying CRLF on disk : 0
differing from HEAD   : 0
```

All 1240 stubs are now byte-identical to their committed blobs, so the restore
carries no content change and the stubs are absent from the commit's pathspec.
The two baselines were restored the same way, with content equality ignoring
terminators asserted FIRST so the write was proved to be a normalisation and
never a revert of a committed measurement:

```
dev/audit/complexity_baseline.json:  restored 66087 -> 65427 bytes, identical=True
dev/audit/size_budget_baseline.json: restored  7985 ->  7911 bytes, identical=True
git diff --stat -- (both)  ->  empty
```

### Verification

Two mutations on the stub manager, one per half of the defect, each flipping a
different set of assertions.

Reverting the comparison to the decoded-text form is the decisive one. The
planted CRLF stub compares equal and the check reports nothing at all:

```
E   AssertionError: assert 'cadrumo.core.errors' in []
E   AssertionError: expected the one translated stub to be rewritten, got 0
FAILED ...::test_check_detects_a_terminator_translated_stub
FAILED ...::test_scaffold_rewrites_a_terminator_translated_stub
2 failed, 8 passed
```

That is the live defect reproduced in a test: `stale_stubs == []` for a file
that genuinely differs on disk. The second failure is the compounding half —
the skip-if-current branch shares the comparison, so the drift would never have
been rewritten either.

Reverting the writer's explicit terminator flips six, and the two that matter
most are the ones that were previously green with the drift present:

```
E   AssertionError: the generator translated terminators in 1240 stubs
E   AssertionError: Drift after scaffold - missing: [], orphans: []
    stale_stubs=['cadrumo', 'cadrumo.adapters', ...]
6 failed, 4 passed
```

The byte comparison catches the translating writer immediately and universally,
which is precisely the feedback loop that did not exist before.

The complexity capture mutation flips its two writer assertions and correctly
leaves the committed-artefact gate alone, because the mutation never touched
the real file:

```
E   AssertionError: the capture translated the file's terminators
E   AssertionError: the second capture translated the terminators of both scopes
FAILED ...::test_a_recorded_baseline_lands_as_untranslated_bytes
FAILED ...::test_recording_one_scope_leaves_the_other_scope_untranslated
2 failed, 1 passed
```

Every mutation was reverted and each module re-verified.

Final state:

```
uv run --no-sync pytest dev/audit/tests/test_complexity_baseline_capture.py \
    dev/docs/apidocs/tests/test_manager.py dev/docs/tests/test_api_stubs.py -q
15 passed in 19.82s

python -m dev.docs.apidocs scaffold --check
Stub tree is conformant. No drift detected.   -> exit=0

uv run --no-sync pytest src/cadrumo/tests/test_dev_tree_lane_coverage.py -q
4 passed in 4.27s
```

The lane check matters because the new test module lands in `dev/audit/tests`,
a directory two existing task-runner lanes already name, so it is executed
rather than merely present.

Style, lint and types over the five changed files:

```
uv run --no-sync ruff format --check ...  -> 5 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
uv run --no-sync ty check ...             -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator
direction; the service is stopped and its index is broken. Grounding was by
whole-file reads and `rg`.

DEFERRED, and it is a real gap in this Step's stated scope. The size-budget
baseline's WRITER lives at `src/cadrumo/tests/_size_budget.py`, inside a tree
this dispatch forbids touching. Its data file is under `dev/audit` and was
restored, and the committed-artefact gate added here covers BOTH baselines
rather than only the writer this package owns — so a re-drift is caught. But
the next `--write-baseline` run through that writer will re-translate the file
and red the gate, which is the correct failure and the wrong owner. The writer
needs the same one-argument change; it is a two-line edit whose only obstacle
is the ownership boundary.

The gate covering both baselines rather than one is a deliberate choice against
tidiness. A reader that covers only the artefact whose writer it owns leaves
the sibling with no reader at all, which is how this class survived: every
individual surface was locally consistent.

The carriage-return assertions are decisive only on a platform whose line
separator is not already LF, which is where the drift was measured. On a
line-feed platform they hold trivially. That scope is stated in each docstring
rather than left for a reader to discover, and the byte-equality assertions in
the capture proofs carry the case independently of platform.

INCIDENT, minor and self-inflicted, and it is this Step's own thesis landing on
its author. The first `git add` warned that `dev/docs/tests/test_api_stubs.py`
carried CRLF — the editing tool had written 82 translated terminators into the
very file that gates against them. Committing it would have been harmless to
git and would have left the working copy drifted from its own blob on the first
checkout. The file was normalised before the commit. The lesson is the measured
one: this drift arrives through ordinary tooling, silently, and the only reader
that catches it is one that looks at bytes.

INCIDENT, environmental. A zero-byte `.git/index.lock` blocked staging for
about six minutes. It was diagnosed rather than assumed: an exclusive-open
probe and then a rename probe, the latter conclusive on this platform because a
live handle without delete-sharing refuses the rename. The rename succeeded, so
the lock was residue from a dead process. It was MOVED aside to the scratchpad
rather than deleted, so the decision is reversible. A second lock appeared
later and was genuinely live; that one was waited out and released on its own.
No destructive git operation was run at any point.
