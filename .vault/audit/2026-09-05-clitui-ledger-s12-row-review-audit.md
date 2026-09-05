---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:be953ad48a8052190013c8137aa9268581c2686533e8ea69acfcfefe567e20a5'
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

## Remediation review

**Ruling: NOT ACCEPTED.** The original missing-route condition is mechanically
closed, and the fifteen named import identities are artifact-applicable and
unproven. Two HIGH semantic/source-consistency findings remain.

The remediated projection reproduces 693 rows, effects
546/83/47/9/7/1, homes 689 planned/four existing, primary gaps 112 AUTHORITY,
546 REGISTRY, 34 PRODUCT, one ARTIFACT and zero COMPOSITION/proof-only, and
registry dispositions 510 direct/three sidecar/33 destinationless/147 not
applicable. It reports 23 artifact-applicable rows. All 680 TUI-applicable rows
have a known route and the 13 non-applicable rows have none; published route
counts are Classification 9, Entries 32, Evidence 21, Import 13, Overview 1,
Reconciliation 587 and Review 17. Exactly 679 component-only rows retain a
reachability gap/blocker and the sole Overview row is the read-only
`ledger.workspace.read` query. No applicable decision is upgraded above
UNPROVEN.

Row-review, attestation and union digests independently reproduce as
`sha256:3809546161a2164a50fa442ad5759b104092ccf231627d45f849e5b3023ccfb8`,
`sha256:60fd297e03e1384d3eca3d56b568a21ea0f6b913cc8c2b7f15dc6aab7e2b0ce4`,
and
`sha256:a8e2854f6fa822824618e428a56c0390343f77b7f0233bd165985f9d0edb9f65`.
The focused artifact/route/review lane passes 18 tests.

### tui-route-source-contradiction | high | Invoice-link is mapped away from the live reconciliation component that selected it

The supported-surface source observation for `ledger.reconciliation` selects
`ledger.transaction.invoice_link`. The live `LedgerReconciliationScreen`
renders transaction/invoice pairs and submits that exact link operation through
its injected door. The exhaustive mapping instead assigns
`ledger.transaction.invoice_link` to `ledger.entries`. Validation checks that
both tables are separately complete but never joins a supported-surface
selection back to its source destination, so the contradiction survives every
row, attestation and outer digest recomputation.

Move invoice-link to `ledger.reconciliation`; absent another independently
grounded reassignment, the honest route totals are Entries 31 and
Reconciliation 588. Add a detector requiring every capability selected by a
supported-surface observation to include that observation's destination in its
row-level TUI route authority. Mutate the source destination/selection and the
row mapping independently, refresh all dependent digests, and require refusal.

### artifact-input-authority-omits-live-local-inputs | high | The claimed exhaustive set excludes evidence and inventory files

The new fifteen-row set correctly covers the requested import cohort, but its
validator and test describe it as the exhaustive local file/directory input
set. Live command metadata contradicts that assertion:
`ledger.evidence.add` declares a primary LOCAL_IN file,
`ledger.evidence.batch` declares primary LOCAL_IN directory and file inputs,
and `ledger.inventory.closing-authority.record` declares a primary LOCAL_IN
file. All three rows remain artifact-not-applicable and omit the artifact gap,
proof requirement and blocker. The already admitted planned
`ledger.evidence.replace` capability likewise consumes the replacement
attachment. Thus 23 is not an exhaustive artifact-applicable cohort: the live
minimum is 26, and it is 27 when the explicit atomic-replace product is
included. These additions do not change the primary-gap partition because
their authority/product gaps retain higher priority.

Derive or cross-check local artifact inputs from live `CommandSpec` transport
locus/shape metadata, then add a small explicit authority only for planned
inputs that have no installed command metadata. Add positive and removal/
reclassification mutations for evidence add, evidence batch, inventory closing
authority and evidence replace, with every digest recomputed.

G0 remains OPEN and the remediation contains no Ledger product or TUI
implementation changes. Green tests encode both remaining contradictions and
therefore cannot support acceptance.

## Final remediation review

**Ruling: ACCEPT.** Both remaining HIGH findings are closed. No CRITICAL or
HIGH finding remains; one MEDIUM publication-currentness finding is recorded
below.

The live Ledger `CommandSpec` projection independently reproduces exactly eight
`LOCAL_IN` file/directory parameter observations: classify `file`; evidence-add
`source_path`; evidence-batch `directory` and `file`; import `file` and
auxiliary `verify_source`; inventory closing-authority `file`; and invoice
import `file`. Their endpoint and sub-operation selections expand to 29 unique
semantic rows. The separately reviewed current `ledger.import.source` input
makes 30, and planned `ledger.evidence.replace` makes 31. The matrix has exactly
39 artifact-applicable rows after the eight output/query products are added:
`ledger.evidence.download` plus the seven export identities. All 31 inputs are
`APPLICABLE`/`UNPROVEN` on the artifact axis, retain artifact gaps and explicit
readability/refusal/digest/custody proof, and `ledger.import.source` remains the
sole artifact-primary row. Removal, addition, shape/role drift, and semantic
selection drift in the live observation contract refuse against the exact
committed eight-observation authority; independent removal and selection
reassignment counterexamples also refused.

The supported-surface join now checks the destination encoded by every live
supported-surface observation against every semantic row it selects.
`ledger.transaction.invoice_link` is routed to `ledger.reconciliation`, in
agreement with the live component observation. Independent wrong-selection and
destination-remint counterexamples refused at that join. The durable serialized
test additionally changes the selection, moves observation membership, refreshes
the supported-surface source digest, every row digest, aggregate review digest,
attestation and outer union digest, and is still refused. Exact non-registry
observation authority supplies the second boundary against destination/identity
remints.

Current route totals reproduce as Classification 9, Entries 31, Evidence 21,
Import 13, Overview 1, Reconciliation 588 and Review 17. TUI disposition remains
680 applicable/held and 13 not applicable/unheld, with 679 component-only rows
retaining the reachability gap. Primary gaps reproduce as 112 AUTHORITY, 546
REGISTRY, 34 PRODUCT, one ARTIFACT and zero COMPOSITION/proof-only. Selection
accounting remains 760 observations, 769 edges and 693 rows. Every applicable
axis remains `UNPROVEN`; no operational `PROVEN` or complete row is asserted.
G0 remains OPEN.

The independently reproduced current digests are:

- row review:
  `sha256:4e42e5e04ccfd7a8654e629933698e141033b0767d0f94ec5433619400203ff8`;
- row-review attestation:
  `sha256:fc15a433ad145832934cbe894d3d0b875d27e9a54ed1a70ae271c16ff81aedf7`;
- union:
  `sha256:8a158b5cc4c8e6c3035dc272999af61ac6cb080af8c208eccc8d28e4105a7575`.

### stale-s07-tui-digest-publication | medium | Historical digests are still described as current

The reference's S07 supported-surface paragraph still says the current
126-file source-set and census digests are
`sha256:e7337508a02ef2260e0b28205c31bb872b69f59aa51a18391ae209c21b8f9d57`
and
`sha256:c136cfe1ae3f82a239476c00e805f8c9a29e010d502e74397963cea7e6f42371`.
The live projection now reproduces
`sha256:70709a369bece8e06033e56e18bd82425ec9b48767c3466e80f92c901143ff67`
and
`sha256:a52180bb77b70c205c7d31f657a64ad55142035b63dd9d5bf69b79503754c25f`.
The schema-v4 union embeds and validates the latter current census, its route
facts are unchanged, and the correct current census is already bound by the
accepted union digest, so this is stale human-readable evidence publication
rather than a silent denominator or routing defect. Update the S07 paragraph
and evidence coordinate through the canonical publication workflow, or label
those hashes explicitly as the historical S07 snapshot.

Verification on the final candidate: the focused artifact/TUI-route/review lane
passed 24 tests with 253 deselected; the full matrix file passed 277 tests.
Ruff format and check, scoped `ty`, scoped `basedpyright`, plan checking and the
complete `clitui-ledger` Vault feature check all passed. The reviewed S12 commits
change only the quality contract/tests and Vault documents; they contain no
Ledger product or production TUI edit. The unrelated modified duplication-
burndown execution record was preserved and excluded from this review.
