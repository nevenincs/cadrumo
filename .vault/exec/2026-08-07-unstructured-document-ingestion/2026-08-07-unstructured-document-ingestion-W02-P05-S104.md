---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0f26ffe8486dfb70f3bf44cf7f507d5a714a30227ed433c39de67fb31bffa92e'
step_id: 'S104'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Re-arm the positive-role-evidence filter by removing the manufactured evidence the reading path supplied

## Scope

- `src/cadrumo/application/ledger`

## Description

- Remove the synthesised role-evidence string the reading path attached to every identity candidate.
- Record in the producing function's docstring why no evidence is supplied there, and what supplying none costs.
- Add the gate: no candidate arrives carrying evidence, the measured defect no longer grounds a lone survivor, the no-role-evidence fallback note renders on competing candidates, and a candidate carrying real evidence still grounds.
- Measure what the change closes, and report the size rather than only the fix.

## Outcome

The counterparty resolver grounds an identity only on positive role evidence, never on survival, because sole survivorship is first-match with the competitors removed beforehand. That filter is a truthiness test over a free-text field.

The reading path handed every candidate the string "the reader assigned this identifier to" plus the field name. Always non-empty, so the filter accepted every candidate and could never exclude one. The guard was permanently satisfied.

So the defect the filter exists to stop was live through it. With the true supplier's identifier failing its control character and one unrelated but checksum-valid identifier left standing, the survivor resolved and was stamped anchored, under a note reading "role evidence picks exactly one identifier: the reader assigned this identifier to supplier tax id". That note is circular: it states that the reader assigned the field, not that the document evidences the party. A guard that cannot refuse is worse than no guard, because its output is trusted.

The producing function's own docstring warned against re-scanning the transcription because that "would restore first-match selection at the exact seam that was fixed", while the line below it did the equivalent by another route.

### What supplying none costs, measured

Four cases through the resolver, at the commit that landed:

| case | resolved | outcome |
| --- | --- | --- |
| true identifier fails its control character, unrelated valid one survives | none | unanchored |
| single valid identifier, nothing competing | none | unanchored |
| two parties read, the filer's own excluded | none | unanchored |
| one candidate carrying real role evidence | resolves | anchored |

The second and third rows are the ordinary path, and they now refuse. In practice no identity resolves from the reading path until the extraction stage carries real evidence, including the plain single-counterparty invoice, which was the bulk of successful reads.

This is recorded as the size rather than softened. The direction fails closed: an identity that cannot be evidenced stays unresolved, and an unresolved counterparty refuses as a missing field naming the override that supplies it, where a wrong one reaches the counterparty totals the tax authority reconciles against the other party's own filing. A wrong counterparty is worse than an absent one. But the operator-visible effect is that counterparty auto-fill stops on ordinary documents until the payload carries evidence, and if that window is too wide the lever is the priority of that work rather than a partial re-arming, which would only restore a filter that cannot refuse.

The fourth row is what distinguishes this change from deleting the resolution path outright: hand the filter real evidence and it promotes exactly as designed.

### Deliberately not done

No role-evidence payload field was added. That is the extraction stage's deliverable and it needs transcription context this Step does not plumb. This Step re-arms the guard; the later one gives it something true to test.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_grounded_reading_wiring.py src/cadrumo/application/ledger/tests/test_identity_roles.py -n 0
    36 passed in 1.92s

Collected 36, zero deselected. Ruff clean on both touched files; basedpyright reports zero errors, warnings and notes.

Restoring the manufactured evidence from a throwaway plugin on the interpreter path outside the repository, with nothing inside the tree edited, reds exactly three: that no candidate arrives carrying evidence, that a lone survivor is not grounded as the counterparty, and that the no-role-evidence fallback note renders on competing candidates. The fourth assertion, that a candidate carrying real evidence still grounds, stays green under the same mutation, which is what separates a re-armed filter from a disabled one.

Every red was checked for its origin rather than counted. All three land at the new assertions.

The fallback assertion closes the Step's second stated criterion. That message could not render before, because the ``or`` supplying it was always short-circuited by the manufactured string.

The full owning-package suite was run to measure blast radius: 778 collected, 19 deselected, 743 passed, 16 failed. None of the sixteen belongs to this change, established rather than assumed. Most raise a registry validation error from a concurrent edit across two modelos' authoring trees, which also accounts for three failures in the end-to-end waist gate that read one of those snapshots. The remainder fail on an extract payload refusing a provenance field a concurrent change added to the envelope without updating the payload model. Neither touches role evidence.

## Notes

Nothing in the suite failed as a result of this change, which is itself the finding: the reading path's identity resolution had no test asserting that it resolved end to end. The guard was disarmed and unwitnessed at the same time, which is why it survived. The gate added here is the first assertion over that behaviour from the reading path's own side.

The change was found by semantic search while grounding a different Step, whose files would not have shown it. The schema work that Step asks for looks complete on its own, and building it would have left the disarmed filter standing underneath.
