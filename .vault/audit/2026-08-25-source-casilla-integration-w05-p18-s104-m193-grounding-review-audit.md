---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:98cc25f503b6fa71047ab62d531dc6d9c6691329ff949bed181fbec72ae855e6'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-25-source-casilla-integration-m193-row-source-grounding-research]]"
---
# `source-casilla-integration` audit: `W05 P18 S104 Modelo 193 grounding review`

## Scope

Independent review of commit `020bc7aacd`, its S104 evidence record, the M193
registry/binding/manual/export surfaces, source mesh, census, worksheet
assembler, and withholding repository. This review verifies that the stated
semantics remain bounded to the official evidence and do not enroll a source.

## Findings

### official-expense-record | low | The primary record designs support a distinct Article 26.1.a type-2 expense row

The independently recomputed SHA-256 digests match the reviewed 2024-late AEAT
design (`361842...aff8e`), 2025 AEAT design (`25ab190...62489`), and BOE form
specification (`6a5405...cb6b`). The 2025 official extracted design calls the
record `RelaciÃ³n de gastos` and identifies the Article 26.1.a expense annex;
it separately carries contributor NIF, conditionally applicable representative
NIF, contributor name, and annual expense. That establishes reporting grammar,
not an automated acquisition authority.

### deferred-owner-boundary | low | Current code and census truthfully retain the candidate as ingress-blocked

The worksheet assembler synthesises its source identity and annual date, while
the binding helper folds observations by contributor identity. The source mesh
keeps `GASTO193_CONTRIBUTOR` deferred, and the census retains the named
campaign owner, 2026-12-31 expiry, and 2026-11-30 bounded follow-up. No secure
contributor repository, calculation-revision handoff, replay path, or live
resolver was found in the whole M193 epicenter. S104 does not invent any of
those runtime or census capabilities.

### manual-and-withholding-separation | low | Manual filing and encrypted withholding custody are not substituted for the contributor source

Both supported M193 revisions expose the four direct `gasto.*` row fields and
repeat them through the fixed-record export layout; they remain valid manual
filing entry/output paths. The encrypted retenciÃ³n repository persists a
separate perceptor/withholding record, not the Article 26.1.a contributor
expense record. The evidence and execution record preserve those boundaries.

### dormant-token-mismatch | low | The `gasto193` helper spelling mismatch is accurately limited to S105

The dormant helper compares bindings against `gasto193`, whereas both current
registry revisions declare `gasto193_contributor`. Exact call-site search found
no production enrollment of either helper. S104 records this only as a future
S105 prerequisite and makes no misleading repair or connected claim.

## Recommendations

Approve S104 as grounded discovery. Keep the current ingress-blocked census
state and direct manual route unchanged. Any S105 proposal must first establish
a secure non-lossy contributor-record owner and then prove the full lifecycle
before resolver enrollment; it must also resolve the exact declared source-kind
mismatch as part of that separately authorized work.
