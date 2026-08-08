---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d971e257f3d55391d8972ca12b2c23adb5d5afbe264ae0f9aa860f86e1e926e8'
step_id: 'S248'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Settle whether the relief exemption depends on the code system

## Scope

- `src/cadrumo`

## Outcome

**No defect. The exemption does not depend on the code system.** Measured from inside the suite, with the fixture state the earlier attempt was missing, all four spellings report the same status through the authority production uses and produce the same outcome:

    TH:  status=uncatalogued outcome=unsupported_relief
    AF:  status=uncatalogued outcome=unsupported_relief
    ABW: status=uncatalogued outcome=unsupported_relief
    THA: status=uncatalogued outcome=unsupported_relief

Two alpha-2 spellings and two alpha-3 spellings of the same catalogue gap, identical at every step. The status is the only thing the token contributes to the resolver, so identical statuses could not have produced different outcomes; the earlier suspicion required a mechanism that does not exist in the call path.

## Description

- Establish the fixture state first, as the row directs, rather than re-attempting the comparison that failed.
- Rule out the two environmental hypotheses by measurement: the module-path insertion and the isolated storage root both leave the outcome unchanged.
- Take the reading from inside the suite instead, where the fixture state is whatever the suite actually provides, and read status and outcome side by side for four spellings in one pass.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_ingestion_category_resolution.py -n0 -q
    33 passed in 5.33s

The diagnostic that produced the table above was run inside the suite and removed immediately; the file is byte-identical to the committed tree.

## Notes

The question arose from a stale premise rather than from the code. The earlier attempt compared its result against a shipped case believed to assert that an uncatalogued counterparty is spared. That case no longer exists under that name or that specification: it was renamed and re-specified when the exemption was scoped, and it now expects the refusal, because its fixture establishes neither party and the filer's own slot is outstanding. So the contradiction that looked like a defect was a comparison against a test that had been rewritten underneath it.

Both failed attempts at this question shared one shape: a comparison whose control had not been established. The first trusted a swap of one module while a peer edited another; the second trusted a remembered assertion instead of reading the assertion that ships. In both the arms were fine and the baseline was wrong.

No test was added. A spelling-independence assertion over the helper this question used would pass for the wrong reason: that fixture leaves the filer slot outstanding, so every spelling refuses and the assertion holds without the exemption ever firing. Writing it would have produced exactly the vacuous gate this campaign keeps removing. A non-vacuous version needs a fixture where only the counterparty slot is outstanding, which is a fixture this row did not have and did not invent.
