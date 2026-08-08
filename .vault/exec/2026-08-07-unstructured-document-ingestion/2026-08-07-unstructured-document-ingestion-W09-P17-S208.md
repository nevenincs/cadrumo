---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:f8de3209e627584581770e081c1e2c141dba35cc0cd2dac24140590d41f832c3'
step_id: 'S208'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Project the three computed-but-unread confirm-path signals onto the shared Notice channel, since all three are constructed, carried on a field nothing reads, and seen by nobody. Measured at HEAD: zero production readers of InvoiceConfirmationResult.establishment, the only production review_items hits are its own constructor, and the confirm payload is built from invoice, created, provenance, discrepancies, confirmed_provenance and confirmation_id and never touches establishment. (1) The country advisory, reachable only from review show, where before the advisory move both kinds drove blocking_count and were filterable by reason and finding, a queue removal nothing has ruled on, since S193 is an open question about the ATTRIBUTION advisory rather than a recorded ruling, so queue visibility is undecided for both advisories. (2) The ladder's review_items, whose exhaustion, contradiction, registration conflict and filer-profile gap are all computed and carried. (3) The IvaCategoryOutcome, which is neither persisted nor emitted, so a RATE_INFERRED record is indistinguishable at rest from one the rule table placed outright and enumerating them requires re-running resolution rather than querying a store. RATE_INFERRED is the most urgent: a contradiction at least has teeth because the withheld category is refused out loud by the decomposition contract, while an inferred category produces a perfectly ordinary-looking record. Notice channel per the CLI contract, never a bespoke result field

## Scope

- `src/cadrumo/entrypoints/cli`
- `src/cadrumo/application/ledger`

## Description

- Declare `ReviewAdvisoryKind` in `core`, the closed non-blocking sibling of the review gate's blocking reason axis.
- Add `review_advisory_kinds` in `application/ledger` as the one projection both review surfaces read for which advisory kinds a pending draft carries.
- Report `advisory_count` and `advisories` on every review-queue row, add the `--advisory` filter, and emit one queue-level advised-pending notice naming the count and the kinds.
- Add `_ledger_evidence_confirm_notices` in the CLI package, projecting the confirm path's IVA category outcome and its carried review items onto the shared `Notice` channel.
- Emit `iva_category` and `iva_category_outcome` on the confirm result payload, and the matching `iva_category` and `review_item` lines on the text surface.
- Set the eight new operator strings in all four locale catalogues through `dev.locales set`.

## Outcome

Four signals that were computed on every confirm and read by nobody now reach the operator.

The severity rule is single and tracks the operator's consequence rather than the outcome's name: a resolution that produced a category is reported at INFO however weak its rung, and one that produced none is a WARNING because the record now carries no IVA treatment. An ordinary domestic invoice printing no postal code is the commonest document there is and reaches the same unestablished counterparty as a withheld-relief one, so warning on both would train an operator to skip the channel the second needs. Measured: the domestic case leaves the envelope at `status: success` with two INFO notices; the relief case reaches `status: warning`.

The two advisories reach the review queue as a count and a filter, per the coordinator's ruling recorded as `W09.P17.S214`, rather than a row per advisory. The per-document prose already lives on the one-document surface; the queue's job is to give an operator a reason to open the document at all.

Diagnostics ride the typed notice channel only. The per-row advisory kinds and the category outcome are the verbs' own result data -- what each document carries, and what treatment the record got -- and a gate on each payload asserts no bespoke advisory, next or suggestion field appeared beside them.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_confirm_resolution_cli.py -n0 -q -m integration
    9 passed in 12.19s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_queue_advisories_cli.py -n0 -q -m integration
    8 passed in 13.53s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests -n0 -q -m integration
    43 failed, 2983 passed, 748 deselected, 1 warning in 2051.48s (0:34:11)

    uv run --no-sync pytest src/cadrumo/application/ledger/tests -n0 -q -m unit
    7 failed, 1211 passed, 26 deselected, 16 warnings in 142.63s (0:02:22)

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok / en.yml: ok / es.yml: ok / hu.yml: ok

Mutation proof, run from outside the repository with the plugin on `PYTHONPATH` so no tracked path was edited: rebinding the notice projection to return an empty list and the advisory projection to return an empty tuple, with a positive control asserting each rebinding replaced the object the module holds, reds 10 of the 17 new cases. A gate that only asserted the notices were constructed would have stayed green under exactly that mutation, which is the defect this row exists to close.

Owner triage of the two full-lane runs: none of the 50 failures is on this surface. The confirm and extract CLI failures are an absent on-host reading model refusing the text-layer path; the country-vocabulary failures across both lanes are a sibling lane's in-flight change that catalogued Thailand, so fixtures using `TH` as their uncatalogued specimen no longer produce that kind; the remainder name sub-verbs, payload fields and modules this Step does not touch.

## Notes

The document this row cites as its worked example -- the bundled EN16931 UBL intra-community specimen -- cannot be confirmed at all, for a reason outside this Step. Its supplier states a fourteen-character EU VAT number and the invoice model's tax-identifier validator requires exactly nine characters, so both directions refuse before any resolution runs. The surface built here is therefore proven against an equivalent-shape document: the same declared intra-community category, the same absent country evidence, a counterparty identifier the model accepts. Two consequences worth a row of their own: no foreign-counterparty document can be confirmed through this path today, and the refusal an operator actually receives is the generic input-validation message, with the fourteen-character identifier named only in the log.

The filer's own profile gap is raised as a second, separately-addressed question on the same reason, and it is not about the document at all: an incomplete profile silently disables the rule table for every invoice, so an operator re-reading pages would never find the setup gap that was actually stopping them.

Code review has not yet run against this change.
