---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4345a8d9c9a788c886c96f6183f1cfef070ad05b194d088f71b787e52cb4b776'
step_id: 'S17'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Delete the dead second Invoice writer and its tests outright rather than routing it, because the live bulk importer already routes canonically and routing would create a third import surface

## Scope

- `src/cadrumo/application/invoices/_importing.py`

## Description

- Confirmed the live import path and its canonical routing BEFORE deleting anything.
- Swept the module's exported symbols with word boundaries after a substring collision nearly produced a false finding.
- Deleted the module, its two test files, its facade exports, its apidocs stub and its parent toctree entry.
- Removed the three dependent tests in a different package and the docstring lines naming the retired symbols.
- Staged only this deletion from a generator run that swept the whole tree.

## Outcome

**The dead second `Invoice` construction authority is gone, so exactly one remains — which is the whole-plan gate's wording.**

The reachability claim was verified before the deletion rather than after, because a deletion premised on an unverified claim is the mis-specified retirement this plan is guarding against. The live import path is the bulk importer, reached from the CLI import verb, and it routes every row through the canonical creation primitive.

**The plan's own corrected scope list was still incomplete, and by more than a little.** That correction states the module exports FOUR symbols and that one test in another package imports one of them. Measured at `HEAD`: **five** symbols — `InvoiceRowPayload` was missed — and **three** dependent tests in that other package, not one. A sweep that trusted the list would have deleted the module and left the tree importing two symbols that no longer exist, surfacing as a collection error in an unrelated package: exactly the failure shape the correction was written to prevent.

**A near-miss worth recording, because it would have read as a finding.** The first consumer sweep returned three PRODUCTION consumers and looked like a refuted premise — the module appeared to be live, and the Step's deletion unsafe. It was a substring collision: `BulkInvoiceImportResult` and `CatalogueInvoiceImportResult` both contain `InvoiceImportResult`. A word-boundary re-run showed the premise holds and the module is genuinely dead.

Had the first reading been reported, it would have blocked a correct deletion on a defect that does not exist. Comparing a name without its namespace is how that happens, and the cost is asymmetric: an over-severe finding stops good work, where a missed one ships bad work — both are expensive, and only measurement tells them apart.

## Verification

    uv run --no-sync pytest src/cadrumo/application/invoices src/cadrumo/tests/test_wizard_locale_and_typed_payloads.py -m "integration or unit" -q --no-header
    183 passed in 30.05s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_payloads.py -m "integration or unit" -q --no-header
    14 passed in 9.47s

    uv run --no-sync ruff check src/cadrumo/application/invoices/ src/cadrumo/tests/test_wizard_locale_and_typed_payloads.py
    All checks passed!

A tree-wide word-boundary sweep for all five symbols returns no residual reference in source or docs. The commit removed 624 lines across 7 files, all of them this Step's.

## Notes

**The apidocs generator run had side effects on peer-owned files, and they are disclosed rather than quietly left.** The stub and its parent toctree entry had to go, since an orphan stub hard-crashes the nitpicky docs build. The rule requires the generator rather than a hand-edit, but the generator regenerates the WHOLE tree.

Only this deletion was staged. The parent toctree was reconstructed as `HEAD`'s content minus the single retired line, because the regenerated version also added two peer modules whose stubs are not committed — staging it whole would have referenced stubs absent from the commit and pulled unrelated campaigns' work in.

What could NOT be undone is the working tree: the same run left eleven tracked peer stub files modified or deleted, and created twelve untracked ones. Those changes are *correct* — the deletions are genuine orphans from a peer's re-export-bridge removal, and the additions are stubs peer modules legitimately need — but they are peer work sitting dirty in a shared worktree, and reverting them is not available: every command that would do so is categorically forbidden here.

They are therefore left in place and named, so a peer who finds them knows where they came from. The general lesson is that the generator's blast radius is the whole tree even when the intended change is one file, and the only isolation available is at the staging step — not at the running step.
