---
tags:
  - '#adr'
  - '#portal-catalogue'
date: '2026-04-17'
modified: '2026-04-17'
related:
  - '[[2026-04-17-portal-catalogue-research]]'
  - '[[2026-04-13-modelo-inventory-adr]]'
  - '[[2026-04-13-modelo-inventory-research]]'
  - '[[2026-04-12-submission-engine-adr]]'
  - '[[2026-04-12-setup-wizard-adr]]'
  - '[[2026-04-12-cert-auth-adr]]'
  - '[[2026-04-12-trilingual-i18n-adr]]'
  - '[[2026-04-12-self-healing-sync-adr]]'
  - '[[2026-04-12-base-module-structure-adr]]'
---

# portal-catalogue adr: AEAT filing portal + URL registry (**status:** `accepted`)

Date: 2026-04-17
Branch: `feature/7-portal-catalogue`
Issue: wgergely/aeat#7

## Status

Accepted (self-review, 2026-04-17). Executed end-to-end per the
vaultspec-system mandate; code review documented in the matching exec
summary.

## Problem Statement

The automation needs to navigate dozens of AEAT Sede Electrónica URLs
(per-modelo filing procedures, authentication gateways, consultation
endpoints, payment flows, borradores). Today those URLs live as free-form
strings: a `submission_portal_hint: str` on `ModeloMetadata` (#108) and
scattered literals across setup-wizard copy and submission planning.

Scattered literals:

- preclude URL validity checks at import time,
- make self-healing sync (the out-of-band URL drift detector) impossible
  to target because there is no authoritative inventory,
- block #77 (workflow engine) and the submission engine from cross-
  referencing "which portal do I present this modelo on" by type,
- violate the pydantic mandate: no strict, schema-bound representation.

The portal-catalogue solves this by publishing a closed enum of Portal
members, each bound to a strict pydantic v2 `PortalMetadata` carrying
the URL, purpose, trilingual labels, auth methods, URL stability, and
optional `related_modelo` cross-reference.

## Considerations

- **Pydantic mandate**: every record must be a pydantic v2 model with
  `ConfigDict(strict=True, frozen=True, extra="forbid")`. No bare
  dataclasses, no TypedDicts for records. `PortalMetadata` is the only
  record type this ADR introduces.
- **Trilingual contract**: labels use `Translatable` from `aeat.core.i18n`;
  Spanish authoritative for AEAT terminology; English authoritative for
  internal/docs; Hungarian target user-facing.
- **#108 alignment**: same registry shape (one file per entry, import-
  time integrity check, frozen `MappingProxyType`, CLI mirror). Code
  reviewers already trust this pattern; diverging would be pure churn.
- **Subpackage boundary**: `aeat.domain.portals` imports `aeat.domain.modelos._codes.ModeloCode`
  (one-way, leaf module). `aeat.domain.modelos` in turn gains a typed
  `submission_portal: Portal | None` field on `ModeloMetadata` — this
  creates a bidirectional subpackage coupling but no module cycle because
  `_codes.py` imports nothing from `aeat.domain.portals`.
- **URL validation strictness**: pydantic's `HttpUrl` gives scheme +
  netloc parsing; custom `field_validator` asserts the host matches the
  declared `Subdomain` and that FILING portals' paths match the Sede
  procedure pattern.
- **URL stability**: the self-healing sync needs a hint to prioritise
  drift-prone URLs. A closed `UrlStability` enum (four tiers) is
  cheaper than runtime heuristics and testable in unit tests.
- **Retired portals**: Modelo 037 was suppressed 2025-02-03 (Orden
  HAC/1526/2024, BOE-A-2025-410). Retaining it with `active=False` and
  a `replaced_by` pointer preserves the registry closure over every
  `ModeloCode` member and enables historical lookup.
- **Cl@ve vs AuthMethod**: Cl@ve surfaces both gateway URLs AND
  authentication methods. The ADR models them orthogonally — Cl@ve
  gateways are first-class Portal members; Cl@ve is also one of seven
  `AuthMethod` values that any gated Portal carries.
- **Borrador vs presentation**: Renta Web borrador (M100) and Pre303
  (M303) are architecturally distinct from their presentation siblings.
  They become separate Portal members rather than a `modes` field on
  one Portal, mirroring the "one URL, one Portal" simplicity.
- **No new env vars**; no live-write surface touched. Portal navigation
  is read-only in v1; the submission engine and self-healing sync will
  consume the registry in their own PRs.

## Constraints

- Python 3.13, pydantic v2, uv, src layout; all code under
  `src/aeat/domain/portals/`.
- Unit tests only (`@pytest.mark.unit`) — no live AEAT calls. Tests
  cover URL validity, registry completeness, modelo cross-reference,
  subdomain/auth invariants, and CLI determinism.
- Google-style docstrings and type hints on every public signature.
- Must not reach `aeat.domain.deadlines`, `aeat.domain.casillas`, or the filing
  subpackage. Portal metadata is a leaf catalogue like `aeat.domain.modelos`
  (sans the deadline-engine coupling).
- Must respect the repo's conventional-commit mandate and pass the
  pre-commit hook (ruff, mypy, etc.).
- `submission_portal_hint: str` on `ModeloMetadata` is replaced with
  `submission_portal: Portal | None`. The string hints in the 20
  existing modelo entries are migrated to the corresponding `Portal`
  member in the same PR. The #108 registry closure test is extended to
  assert the cross-reference resolves.

## Implementation

### 1. Module layout

All new code lives under `src/aeat/domain/portals/`. Split by concern, one
file per portal entry — identical to `aeat.domain.modelos`:

- `__init__.py` — public API, `__all__`.
- `_codes.py` — `Portal` `StrEnum` listing every member.
- `_categories.py` — `PortalCategory`, `AuthMethod`, `UrlStability`,
  `Subdomain` `StrEnum`s.
- `_metadata.py` — `PortalMetadata` pydantic model.
- `_registry.py` — `PORTAL_REGISTRY` assembly, `get_portal`,
  `portals_for_modelo`, `portals_by_category`, and the import-time
  integrity check.
- `_entries/` — package with one file per portal
  (`portal_sede_root.py`, `portal_m303_iva_autoliquidacion.py`, ...).
  Each file exposes a module-level `ENTRY: PortalMetadata`.
- `_cli.py` — Typer subcommand wired into `aeat.entrypoints.cli`.
- `_errors.py` — `PortalRegistryError`, `UnknownPortalError`,
  `PortalIntegrityError`.
- Colocated tests: `test_codes.py`, `test_categories.py`,
  `test_metadata.py`, `test_registry.py`,
  `test_modelo_cross_reference.py`, `test_cli.py`, `test_smoke.py`.

A monolithic `_registry_data.py` is rejected for the same reason as
#108: 36+ entries each carrying a trilingual label tuple, auth methods,
and stability notes would balloon past the reviewable threshold.

### 2. Portal shape

`Portal` is a `StrEnum` in `_codes.py`. Members use the
`PORTAL_<CATEGORY>_<SHORT>` convention from the research doc. The
value is the member name lowercased (`portal_sede_root`,
`portal_m303_iva_autoliquidacion`, ...) — stable, machine-predictable,
and safe to serialise to JSON/CLI output without further mapping.

The complete closed membership is 41 (fixed, enumerated in the research
doc §6): 8 AUTH + 20 FILING (19 active + 1 retired M037) + 2 BORRADOR +
4 CONSULTATION + 5 PAYMENT + 2 CALENDAR_REFERENCE. Adding a future
Portal is a first-class enum widening and requires a new ADR or explicit
amendment.

### 3. PortalCategory, AuthMethod, UrlStability, Subdomain

All four are `StrEnum`s in `_categories.py`:

- `PortalCategory` has seven members: `AUTH`, `FILING`, `CENSUS`,
  `CONSULTATION`, `BORRADOR`, `PAYMENT`, `CALENDAR_REFERENCE`. Values
  are lowercase (`"auth"`, `"filing"`, ...).
- `AuthMethod` has seven members: `ANONYMOUS`, `CLAVE_PIN`,
  `CLAVE_PERMANENTE`, `CLAVE_MOVIL`, `CERTIFICATE`, `DNIE`,
  `REFERENCE_NUMBER`. `ANONYMOUS` means no auth required. A Portal
  declaring `ANONYMOUS` must declare no other method.
- `UrlStability` has four members: `STABLE_PROTOCOL_GRADE`,
  `STABLE_WITHIN_CAMPAIGN`, `VOLATILE_APP_PATH`, `RETIRED`. Drives
  self-healing sync priority when it lands (#83).
- `Subdomain` has seven members naming the exact hosts:
  `SEDE = "sede.agenciatributaria.gob.es"`,
  `WWW1 = "www1.agenciatributaria.gob.es"`,
  `WWW2 = "www2.agenciatributaria.gob.es"`,
  `WWW3 = "www3.agenciatributaria.gob.es"`,
  `AGENCIATRIBUTARIA_GOB = "agenciatributaria.gob.es"`,
  `AGENCIATRIBUTARIA_ES = "www.agenciatributaria.es"`,
  `CLAVE_GOB = "clave.gob.es"`.

### 4. PortalMetadata

`PortalMetadata` is a pydantic v2 model:

- `model_config = ConfigDict(strict=True, frozen=True, extra="forbid")`
- `portal: Portal` — self-reference enum member this entry describes.
- `url: HttpUrl` — canonical URL. Must be `https://`.
- `subdomain: Subdomain` — declared host.
- `category: PortalCategory`.
- `auth_methods: frozenset[AuthMethod]` — non-empty.
- `url_stability: UrlStability`.
- `related_modelo: ModeloCode | None` — foreign key to #108. Required
  non-`None` iff `category in {FILING, CENSUS, BORRADOR}`; forbidden
  (must be `None`) for every other category.
- `label: Translatable` — trilingual label with non-empty `es`, `en`,
  `hu` keys.
- `purpose_es: str` — one-sentence Spanish purpose, non-empty after
  strip.
- `active: bool = True` — `False` marks retired portals.
- `replaced_by: Portal | None = None` — set only when `active is False`.
- `notes_es: tuple[str, ...] = ()` — free-form Spanish short-form
  gotcha strings.

Validators (all `field_validator` or `model_validator` with
`mode="after"`):

- `purpose_es` non-blank after strip.
- `label` trilingual check (same shape as `ModeloMetadata`).
- `auth_methods` non-empty; `ANONYMOUS` is exclusive (cannot appear
  alongside any other method).
- URL scheme must be `https`.
- URL host must equal `subdomain.value`.
- If `category in {FILING, CENSUS}` and `active is True`, the URL path
  must match `^/Sede/procedimientoini/G[A-Z0-9]{3}\.shtml$`. (Retired
  entries skip the path check because their URL is vestigial.)
- If `active is False`, `replaced_by` MAY be `None`; when
  `replaced_by is None`, `notes_es` MUST be non-empty with a
  discontinuation rationale. Enforced by a `model_validator(mode="after")`.
- If `category in {FILING, CENSUS, BORRADOR}`, `related_modelo` must
  not be `None`; otherwise `related_modelo` must be `None`.

### 5. PORTAL_REGISTRY

`PORTAL_REGISTRY: Mapping[Portal, PortalMetadata]` is a
`MappingProxyType` assembled in `_registry.py`. Invariants enforced at
import time (every failure raises `PortalIntegrityError` and aborts
package import):

- `set(PORTAL_REGISTRY.keys()) == set(Portal)` — closure over every
  member; no missing entries, no stray keys.
- No duplicate entries (`Portal` → `PortalMetadata`) — loader rejects
  re-registration.
- Every `replaced_by` points at a `Portal` that is itself in the
  registry.
- Every `FILING` / `CENSUS` / `BORRADOR` entry's `related_modelo`
  resolves to a `ModeloCode` member (`ModeloCode(related_modelo.value)`
  round-trips).
- For every `ModeloCode` member, at least one `FILING` or `CENSUS`
  portal declares it as `related_modelo`, **except** `ModeloCode.MODELO_037`
  whose CENSUS portal has `active=False`. The registry test asserts this
  carve-out explicitly so a future activation does not silently skip the
  check.

### 6. Helpers

Public functions on `aeat.domain.portals`:

- `get_portal(portal: Portal | str) -> PortalMetadata` — lookup by
  member or value; raises `UnknownPortalError` on miss or bad string.
- `portals_for_modelo(code: ModeloCode | str) -> tuple[PortalMetadata, ...]`
  — return every `FILING` or `BORRADOR` portal whose `related_modelo`
  matches. Sorted by `Portal` value for determinism. Raises
  `UnknownModeloError` (re-exported from `aeat.domain.modelos`) on unknown code.
- `portals_by_category(category: PortalCategory) -> tuple[PortalMetadata, ...]`
  — sorted by `Portal` value.

### 7. CLI

Typer subcommand `aeat portals` in `_cli.py`, wired into `aeat.entrypoints.cli`:

- `aeat portals list [--category CAT] [--modelo CODE] [--active-only]` —
  JSON list of portal summaries.
- `aeat portals show <member>` — JSON detail for one portal.
- `aeat portals for-modelo <code>` — JSON list for a modelo.

Output is deterministic JSON, sorted by `Portal` value. `test_cli.py`
snapshots the JSON shape.

### 8. ModeloMetadata migration

In the same PR, `ModeloMetadata.submission_portal_hint: str` becomes
`submission_portal: Portal | None`. The 20 existing `_entries/modelo_*.py`
files are updated to reference the Portal member instead of the
free-form string:

- `MODELO_036.submission_portal = Portal.PORTAL_M036_CENSAL`
- `MODELO_037.submission_portal = Portal.PORTAL_M037_CENSAL_SIMPLIFICADA`
  (retired portal; callers must check `active` before dispatching).
- ... through all 20. Every modelo maps to exactly one `Portal` member;
  there is no `None` in v1.

The `_registry.py` integrity check on `aeat.domain.modelos` gains a new
invariant: `submission_portal` must resolve in `PORTAL_REGISTRY` and
the portal's `related_modelo` must equal the modelo's `code`. This
closes the cross-reference round-trip at import time. The field type
is `Portal | None` (not `Portal`) to keep the schema open for future
modelos that may not have a dedicated portal, but every v1 entry is
non-`None`.

A new test `aeat/domain/modelos/test_portal_cross_reference.py` asserts the
round-trip for every modelo.

### 9. Errors

All subclass `AeatError`:

- `PortalRegistryError` — base for portal-registry problems.
- `UnknownPortalError(PortalRegistryError)` — raised by `get_portal`.
- `PortalIntegrityError(PortalRegistryError)` — raised during
  registry assembly.

### 10. Logging

`aeat.core.logging.get_logger(__name__)` at module scope in `_registry.py`.
A single `info` line on successful import recording the count. No
`print`. No other log calls in v1.

## Rationale

- **One file per entry**: proven by #108 to minimise merge churn and
  keep citation / URL revisions reviewable.
- **Separate Portal members for borrador vs presentation**: mirrors the
  scraper's mental model ("navigate to URL A vs URL B") and sidesteps
  the need for a `modes: frozenset` field that would complicate the
  `related_modelo` cross-reference ("which URL did we mean?").
- **Cl@ve + DNIe as Portal entries AND AuthMethod values**: Cl@ve's
  gateway URLs are real endpoints the scraper hits; modelling them
  only as `AuthMethod` values would lose that fact. Keeping both
  representations orthogonal costs nothing and matches the research
  taxonomy.
- **Import-time integrity check**: #108 already normalised this; any
  divergence would surprise maintainers.
- **Retained modelo 037**: deleting it would force every downstream
  closure test to special-case "skip if `code == 037`" at the call
  site; keeping it with `active=False` localises the exception to the
  portal entry itself.
- **`HttpUrl` + subdomain + G-code regex**: three lightweight checks
  that catch 95 % of copy-paste mistakes at import time. No external
  URL fetching — the pytest suite stays fully offline.
- **No SubmissionEngine integration in #7**: the submission engine
  (#77 / #129) will consume `Portal` in its own PR. Shipping the
  consumer in the same branch would conflate surface with adoption.

## Consequences

### Positive

- Sibling branches get a typed `Portal` import surface; #77 (workflow
  engine), #83 (self-healing sync), and #129 (submission driver) can
  unblock on this landing.
- The #108 `submission_portal_hint: str` is replaced with a typed
  reference — the pydantic mandate is fully satisfied across both
  catalogues.
- Unit-test-enforced URL well-formedness catches typos before runtime.
- `UrlStability` lets the self-healing sync focus probes on `VOLATILE_APP_PATH`
  entries, skipping `STABLE_PROTOCOL_GRADE` URLs.
- CLI mirror keeps the catalogue debuggable from the shell without
  spinning up Python.

### Negative / open follow-ups

- `aeat.domain.modelos` now imports `aeat.domain.portals.Portal`, introducing a
  bidirectional subpackage coupling. The module-level import graph
  stays acyclic (`aeat.domain.portals._codes` and `aeat.domain.modelos._codes` are
  both leaves) but maintainers must not introduce a direct import
  from `aeat.domain.portals._metadata` into `aeat.domain.modelos._codes` or vice versa.
- The submission engine must adopt `Portal` in a follow-up PR; until
  then, `submission_portal` exists but is not driving navigation.
- Retired portals remain in the enum forever once recorded. Removing a
  member is a breaking change; the registry grows monotonically.
- Modelo 037's filing portal is `active=False`. The `portals_for_modelo("037")`
  helper returns exactly one inactive portal; callers that dispatch
  filing actions must check `active` before acting.
