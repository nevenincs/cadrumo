---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:12f0144162761b1650034de8d23e9f0b6d86bf74847c8f2df761b0cf743ba3a8'
step_id: 'S19'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Add the plausibility gate at the confirm boundary refusing a document confirmed as ISSUED that was not plausibly issued by this taxpayer, mirroring the hard gate that already refuses an ISSUED invoice as purchase evidence

## Scope

- `src/cadrumo/application/ledger/_evidence_draft.py`

## Description

- Established what the existing sibling guard already covers, and what it structurally cannot.
- Found the signal the new gate can judge on, rather than inventing a heuristic.
- Added the gate as a refusal, alongside the sibling rather than folded into it.
- Added the refusal proof, matched on a gate-specific phrase, plus a positive control for the case the gate must decline to judge.

## Outcome

**The confirm boundary now refuses a document confirmed as ISSUED that someone else issued.**

The Step asked for a gate mirroring the one that refuses an ISSUED invoice as purchase evidence. Measuring first showed a sibling guard already exists and covers the *adjacent* case — a counterparty that names the filer — and that it structurally cannot cover this one.

The difference is the point. When a supplier's invoice is confirmed as issued, the counterparty is a **genuine third party**, so every identity check passes and the record is internally coherent. It simply describes the wrong direction, and nothing in the record contradicts itself. The sibling guard has nothing to fire on.

**The signal is the evidence, not a heuristic.** On a genuinely issued document the printed supplier IS the filer. So an extracted supplier identity belonging to somebody else is positive evidence that somebody else issued the document — the gate judges on what the document says, not on a plausibility score.

**Why refusing rather than warning.** Direction decides which informativa the record feeds and on which side. A received invoice booked as issued moves a purchase into the sales column, inverts the cuota's meaning between soportado and repercutido, and reaches Modelo 347 as an operation the counterparty will have declared with the opposite sign — and AEAT reconciles those two declarations against each other. Like the sibling guard's case, this is wrong under every reading rather than merely doubtful.

**The gate declines to judge where it cannot**, and that half has its own positive control rather than being assumed. An absent extracted supplier is silence, not evidence; a profile carrying no tax id gives nothing to compare against. Both return without refusing. A gate that refuses what it cannot judge is worse than no gate, because it blocks correct work while appearing principled — here it would have blocked every issued invoice whose letterhead the extractor could not read.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_self_counterparty.py -m "integration or unit" -q --no-header
    5 passed in 13.63s

    uv run --no-sync pytest src/cadrumo/application/ledger src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_self_counterparty.py -q --no-header
    578 passed in 35.97s

    uv run --no-sync ruff check .../_evidence_draft.py .../test_ledger_evidence_self_counterparty.py
    All checks passed!

The refusal proof was strengthened mid-Step. Its first form asserted only that the word "received" appeared in the output — which would also pass if an unrelated refusal fired, leaving the gate unproven while the test looked green. It now matches a phrase only this gate emits, and separately asserts the message names the remedy.

## Notes

The Step's criterion required a positive control proving "a genuinely-issued document still confirms", on the reasoning that a gate refusing everything passes its own negative test. The control landed on a sharper case than that: the document the gate **cannot judge**. A genuinely-issued document is already covered by the sibling guard's existing control, whereas the unreadable-letterhead case is the one this gate could plausibly over-refuse, and it is the one an operator would meet most often.

One incidental measurement worth recording for the sibling campaign: the draft model already carries `recargo_rate` and `recargo_amount`. The cross-lane note in this plan lists the draft-side recargo slot as that lane's outstanding work; it has landed.
