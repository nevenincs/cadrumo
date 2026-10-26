# taxpayer and family domain records

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-139` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope

This implementation chunk covers 17 files in `src/cadrumo/domain/contribuyente`, totaling 4,226 manifest-counted lines, 206,379 bytes, and 46,089 measured `o200k_base` tokens. The assigned modules are the package initializer, CCAA and entity-type tokens, profile schema/version and error types, descendant fact serialization and parsing, descendant legal-behavior mixins and record, family resolution and aggregation, monthly nursery-spend grammar, and the inventory package initializer. Each file was read in bounded sections through its end. Inspection was static: no application imports, execution, mutation of `src/`, or runtime validation occurred. The inventory initializer describes its sibling package but contains no ledger engine itself.

## Product capabilities

The main capability is a typed personal/family fact layer for Spanish RENTA calculations. An operator can represent descendants with birth and death dates, legal relationship, adoption or qualifying foster-care dates, disability band, household and income facts, custody/proration signals, mother’s qualifying work months, optional identity number, and nursery costs. These records then answer eligibility questions and aggregate minimums, maternity relief, childcare increments, and Madrid birth/adoption deductions. The aggregate profile distinguishes Modelo 100 form rows from richer calculation records and exposes counts and totals for calculation-time bindings. The record and profile declare themselves strict and frozen, while legal rates and thresholds are supplied by governed-fact callers rather than embedded as current amounts DescendantRecordBase and fields (`src/cadrumo/domain/contribuyente/descendant_record.py`), RentaFamilyProfile (`src/cadrumo/domain/contribuyente/family_profile.py`).

The legal behavior modeled here is materially more detailed than a simple age filter. Ordinary descendant eligibility combines cohabitation or an explicit economic-dependency route, age or disability, a registry-resolved rentas ceiling, and the own-return exclusion. The dependency route is disabled by default at the record boundary and is enabled by the family profile only when its filer-level food-support declaration does not suppress it. Because the profile cannot attribute payments to an individual child, any positive declared amount suppresses assimilation for every child; the model documents this as a visible conservative narrowing ordinary and non-income gates (`src/cadrumo/domain/contribuyente/descendant_record.py`), dependency availability (`src/cadrumo/domain/contribuyente/family_profile.py`).

The calculation layer also distinguishes the ordinary minimum, the under-three increase, and the Madrid autonomous deduction. Deceased descendants are excluded from prior-year eligibility, age is evaluated at death when death occurs in the filing year, and death in the year substitutes a flat tranche while a death before devengo vacates rank for survivors. Adoption and qualifying placement anchors are kept separate from the Madrid birth/adoption anchor. Art. 81 maternity eligibility uses the set of mother-qualified months intersected with a date-bounded child window; nursery proration intersects that set with declared nursery months when available. Turning-three periods, the second-cycle cutoff, and the post-birth enrollment increment each have separate predicates death and age behavior (`src/cadrumo/domain/contribuyente/descendant_record.py`), maternity month selection (`src/cadrumo/domain/contribuyente/descendant_maternity.py`), nursery simultaneity and spend (`src/cadrumo/domain/contribuyente/descendant_guarderia.py`), state minimum aggregation (`src/cadrumo/domain/contribuyente/family_profile.py`).

The chunk includes a pure maternity-deduction helper. It resolves a governed mapping that names the monthly amount, annual cap, post-birth increment and effective year, then resolves each named integer at the filing-period coordinate. It computes a per-child amount and cap, adding the declared increment only when the filing year and child identifier qualify formula resolution and computation (`src/cadrumo/domain/contribuyente/deduccion_maternidad.py`) computation entrypoint (`src/cadrumo/domain/contribuyente/deduccion_maternidad.py`). The Madrid mixin supplies an eligibility window and per-descendant proration share, while this chunk’s CCAA type projects choices and aliases from a dated catalogue. EntityType and LegalEntityForm similarly defer their vocabularies to registry functions CCAA projection (`src/cadrumo/domain/contribuyente/ccaa.py`), entity-type projection (`src/cadrumo/domain/contribuyente/entity_type.py`).

## How it works

`DescendantInfo` combines record, maternity, nursery, and Madrid mixins over a strict frozen Pydantic record. Validators normalize ISO dates, reject incoherent or future entry events, reject duplicate/noncanonical month sets, and enforce that a post-birth enrollment month agrees with the first declared work month. An adoption inscription can resolve an unstated relationship as adoption; an ambiguous foster-care date cannot. Entitlement dates are checked against relationship tokens from the registry, and behavior methods consume typed family facts through `FamilyFactResolutionContext`, which fixes the date axis and rejects undeclared fact IDs or wrong result types record validators and relationship coherence (`src/cadrumo/domain/contribuyente/descendant_record.py`), typed resolution context (`src/cadrumo/domain/contribuyente/family_fact_context.py`).

The persistence adapter writes each descendant as canonical string-valued indexed paths and separately writes a row count. Optional values are omitted; dates use ISO form; work months and nursery-month maps use canonical serializers. Reload groups recognized paths by index, sorts rows, parses values, and reconstructs `DescendantInfo`. The CLI parser accepts one comma-separated `--descendiente` record with a closed case-insensitive key set; it uses the same typed model, month parser, date parser, registry relationship catalogue, and identity authority as other paths. Unknown keys and malformed values are intended to fail rather than vanish fact projection (`src/cadrumo/domain/contribuyente/descendant_facts.py`), fact hydration (`src/cadrumo/domain/contribuyente/descendant_facts.py`), closed flag parser (`src/cadrumo/domain/contribuyente/descendant_facts.py`), flag entrypoint (`src/cadrumo/domain/contribuyente/descendant_facts.py`).

The monthly nursery grammar accepts individual months or inclusive ranges with whole-euro amounts, expands ranges, rejects duplicates and reversed ranges, and serializes a month-sorted canonical map. Annual total and monthly detail are mutually exclusive. A turning-three child with only an annual amount contributes no spend because the period cannot be apportioned; with monthly details, the second-cycle start month bounds eligible months. Advisories expose those missing inputs through predicates, and the family aggregator applies a per-child prorated cap before summing monthly grammar (`src/cadrumo/domain/contribuyente/guarderia_mensual.py`), turning-three window and advisories (`src/cadrumo/domain/contribuyente/descendant_guarderia.py`).

## Knowledge and data

Legal vocabulary and numerical facts are not authoritative in these domain records. CCAA membership and aliases come from a dated CCAA catalogue; descendant relationships, disability grades, age limits, proration factors, Madrid windows, maternity operands, and filing thresholds are resolved from the governed-fact authority. The family context explicitly maps known fact identifiers to a date axis, while the maternity helper follows a mapping fact to its declared operand IDs. This reduces hard-coded rates and stale local lists, but correctness and freshness depend on upstream registry declarations and their provenance, which this chunk does not validate against outside sources.

The primary inputs are operator-entered personal and financial facts, including children’s birth/death dates, income, tax identifiers, employment months, and childcare spending. They become indexed profile facts through the adapter. NIF/NIE/CIF checksum validation is present at the CLI parser through the runtime tax-ID format; the Pydantic record itself checks only trimmed uppercase form and nine-character length. This means the identity guarantee depends on which construction door is used CLI checksum validation (`src/cadrumo/domain/contribuyente/descendant_facts.py`), record shape validation (`src/cadrumo/domain/contribuyente/descendant_record.py`). No storage encryption, retention policy, or redaction layer is implemented in this chunk.

## Security and safety

The strongest local controls are closed input vocabularies, strict model validation, immutable record instances, bounded canonical parsing, governed fact resolution, and refusal of malformed values on CLI input. Identity parse refusals do not echo the tax identifier. Profile errors are typed and translated through a shared hierarchy. These controls constrain shape and calculation inputs; they do not establish who may edit a profile or protect persisted personal data. Authorization, filesystem access, network boundaries, and persistence permissions are outside these domain modules.

Two local trust-boundary weaknesses merit follow-up. First, persisted `convivencia` and `custodia_compartida` values are interpreted with a permissive “anything other than false/0 means true” rule, even though the CLI path correctly rejects unreadable booleans. A corrupted or noncanonical stored value can therefore turn cohabitation or shared custody on, affecting eligibility or halving/ranking amounts; the persisted reader should be checked against the upstream fact-store guarantees stored booleans (`src/cadrumo/domain/contribuyente/descendant_facts.py`), strict CLI boolean reader (`src/cadrumo/domain/contribuyente/descendant_facts.py`). Second, hydration ignores indexed rows without a truthy `birth_date` and does not compare reconstructed rows to the stored count. An incomplete row can disappear without a refusal, potentially suppressing a claimed entitlement; whether upstream schema validation makes that unreachable is unresolved hydration row filter (`src/cadrumo/domain/contribuyente/descendant_facts.py`).

CCAA construction validates ordinary inputs through the catalogue, but `from_registry` is a publicly named unchecked constructor whose docstring says it is private to the projection module. It trusts callers to provide a canonical token, so the type’s fail-closed property depends on that convention and on call-site discipline CCAA constructors (`src/cadrumo/domain/contribuyente/ccaa.py`). No irreversible operation or external side effect exists in the analyzed code.

## Implementation assessment

The design’s main strength is that it carries facts at the precision needed by distinct legal rules: date versus tax-period windows, relationship categories, actual month sets, death timing, and explicit-versus-unset answers. Registry indirection is used for vocabularies and thresholds, and canonical serialization gives stable round trips. The parsers give instructive refusals and avoid guessing ambiguous values. These are local implementation properties, not confirmation that the legal interpretation or the registry values are correct.

The persisted-boolean permissiveness and dropped incomplete rows are concrete robustness concerns in this chunk. The NIF checksum difference is an interface consistency question: direct model construction accepts a shape-valid but checksum-invalid identifier, while the CLI path verifies it. The `CCAA.from_registry` bypass is a conditional API risk rather than proof of invalid values entering production. The death/order, nursery, foster-care, and income-threshold paths have many separate branches; no tests are included in this assigned chunk, so static inspection cannot certify their arithmetic or behavior. No runtime execution was performed per protocol.

## Dependencies and follow-up

Synthesis should connect these records to the profile-fact read/write boundary and calculate-time derived-fact injector, which determine whether malformed or incomplete facts can reach hydration and whether advisories are surfaced. It should also trace the governed-fact registry and binding consumers to verify the age, month, and money declarations used by the domain. The CCAA catalogue and identity-format registry are runtime dependencies, while `EntityType` and `LegalEntityForm` delegate their dated values to the registry. The inventory initializer is only a package-level description; substantive inventory behavior lies outside this chunk.

## Complete assigned-file coverage

- contribuyente/__init__.py (`src/cadrumo/domain/contribuyente/__init__.py`)
- ccaa.py (`src/cadrumo/domain/contribuyente/ccaa.py`)
- constants.py (`src/cadrumo/domain/contribuyente/constants.py`)
- deduccion_maternidad.py (`src/cadrumo/domain/contribuyente/deduccion_maternidad.py`)
- descendant.py (`src/cadrumo/domain/contribuyente/descendant.py`)
- descendant_facts.py (`src/cadrumo/domain/contribuyente/descendant_facts.py`)
- descendant_guarderia.py (`src/cadrumo/domain/contribuyente/descendant_guarderia.py`)
- descendant_madrid.py (`src/cadrumo/domain/contribuyente/descendant_madrid.py`)
- descendant_maternity.py (`src/cadrumo/domain/contribuyente/descendant_maternity.py`)
- descendant_record.py (`src/cadrumo/domain/contribuyente/descendant_record.py`)
- entity_type.py (`src/cadrumo/domain/contribuyente/entity_type.py`)
- errors.py (`src/cadrumo/domain/contribuyente/errors.py`)
- family_fact_context.py (`src/cadrumo/domain/contribuyente/family_fact_context.py`)
- family_profile.py (`src/cadrumo/domain/contribuyente/family_profile.py`)
- family_types.py (`src/cadrumo/domain/contribuyente/family_types.py`)
- guarderia_mensual.py (`src/cadrumo/domain/contribuyente/guarderia_mensual.py`)
- inventory/__init__.py (`src/cadrumo/domain/contribuyente/inventory/__init__.py`)
<!-- /preserved:article -->
