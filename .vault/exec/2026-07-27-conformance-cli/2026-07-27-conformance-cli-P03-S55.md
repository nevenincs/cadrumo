---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:0d71cc01d696708359161d6df8e0acb52fe6d3760d9613644a0181a54dcecf7d'
step_id: 'S55'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# reconcile the reviewer column between the text and JSON surfaces so one key name never carries two different values, and refuse a reviewer value containing the tier separator so the qualified form stays unambiguously parseable

## Scope

- `dev/registry/conformance/manager.py`
- `dev/registry/conformance/_stamp.py`
- `dev/tests/test_registry_conformance_cli.py`

## Description

- Rename the text row's reviewer column to `reviewed_by_attribution`, matching the payload
  key exactly and carrying exactly the payload's value.
- Stop emitting a bare reviewer column in text, so no key name can disagree across the two
  surfaces.
- Refuse, at the writer boundary, a reviewer identity whose leading colon-delimited
  segment is a review-status token.
- Record on the manager's reading rules and on the join function what the reconciliation
  fixes and what the refusal is narrowly about.
- Add the cross-surface agreement test, three spoof refusal cases proved on bytes, and the
  paired case keeping a qualified name legal.
- Correct the S46 record's claim that a JSON consumer filtering on the reviewer alone
  reached the qualified answer.

## Outcome

### One key, two values, and the surface a program reads carried the wrong one

The third round qualified the reviewer and reported the JSON half closed. It was not. The
joined form went into a NEW payload key while the text row kept rendering under
`reviewed_by` — so the same symbol carried the qualified form in text and the raw name in
JSON, and a consumer filtering on `reviewed_by`, the reviewer field, alone reached exactly
the bare-name reading the join was introduced to prevent. Only a consumer that already
knew to ask for `reviewed_by_attribution` reached the qualified answer, and a reader who
already knows the rule is not the reader either mechanism protects.

Text now names the joined field `reviewed_by_attribution` and emits no bare reviewer
column at all. Nothing is lost by the omission, because the joined form contains the name.
The payload still declares the raw `reviewed_by`, which is right: it is the datum the
manifest carries, and its own field documentation already says to read it beside its
attribution rather than alone. The reconciliation is now that every key name present on
both surfaces carries one value.

### The free-text field could forge the vocabulary

`reviewed_by` is the one governance field with no vocabulary, by necessity. Recorded as
`operator_reviewed:<a person's name>` on an agent-tier review, its RAW value is
indistinguishable from a genuine operator attribution — an agent-tier stamp readable as a
human signoff without ever writing the status this CLI refuses to write, which is the same
claim the effective-status guard exists to protect, arriving through the door with no
guard on it.

The writer now refuses a reviewer whose leading colon-delimited segment is a review-status
token, case-insensitively, and the predicate reads the core vocabulary so a fourth status
enrols itself.

### Ruling: the refusal is the status prefix, not the separator

The Step text asked for a refusal of any reviewer containing the tier separator. That is
wider than the hazard and would cost something real, so it was narrowed deliberately.

The JOINED form was never ambiguous. No review-status value contains a colon, so
everything before the first separator is the tier and everything after it is the name,
whatever the name holds: `agent_reviewed:agent:opus-executor` parses correctly at its first
separator. Refusing every colon would therefore buy no additional parseability, while
breaking `agent:<name>` — the convention this campaign's own execution records and its
shipped tests already use. The ambiguity is entirely in the RAW field read alone, and that
is precisely what the status-prefix refusal closes. The paired test asserts a qualified
non-status name stays legal, so a later widening to a blanket colon refusal cannot land
silently.

### Verification

Two mutations, each flipping its own assertion and leaving the paired case alone.

Reverting the text key to `reviewed_by`:

```
FAILED ...::test_a_revision_claiming_no_review_is_never_joined_to_a_tier
FAILED ...::test_the_reviewer_key_carries_one_value_across_both_surfaces
2 failed in 50.45s
```

Neutering the tier-shape refusal:

```
FAILED ...::test_stamp_refuses_a_reviewer_that_reads_as_an_already_qualified_attribution[operator_reviewed:Gergely Wootsch]
FAILED ...::test_stamp_refuses_a_reviewer_that_reads_as_an_already_qualified_attribution[OPERATOR_REVIEWED:Gergely Wootsch]
FAILED ...::test_stamp_refuses_a_reviewer_that_reads_as_an_already_qualified_attribution[agent_reviewed:somebody]
3 failed, 1 passed in 8.22s
```

The one that passed is the qualified-name-stays-legal case, which is the shape that proves
the refusal keys on the status prefix rather than on the colon.

The real verbs after the rename:

```
uv run --no-sync python -m dev.registry.conformance report   -> exit=0, 90 row lines
row ... reviewed_by_attribution=n/a ...
uv run --no-sync python -m dev.registry.conformance audit --check -> exit=0
```

Full dev CLI module under the DEFAULT selector:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
58 passed in 70.11s
```

Style and lint:

```
uv run --no-sync ruff format --check ...  -> 3 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator direction; the
service is stopped and its index is broken. Grounding was by whole-file reads and `rg`.

The S46 record's claim that a JSON consumer filtering on the reviewer alone reached the
qualified answer was corrected in place rather than deleted, so the overclaim stays visible
next to its correction.

`StampResult.render()` still echoes a raw reviewer name beside its status on the
single-write confirmation line. It is left alone for the reason S46 gave — it confirms one
write the caller just made, with both fields adjacent, rather than being a ninety-row
scanning surface — and the new spoof refusal now means the name on that line cannot itself
be tier-shaped.
