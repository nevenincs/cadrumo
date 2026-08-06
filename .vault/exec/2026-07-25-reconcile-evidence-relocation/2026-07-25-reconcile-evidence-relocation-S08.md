---
tags:
  - '#exec'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:bd462b3945be7f86a2a1b2e93710e20b967ed519db27121115eb5a03daf1ebb2'
step_id: 'S08'
related:
  - "[[2026-07-25-reconcile-evidence-relocation-plan]]"
  - '[[2026-07-25-bucket-event-payload-bounding-adr]]'
  - '[[2026-07-25-bucket-event-payload-bounding-payload-overflow-survey-audit]]'
---

# Rule whether the bucket-event substrate deserves a standing guard against joining a variable-length value into a capped payload slot, four instances found and three closed by hand, and give the un-ratified 500-character cap its first declared home

## Scope

- `src/cadrumo/domain/buckets/_event.py`
- `new ADR`

## Description

- Re-derive the occurrence tally against the working tree rather than accepting
  the four-instance count the plan step carries.
- Survey every production site binding a variable-length value to a
  bucket-event payload key.
- Prove the split and merge overflow threshold by executing the real event
  model against progressively larger cohorts.
- Confirm the split cohort stays recoverable from the transaction catalogue
  before choosing a count as the remedy.
- Replace both joins with counts, recording the arithmetic and the
  recoverability justification in place.
- Give the cap its first declared home as
  `BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH`, with the three sanctioned
  alternatives stated on it, exported through the package facade.
- Add `payload_value_fits` so a producer can check the bound before building an
  event.
- Add the static gate, scoped to modules that build bucket events, recognising
  both payload spellings, with a self-expiring exemption map and a
  detector-liveness proof.
- Persist the survey as an audit record and the ruling as its own ADR.

## Outcome

Ruled that the substrate does carry a standing guard, and the ruling rests on
evidence the step's own framing did not have.

The step describes a four-instance shape with three closed. The tally is six.
Two live occurrences were found that no prior pass had recorded, both in the
ledger split and merge events, both joining 64-character transaction ids into a
500-character slot, both overflowing at exactly eight children. The threshold
was confirmed by execution against the real model, not by arithmetic: seven
children pass the joined key, eight and ten are refused on it. The verb imposes
no upper bound on the cohort.

That falsifies the conclusion the governing record reached at its
re-verification — that the pattern had resolved itself around a single
exception. Its facts were true when written; the inference fails, and it fails
for the reason that record itself gives, having been written without reliable
search.

The decisive evidence for the guard is the discovery record rather than the
count. None of the six was found by a pass looking for it, and two survived a
recount whose explicit purpose was to enumerate them. Both new occurrences
already carried the correct remedy on an adjacent line, which settles that the
missing ingredient is detection rather than knowledge.

Both live occurrences are closed with counts. Every split child carries a
required `split_group_id` and both events already carry that group id, so the
cohort remains recoverable from the transaction catalogue and nothing is lost —
the justification holding on its own terms rather than by analogy to the
removal fix. The operator-facing enumeration of child ids is unaffected: it is
served from the returned result model, never from the event payload, which the
CLI suite confirms.

The gate flags a value bound to a payload key that it cannot prove bounded, and
was validated in both directions. Run against the pre-fix content it reports
both offences at their exact lines; run against the fixed content it reports
none. A detector-liveness test pins it against each offence shape and each
sanctioned remedy, and a surface test pins that it inspects a non-empty
production surface, so a green run is evidence the surface is clean rather than
evidence the detector is dead.

Two design corrections were forced by measurement. An unscoped first cut keyed
on the name `payload` flagged twenty-two values, twenty-one of which were
Sheets, LLM or CLI payloads carrying no capped-slot contract; scoping to
modules that build bucket events removed the noise without an allowlist. And a
keyword-only matcher returned clean against the reconcile file whose overflow
prompted the work, because that payload is built into a local and passed later
— so the detector recognises both spellings.

Verification: the buckets suite passes 26 unit and 4 integration tests, the
ledger split, merge and merge-refusal suites pass 13, and the CLI split and
merge payload suite passes 4. Lint and format are clean on every touched file.

## Notes

Semantic search was unavailable throughout and its degradation is silent: the
code index held roughly 902 chunks against roughly 4,546 source files while
reporting no degraded reasons. No claim here rests on a search miss; every
statement rests on direct reads, on `rg`, or on execution.

The exemption map ships empty, and that was not the plan. It initially carried
the reconcile diff detail as the one occurrence bounded metadata cannot close.
The self-expiring exemption test flagged that entry as stale within the hour,
because the relocation work removed the line it excused while this step was in
flight. The ratchet worked earlier than intended, which is the strongest
available evidence that it works at all.

That created a commit-ordering dependency rather than a defect: the gate is
green only once the relocation lands, so this work must commit after it. The
dependency was raised with the owner rather than resolved by weakening the
test.

One measurement error was made and corrected during the survey. An early probe
reported both seven and eight children refused, which would have put the
threshold in the wrong place; the seven-child refusal was the probe's own
undersized event id, not the payload bound. Isolating the failing field
corrected it. The threshold reported above is from the corrected probe.
