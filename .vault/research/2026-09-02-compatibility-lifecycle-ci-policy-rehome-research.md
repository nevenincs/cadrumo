---
tags:
  - '#research'
  - '#compatibility-lifecycle'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:73c88a6335684d696b93b2646856a009979521a390f59f129f296fb2df164131'
related: []
---

# `compatibility-lifecycle` research: `rehome dormant CI policy out of the wheel`

The exact reachability finding is mechanically correct but does not identify missing runtime wiring: `core.compatibility_lifecycle` is a deliberate test/CI policy authority, and the accepted ADR requires no production read-path effect before a compatibility flip. Because the module is nevertheless shipped and API-documented, reaching zero honestly requires an ADR amendment that rehomes this pure governance authority to `dev`, updates its test consumers, removes its generated API surface, and shrinks the ratchet.

## Findings

### Runtime wiring would violate the accepted posture

The compatibility-lifecycle decision requires dormant regime-aware gates while current-version readers remain tier-local. `PERSISTED_FORMATS` is the sole cross-format lifecycle/classification inventory, but production serializers and readers correctly do not consult it. Adding a production import merely to satisfy reachability would create a false green and change the pre-flip runtime contract.

### The module is shipped despite being CI-only

Hatch includes `src/cadrumo/core/compatibility_lifecycle.py` in the wheel and API-doc generation publishes it. The graph scanner therefore correctly reports it unreachable. Four direct test modules become orphan findings with it, and three other gate modules consume it alongside live production subjects. This is placement debt, not dead policy.

### A dev quality-gate home preserves the single authority

The smallest coherent rehome moves the pure inventory and classification logic into a named `dev` quality-gate module, updates all seven test consumers to import it directly, removes the generated API stub through the docs generator, and removes the exact ratchet entry. Production format-version and migration behavior remains in its current owning tiers. Deletion, a runtime import, or an audit exemption would each lose or obscure the gate.

### The gate exposed a separate live declaration gap

The focused suite passed 31 tests and failed one real binding check: `SUPPORTED_PROFILE_SCHEMA_VERSION` is not classified by the persisted-format enrollment authority. Its production use is in domain projection models rather than a direct persistence serializer, so it needs an explicit owning classification grounded in its actual durability contract; it must not be silently allowlisted while rehoming the gate.

## Sources

- `src/cadrumo/core/compatibility_lifecycle.py`
- `src/cadrumo/core/tests/test_compatibility_lifecycle.py`
- `src/cadrumo/core/tests/test_compatibility_lifecycle_gate.py`
- `src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py`
- `src/cadrumo/core/tests/test_regenerable_persisted_format_floors.py`
- `src/cadrumo/domain/contribuyente/constants.py`
- `pyproject.toml`
