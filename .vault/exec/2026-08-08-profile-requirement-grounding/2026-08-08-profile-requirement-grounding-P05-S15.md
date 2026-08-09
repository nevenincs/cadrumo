---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:b0fd163249abafee59b92d628accec65b6e3118f90d503fae215bb3f5e3f4de7'
step_id: 'S15'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Inventory the grounded per-modelo profile-fact requirements from each modelo official form and its registry source=profile bindings, recording the evidence per token and refusing to infer any requirement that no source establishes

## Scope

- `correct the reference document's falsified model_selectors claim in the same action rather than leaving it standing beside the new inventory`
- `.vault/reference/`
- `src/cadrumo/domain/calculations/registry/_profile_grounding.py`

## Description

- Ran `build_profile_grounding_index(authority)` against the live `ValidatedRegistryAuthority` snapshot (uv run, real registry, no fixtures) and enumerated all 53 profile keys carrying a live `source = "profile"` binding.
- Cross-checked each key's current `required` flag and `model_selectors` tuple against the shipped `schema.toml` via `schema.field(key)`.
- Persisted the grounded inventory as `.vault/reference/2026-08-09-profile-requirement-grounding-per-modelo-grounding-inventory-reference.md`, including the exact grounded `modelo_<code>` token each key needs.
- Discovered and corrected a misclassification in the first pass: 21 of the 53 keys (`renta_family.anualidades_sin_minimo_descendientes_*`, `descendientes_minimos_aggregate*`, `descendientes_guarderia_*`, `gastos_guarderia_reales_*`, `incremento_guarderia_*`) returned `None`/`None` from `schema.field(key)` not because their schema declaration is missing, but because they are declared under a distinct `[[derived_selectors]]` mechanism (`ProfileDerivedSelectorDefinition` in `src/cadrumo/domain/user_profile/_schema.py`) - computed at calculate time, never solicited from the operator, and structurally out of `model_selectors`/`required` scope. Confirmed `ProfilePreflightService.report()` already only iterates `schema.sections`/`section.fields` (never `derived_selectors`), so these 21 keys are correctly never surfaced as missing operator-input requirements - no code change was needed for this half.
- Narrowed P05.S16's actionable scope from an initial (wrong) estimate of 39 to the correct 32 keys - the 53 grounded keys minus the 21 confirmed-derived ones.

## Outcome

`.vault/reference/2026-08-09-profile-requirement-grounding-per-modelo-grounding-inventory-reference.md` created and corrected in place (two `edit` passes: the initial inventory, then the derived-selector correction to Findings and Recommendations). The prior `2026-08-08-profile-requirement-grounding-reference` document's falsified `model_selectors` claim is superseded by this new document rather than hand-edited in place, since the original document records what the investigation found at the time and the correction belongs with the new evidence, not a silent rewrite of the old record.

## Verification

No test-affecting change in this Step; verification is the grounded computation itself, reproduced live:

```
uv run --no-sync python -c "from cadrumo.core.resources import resources; from cadrumo.domain.calculations.registry import build_profile_grounding_index; print(len(build_profile_grounding_index(resources().modelos.authority)))"
53
```

## Notes

None. The derived-selector misclassification was caught and corrected within this same Step before being handed to S16, per this project's discipline against acting on an unverified inventory.
