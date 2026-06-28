---
name: 2026-04-13-modelo-inventory-adr
description: Architecture decision for the authoritative AEAT modelo inventory + pydantic registry under aeat.domain.modelos (#108)
type: adr
tags:
  - "#adr"
  - "#modelo-inventory"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-modelo-inventory-research]]"
  - "[[2026-04-12-modelo-303-390-adr]]"
  - "[[2026-04-12-casilla-db-adr]]"
  - "[[2026-04-12-manual-practico-adr]]"
  - "[[2026-04-12-deadline-engine-adr]]"
  - "[[2026-04-12-normatives-adr]]"
  - "[[2026-04-12-trilingual-i18n-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
---

# modelo-inventory adr (#108)

Date: 2026-04-13
Branch: `feature/108-modelo-inventory-catalogue`
Issue: wgergely/aeat#108

## Status

Accepted (self-review, 2026-04-13). Executed end-to-end per the
vaultspec-system mandate; code review documented in the matching
exec summary.

## Context

`main` ships filing builders for exactly three modelos (130, 303,
390) plus a deadline engine, a casilla catalogue, and a normative
corpus that already references ten autonomo modelos by code. The
`src/aeat/domain/modelos/` subpackage exists as a stub
(`__all__: list[str] = []`) reserved by #6 for the authoritative
modelo inventory. Sibling branches that need a stable
`ModeloCode` import surface include #77 (workflow engine) and
#93 (filing complementaria); both block on a frozen enum and a
typed metadata record.

The companion research doc enumerates 20 modelos a Spanish
autonomo or small SL may owe across IRPF, IVA, retenciones,
informativas, censal, sociedades, and patrimonio categories,
plus 8 distinct taxpayer profiles. It also lists the legal
citations already reachable on disk under `corpus/normatives/`
and flags that those citations are curated Spanish summaries
rather than BOE-verbatim article bodies; the corpus has no
raw-article extraction pipeline yet.

This ADR commits the public shape of the registry, resolves
every open question the research doc raised, and locks the
boundary between `aeat.domain.modelos` and its consumers
(`aeat.domain.deadlines`, `aeat.domain.casillas`, `aeat.application.filing`, `aeat.entrypoints.cli`).

## Decision

### 1. Module layout

All new code lives under `src/aeat/domain/modelos/`. The package is
split into one private module per concern and one file per
modelo entry to keep code-review diffs tractable when citations
are revised:

- `__init__.py` for the public API and `__all__`
- `_codes.py` for the `ModeloCode` `StrEnum`
- `_categories.py` for `ModeloCategory`, `ModeloCadence`,
  `TaxpayerProfile`, `LegalCitationSource` `StrEnum`s
- `_citations.py` for the `LegalCitation` pydantic model
- `_applicability.py` for `ModeloApplicability`
- `_metadata.py` for `ModeloMetadata`
- `_registry.py` for `MODELO_REGISTRY` assembly, `get_modelo`,
  `modelos_for_profile`, `year_plan`, and the import-time
  integrity check
- `_entries/` package containing one file per modelo
  (`modelo_036.py`, `modelo_037.py`, `modelo_100.py`,
  `modelo_111.py`, `modelo_115.py`, `modelo_123.py`,
  `modelo_130.py`, `modelo_131.py`, `modelo_180.py`,
  `modelo_190.py`, `modelo_200.py`, `modelo_202.py`,
  `modelo_232.py`, `modelo_303.py`, `modelo_347.py`,
  `modelo_349.py`, `modelo_369.py`, `modelo_390.py`,
  `modelo_720.py`, `modelo_840.py`). Each file exposes a
  single module-level `ENTRY: ModeloMetadata`. `_registry.py`
  imports every entry and stitches them into the registry.
- `_cli.py` for the Typer commands wired into `aeat.entrypoints.cli`
- `_errors.py` for `ModeloRegistryError`, `UnknownModeloError`,
  `RegistryIntegrityError`
- Colocated test files (`test_codes.py`, `test_registry.py`,
  `test_applicability.py`, `test_citations.py`,
  `test_metadata.py`, `test_cli.py`,
  `test_casilla_cross_reference.py`)

A single monolithic `_registry_data.py` was rejected: 20
entries each carrying at least one quoted citation, an
applicability partition, a deadline rule reference, and a
gotcha tuple would push the file past the practical review
threshold and cause merge-conflict churn whenever a citation
is touched.

### 2. ModeloCode shape

`ModeloCode` is an `enum.StrEnum` declared in `_codes.py`. It
has exactly twenty members, one per modelo in section 1 of the
research doc:

`MODELO_036`, `MODELO_037`, `MODELO_100`, `MODELO_111`,
`MODELO_115`, `MODELO_123`, `MODELO_130`, `MODELO_131`,
`MODELO_180`, `MODELO_190`, `MODELO_200`, `MODELO_202`,
`MODELO_232`, `MODELO_303`, `MODELO_347`, `MODELO_349`,
`MODELO_369`, `MODELO_390`, `MODELO_720`, `MODELO_840`.

The value is the official AEAT three-digit code as a string
(`"036"`, `"100"`, `"840"`). `StrEnum` (not `IntEnum`) is
mandatory because 036 and 037 carry a leading zero and because
every existing consumer (`aeat.domain.deadlines`, `aeat.domain.casillas`,
`aeat.application.filing._builders`) already keys on three-character
strings. Member names use `MODELO_<code>` (not semantic names
like `IRPF_ANUAL`) so sibling branches get a stable,
mechanically predictable import surface and so that a new
modelo code never forces a rename.

### 3. Category and cadence taxonomies

`ModeloCategory` is a `StrEnum` with eight closed members:
`IRPF`, `IVA`, `RETENCIONES`, `INFORMATIVA`, `CENSAL`,
`SOCIEDADES`, `PATRIMONIO`, `OTROS`. Values are lowercase
(`"irpf"`, `"iva"`, ...) to match the issue text and the
research doc.

`ModeloCadence` is a `StrEnum` with four closed members:
`MONTHLY = "monthly"`, `QUARTERLY = "quarterly"`,
`ANNUAL = "annual"`, `AD_HOC = "ad_hoc"`. `AD_HOC` covers
censal filings (036/037) and event-triggered filings (720
first declaration). Monthly is reserved for SII-level
large-volume filers and is not used by any v1 entry, but the
member exists so the catalogue can express it without a
future enum widening.

### 4. TaxpayerProfile

`TaxpayerProfile` is a `StrEnum` declared in `_categories.py`
with exactly the eight profiles the research D2 matrix locks:

- `AUTONOMO_ED_SOLO = "autonomo_ed_solo"`
- `AUTONOMO_ED_CON_EMPLEADOS = "autonomo_ed_con_empleados"`
- `AUTONOMO_ED_CON_PROFESIONALES = "autonomo_ed_con_profesionales"`
- `AUTONOMO_ED_CON_ALQUILER = "autonomo_ed_con_alquiler"`
- `AUTONOMO_ED_UE = "autonomo_ed_ue"`
- `AUTONOMO_ED_BIENES_EXTRANJERO = "autonomo_ed_bienes_extranjero"`
- `AUTONOMO_EO = "autonomo_eo"`
- `SL = "sl"`

This is the catalogue profile space and the keying dimension
for `ModeloApplicability`. It deliberately does NOT model IVA
regime as a second dimension; IVA regime continues to live on
`aeat.domain.deadlines.AutonomoProfile.iva_regime` and the
applicability of regime-specific modelos (369 OSS, recargo de
equivalencia branches) is captured inside the per-profile
`trigger_notes_es`. A two-dimensional `(profile, iva_regime)`
keying was rejected as combinatorially expensive for v1 (it
would force every entry to enumerate eight profiles times
four regimes) and out of scope for #108.

### 5. LegalCitationSource and LegalCitation

`LegalCitationSource` is a `StrEnum` enumerating the citation
provenance: `LEY`, `REAL_DECRETO`, `ORDEN_MINISTERIAL`,
`REGLAMENTO`, `MANUAL_PRACTICO`, `BOE`. Every citation
declares which corpus it came from so the test suite can
enforce that at least one structural law / decree / order is
present per modelo.

`LegalCitation` is a pydantic v2 model with strict semantics:

- `model_config = ConfigDict(frozen=True, extra="forbid", strict=True)`
- `source: LegalCitationSource`
- `article: str` non-empty, e.g. `"Ley 35/2006, art. 99"`
- `url: HttpUrl | None`
- `quoted_text_es: str` with a `field_validator` that rejects
  empty or whitespace-only values; minimum length 1 character
  after `.strip()`
- `retrieval_date: date`
- `is_curated_summary: bool` set to `True` when
  `quoted_text_es` is the curated Spanish summary shipped
  under `corpus/normatives/` rather than a BOE-verbatim
  passage

The research doc flagged that the on-disk corpus only carries
curated summaries; this ADR explicitly accepts curated
summaries for v1 and surfaces the distinction at the type
level so a future BOE-extraction pipeline can flip the boolean
without changing the citation shape.

### 6. ModeloApplicability

`ModeloApplicability` is a pydantic v2 model:

- `model_config = ConfigDict(frozen=True, extra="forbid", strict=True)`
- `mandatory_profiles: frozenset[TaxpayerProfile]`
- `optional_profiles: frozenset[TaxpayerProfile]`
- `exempt_profiles: frozenset[TaxpayerProfile]`
- `trigger_notes_es: str` non-empty after strip

A `model_validator(mode="after")` enforces a strict partition:

- The three sets are pairwise disjoint; no profile may
  appear in two buckets.
- Their union equals `set(TaxpayerProfile)`; every profile is
  classified exactly once.

The matrix `n/a` cells map to `exempt_profiles`; the
`trigger_notes_es` field carries the human distinction (e.g.
"profile does not exist for this modelo" vs "profile is
explicitly exempt by Ley 37/1992 art. X"). This collapsing is
deliberate: the registry job is to answer "must this profile
file modelo X this year, yes or no" and any further nuance is
a human-readable annotation.

### 7. ModeloMetadata

`ModeloMetadata` is a pydantic v2 model:

- `model_config = ConfigDict(frozen=True, extra="forbid", strict=True, arbitrary_types_allowed=True)`
  the `arbitrary_types_allowed` is required so the field can
  hold a `DeadlineRule` imported from `aeat.domain.deadlines`
- `code: ModeloCode`
- `official_name_es: str` non-empty after strip
- `display_label: Translatable` must contain `es`, `en`, `hu`
  keys; validated by a `field_validator`
- `category: ModeloCategory`
- `cadence: ModeloCadence`
- `legal_basis: tuple[LegalCitation, ...]` with `min_length=1`
- `applicability: ModeloApplicability`
- `caps_into: ModeloCode | None`
- `related_modelos: tuple[ModeloCode, ...]`
- `submission_portal_hint: str` free-form string; locked as a
  string for v1 because `aeat.domain.portals` (#7) has not landed
- `deadline_rule: DeadlineRule` imported from
  `aeat.domain.deadlines`; for v1 entries that have no rule on
  `aeat.domain.deadlines.CALENDAR` yet, the field accepts a
  `DeadlineRule` synthesised from the calendar existing
  helpers (no new public surface on `aeat.domain.deadlines`)
- `known_gotchas: tuple[str, ...]`

Two integrity invariants are enforced:

- **Import-time:** `_registry.py` validates that every
  `caps_into` value resolves to another `ModeloCode` member
  that is itself present in `MODELO_REGISTRY`. Failure
  raises `RegistryIntegrityError` at import.
- **Test-time only:** any casilla codes referenced inside a
  `known_gotchas` string or in a future structured cross-
  reference field are validated against `aeat.domain.casillas`
  from `test_casilla_cross_reference.py`. This is
  intentionally NOT enforced at import to avoid pulling the
  casilla catalogue into every consumer of `aeat.domain.modelos`.

### 8. MODELO_REGISTRY

`MODELO_REGISTRY: Mapping[ModeloCode, ModeloMetadata]` is a
`types.MappingProxyType` over a module-level dict assembled
in `_registry.py`. The completeness invariant is:

- For every member `c` of `ModeloCode`, `MODELO_REGISTRY[c]`
  is defined and has `code == c`.
- `set(MODELO_REGISTRY.keys()) == set(ModeloCode)`; no
  orphans, no missing entries.

Both directions are tested in `test_registry.py` as a hard
unit test (`@pytest.mark.unit`) and the import-time check
raises `RegistryIntegrityError` if a `caps_into` value points
outside the registry. The registry contains exactly 20
entries in v1.

### 9. Legal citation policy

Every entry in `MODELO_REGISTRY` carries at least one
`LegalCitation` (`min_length=1` on `legal_basis`). For v1 the
policy is:

- A citation MAY have `is_curated_summary=True`. Curated
  summaries drawn from `corpus/normatives/` are acceptable
  and expected while the BOE-verbatim extraction pipeline
  is unbuilt.
- A citation `quoted_text_es` MUST be non-empty Spanish
  text; empty placeholders are rejected by the field
  validator.
- A follow-up issue (sketch in the research doc, opened by
  the PM after #108 lands) will backfill BOE-verbatim
  `quoted_text_es` and flip `is_curated_summary` to `False`
  once raw article extraction ships.

Code review of the registry entries must accept
`is_curated_summary=True` as the v1 norm and not block on
verbatim BOE text.

### 10. SL inclusion and deferral set

The registry ships ALL twenty modelos in v1, including the
SL/optional ones (200, 202, 232, 720, 369, 840). The
catalogue is the single source of truth and an incomplete
catalogue undermines the premise of #108. The SL profile
(`SL`) is a first-class `TaxpayerProfile` member.

Builder/submitter implementation priority is the SEPARATE
question; the research doc D5 follow-up sketches mark 200,
202, 232, 369, 720, 840 as low-priority because the current
user is `AUTONOMO_ED_SOLO`. Catalogue presence is required;
implementation order is not. This decoupling is the whole
point of the registry.

`Modelo 720` lands in the registry with mandatory profile
`{AUTONOMO_ED_BIENES_EXTRANJERO}`. `Modelo 369` lands with
empty `mandatory_profiles` and optional
`{AUTONOMO_ED_UE, SL}` plus a `trigger_notes_es` describing
the OSS opt-in.

### 11. CLI commands

A new `_cli.py` declares a Typer app `models_app` registered
into `aeat.entrypoints.cli` under the command group `aeat modelos`. Four
commands, all gain a `--json` flag that switches output from
a human-readable table to a stable JSON document derived
from `model_dump(mode="json")`:

- `aeat modelos list [--category CAT] [--cadence C] [--json]`
- `aeat modelos show <code> [--json]`
- `aeat modelos applicable-to <profile> [--json]`
- `aeat modelos year-plan <year> [--profile P] [--json]`

`year-plan` consumes `aeat.domain.deadlines.DeadlineEngine` to
expand the per-modelo `deadline_rule` for the requested year
and emits a calendar-style listing. `list` and `show` are
pure registry queries. `applicable-to` returns the union of
`mandatory_profiles` membership for the requested profile and
is the function exposed publicly as `modelos_for_profile`.

### 12. Public API discipline

Only `src/aeat/domain/modelos/__init__.py` re-exports symbols. Every
other file is underscore-prefixed. The locked `__all__` tuple
is:

```
__all__ = (
    "ModeloCode",
    "ModeloCategory",
    "ModeloCadence",
    "TaxpayerProfile",
    "LegalCitationSource",
    "LegalCitation",
    "ModeloApplicability",
    "ModeloMetadata",
    "MODELO_REGISTRY",
    "ModeloRegistryError",
    "UnknownModeloError",
    "RegistryIntegrityError",
    "get_modelo",
    "modelos_for_profile",
    "year_plan",
)
```

Every consumer (sibling branches included) MUST import from
`aeat.domain.modelos` only, never from `aeat.domain.modelos._registry` or
`aeat.domain.modelos._entries`. This is the same discipline the rest
of the project already enforces under the
base-module-structure ADR.

### 13. Errors

A new error hierarchy lives in `_errors.py`:

- `ModeloRegistryError(AeatError)` base
- `UnknownModeloError(ModeloRegistryError)` raised by
  `get_modelo(code)` when `code` is not a `ModeloCode`
  member
- `RegistryIntegrityError(ModeloRegistryError)` raised at
  import time by `_registry.py` when the completeness or
  `caps_into` invariants are violated

These are the ONLY error types `aeat.domain.modelos` raises. Every
other failure (citation validation, applicability partition,
metadata field validation) is a pydantic `ValidationError`
and surfaces at construction time inside
`_entries/modelo_*.py`, which means a malformed entry breaks
at module import; exactly the desired behaviour.

### 14. Logging

Every module under `aeat.domain.modelos` obtains its logger via
`aeat.core.logging.get_logger(__name__)`. The CLI logs query
parameters at INFO and full registry traversal at DEBUG; the
registry import path logs the count of loaded entries at
INFO exactly once.

### 15. Testing

`pytest` only, every test marked `@pytest.mark.unit`,
colocated under `src/aeat/domain/modelos/`:

- `test_codes.py` checks that `ModeloCode` has exactly 20
  members; values are three-character strings; member
  names match `MODELO_<value>`.
- `test_registry.py` checks the completeness invariant in
  both directions; `caps_into` resolves; no orphans;
  `RegistryIntegrityError` raised on synthetic violations.
- `test_applicability.py` checks the partition invariant;
  rejection of double-bucketed profiles; rejection of
  incomplete partitions.
- `test_citations.py` checks every modelo has at least one
  citation; every citation has non-empty `quoted_text_es`;
  the field validator rejects empty / whitespace; at least
  one citation per modelo has `source` in `{LEY,
  REAL_DECRETO, ORDEN_MINISTERIAL, REGLAMENTO}` (i.e. not
  only `MANUAL_PRACTICO`).
- `test_metadata.py` checks frozen, `extra="forbid"`
  enforcement; `display_label` trilingual key check.
- `test_cli.py` smoke-tests `list`, `show`, `applicable-to`,
  `year-plan` in both human and `--json` modes; `year-plan`
  exercised against the real `aeat.domain.deadlines.DeadlineEngine`.
- `test_casilla_cross_reference.py` lazy-imports
  `aeat.domain.casillas` and asserts that any casilla codes
  referenced by `known_gotchas` strings (or any future
  structured field) resolve in the casilla catalogue.

Zero mocks, patches, fakes, or stubs. Every test fixture is
a hand-rolled strict pydantic instance constructed inline.

### 16. No CI workflows

No `.github/workflows/` file is added. GitHub Actions is
permanently disabled on this repository per the
ci-github-actions ADR; `tests/test_release_config.py`
already guards the workflow directory.

### 17. Conventional commits

Every commit on this branch follows the conventional-commits
mandate with the `feat(models): ...` prefix. The final pull
request body carries `Closes #108` and references #6 as the
superseded issue.

## Alternatives considered

- **Frozen dataclass for `ModeloMetadata`.** Rejected; the
  project pydantic mandate is non-negotiable for any
  boundary-crossing record, and the registry is the
  highest-visibility boundary surface in `aeat.domain.modelos`.
- **`IntEnum` for `ModeloCode`.** Rejected; modelos 036 and
  037 carry a leading zero that vanishes under integer
  representation, every existing consumer keys on strings,
  and the AEAT portal URLs use the three-character form.
- **Single `_registry_data.py` file.** Rejected; twenty
  entries with quoted citations, partition specs, gotchas,
  and deadline rules push a single file past practical
  review size and cause needless merge-conflict churn.
- **Defer SL and optional modelos.** Rejected; the catalogue
  is the source of truth and shipping an incomplete
  inventory defeats #108.
- **Require BOE-verbatim citations in v1.** Rejected; the
  corpus has no BOE-extraction pipeline yet and would block
  #108 indefinitely. The `is_curated_summary` boolean
  documents the v1 compromise at the type level.
- **Two-dimensional applicability keyed on
  `(TaxpayerProfile, IVARegime)`.** Rejected; out of scope
  for v1 and combinatorially expensive; IVA regime stays on
  `aeat.domain.deadlines.AutonomoProfile`.
- **Import-time casilla cross-reference enforcement.**
  Rejected; would pull the casilla catalogue into every
  consumer of `aeat.domain.modelos`. Test-time enforcement is
  sufficient.
- **`AeatPortal` typed enum on `submission_portal`.**
  Rejected; `aeat.domain.portals` (#7) has not landed; a free-form
  string is the lowest-risk placeholder.

## Consequences

**Positive**

- Closes #6 (modelo enum scoping) and unblocks #77 (workflow
  engine) and #93 (filing complementaria) by giving them a
  stable `ModeloCode` import surface.
- The Transaction Data Pipeline T6 Handoff (#104) gains a
  concrete target: a single registry it can iterate to
  derive per-modelo casilla inputs.
- `aeat modelos year-plan` is the project first user-visible
  "what do I owe this year" answer surface and exercises the
  deadline engine end-to-end.
- One file per modelo entry keeps citation revisions
  reviewable and isolates merge conflicts when sibling work
  touches a single modelo.

**Negative / deferred**

- Every v1 citation is `is_curated_summary=True`. A
  follow-up issue must backfill BOE-verbatim text once the
  extraction pipeline lands.
- `submission_portal_hint` is a free-form string until #7
  ships `aeat.domain.portals`. Portal URL drift is a manual
  maintenance burden until then.
- `caps_into` casilla cross-reference integrity is enforced
  at test time, not import time. A consumer that imports
  `aeat.domain.modelos` without running the test suite cannot
  detect a broken casilla reference.
- IVA regime is not a registry-level dimension;
  regime-specific filings (369 OSS, recargo de equivalencia)
  carry their nuance inside `trigger_notes_es` rather than
  in the type system.

## Non-goals

- Building any new filing builder. The scope of #108 stops
  at the catalogue.
- Modifying any of the existing 130 / 303 / 390 builders or
  their schemas.
- Ingesting BOE article bodies or extending the normative
  corpus. That is the scope of #17.
- Touching any in-flight sibling branch (#77, #93, #95, #73,
  #85). The new `ModeloCode` is purely additive on `main`.
- Adding any GitHub Actions workflow.
- Modelling IVA regime as a second applicability dimension.
- Promoting `submission_portal_hint` to a typed `AeatPortal`
  reference (deferred to #7).
