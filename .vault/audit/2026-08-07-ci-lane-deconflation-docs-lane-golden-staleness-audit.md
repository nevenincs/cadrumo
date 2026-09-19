---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d01345c1d9ad2e014908065f825154507cd5712e134e575461f64fb37999d730'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` audit: the docs lane is red on stale goldens, not on nondeterminism

## Summary

The docs conformance lane has failed every run for a day. Two distinct causes sat
behind that single red signal, and conflating them is what kept the finding open.

The first is fixed and confirmed on a runner: two health rows described the HOST
rather than the product, so a golden could only ever match the machine that
recorded it. That is closed.

The second is what remains, and it is mundane: the goldens are stale against a
legal-grounding change that landed since they were recorded. It is not the
nondeterminism this campaign has been chasing.

## What the runner actually reports

On the pushed head, the lane reports thirteen pages diverging. Aggregating every
reported envelope path by shape rather than reading them one at a time:

    60  result.observations[N].legal_refs[N]
    27  result.observations[N].legal          (truncated in the log)
     6  result.revisions[N].observations[N].legal_refs[N]
     6  result.bindings[N].legal_refs[N]
     5  result.rows[N].legal_refs[N]
     2  result.profile_derivable[N].casilla_id
     2  result.profile_derivable[N].binding_id

Roughly a hundred of about a hundred and ten diverging paths are `legal_refs`.
A peer campaign added place-of-supply grounding, and every golden carrying an
observation now disagrees with the live output by exactly those references. The
change is correct and well grounded; only the recordings are behind.

The remaining handful on `profile_derivable` are a separate, smaller change and
are not explained by this finding.

## The fix, and why it is not applied here

The repair is a golden refresh. It is deliberately not performed in this pass,
and the reason is a working-tree condition rather than a doubt about the repair.

The docs sequences execute the real CLI in a sandbox, so they exercise the
storage runtime on every frame. That layer is currently mid-refactor across seven
uncommitted files, and the sandbox subprocess dies on an unbound name inside it.
A refresh under that condition rewrites goldens from a crashed or partially
executed run, which is strictly worse than leaving them stale.

One mass refresh was attempted and produced exactly that outcome: locally the
failing-page count went from thirteen to twenty-four. All thirty-five rewritten
goldens were restored to their committed state rather than published.

## What was ruled out, by measurement

A plausible mechanism was that the tie-break identifier varies per run. Bucket
events are ordered on a pair of occurrence time and event identifier, the
identifier is content-addressed, and the documentation sandbox pins the profile
identity but demonstrably not the bucket identity - a test asserts the two
differ. If the bucket identity entered the event body, the derived identifier
would change every run and sibling events sharing a frozen instant would reorder
about half the time.

That is wrong. Comparing the identifiers stored in a committed golden against a
freshly recorded one shows them byte-identical. The tie-break is stable.

This would have been the third wrong diagnosis recorded against the ordering
finding, and it is written down as refuted so a fourth attempt does not start
from it.

Re-reading the divergence itself corrects the symptom too: both lines carry a
removal marker, so the events are ABSENT from the live run rather than reordered.
The event count varies, not the order. That mechanism is still unidentified, and
it is a smaller finding than the lane's red signal suggested.

## Isolation result worth keeping

Per-page behaviour separates the two causes cleanly. A page refreshed and then
checked twice in isolation is stable across both checks. The same page inside a
full-tree refresh followed by a full-tree check is not. Whatever remains is
therefore a property of the whole-run execution, not of an individual sequence -
which is where a later investigation should start, rather than at the sort key.

## Recommendation

Refresh the goldens once the storage refactor lands and the sandbox executes
cleanly, then re-run the lane. Treat a refresh performed while any layer the
sequences exercise is mid-edit as invalid, because the failure mode is silent:
the sequence crashes, the golden is rewritten anyway, and the result reads as a
recorded expectation.
