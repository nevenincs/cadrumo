---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:cb2cbe4fd3acfec6f977732cb22caffd47c64c749c2ef1fb41a171271dfeeb73'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S220]]"
  - "[[2026-09-04-reachability-burndown-reference]]"
---

# `reachability-burndown` audit: `S220 compatibility lifecycle metastate withdrawal review`

## Scope

Independent review of W05.P12.S220: removal of the production compatibility-lifecycle regime, floors and persisted-format classification inventory; deletion of its synthetic policy and enrollment census tests; narrowing of schema-lineage and secret-index tests; related stale prose cleanup; cadence guidance; and Step Record evidence.

## Findings

No critical, high, medium, or low findings.

The deleted `compatibility_lifecycle` module encoded development lifecycle state in production: a dormant pre-release/released switch, future frozen-floor placeholders, a hand-maintained persisted-format classification map, and pure predicates exercised only by synthetic tests. No live reader, writer, upgrader, composition root, or durable artifact consumed that regime. The enrollment suite independently reconstructed format identity from package registries plus its own non-file key list and compared that census with the production census; it did not prove a concrete stored artifact remained readable.

Concrete protections remain with their storage owners. Schema-lineage tests still prove floor coherence, refusal of future schemas, refusal of missing upgrade hops, ordered registered upgrades, current-version no-op behavior, and single-writer/reversible upgrader registration. Secret-index tests still drive real writes and reads, require the version marker, refuse omitted and future versions before reads or whole-index mutation, preserve bytes on refusal, and recover when the supported version is restored. The writer continues stamping `SECRET_INDEX_SCHEMA_VERSION`, and the loader continues fail-closed comparison. Thus no current write format, read door, refusal contract, or real upgrade chain was removed.

The cleanup introduces no replacement allowlist, lifecycle flag, format census, or source dependency on tests/dev. Exact residue for the removed regime, floors, inventory and classification type is clean. The Step Record honestly reports 15 focused concrete tests, Ruff success, orphan reduction to 13, one fewer unreachable module, and 2029/2091 reachable shipped modules with 311 exact unused symbols. Its release-config failure is explicitly separated as peer-owned configuration drift and does not bear on the removed dormant mechanism.

### adr-corpus-reconciliation | low | Resolved: accepted decisions now match the withdrawal

The reopened review found the implementation decision had previously outpaced three accepted ADRs and an obsolete checkpoint reference. The 2026-09-08 amendments now resolve that documentary contradiction without weakening the durable product contract.

The released-data-durability ADR withdraws preinstalled empty dispatch and vacuous chain governance while retaining explicit version stamps, fail-closed reads, and the requirement that a real transition ship its reader/upgrader and old-shape production-path proof. The compatibility-lifecycle ADR explicitly withdraws the dormant regime, floor placeholder, classification inventory, synthetic branch proofs, and central enrollment census while preserving readability of released taxpayer data. The current-schema-only-purge ADR now consistently requires exact-current markers and early refusal and no longer prescribes future-state scaffolding. The checkpoint reference has been reduced from an obsolete mechanical flip checklist to the same evidence-at-transition rule.

The amended S220 plan row and regenerated Step Record name all four documents and the widened scope accurately. No contradictory authorization for the deleted production metastate remains in the reviewed decision chain. Final verdict: approved.


## Recommendations

Approve W05.P12.S220. Future compatibility obligations should be introduced only with a real version transition, persisted old-shape evidence, and the owning reader/upgrader path—not as a dormant production regime or hand-maintained format-classification census.
