---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ef0e2ecc6d9726eaf7c90cd596a043b38c7b1ed43a800dfe7028d7c9a17eaf6a'
step_id: 'S70'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---

# Prove the parsers give the sibling campaign's multi-line writer a real per-rate producer by round-tripping a two-rate structured document from parse to a confirmed multi-line invoice, sequenced after that campaign's writer Step lands, red if the confirm boundary is bypassed or the second rate is lost in transit

## Scope

- `src/cadrumo/application/ledger/tests/`

## Description

- Round-trip the bundled two-rate EN16931 UBL document from parse through the confirm boundary to a persisted invoice.
- Assert the confirmed invoice carries one line per rate, keyed on the closed rate slot rather than a percentage.
- Fix the confirm boundary, which was collapsing the per-rate split.

## Outcome

The Step was written to be red if the confirm boundary were bypassed or the second rate lost in transit. It was red for the second reason, and worse than the wording anticipated.

The parsers read the document exactly and the writer already sums supplied lines authoritatively -- its docstring names this exact 21/10 case. The boundary between them read neither. It built a single line from the collapsed scalars and only when an explicit cuota was passed; a multi-rate draft carries no single rate, so the branch never fired at all. The fixture confirmed as ONE line at the exempt slot with `iva_total` 0,00: not a lost rate split, a lost cuota.

Confirm now builds one line per breakdown entry and the writer sums them. The operator-override path is explicitly skipped, because an override is a statement about the whole invoice and keeping a per-rate split beside it would leave two disagreeing authorities on the same figures.

## Verification

Red before the fix:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_confirm_multi_rate.py -m "unit or integration" -n 0
    AssertionError: the second rate was lost in transit: ['EXEMPT']
    2 failed in 4.36s

Green after:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_confirm_multi_rate.py -m "unit or integration" -n 0
    2 passed in 8.05s

No regression across the boundary's other callers:

    uv run --no-sync pytest src/cadrumo/application/ledger/ src/cadrumo/application/invoices/ src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_confirm_cli.py src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_printed_total_notice.py -m "unit or integration"
    680 passed in 73.64s

## Notes

The proof runs against the real bundled corpus fixture rather than a hand-built draft, so the parser and the confirm boundary are exercised together and neither can be satisfied by a stub of the other. That mattered here: each half had its own passing tests, and neither could see the loss between them.

This is the shape worth carrying forward -- two correct halves with a lossy boundary between them -- and it is why a dedicated sweep for sibling instances was opened rather than treating this as a one-off.
