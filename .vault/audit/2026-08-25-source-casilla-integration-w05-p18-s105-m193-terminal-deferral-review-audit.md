---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:ca2c30415186917d3034c1729b034f847b4d0f361c3d0bee25d77eb3b4ffa8c8'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-W05-P18-S105]]"
  - "[[2026-08-25-source-casilla-integration-m193-row-source-grounding-research]]"
---
# `source-casilla-integration` audit: `W05 P18 S105 Modelo 193 terminal deferral review`

## Scope

Independent re-review of stable repair `88e8e245d1` against invalid predecessor
`58e4b3ab63`. The review covers the M193 census and bounded follow-up, the
S105 deferral test, manual/export authority, source mesh, dormant helper, and
withholding repository boundary.

## Findings

### predicate-validation-ceiling | low | The prior HIGH census-load failure is resolved

The repaired reopening predicate is exactly asserted by the focused test and
remains within the manifest's 500-character ceiling. The real census loader now
accepts it. The entry retains `ingress_blocked`, owner
`source-connectivity-campaign`, expiry 2026-12-31, and the same explicit owner
and 2026-11-30 deadline on its bounded follow-up.

### deferral-boundary | low | No resolver or new source authority was introduced

`GASTO193_CONTRIBUTOR` remains in the deferred source set and absent from every
canonical route resolver ownership declaration. The helper still uses its
dormant `gasto193` comparison while the registry declares
`gasto193_contributor`; S105 names exact canonical alignment as a reopening
predicate rather than treating that helper as connected.

### manual-and-withholding-separation | low | Direct filing inputs and encrypted withholding custody stay non-substitutable

The focused runtime test proves all four manual `gasto.*` fields remain
available, the source still emits the unhandled-source diagnostic, and no
connected proof fixture owns the candidate. The census separately denies that
withholding storage supplies contributor-expense ownership.

### mutation-and-coverage-bites | low | The test cannot pass vacuously on an invalid deferral

The test asserts the exact predicate, boundary owner, expiry and follow-up,
refused coverage result, absent resolver ownership and connected fixture, and
an expiry mutation that governance rejects. It covers the deferred advisory
surface and source-connectivity coverage across the two scoped M193 revisions.

## Recommendations

Approve S105's terminal ingress-blocked disposition. The earlier HIGH
manifest-validation finding is resolved by `88e8e245d1`. S106 remains the
separately required lifecycle, provenance, persistence/replay, and export
proof; no resolver may be enrolled before that work and the stated reopening
predicate are satisfied.
