---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S64'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# read the declared review status off the compiled revision the writer already loads rather than off the manifest text, so the signoff guard stops depending on the fragment refusal it exists to complement

## Scope

- `dev/registry/conformance/_stamp.py`
- `dev/tests/test_registry_conformance_cli.py`

## Description

- Return the compiled revision from the existence check instead of discarding it.
- Feed the review-axis guard that revision's status, and retype the guard to the
  compiled enum so the manifest-text value cannot be handed back to it.
- Record at the guard and in the module docstring why the authority is the
  compiled record and what the manifest reading was resting on.
- Add the assertion that the compiled record carries the signoff the writer
  refuses on.
- Add the fragment-laundering exhibit, with the safety assertion and the
  mechanism assertion separated.

## Outcome

### Verifying the assessment: free, yes; strictly stronger, yes; live defect, no

The Step asked for the "free and strictly stronger" assessment to be verified
rather than assumed, so all three halves were measured.

FREE holds exactly. `_assert_revision_is_compiled` already calls
`load_modelo_directory` and already indexes the revision map to decide existence;
it now returns the record it looked up instead of dropping it. One load, before
and after — a load costs about 31 ms on this modelo, and no second one was
introduced.

STRICTLY STRONGER holds. The manifest-text reading yields "nothing declared" when
the manifest is silent, and "nothing declared" is the PERMIT branch. So in the
one case the two readings could disagree — a signoff reaching the compiled record
from somewhere the manifest does not show — the old guard permits precisely the
write it exists to refuse. The compiled reading has no such branch, because the
schema fails closed to `pending_review`, so absence arrives as the in-vocabulary
value it means rather than as a `None` the guard would have to interpret.

A LIVE DEFECT does NOT hold, and that is worth stating plainly rather than
letting the fix read as a bug fix. Three routes to a divergence were built and
run against byte copies of the real Modelo 130 tree, and every one is refused
before the writer sees it:

```
fragment route        REFUSED: revision governance field 'review_status' must be
                      declared in the revision's revision.toml manifest, not in a
                      per-section fragment
sibling-file route    REFUSED: revision '2019-y-siguientes' already declared in
                      another revisions/*.toml file
modelo-manifest route REFUSED: directory-mode manifest must not declare [revisions]
```

That measurement IS the finding. The two readings agree today only because those
refusals hold, and the first of them is the laundering path the manifest-only
rule exists to close — so the guard's correctness was resting on the mechanism it
was written to complement. Removing that dependency is the whole content of this
Step, and no behaviour changes today because nothing can currently exercise the
divergence.

### The exhibit is kept runnable rather than described

The fragment-laundering construction is now a durable test rather than a sentence
in a record. It carries two assertions with different jobs. The write MUST NOT
land, which stays true whichever mechanism refuses it. And the refusal today is
the LOADER's, asserted by its own message: if that ever changes, the construction
has become live and the compiled-status guard is what stands in front of it, so
the failure is a signal to read the test rather than delete it.

### Verification

The decisive mutation is the call site reverted to the manifest-text status, with
nothing else moved. Seven cases flip, including all five of the S53 refusal
parametrisations, and the two that stay green are the ones that do not reach the
guard:

```
E   AttributeError: 'str' object has no attribute 'value'
E   AttributeError: 'NoneType' object has no attribute 'value'
FAILED ...::test_stamp_refuses_to_touch_the_review_axis_of_an_operator_signed_revision[substitution-arguments0]
FAILED ...::test_stamp_refuses_to_touch_the_review_axis_of_an_operator_signed_revision[reviewer_alone-arguments1]
FAILED ...::test_stamp_refuses_to_touch_the_review_axis_of_an_operator_signed_revision[date_alone-arguments2]
FAILED ...::test_stamp_refuses_to_touch_the_review_axis_of_an_operator_signed_revision[erasure-arguments3]
FAILED ...::test_stamp_refuses_to_touch_the_review_axis_of_an_operator_signed_revision[downgrade-arguments4]
FAILED ...::test_the_review_axis_guard_reads_the_status_the_compiled_revision_carries
FAILED ...::test_the_review_axis_guard_reads_the_vocabulary_and_not_one_hardcoded_status
7 failed, 2 passed in 42.79s
```

The failure mode is worth naming honestly: because no divergence is constructible,
no test can flip on a semantic difference, and what flips instead is the TYPE. The
guard now takes the compiled status, so feeding it the manifest text is not a
subtly-wrong value but an object with no such field. That is the strongest proof
available on this seam, and it is a real one — the wrong source can no longer be
supplied by accident.

Every S53 case was then re-run unmutated, which is the Step's own required proof:

```
uv run --no-sync pytest ... -k "operator_signed or review_axis or stampable or vocabulary or refuses"
28 passed in 77.38s
```

Full dev CLI module under the DEFAULT selector:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
69 passed in 58.63s
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

The verb was NOT run against the shipped registry. Every write and every
divergence probe was against a byte copy of the real Modelo 130 tree.

The manifest text is still parsed. `_resolve_stamp` needs the declared authorship,
reviewer and date to merge onto, and the line editor needs the file's own lines;
both are genuinely about the FILE this writer edits, whereas "what does this
revision declare" is a question about the revision. Only the latter moved.

A mutation-revert script written during this Step rewrote `_stamp.py` through
`write_text` and translated all 910 of its terminators to CRLF — the same defect
class S62 closed in the baseline writer, arriving through a throwaway probe. It
was caught by `git add` warning about the working-copy translation, normalised
back to LF before staging, and the module re-run. Recorded because the probe
scripts around this surface are as capable of drifting the tree as the writers
are, and nothing in the campaign watches them.
