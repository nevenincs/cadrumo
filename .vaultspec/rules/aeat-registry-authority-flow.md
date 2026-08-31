# AEAT registry authority flow

## Single authority path

- Registry source data is compiled, validated, and published through `ValidatedRegistryAuthority` and the established loader. Filing, calculation, pull, support reporting, and development diagnostics consume that authority rather than parsing raw files independently.
- Registry source files are declarations, not a second runtime API. Direct file reads may diagnose source shape but cannot establish filing-grade behavior.
- Public registry symbols are defined in semantically named public modules and imported directly. A curated re-export layer is still a facade and is forbidden; package initializers remain inert.

## Registry identity and selection

- Modelo identity uses the canonical typed modelo representation. Revisions, filing periods, legal windows, and territorial or taxpayer applicability are explicit and validated.
- Select a revision from the applicable law and filing context, never from filename ordering, newest-available fallback, or string comparison.
- Fragmented declarations compile into one validated revision. Duplicate ownership, missing fragments, ambiguous casilla identity, invalid references, or conflicting declarations fail before publication.
- Values used by calculations come from typed registry fields or their canonical configuration mechanism. Do not scatter regulatory constants through runtime code.
- Cross-revision continuity is accepted only when the chain and its evolutions are grounded. A repeated box number or similar label is candidate evidence, not identity.

## Publication and failure

- The authority publishes only a completely validated snapshot and never exposes a partially constructed generation.
- Cache identity includes the authoritative source state and invalidates on relevant source or evidence changes. Callers receive isolated validated snapshots rather than mutable shared registry state.
- Unsupported or insufficiently grounded capability fails closed or remains explicitly advisory. It must not be upgraded by a consumer-side fallback.

Authority: accepted registry/compiler and import-centralization architecture decisions plus the live registry authority tests.
