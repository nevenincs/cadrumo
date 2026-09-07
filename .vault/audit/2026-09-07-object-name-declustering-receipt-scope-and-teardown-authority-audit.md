---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:201b6801f64a3aee340cab27d69c2828f6b96baac0a79722594a06e9da993853'
related:
  - "[[2026-09-02-object-name-declustering-adr]]"
  - "[[2026-09-02-object-name-declustering-s23-concurrency-staleness-review-audit]]"
  - "[[2026-09-02-object-name-declustering-s24-scoped-receipt-review-audit]]"
---

# `object-name-declustering` audit: `receipt scope and teardown authority`

## Scope

Reviewed the live rehearse/apply pipeline against the accepted declustering ADR and the
`S23` and `S24` review audits, using twenty-one consecutive refusals of one four-operation
batch (`Lexicals` -> `LexicalSet` in `src/cadrumo/application/filing/export_producer.py`) as
the evidence corpus. Every refusal was read, reproduced where a clone was retained, and
attributed. No renames were landed; the working tree is unchanged at
`export_producer.py`.

The question under review is not whether the gates are correct -- they refused correctly
every time -- but whether the receipt's binding scope and the replay's teardown path let a
verified operation ever complete in a repository under concurrent development.

## Findings

### s23-high-finding-is-not-closed | high | Unrelated churn still refuses a valid leaf operation

The `S23` review recorded, at `high`, that the manifest relaxation "does not survive
rehearsal or replay" and that "the approved step objective -- preventing unrelated churn from
invalidating a leaf operation -- is not achieved". `S24` was the closure step. The plan now
reports 24 of 24 steps closed.

The objective is still not achieved. A rehearsal completed at 14:25:04 emitting a green
receipt (`9f1ae6fd...`, finding delta 459 -> 455, zero introduced). A freshness check forty
seconds later refused it: the receipt's `inventory_digest` was `481bd62a...` against a live
`71488bdf...`. A second check a minute afterwards read `866f380f...`. Three consecutive
inventory scans in the same minute returned an identical digest, so the value is
deterministic; it moves because the tree moves.

The scale of the movement is the point. Fifty files were dirty in the worktree, and
inventory-affecting commits landed roughly every six minutes at peak (14 in 90 minutes;
48 commits between one receipt's cut and its apply). A rehearse-plus-apply cycle takes
approximately 65 minutes. The receipt therefore expires long before the operation it
authorises can complete, and no retry strategy closes that gap.

One earlier apply reached its verification step and refused with `regenerated transformation
or verification differs from the receipt` after 34 minutes of work, which is the same defect
observed from the other end.

### s24-churn-teeth-are-vacuous | high | The test that should catch this cannot fail

The `S24` review already recorded this as `inventory-churn-integration-teeth`: replay's
unrelated-churn success test edits `dev/untracked.txt`, "outside the Python declaration
census, so neither the current inventory digest nor selected graph evidence changes", and
concluded "the committed suite would not catch reintroduction of receipt/current
global-inventory equality".

That is a gate which is green because it cannot fail, in the sense adjudicated by
`2026-09-07-quality-gate-zero-closure-blind-green-gates-adr`: green, fast, accurately named,
and silent through the exact defect it was written to catch. It was recorded at `medium` as a
missing-teeth observation; under that accepted decision it is a gate failure, and it is the
mechanism by which a `high` finding came to be reported as closed.

### teardown-can-overturn-a-verified-result | high | Cleanup failure reverted an apply whose gates all passed

`_run_gates_in_verified_copy` removed its temporary copy with a bare `shutil.rmtree` inside a
`finally`. On Windows that raises `WinError 145` whenever anything inside the copy is still
held. Raising from `finally` replaced the function's real result, so the `OSError` became
`apply_error` at `dev/quality/object_name_replay.py:595` and the live tree was rolled back.

Observed once, on a run whose six gates had all passed: the apply wrote the tree, the
post-apply verified copy could not be deleted, and the writes were reverted with
`live replay failed and was rolled back: [WinError 145] ... \.vault\data`.

The distinction the code did not draw is between an artefact that is evidence and one that is
litter. The transaction root's removal is semantically meaningful and is correctly strict; the
verified-copy root lives in system temp, holds nothing the caller still needs, and its removal
proves nothing about the replay. Fixed in `069c01a78d`: the removal retries past a read-only
bit and then gives up quietly, leaving the directory rather than failing verified work. The
regression test refuses the removal the way Windows does and asserts the replay still applies;
reverting either call site fails it.

No accepted record states the invariant, which is why the defect was available to be written.

### transaction-residue-accumulates-with-no-disposition | medium | Retained evidence has no owner or lifecycle

A failed replay deliberately retains its transaction root, and `_create_transaction_root`
refuses to start while one exists, demanding "explicit operator inspection". That is correct
design. There is no verb that discharges one, so disposition is manual and unrecorded.

Three roots were present. The one belonging to this campaign's receipt was inspected and
proven inert -- members exactly `.absent-paths` (empty) plus one backup file, and that backup
byte-identical to both the live tree and the receipt baseline `a000b473...` -- then removed so
the batch could proceed. Two older roots remain untouched and undisposed: `51d62ca4...`
(3 files, 2026-09-06) and `815c231d...` (11 files, 2026-09-05).

### freshness-checking-covered-a-subset-of-the-binding | medium | A support tool reported fresh against a stale receipt

The campaign's `receipt_fresh.py` hashed only `baseline_files` -- the receipt's changed paths.
A receipt also binds `inventory_digest`, `manifest_digest`, `baseline_tree_digest` and seven
gate outcomes. The tool therefore reported `RECEIPT FRESH` while 48 peer commits had moved the
inventory, and two applies were fired on that green and refused after their full run.

The tool is session scratch, not repository code, so this is recorded as evidence rather than
as a defect in a shipped surface: it is the same class as the two findings above, committed
independently, one layer up. It now compares `inventory_digest` and exits non-zero, which
caught a forty-second-old receipt in seconds instead of after a 34-minute apply.

## Evidence

- Refusal corpus: 21 refusals of one batch across 16 rehearse/apply attempts, 2026-09-07
  09:26 to 14:25. Attributed causes: broken gate at HEAD (4), peer mid-refactor working tree
  (3), retained transaction root (1), teardown cleanup (1), receipt staleness (2), operator
  invocation error (1), the remainder environment. **None attributable to the renames.**
- `dev/quality/object_name_replay.py:589-602` (rollback path), `:317-319` (verified-copy
  teardown), `:334-337` (`_create_transaction_root` refusal), `:651` (transaction removal
  gated on `not primary_failure_active`).
- Inventory determinism probe: three scans at 14:26:05 / :28 / :50, all `866f380f...`.
- `git status --short | wc -l` = 50 dirty files at time of measurement.

## Recommendations

Reopen the `S23` objective rather than re-deriving it. The ADR already states the required
distinction -- "finding identity must survive unrelated movement, while execution must refuse
concurrent byte changes; these require separate hashes" -- and the `S23` review already wrote
the remedy: rehearsal records the *current* scanned digest, replay compares against a freshly
scanned current inventory, and the authored inventory value stays bound only through the exact
manifest digest. What is missing is that carried through receipt generation and replay, plus a
churn test that perturbs a real Python declaration so it can fail.

State the teardown invariant in the record so it is not re-lost: cleanup of an artefact
outside the unit of work is best-effort and may never convert a verified result into a
failure; cleanup whose success is semantically meaningful stays strict and says so.

Give the retained transaction root a disposition path, so "explicit operator inspection"
resolves to a recorded action rather than an accumulating directory.
