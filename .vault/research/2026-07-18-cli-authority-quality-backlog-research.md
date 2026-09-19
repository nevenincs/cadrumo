---
tags:
  - '#research'
  - '#cli-authority-quality-backlog'
date: '2026-07-18'
modified: '2026-07-18'
body_hash: 'sha256:fd7a788e4f809d4929743bda4e48f6fa734e4e025cb3df34ecfb94649985591d'
related: []
---

# `cli-authority-quality-backlog` research: `S27 clave-diagnostics namespace authority grounding`

Read-only grounding for plan step `P03.S27` ("resolve the split namespace
authority for clave-diagnostics values"), produced to make the operator's
adjudication fast without pre-empting it or touching the active auth-cert door.
All sites confirmed at HEAD by semantic search plus targeted `rg`.

## Findings

### 1. The duplication graph (four authority tiers)

The literal `"cadrumo.outbound.aeat.auth.clave_movil.diagnostics"` (and its
`.clave_permanente.` sibling), plus `SensitivityClass.SESSION` and
`schema_version=1`, are declared or consumed at four tiers:

- **A — core:** `core/external_constants.py:640` declares
  `CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE: Final[str]`. Re-exported through
  `adapters/outbound/aeat/auth/__init__.py` and `_clave_movil.py`. No
  `CLAVE_PERMANENTE` equivalent exists in core (asymmetric).
- **B — storage registry:** `adapters/persistence/storage/_namespace_registry.py:672,682`
  declare `CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE` / `CLAVE_PERMANENTE_DIAGNOSTICS_NAMESPACE`
  as `SecureObjectNamespaceDefinition`s. Their `.namespace` strings are raw
  literals byte-duplicating A; each also carries the canonical
  `sensitivity=SensitivityClass.SESSION` and `schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1`.
- **C — clave-movil support:** `adapters/outbound/aeat/auth/_clave_movil_support.py`
  imports A from core and re-declares a module-local alias, consumed by
  `_clave_movil_page_flow.py`.
- **D — clave-permanente support:** `adapters/outbound/aeat/auth/_clave_permanente_support.py:49`
  declares a raw literal with no core symbol and no registry sourcing (the
  fully-orphaned tier).
- **E — sensitivity/schema duplication:** `_clave_movil_page_flow.py:460-461`
  passes raw `SessitivityClass.SESSION` / `schema_version=1` to `.save(...)`,
  duplicating B's `.sensitivity` / `.schema_version`.

The application-layer sibling `application/auth/_diagnostics.py` **already sources
from the registry def** (`.namespace` / `.sensitivity` / `.schema_version`),
landed in W03.P05.S23 — so the adapters/outbound consumers are the only laggards.

### 2. The layering question — resolved, no violation

Making B (the storage registry) the authority means
`adapters/outbound/aeat/auth/_clave_*` imports the namespace def from
`adapters/persistence/storage/`. This is an **intra-layer edge** (both are
`cadrumo.adapters`). The `.importlinter` layered contract governs only between
layers (entrypoints > adapters > application > domain > core); no contract
forbids `adapters.outbound -> adapters.persistence`. No allowlist entry needed.

Abundant sanctioned precedent for the identical edge: `adapters/outbound/llm/_usage.py`,
`_cache.py`, `_run_telemetry.py`; `adapters/outbound/aeat/auth/_session_store.py`;
`adapters/outbound/aeat/sede/_observation_store.py`; and `_clave_movil_page_flow.py`
already eagerly imports `secure_object_repository_for_active_bucket` from
`persistence.storage` — the very file carrying the raw sensitivity/schema
literals already holds this edge, so adding the namespace-def import there is zero
new coupling. No circular-import risk (storage does not import auth).

### 3. What the rules imply

A secure-storage namespace identifier is storage-structural metadata, not an AEAT
regulatory value, so `aeat-schema-central-config` points at the storage registry
authority, not the modelo registry TOML and not the regulatory
`external_constants` surface. The `binding-source-kind-single-taxonomy` "one typed
home + derived collections" pattern is already embodied by the
`SecureObjectNamespaceDefinition` (namespace + sensitivity + schema_version +
custody as one record); splitting the namespace string into core while
sensitivity/schema live in the registry def is the anti-pattern.
`service-imports-via-top-level-reexports` is satisfied by importing the def from
the storage package facade. `no-legacy-compatibility` requires deleting the core
symbol, not aliasing it. The phase already made this decision for every other
consumer in S06-S08 (task #68 bound profile/calc/aggregation/filed-observation
repos to registry definitions); S27's clave case is the last holdout.

### 4. Recommendation (input for the operator's ruling)

**Option 1 (recommended): the storage registry `_namespace_registry.py` is the
single authority.** The `SecureObjectNamespaceDefinition` is canonical for
namespace, sensitivity, and schema_version. The clave-movil and clave-permanente
support modules import the def from the storage package facade and expose
`.namespace`; `_clave_movil_page_flow.py` reads `.sensitivity` / `.schema_version`
off the def instead of raw literals; the core `CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE`
symbol is deleted. Matches the LLM/session/observation-store precedent, matches the
app-layer `_diagnostics.py` consumer, unifies namespace + sensitivity + schema in
one typed record (kills the E duplication too), and introduces no layer violation.

Option 2 (core is authority, registry sources from it) inverts the natural
ownership of storage-structural metadata, still leaves sensitivity/schema split,
and contradicts the S06-S08 direction — not recommended. Option 3 (new core
StrEnum) is over-engineered for a free-form dotted string and still would not home
sensitivity/schema — not recommended.

### 5. Execution risk and follow-up

The eventual fix touches `core/external_constants.py` (delete symbol) and the
auth-zone consumers (`_clave_movil_support.py`, `_clave_movil_page_flow.py`,
`_clave_movil.py`, `_clave_permanente_support.py`, `auth/__init__.py`) plus tests.
Those auth-zone files are the operator's active P04 door surface / S08 quiescence
zone, so S27 execution (and dependent S09) must wait for the door to settle and
land as one atomic explicit-path commit sweeping the core delete plus all auth
consumers and tests together.

Separate follow-up flag: the clave-permanente `DIAGNOSTIC_NAMESPACE` (tier D)
appears to have no `.save(...)` consumer — either a dormant declaration or a
producer never wired. Worth a check independent of the S27 dedup decision.
