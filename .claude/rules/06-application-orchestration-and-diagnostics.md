---
name: 06-application-orchestration-and-diagnostics
trigger: always_on
---

# Application orchestration and diagnostics

Evidence bundles still require recipient review for authenticity and legal relevance.

Application orchestration covers profile-bound state, health, reset, local model provisioning, flows, inventory and asset operations, offline retrieval, evidence bundles, and supervised exports. The application generally distinguishes availability, stale facts, proposed calculations, and attempted external effects. Workbench generation joins secure readers only after source revision checks; Modelo readiness preserves distinct profile, registry, binding, and ledger axes. AEAT Sync's local projection reports remote data as never captured rather than reading the network. [State projection](../../src/cadrumo/application/state_projection.py#L543) [Workbench assembly](../../src/cadrumo/application/workbench_generation.py#L502) [Local AEAT Sync](../../src/cadrumo/application/aeat_sync/workspace_reader.py#L432).

Enforced controls include exact-profile operation binding, typed health and result projections, confirmation and retention checks for journaled all-profile reset, memory admission for model load, stale-answer review in interactive flows, revision-guarded inventory and amortization writes, and digest verification before evidence-bundle export. Remote Google workbook export records an uncertain effect before mutation; the code here cannot confirm remote delivery. Offline exact citations use pinned registry evidence, while phrase search uses a content-keyed local index of extracted HTML. [Reset recovery](../../src/cadrumo/application/config_reset.py#L516) [Model admission](../../src/cadrumo/application/provisioning_runtime.py#L256) [Bundle checks](../../src/cadrumo/application/evidence/service.py#L247).

Scoped follow-ups: failed secure-object probing can look like an empty OK integrity row; deadline errors can look like no pending obligations; a readiness probe may cold-load a model outside normal admission; legal-hold snapshots have no established post-registration refresh; spreadsheet text lacks explicit formula neutralization. These are distinct local behaviors and conditional integration risks, not verified production failures. [Integrity probe](../../src/cadrumo/application/diagnostics.py#L262) [Readiness probe](../../src/cadrumo/application/provisioning_runtime.py#L1031) [Legal-hold producer](../../src/cadrumo/application/evidence/profile_legal_hold.py#L202).
