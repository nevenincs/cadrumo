---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S16'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# add the stamp verb writing the per-revision governance scalars with vocabulary and coherence validation

## Scope

- `dev/registry/conformance/_stamp.py`

## Description

- Add `_stamp.py` with `stamp_revision`, a narrowed `StampableReviewStatus` vocabulary,
  containment-checked manifest resolution, and a typed internal stamp record.
- Wire the `stamp` verb onto the CLI with the four governance options plus
  `--clear-engineered-by`.
- Validate the intended stamp by asking the real revision schema through a probe revision,
  before touching the file.
- Re-load the whole modelo through the real loader after writing, restoring the previous
  bytes if it refuses.
- Promote `REVISION_GOVERNANCE_FIELDS` to the registry package facade and derive the
  writer's key set from it, removing a hand-listed second copy of a closed set.
- Refuse a whitespace-only authorship or reviewer identity, and trim what is written.

## Outcome

### Ruling: this CLI may not write `operator_reviewed`, deliberately

`StampableReviewStatus` carries exactly two members — `pending_review` and
`agent_reviewed` — and `operator_reviewed` is absent by decision, not by omission.

The reasoning. This CLI is driven by agents. An agent writing "the operator reviewed this"
is precisely the dishonesty the whole conformance feature exists to detect, and it is
worse than an unreviewed backlog because it is invisible: a false `operator_reviewed`
stamp is indistinguishable in every rendered row from a true one. No flag repairs it. An
`--i-am-the-operator` switch is exactly as assertable by an agent as the value itself, so
it would add the appearance of assurance and none of the substance — and an appearance of
assurance is worse than none, because a reader trusts it.

The registry schema still accepts the value, which the governing decision explicitly keeps
legal, so the operator retains full ability to sign off by editing `revision.toml`
directly. That friction is the feature, not a gap: operator signoff stays a human act on
the file, and this tool cannot manufacture one. The narrowing is a NARROWING of the core
vocabulary and not a second taxonomy — every member's value is byte-identical to its core
counterpart, pinned by a test that also pins the deliberate absence.

The narrowed enum is declared as the Typer option type, so the refusal lands at the parse
boundary with the accepted set named rather than as a late error:

```
Invalid value for '--review-status': 'operator_reviewed' is not one of
'pending_review', 'agent_reviewed'.
```

### The write path cannot open a second laundering vector

A stamp declared inside a per-section fragment once merged silently and won, so a revision
could read unstamped in `revision.toml` while the compiled snapshot claimed a completed
review. The loader now refuses that outright, and this writer must not reopen it. It
writes ONLY the governance scalars, ONLY into the revision's own `revision.toml`, and only
after the revision has been confirmed to exist as a COMPILED record rather than as a
directory that happens to be on disk. A test snapshots every file under the revision
directory and asserts exactly one changed.

The coherence rule is asked of the real schema rather than mirrored. A probe revision
carrying the intended stamp is validated by `ModeloRevision` itself, so the refusal a
caller sees is the refusal registry build would raise and this module cannot drift from
it. After the write the whole modelo is re-loaded through the real loader; if it refuses,
the previous bytes are restored and the refusal is raised, so a state the loader would
reject is unreachable through this path.

### A silent drop found and closed during execution

The first draft DROPPED a reviewer supplied while the status stayed `pending_review` and
reported success. That is the same shape as the defect this feature exists to surface: the
caller asked to record a review, the tool discarded the request, and the report would show
an unreviewed revision the operator believed was stamped. It is now a refusal naming the
flag that would make the request coherent. Returning the status to `pending_review`
without supplying a reviewer still drops the declared identity, which is correct — the
identity must leave with the claim it attests to.

Following the coordinator's note that `reviewed_by` accepts a whitespace-only string, the
writer now refuses an identity that names nobody and trims what it writes. The schema fix
is the deeper gate and lands separately; this is the CLI boundary refusing to write a
value it can already see is empty of content.

`--clear-engineered-by` exists because without it the first write of an authorship claim
would be a one-way door and a wrong name uncorrectable.

### Verification

Exercised against a byte copy of the real shipped modelo 130 tree — real fragments, real
loader, real schema. The verb was deliberately NOT run against the shipped registry:
stamping a real revision `agent_reviewed` would write a review claim nobody made, which is
the exact dishonesty this ruling is about. Actual output:

```
stamped modelo=130 revision=2019-y-siguientes manifest=revision.toml
  engineered_by="conformance-cli campaign" review_status="agent_reviewed"
  reviewed_by="agent:opus-executor" reviewed_at=2026-07-27 removed=-
```

and the resulting manifest, with the hand-authored arrays untouched:

```
[revisions."2019-y-siguientes"]
label = "Orden HAP/258/2015, ejercicios 2019 y siguientes"
valid_from = 2019-01-01
period_selector = { year_from = 2019, periods = ["1T", "2T", "3T", "4T"] }
orden_aplicabilidad = ["orden-eha-672-2007:art-1"]
legal_refs = ["rd-439-2007:art-110", "orden-eha-672-2007:art-1", "ley-35-2006:art-99", "rd-439-2007:art-95"]
source_refs = ["aeat-dr-130-2019-v12", "aeat-modelo-130-instructions"]
engineered_by = "conformance-cli campaign"
review_status = "agent_reviewed"
reviewed_by = "agent:opus-executor"
reviewed_at = 2026-07-27
```

Returning to the backlog drops the identity:

```
stamped modelo=130 revision=2019-y-siguientes manifest=revision.toml
  engineered_by="conformance-cli campaign" review_status="pending_review"
  removed=reviewed_by,reviewed_at
```

Refusals, actual messages:

```
refusing to record ['reviewed_by'] while review_status is 'pending_review': the schema
  refuses a reviewer attached to a review the status denies. Record the review by also
  passing review_status='agent_reviewed'
nothing to stamp: supply at least one of engineered_by, clear_engineered_by,
  review_status, reviewed_by, reviewed_at
modelo id '../../etc' is not a plain registry identifier; accepted shape is letters,
  digits, dot, dash and underscore, starting with a letter or digit
engineered_by names nobody: a provenance claim must identify the person or agent it
  attributes the work to, and whitespace identifies neither
```

The line editor is deliberate rather than a TOML round-trip: a full re-serialisation would
reformat every hand-authored multi-line array and bury the one-line stamp in an
unreviewable diff.

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator direction;
grounding was by whole-file reads and `rg`.

A cleared revision keeps an explicit `review_status = "pending_review"` line rather than
reverting to a pristine manifest. Absence already reads as `pending_review`, so the line
adds no derived fact — it adds a stated one, and a manifest that says what it means beats
one a reader must know a default to interpret. Recorded because it means a stamp is not
byte-reversible.

`_stamp.py` first reached HEAD inside a peer's no-pathspec commit `ec789b9243`, which
swept my staged files. Nothing was lost; the committed bytes were diffed against the
working tree and are what I intended, and my own later commits `b76af2d111` and the
identity-refusal commit carry the reasoning. Recorded so the trail is honest about the
mis-attribution rather than tidy.

A duplication was found and closed mid-Step. A peer landed a change deriving
`REVISION_GOVERNANCE_FIELDS` from the field declarations themselves, making it the sole
input to the loader's fragment refusal, while this writer still hand-listed the same four
names. Two copies of one closed set meant a fifth governance scalar could reach the
loader's refusal and never reach the writer. The set was promoted to the registry package
facade — the precondition of the consuming change, not a follow-up — and only the emit
ORDER remains dev-side, appending any field the order does not name rather than dropping
it.
