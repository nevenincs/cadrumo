---
tags:
  - '#adr'
  - '#schedule-predicate-catalogue'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-schedule-predicate-catalogue-research]]'
---

# schedule-predicate-catalogue adr: eager compile-time validation of schedule-predicate field references | (status: accepted)

## Problem Statement

Schedule predicates in the calculation registry (filing_schedules.profile_conditions,
deadline_windows.applicability_conditions, live_cross_references.applicability_predicates)
reference profile-fact field paths by string. Before the _registry_contract.py mechanism
was introduced, a typo or stale reference in a predicate field would only surface when
the predicate was evaluated at runtime -- not when the registry was loaded.

As of the current codebase the structural validation gate is substantially present but
three gaps remain: (1) validation is deferred to first modelo use, not to registry load;
(2) proof tests for filing_schedule and deadline_window predicate surfaces are missing;
(3) runtime attribute aliases in _schedules.py are undocumented.

## What field reference means

A schedule-predicate field reference is a dot-separated path string (e.g.
enrollment.large_company, iva.regime, taxpayer.entity_type) that names a fact
in the user-profile schema. The profile schema TOML declares which paths are valid
as schedule predicates via the schedule_predicates array on each sections.fields entry.
The compile-time index is the schedule_predicates frozenset built by
build_user_profile_selector_index.

Field references are NOT casilla IDs and NOT model selector paths.

## Decision

Adopt the following three changes to bring #560 to full compliance:

1. Eager validation at authority load. Call validate_registry() inside _load_authority
   immediately after load_registry_tree() returns. The LRU cache on _load_authority
   guarantees this runs at most once per process per registry fingerprint. Broken predicate
   fields then fail at load time, not at the first snapshot() call.

2. Proof tests for the two untested predicate surfaces. Each test injects a synthetic
   ProfilePredicateDefinition with a non-existent field string into a committed revision
   and asserts that validate_user_profile_registry_contract returns an issue with
   severity ERROR and the correct surface name.

3. Alias documentation in _schedules.py. Add inline comments next to the two
   hardcoded attribute aliases in _resolve_profile_fact: iva.regime -> iva_regime
   and taxpayer.entity_type -> entity_type. No behavioural change.

## Validator failure shape

At registry load: RegistryValidationError raised from validate_registry() with the
message format: modelo <id> revision <id>: user-profile schema <id>
<surface> <construct_id> selector <field>: <message>.

## Migration

Every predicate currently in the committed registry already resolves cleanly. No TOML fixes
are needed. Adding the eager validate_registry() call will not break any committed TOML.

## Files in scope

Edit only:
- src/aeat/domain/calculations/registry/_authority.py (gap 1)
- src/aeat/domain/calculations/registry/test_filing_schedule_selection.py (gap 2)
- src/aeat/domain/calculations/registry/_schedules.py (gap 3)

Do NOT touch application/, adapter code, or _registry_contract.py (already correct).

## Alternatives considered

Pydantic model_validator on ProfilePredicateDefinition to check field against schema at
parse time: rejected because the profile schema is not available as a global during
TOML parse. Injecting schema context into the pydantic model violates the registry boundary.

Separate TOML-level catalogue of valid predicate names: rejected as redundant. The
user-profile schema TOML already declares schedule_predicates per field.