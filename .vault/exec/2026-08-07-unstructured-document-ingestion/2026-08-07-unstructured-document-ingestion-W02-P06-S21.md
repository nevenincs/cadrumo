---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:2ce8192105a6dabff1959e89671a56c7ea92e68dffb92086b96a16b164b35d71'
step_id: 'S21'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Route per-field degradation advisories through the typed Notice channel naming what was seen and why it was rejected

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Add `_evidence_field_notices.py`: one notice per field whose value did not
  come through its check, keyed by what the check established.
- Emit them from both evidence surfaces, extract and confirm, against the same
  pre-override draft.
- Add the five operator messages to all four locale catalogues.

## Outcome

The reading path raises on nothing. It returns a draft with fewer fields, which
on its own is indistinguishable from a document that genuinely carries fewer
fields — so reading a layout badly and reading it well arrived at the operator
looking identical. These notices are that distinction, per field, naming the
printed form the reader claimed to have read and what the check concluded about
it.

Five shapes, each its own code, because each is a different operator action:

| shape | severity | what it says |
| --- | --- | --- |
| `contradicted` | warning | an independent check disagreed; the document says something else |
| `ambiguous` | warning | several readings competed and none was decidable |
| `anchor_not_found` | info | the reader pointed at a printed form the transcription does not contain |
| `no_anchor` | info | the reader offered nothing to point at |
| `anchor_self_reported` | info | the claim came from the same reader that produced the value |

The last two rows are the distinction that must not collapse. A text-lane
unanchored field is a check that **ran** against an independently produced
transcription and did not pass; a self-reported anchor is a check that **could
not run at all**, because the vision lane reads image to fields in one call and
matching its anchor against its own reply would confirm only that the model is
self-consistent — which a fabricating model also is. Same enum member,
different strengths of evidence, two codes and two messages.

Severity follows what the check established rather than how much is missing. A
disagreement and an undecided ambiguity move the envelope status to `warning`; a
missing verbatim match does not. That asymmetry is deliberate: a normalised
value — a date rewritten to ISO form, a tax id stripped of separators —
legitimately fails a verbatim search, and warning on every one of those would
train an operator to ignore the channel, which is how an anti-fabrication signal
becomes decoration.

The reported set is **derived** by excluding the two outcomes that mean a value
came through intact, so a member added to the vocabulary is reported by default
instead of silently ignored.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_evidence_field_notices.py src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py src/cadrumo/entrypoints/cli/tests/test_source_advisory_notice_channel.py -p no:randomly -n0 -m "unit or integration"
    collected 176 items
    176 passed in 31.66s

Collection is quoted alongside the result because an earlier attempt at this
same gate selected **nothing**: a path in the invocation named a file that does
not exist, and the run reported `0 tests` with a non-zero usage exit that reads
nothing like a pass.

The locale keys were verified per key **per locale** after writing — twenty
combinations present, and separately checked that none holds a value equal to
its own key. A single write pass is not evidence here: concurrent catalogue
writes have been losing entries, and a placeholder left behind is refused by the
shipped honesty gate in somebody else's run rather than this one.

Six mutations, applied from a throwaway plugin outside the repository so no
tracked file changed:

| mutation | reddened |
| --- | --- |
| emit no notices at all | **7** |
| report a self-reported anchor as a failed check | **1** — the distinction test |
| report fields that passed their check too | **2** |
| downgrade a contradiction to informational | **1** |
| drop the printed form from the report | **1** — the what-was-seen test |
| delete both call sites in the commands | **1** — the wiring guard |

All restored and re-run green.

## Notes

The builder tests alone would have left the two call sites unguarded — every
assertion would pass over a builder nothing invokes. The wiring guard closes
that, and is deliberately structural: exercising either command for real now
routes through the reading pipeline to a model endpoint, which this environment
must not provide.

Two evidence tests fail at HEAD with a transport connection error, reaching that
same endpoint. They are unrelated to this Step — this Step's code appears in
neither traceback, and both failures occur inside the reading call that returns
before any notice is built. Recorded rather than patched.

That failure is also the reason the sibling deletion Step was not started. Its
gate requires the bundled fixtures to pass **through the new path**, and the new
path cannot be exercised without a model endpoint that must not run here, so the
evidence that would make deleting the current reader safe cannot be produced in
this environment.

A second hazard for that Step, found while taking its inventory: the label-regex
names it deletes are not unique to the invoice evidence reader. The justificante
and declaracion inbound parsers carry their own `LABEL_RE` symbols, and a gate
reading "zero remaining label-regex references" tree-wide would sweep two
working AEAT parsers into a deletion aimed at neither. The gate needs scoping to
the invoice-evidence family in its own module.
