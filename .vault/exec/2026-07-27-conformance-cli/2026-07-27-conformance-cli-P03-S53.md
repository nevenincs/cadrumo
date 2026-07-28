---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S53'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# apply the vocabulary refusal to the effective review status resolved from the manifest, not only the requested one, so an agent cannot re-attribute an existing operator signoff to itself while leaving an authorship-only write legal

## Scope

- `dev/registry/conformance/_stamp.py`
- `dev/tests/test_registry_conformance_cli.py`

## Description

- Add `_assert_review_axis_is_writable`, reading the status the manifest already
  declares and refusing when the request touches `review_status`, `reviewed_by`, or
  `reviewed_at` while that declared status is outside the writable vocabulary.
- Key the predicate on membership of `StampableReviewStatus`, never on the single token
  `operator_reviewed`, so a fourth core status enrols itself in the refusal.
- Scope the guard to the review axis so an authorship claim on a signed revision stays
  legal.
- Narrow the module docstring and the requested-status coercion's docstring to what each
  actually enforces, and name the other half.
- Add a fixture seeding a hand-authored operator signoff on a real modelo copy, five
  parametrised refusal cases proved on bytes, the paired authorship-still-served case,
  and the in-vocabulary restatement case.

## Outcome

### The stamp could still lie, one layer under where the last round closed it

The third round coerced the REQUESTED status and stopped there. That closed the CREATION
of a false operator claim and left its ATTRIBUTION writable, and attribution is the whole
content of the claim, because a status alone names nobody. With no status supplied the
coercion returns `None` and never fires; the merge then resolves the effective status from
the manifest and writes the reviewer identity against whatever that manifest declares.

Reproduced against a byte copy of the shipped Modelo 130 tree carrying a hand-authored
operator signoff, before the change:

```
seeded : operator_reviewed | Gergely Wootsch (operator) | 2026-07-01

--- A. library call, no review_status supplied ---
ACCEPTED: stamped modelo=130 revision=2019-y-siguientes manifest=revision.toml
  engineered_by="the operator, by hand" review_status="operator_reviewed"
  reviewed_by="agent:opus-executor" reviewed_at=2026-07-28 removed=-
after  : operator_reviewed | agent:opus-executor | 2026-07-28
manifest byte-identical: False
```

A compiled revision claiming a completed operator signoff and naming an agent as the
signatory. Two properties make it worse than the case the previous round closed. It is
SILENT to every gate: the shrink-only counter CI protects is
`revisions_without_operator_review`, which counts revisions LACKING a signoff, and this
revision still has one, so the number does not move. And it DESTROYS the operator's real
name and date, which the governing decision calls underivable by construction, so nothing
in the tree can reconstruct what was overwritten. The two existing guards are structurally
unable to object: the pre-write schema probe passes because `operator_reviewed` is a legal
registry value, and the post-write reload passes because the tree still compiles.

Both module docstring claims covering this path were false. "Operator signoff stays a
human act on the file, and this tool cannot manufacture one" was false because the tool
could re-address an existing one, and "This one protects the CLAIM" was true only of the
claim a caller STATES, never of the claim the file already carries.

### The check now reads the status the write resolves to

`_assert_review_axis_is_writable` runs after the manifest is parsed and before the merge.
When the declared status is outside `StampableReviewStatus` and the request touches any
review-axis argument, the write is refused and the caller is sent to the manifest, which
is the same door a real signoff comes through.

The predicate is the VOCABULARY rather than the literal `operator_reviewed`, matching the
subtraction the operator ceiling already uses: a fourth status added to the core enum
without being added here enrols itself in the refusal instead of escaping it.

### Ruling: erasure is refused too

`--review-status pending_review` on a signed revision is refused by the same rule, and the
reasoning is not that it is equally dangerous but that the ratchet is the wrong instrument
for it. Clearing a signoff DOES red the gate, because it raises the operator backlog. It
reds it AFTER the name and the date are already gone, and those two fields are underivable
by construction, so the gate reports an unrecoverable loss rather than preventing a
recoverable one. A loud alarm over destroyed evidence is not a substitute for a closed
door. The ratchet catches destruction; only the refusal prevents it. Erasure is
parametrised alongside substitution in the durable test for that reason.

The one cost is that the tool can no longer help an operator withdraw a signoff. That is
consistent rather than a gap: the operator signs off by editing `revision.toml`, so the
operator un-signs the same way, and the refusal message says so.

### Authorship stays orthogonal

A blanket "the resolved status must be stampable" rule would have satisfied every refusal
above while refusing an honest `engineered_by` write on a signed revision for a reason
that has nothing to do with authorship. Who built a revision is a different fact from who
signed it off. `engineered_by` is deliberately absent from the review-axis set, and the
paired test asserts the write is served AND that the signoff survives it byte-for-byte in
the compiled record.

### Verification

The decisive proof is the identical probe script against an identical byte copy of the
shipped tree, run once before the change and once after. Only the module moved. After:

```
--- A. library call, no review_status supplied ---
REFUSED StampError: refusing to touch ['reviewed_by', 'reviewed_at']: ...revision.toml
  already declares review_status 'operator_reviewed', which is outside the vocabulary
  this CLI writes ('pending_review', 'agent_reviewed'). Restating the review axis here
  would re-attribute a signoff this tool could not have made, and would overwrite a
  reviewer identity and date that are underivable by construction, so nothing could
  restore them. Both advancing and clearing that claim are edits to the manifest, made by
  the same hand that made the claim. engineered_by is unaffected and remains writable.
after  : operator_reviewed | Gergely Wootsch (operator) | 2026-07-01
manifest byte-identical: True

--- B. the erase direction ---
REFUSED StampError: refusing to touch ['review_status']: ...
after  : operator_reviewed | Gergely Wootsch (operator) | 2026-07-01
manifest byte-identical: True

--- C. authorship-only write (must stay legal) ---
ACCEPTED: stamped modelo=130 revision=2019-y-siguientes manifest=revision.toml
  engineered_by="conformance-cli campaign" review_status="operator_reviewed"
  reviewed_by="Gergely Wootsch (operator)" reviewed_at=2026-07-01 removed=-
after  : operator_reviewed | Gergely Wootsch (operator) | 2026-07-01
```

The durable tests were separately proved to flip by mutating the production guard's early
return so it never refuses; five of the seven failed with `DID NOT RAISE StampError` and
the two paired positive cases stayed green, which is the correct shape. The mutation was
reverted and the file re-verified.

Full dev CLI module under the DEFAULT selector:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
51 passed in 49.19s
```

Style and lint:

```
uv run --no-sync ruff format --check ...  -> 2 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator direction; the
service is stopped and its index is broken. Grounding was by whole-file reads and `rg`.

The verb was NOT run against the shipped registry, following the S16 and S39 precedent.
Every write was against a byte copy of the real Modelo 130 tree.

The finding was reported as confirmed end to end through the real Typer app. It could not
be re-confirmed that way here without writing to the shipped registry, because the `stamp`
verb exposes no registry-root override: `stamp_revision` accepts `registry_root` but the
Typer command never passes it, so the only CLI-level stamp coverage that exists is a
refusal caught at the parse boundary. The refusal is proved at the writer's function
boundary instead, which is where it must live in any case, since that boundary is what a
driver script reaches. The missing override is carried as H5 in the fifth-hole sweep
recorded under Step S57 rather than added here.

The seeding fixture asserts the operator signoff COMPILED before any test reads it. A
refusal test whose fixture never established the state being refused would pass for the
wrong reason.
