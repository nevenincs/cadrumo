---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:57e1fcf4b7c4196ad5e1ff30febdf92f30225f419cab799ae1ef641a63f85ca1'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-09-04-clitui-ledger-reference]]"
  - "[[2026-09-04-clitui-ledger-W01-P04-S12]]"
---

# `clitui-ledger` audit: `S12 exhaustive row review`

## Scope

Reviewed the schema-v4 union row-review contract, its live projection and
validators, the S12 execution record, plan, reference and index, and the
underlying application/import and TUI census evidence. Vaultspec-RAG was used
first, but the local code corpus reported zero indexed sections; whole-file
reads, exact searches, independent projection scripts, and mutation/focused
tests therefore supplied the review evidence.

## Findings

**Ruling: NOT ACCEPTED.** Two HIGH under-declarations remain.

The mechanical envelope is otherwise reproducible and conservative. It has
760 observations, 769 selection edges and 693 reviewed rows. Effects reproduce
as 546 registry routes, 83 mutations, 47 queries, nine proposals, seven
artifacts, and one artifact query. Semantic homes are 689 planned and four
signature-validated existing homes. Registry disposition is 510 direct, three
application sidecars, 33 destinationless, and 147 not applicable. TUI
applicability is 680 held until G3 and 13 not applicable/unheld. All 693 rows
carry eight canonically ordered decisions; every applicable proof is unproven,
every non-applicable proof is not applicable, and no COMPLETE or PROVEN state
is manufactured.

Every row digest, aggregate review digest, reviewed-row count, attestation, and
outer digest validates. The current row review digest is
`sha256:43b50491b84cb7e6bc3a69f4688aaa3550e602ce18ed47f0a31fff2f0b7dc871`;
the attestation digest is
`sha256:73c3b5784e2af9d681ed80bd535272e532d798679fc2235f0081e6c692a3b90d`;
and the union digest is
`sha256:64c66b465d8c5d13dfbd93b8b55e36c50b15a51a3063964c166b85fe54fbb3de`.
Existing tests reject omitted, duplicated, stale, owner/home, applicability,
gap, proof, action, TUI-route, registry-status, row-digest, coverage, and
attestation mutations after dependent public digests are refreshed.

### import-artifact-axis-is-suppressed | high | File-consuming import rows are classified as artifact-not-applicable

`_axis_decisions` makes artifact applicability depend only on the row's
single effect being `artifact` or `artifact_query`. That contradicts its own
artifact rationale and proof requirement, which cover capabilities that emit
**or consume** independently readable files. `ledger.import.source` is the
clearest counterexample: its existing typed command requires a `Path`, and
`import_ledger_source` validates, opens, hashes/verifies, parses, and ingests
that file, yet the reviewed row says artifact is not applicable. It therefore
has only composition, proof, and reachability gaps and becomes the sole
composition-first row. The required primary partition is not reproduced:
current data has 112 AUTHORITY / 546 REGISTRY / 34 PRODUCT / 0 ARTIFACT / 1
COMPOSITION, rather than 112 / 546 / 34 / 1 / 0.

The exhaustive file-import cohort requiring explicit artifact applicability is
`ledger.classification.bulk_csv`, `ledger.import`,
`ledger.import.directory`, `ledger.import.dry_run`, `ledger.import.file`,
`ledger.import.provider_auto`, `ledger.import.provider_csv`,
`ledger.import.provider_n26`, `ledger.import.provider_ofx_qfx`,
`ledger.import.provider_pdf`, `ledger.import.provider_pdf_n26`,
`ledger.import.provider_xlsx_excel`, `ledger.import.source`,
`ledger.import.verify`, and `ledger.invoice.import`. For the other fourteen,
higher-priority authority or product gaps can remain primary, but artifact must
still be an applicable axis, a secondary gap, and a proof obligation.

### tui-route-review-is-not-exhaustive | high | 673 TUI-applicable rows have neither a destination nor a reachability gap

The seven-route census-to-denominator selection table is reused as the
row-level TUI destination map. That table intentionally selects only one
representative semantic row per route, so it cannot be an exhaustive routing
authority. The result is 673 rows whose TUI axis is applicable but whose
`tui_routes` tuple is empty and whose gaps omit `REACHABILITY`. For example,
`ledger.transaction.create`, `ledger.evidence.download`, the export formats,
LLM decisions, and all registry-route rows are declared TUI-applicable but have
no reviewed destination. Six representative rows have component-only routes
and a reachability gap; only `ledger.workspace.read` is mapped to the installed
Overview. A hold and a generic unproven TUI requirement do not identify where
the other operator capability will be exposed or faithfully summarized.

This silently under-declares the row-level reachability work and makes the
reference's claim that every reviewed field, including TUI routes, is
recomputed materially incomplete.

## Recommendations

- Add an explicit artifact-input applicability authority independent of
  `LedgerCapabilityEffect`, covering the exact fifteen import identities above.
  Recompute gap sets, row/aggregate/attestation/union digests and publication;
  the primary cohort must become exactly 112 AUTHORITY, 546 REGISTRY, 34
  PRODUCT, one ARTIFACT, zero COMPOSITION, and zero proof-only. Add positive
  tests for every identity plus a mutation that removes one identity or marks
  its artifact axis/gap/proof requirement not applicable and still recomputes
  all public digests; validation must refuse it. Derive or detector-check the
  authority against typed local-input command contracts so future file/folder
  imports cannot enter silently.
- Separate source-observation selection from exhaustive TUI destination
  adjudication. Bind every one of the 680 TUI-applicable rows to at least one
  known Ledger route, require all 13 TUI-not-applicable rows to have none, and
  derive reachability gaps/blockers from each assigned route's installed or
  component-only state. Add mutations for deleting, changing, adding, or
  reordering a row destination and for adding a TUI-applicable row without a
  route; recomputation of row, review, attestation, and outer digests must not
  admit them.

The full matrix suite passes 258 tests and Ruff format/check, scoped `ty`,
scoped `basedpyright`, plan validation, and feature Vault checks pass. These
green checks encode the two incorrect classifications and therefore do not
lower their severity. G0 remains OPEN. S12's scoped commits change only quality
contract/tests and Vault documents; they do not implement Ledger product or TUI
behavior.
