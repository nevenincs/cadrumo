---
tags:
  - '#adr'
  - '#profile-requirement-grounding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c9e18fb953a92666ffb344791d57057c7dd6d3b776e11037ced9abf5c1417b4d'
related:
  - "[[2026-07-23-profile-setup-flow-adr]]"
  - '[[2026-08-08-profile-requirement-grounding-reference]]'
---
# `profile-requirement-grounding` adr: `unify the profile-requirement schema across the blocking gate, preflight, and readiness surfaces` | (**status:** `accepted`)

## Problem Statement

Three operator-facing surfaces (the blocking readiness gate on calculate/verify/export, `config profile preflight`, `app modelo readiness`) all report "which profile fields are missing" for a filing context, but every surface can only name the raw dotted schema path (e.g. `identity.tax_id`). An operator running the CLI has no way to see a human label, the legal basis, or which modelo(s) actually need a given field. `2026-08-08-profile-requirement-grounding-reference` documents that the richer data (`description`, `legal_refs`, per-operation `model_selectors`) already exists on the schema object in scope at the point each report row is built, and is simply discarded.

## Considerations

- The requirement row (`ProfilePreflightRequirement`) is shared by all three consumers, so one enrichment fixes all three surfaces at once (`2026-08-08-profile-requirement-grounding-reference`, "Three consumers of the same requirement set").
- `build_profile_grounding_index` already computes the registry-binding-derived union (`legal_refs`/`source_refs`/`modelos` per profile key) and is proven safe/cheap by its existing wizard-only consumer, `application/wizard/_legal_zone.py` (`2026-08-08-profile-requirement-grounding-reference`, "The reusable grounding-union source").
- Locale strings for the blocking-gate message must be authored through the `dev.locales` CLI in all four catalogues (en/es/ca/hu), per this project's locale-catalogue mandate.
- `ProfileKey` and `_DEADLINE_RELEVANT_FIELDS` are separate, disconnected mechanisms describing overlapping facts; reconciling or retiring them is a real but distinct question from enriching the canonical requirement row, and needs its own field-by-field parity check before any retirement (`2026-08-08-profile-requirement-grounding-reference`, "Two other, disconnected profile-requirement mechanisms").

## Considered options

- **Enrich the existing `ProfilePreflightRequirement` row (chosen).** Add `label`, `legal_refs`, `modelos` fields populated from data already in scope plus the existing grounding index. No new schema, no new authority, minimal surface area; all three consumers inherit the fix from one shared model.
- **Invent a new unified "operation requirement" schema from scratch.** Rejected: this project already has a working per-operation schema (`ProfileSchemaDefinition`/`model_selectors`); a parallel new schema would be exactly the kind of duplicate authority this codebase's own architecture rules forbid, and would orphan the existing three consumers instead of fixing them.
- **Fix only the blocking-gate message, leave `preflight`/`readiness` JSON alone.** Rejected: the user-visible complaint applies to all three surfaces equally, and they already share one row type, so a partial fix would immediately re-diverge them.

## Constraints

- No new registry or schema authority may be introduced (`aeat-architecture-boundaries`, `no-legacy-compatibility`); the enrichment must read from `ProfileFieldDefinition` and `build_profile_grounding_index`, both already canonical.
- Locale changes must go through `dev.locales set/scaffold` in all four catalogues; hand-editing the YAML catalogues is forbidden.
- `ProfilePreflightMissingPayload` and `ModeloReadinessMissingRequirementPayload` are registered `OutputSchema` JSON contracts; adding fields is additive/backward compatible, but the CLI's documented-command-conformance and JSON-schema-conformance gates must stay green.
- Reconciling `ProfileKey` / `_DEADLINE_RELEVANT_FIELDS` against the canonical schema is deferred to a follow-up Step with its own parity investigation; it is not a precondition for this enrichment.

## Implementation

Add `label: str`, `legal_refs: tuple[str, ...]`, and `modelos: tuple[str, ...]` to `ProfilePreflightRequirement`. Populate them in `ProfilePreflightService.report()` from the `field` object already in scope (`field.description`, `field.legal_refs`) unioned with `build_profile_grounding_index(authority)[selector]` when present. Mirror the three new fields onto `ProfilePreflightMissingPayload` and `ModeloReadinessMissingRequirementPayload`, and update the `application.modelo.errors.profile_readiness_missing` locale template (all four catalogues) to render label + legal ref instead of the bare selector path. Add roundtrip/anti-tautology coverage for the enriched row per this project's quality-gate rules, and a grounded regression proving the blocking-gate message text changes for a known missing field.

## Rationale

The enrichment is the minimum change that closes the gap for all three surfaces at once, using only data this codebase already computes and already trusts (the wizard's `_legal_zone.py` proves the grounding union is safe). It carries no new schema-duplication risk and stays inside this project's "one canonical mechanism per concept" discipline. See `2026-08-08-profile-requirement-grounding-reference` for the full evidence trail.

## Consequences

Operators get a labeled, legally-grounded, per-operation "why" on every incomplete-profile signal instead of a bare dotted path, across the blocking refusal, `preflight`, and `readiness` surfaces uniformly. The change touches a shared model consumed in three places plus four locale catalogues, so it needs care not to regress any of the three consumers' existing JSON-schema conformance gates. It does not resolve the separate `ProfileKey`/`_DEADLINE_RELEVANT_FIELDS` redundancy; that remains open as a follow-up investigation.
