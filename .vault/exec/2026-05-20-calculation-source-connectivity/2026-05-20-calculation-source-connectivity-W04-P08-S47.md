---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:69a7652639ecb3c649454cc4bfd31e6f7c4c0680356964b2d1b9d970d5207ecc'
step_id: 'S47'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Test committed modelo source inventory against enrolled resolvers

## Scope

- `src/aeat/domain/calculations/registry/test_source_enrollment.py`

## Description

- Add `test_source_enrollment.py` under the registry `tests/` folder (per `tests-live-under-domain-tests-folders`; the plan's colocated target path is folded into it).
- Test the committed registry source inventory (from S44's `source_inventory()`) against the disposition taxonomy: assert no committed revision declares a `RESERVED` (dormant) source kind, and every declared kind classifies `ENROLLED` or `DEFERRED`.
- Add anti-vacuity floors: the inventory is non-empty and well-formed (sites sorted, unique, counts consistent); it carries both an enrolled anchor (`ledger_iva_aggregation`) and a deferred anchor (`atribucion_member`).
- Add an anti-tautology proof: a real `RESERVED` member (`ledger_transaction`) classifies `RESERVED`, so the gate is a live discriminator that can fail.
- Pin the domain-test to `application.aggregation` edge in both `.importlinter` contracts (sibling registry-test precedent).

## Outcome

- New test file; 4 tests green. The gate refuses the `no-dormant-source-resolvers` silent-zero at the registry-inventory boundary.
- Placed the STRICTLY-STRONGER "against the LIVE enrolled resolver set" join in the S48 application companion, because the live enrolled set (`BUCKET_AGGREGATION_OWNED_SOURCES`) is an application (live-mesh) fact that cannot cross into a domain test without inverting the layer boundary. This domain gate owns the registry-inventory-integrity half; S48 owns the live-mesh half.
- Gates green: `Domain must not import application` importlinter contract KEPT; ruff + ty clean; collect-only clean.

## Notes

- Enrolled partition in this domain test is derived as `BindingSourceKind - DEFERRED - RESERVED` (public `application.aggregation` sets) per the disposition parity invariant proven by `test_binding_source_kind_mesh_parity`, avoiding the private live-policy import. The authoritative live-set join is S48.
- The `application/modelo/__init__.py` facade carried peer WIP (staged locale/other churn), so `BUCKET_AGGREGATION_OWNED_SOURCES` was NOT promoted to that facade; the S48 companion reaches it intra-package instead. This kept the change off the peer-WIP file.
