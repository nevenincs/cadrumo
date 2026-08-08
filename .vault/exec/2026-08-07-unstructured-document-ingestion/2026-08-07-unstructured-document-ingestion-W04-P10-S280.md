---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:65c1c12e8e564750da45f0a264ec2645156e36af33a6d7cefc86cba70c1b68be'
step_id: 'S280'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Measure tabular column-role mapping quality over the 71 columns of the nine CSV exports against an operator-authored expected mapping

## Scope

- `dev`

## Description

- Confirm the emitted and expected vocabularies are one closed set before scaling,
  so a figure cannot be a naming artefact.
- Run the real column-role mapping entry point over all nine exports through the
  gated cloud route at the design-proxy tier.
- Score every proposal through the harness scoring arm against the authored
  expectation, per export, never pooled into one ratio.
- Decompose every non-clean slot into declared-defensible and undeclared.
- Repeat the whole run independently to establish the figures are stable.

## Outcome

**Delivered.** Nine of nine exports measured, 71 of 71 columns scored, at
`claude-haiku-4-5` on the ANTHROPIC route — the `cloud_design_proxy` tier, which
is baseline-eligible. Corpus key sha256
`e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593` (890052 bytes).
Tree `1306fe5641`.

**The truth is OPERATOR-GROUNDED and that is the weaker claim.** The corpus key
authors no column-role truth for any tabular document — all nine carry
`ground_truth == {}` and the scoring arm refuses 9 of 9 for want of a denominator.
The expectation was derived from the `FieldRole` member semantics and the printed
headers, **before any model output for these headers existed**. An acceptance
floor set from these numbers is a floor against an operator's judgement, never
against the corpus.

### The naming axis was closed before the run, not assumed

The neighbouring vision lane's pilot produced a figure that measured a dictionary
gap rather than a reader, because its emitted and expected vocabularies were two
different name sets. That cannot happen here, and it was checked rather than
hoped: the mapper emits `FieldRole` members, the allow-list in its prompt is
generated from the same enum, and every authored expectation and alternate is a
`FieldRole` value — 14 expected tokens and 4 alternate tokens, all members, with
**zero tokens expected but not emittable**. One closed vocabulary, gate-enforced.

### Headline, strict, per export

Scorable slots — matched of authored:

- issued libro registro **9/9**, 0 wrong, 0 missed
- point-of-sale Z report **5/5**
- BBVA web export **4/4**
- spreadsheet-exported bank statement **3/3**
- neobank export **4/5**, 1 missed
- bank statement **2/3**, 1 wrong
- expense-tracker export **7/8**, 1 wrong
- legacy ERP export **2/3**, 1 missed
- received libro registro **10/10**

Roll-up: **46 of 50 scorable slots matched**, 2 wrong, 2 missed. Fabrication
traps: **2 of 21 fabricated**, 19 correctly abstained.

### The decomposition, which changes the reading

Six slots of 71 were not clean. **Five of the six are declared-defensible
alternates** — answers recorded as defensible in the authored truth before the
run, under the one-role-per-column constraint:

- bank statement `Fecha valor` → `booked_date` (fabricated, defensible)
- expense-tracker `id` → `transaction_id` (fabricated, defensible)
- expense-tracker `date` → `booked_date` rather than `invoice_date` (wrong, defensible)
- neobank `reference` → declined (missed, defensible)
- ERP `DEBE` → declined (missed, defensible)

**Exactly one slot of 71 is an undeclared error**: the bank statement's
`Fecha operacion` read as `invoice_date` where it is a `booked_date`. That is
precisely the mislabelling `FieldRole.BOOKED_DATE` was declared to prevent — a
movement has no issue date — so the one real failure lands exactly where the
vocabulary's designer predicted it would.

**Undeclared fabrications: 0 of 21 trap slots.** Both fabrications sit on slots
whose alternate was declared in advance. The anti-fabrication guarantee held: on
this corpus, at this tier, the reader invented no meaning that had not already
been reasoned to be defensible.

### Cost, and a defect found in measuring it

Nine calls — **one per export, which is the architecture's own claim**: the
mapping is decided once per file and never per row. 16.7 seconds wall time,
**6796 input and 1429 output tokens**, zero cache hits.

**The USD estimate reads $0.0000 and that is an estimator gap, not a free call.**
The cost estimator resolves an unknown model to zero rather than refusing, and
its pricing table carries `claude-sonnet-4-6` only. Probed directly, a million
input and a million output tokens price at $18.00 for sonnet and **$0 for
`claude-haiku-4-5`, for `claude-opus-4-1` and for `gpt-4o`**. The design-target
tier — chosen because cost matters — is the one tier the estimator cannot price,
and it says so with a plausible number rather than an absence. Carried as `S286`.

### Stability

The whole nine-export run was executed **twice, independently**, each against a
fresh throwaway profile and therefore an empty cache — zero cache hits on both.
Every per-export figure and every verdict was identical. At temperature zero the
mapping is reproducible, so these numbers are not one sample.

## Verification

The naming-axis check, run before any call:

    emitted vocabulary size (FieldRole): 24
    expected tokens used: 14 | all in FieldRole: True
    alternate tokens used: 4 | all in FieldRole: True
    tokens expected but NOT emittable: NONE

The measured run, second of two identical executions:

    key sha256   e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593
    model        claude-haiku-4-5   tier cloud_design_proxy   route gated_cloud
    session provisioned: readiness ready
    decided_by   llm:anthropic-column-role-map:claude-haiku-4-5
    ...
    TOTALS over 9 export(s)
      scorable   46/50 matched, 2 wrong, 2 missed
      traps      2/21 FABRICATED, 19 correctly abstained
      cost       9 call(s), one per export by design, 16.7s total
                 6796 input + 1429 output tokens, est $0.0000, 0 cache hit(s)

Per-slot verdicts for every non-clean slot, which is what separates a defensible
answer from a real error:

    === OP-PUR-bank_statement_2026Q1_Q2
      col00:Fecha operacion   expected=booked_date  got=invoice_date    WRONG UNDECLARED
      col01:Fecha valor       expected=None         got=booked_date     FABRICATED DECLARED-DEFENSIBLE
    === OP-PUR-expenses_app_export_2026
      col00:id                expected=None         got=transaction_id  FABRICATED DECLARED-DEFENSIBLE
      col01:date              expected=invoice_date got=booked_date     WRONG DECLARED-DEFENSIBLE
    === OP-PUR-bank_neobank_2026Q1
      col03:reference         expected=notes        got=unmapped        MISSED DECLARED-DEFENSIBLE
    === OP-REC-ledger_erp_export_2026Q1
      col03:DEBE              expected=movement_amount got=unmapped     MISSED DECLARED-DEFENSIBLE

The authored truth's own gates, sequentially (the harness tests crash an xdist
worker on this share):

    uv run --no-sync pytest dev/ingest_harness/tests/test_tabular_truth.py -m integration -n 0
    12 passed in 2.56s

## Notes

- **No operator secret moved and the real profile was never opened.** The session
  came from the in-tree isolated runtime profile: a throwaway root under the
  dev-test passphrase, provisioning the same durable surfaces production uses,
  discarded with its temporary directory.
- **No consent token was minted, and none was bypassed.** The column-role mapping
  request declares its evidence posture as not-evidence-derived by an earlier
  accepted decision: what crosses that seam is the file's header vocabulary and
  never a cell value, and the prompt compiler accepts headers only. The consent
  gate therefore does not govern this request class. Nothing was disabled,
  weakened or worked around, and no decrypted evidence byte touched disk.
- **The cost estimator gap is the finding a reader is most likely to miss**,
  because a zero looks like an answer. Anyone budgeting the tabular lane from
  this record must read the token counts, not the dollar figure.
- The first execution of the full run reported no cost line at all — a defect in
  the measurement driver, not the product, where the response recorder was bound
  before the calls populated it. It was fixed and the run repeated in full rather
  than patching a cost figure onto quality numbers gathered under a different
  invocation.
- A peer's in-flight harness module was briefly unimportable mid-session, which
  blocked the re-run. It was waited out rather than edited.
