---
tags:
  - '#research'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:f1c7dbc507fb7a15340833d65e296b3881d1650a974001286037a36c7dfcc411'
related:
  - "[[2026-08-24-registry-completeness-closure-adr]]"
  - "[[2026-08-25-registry-completeness-closure-production-emission-proof-reference]]"
---
# `registry-completeness-closure` research: `S33 two-channel filing export proof research`

S33 requires a positive emitted-byte proof for every filing-grade revision, but current evidence proves that no repository fixture can truthfully supply the required filing-instance inputs. This research distinguishes structural rendering evidence from taxpayer-instance acceptance evidence without deciding the release predicate.

## Findings

### Current boundary

The dynamic filing-grade denominator is 66 revisions. The canonical positive route is empty; 25 revisions have generated provenance and literal probe candidates while 41 do not. Fifty-eight revisions cite 662 shared producer keys and eight cite no producer key, but neither group has a source-owned draft/snapshot and independent emission evidence. `f34dab2c16` and `2026-08-25-registry-completeness-closure-production-emission-proof-reference` record those facts.

`LiveFilingExportProofAuthority` is the sole chain: law-selected snapshot, verified provenance, `export_draft`, digest/extent, and official literal-offset probes. Its empty entry tuple makes current results explicit refusal: the former source file and the former source file.

### Custody and alternatives

`ModeloDraft` and `FilingProducerSnapshot` contain taxpayer, identity, account, casilla, binding, election, and amendment facts. Production export rebuilds them from an approved calculation revision, active profile, persisted evidence, ledger state, and cross-period decisions: the former source file. Sensitive custody prohibits repository plaintext values, payloads, and instance-derived acceptance digests.

An official non-sensitive specimen can prove a bounded public example but not a specific operator's source-owned value arrival. Existing M151, M111, M130, and M200 fixtures are synthetic or refusal mechanics; eight M200 cases are separate fixture-coordinate debt.

A two-channel mechanism can split value-independent renderer conformance from secure operator-specific replay. Boundary vectors can prove source-pinned geometry through the canonical writer, while secure replay can prove actual value arrival without persisting taxpayer payloads in the source tree. This requires an ADR because the parent predicate presently requires emitted-byte proof. Predicate demotion would weaken the accepted filing guarantee without an AEAT capability fact.

## Sources

- `f34dab2c16`
- `b9cb7a3682`

- `.codex/rules/sensitive-financial-data-secure-storage-only.md`
- `2026-08-24-registry-completeness-closure-adr`
- `2026-08-10-aeat-export-fragment-generator-authority-adr`
