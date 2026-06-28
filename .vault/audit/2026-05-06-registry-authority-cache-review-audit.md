---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-inventory-research]]'
---



# `calculation-truth-registry` Code Review

Reviewed commits: `0e5fae4d`, `434baf20`, `e126e0e5`, `177294ae`, and `6b1aa1bf`.

REGISTRY-AUTHORITY-001 | MEDIUM | Portal authority resolver drops registry links that use the public `Portal` enum path

`src/aeat/domain/portals/_registry.py` now routes modelo portal lookup through validated registry application links, but `_portal_consumer_binding()` only recognizes raw `portal_*` ids and enum strings prefixed by the private implementation module for `Portal`. Committed registry data also uses the public API path form, for example `aeat.domain.portals.Portal.PORTAL_M200_SOCIEDADES_ANUAL` in `registry/aeat/modelos/200.toml`. That valid registry-authored portal link is silently treated as non-dispatch metadata and ignored, so `portals_for_modelo("200")` returns no filing portal despite the registry binding one. The same pattern is present for other registry-authored portal links such as Modelo 190, 193, 202, and 349. This weakens the central authority cutover because caller-visible portal dispatch no longer faithfully reflects validated registry data, and the tests added in this slice only cover raw `portal_*` consumers.

Residual risks:

- The shared `registry_authority` fixture and `ValidatedRegistryAuthority.snapshot()` cache return the same snapshot instance for repeated requests. Current reviewed tests do not mutate the snapshots, but `RegistrySnapshot` exposes mapping fields as normal mutable dictionaries after Pydantic validation. A future test mutation could become order-dependent and mask real fresh-load behavior.
- The reviewed test hardening mostly replaces direct `load_registry_tree()` plus `build_snapshot()` calls with the authority facade. That improves central routing for selected snapshots, but it does not by itself exercise full `validate_registry()` cross-model closure in these tests.

REGISTRY-AUTHORITY-001-RESOLUTION | INFO | Public `Portal` enum path parsing added to registry portal dispatch

`_portal_consumer_binding()` now accepts both the private enum implementation path and the public `aeat.domain.portals.Portal.*` path used by committed registry TOML. `test_modelo_public_enum_portal_links_resolve_from_registry` covers the public-path bindings for Modelos 190, 193, 200, 202, and 349.
