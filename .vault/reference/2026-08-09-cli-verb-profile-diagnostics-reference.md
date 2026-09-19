---
tags:
  - '#reference'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:f95ab616e98ad458daff46c02825e1e18adad8731bc96d18533889c1e5614c33'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# `cli-verb-profile-diagnostics` reference: `CLI verb profile-refusal message inventory`

## Summary

Inventory of every CLI surface that refuses or warns because the ACTIVE profile
lacks specific information, classified by whether the operator is told WHICH
field is missing, under its human label, with its legal basis.

The canonical mechanism already exists and is not in question:
`build_profile_preflight_requirement` in
`src/cadrumo/application/user_profile/_preflight.py`, exported from
`application/user_profile`, reduces a profile path to its `section.field` form,
resolves the locale-catalogue operator label (never a raw dotted path), and
unions the schema field's `legal_refs` with the registry-binding grounding from
`build_profile_grounding_index`. It already backs the modelo readiness gate,
`config profile preflight` and `app modelo readiness`. What is incomplete is its
COVERAGE across other verbs, not its design.

## Distinguishing the two failure classes

Two different defects share the symptom "unhelpful refusal", and only the first
is in scope here:

- **Message defect.** The verb refuses under the right condition but names the
  missing thing by a raw internal identifier (a profile selector token, a
  registry binding id, a bare count). Fixing it changes WHAT the operator reads,
  never WHETHER the verb refuses. In scope.
- **Verdict defect.** The verb's readiness CONDITION itself disagrees with the
  canonical schema. Rewiring it changes whether real profiles pass. Out of scope
  without its own decision, per the deferral already recorded for
  `config profile status`, `wizard status` and `overview diagnostics`.

A separate class, also out of scope, is the cold-start refusal: no active
profile exists at all. `_no_active_profile_refusal` in
`src/cadrumo/entrypoints/cli/_common.py` already handles this correctly and
distinguishes "no profile registered" from "none active". No field is missing in
that case, so there is nothing for the schema to name. Both
`_require_active_profile` helpers (`_app_quickfile.py:53`, `_modelo.py:265`, and
the late-bound module global in `_modelo_reconcile_cli.py`) delegate to it and
are correct as they stand. They were candidate sites in the initiating brief;
inspection cleared them.

## Confirmed message-defect sites

### A. Overview calendar, agenda and backlog refuse with raw profile selector tokens

`src/cadrumo/entrypoints/cli/_overview.py:104` (`_refuse_calendar_warnings`,
used by `overview calendar`), `:633` (`overview agenda`) and `:710`
(`overview backlog`) each build their refusal as
`", ".join(warning.code for warning in ...warnings)` and pass it to the
`cli.overview.calendar_refused_incomplete` locale key as `keys`.

For profile-completeness warnings, `warning.code` IS the raw profile selector
token: `_build_completeness_and_warnings` in
`src/cadrumo/application/overview/_calendar_warnings.py:448` constructs
`CalendarWarning(code=key, ...)` where `key` comes from `_gating_fields()` and is
a `model_selectors` token such as `has_employees`,
`pays_rent_with_retencion`, `does_intracomunitario`,
`third_party_transactions_above_347_threshold`, `irpf.estimation_regime` or
`iva.regime`. The operator is shown these tokens verbatim, with no operator
label and no legal basis.

Two further defects compound at the same three call sites:

- The warning ALREADY carries a human message. `CalendarWarning.message`
  (`_calendar_models.py:374`) holds the locale key of a written operator
  sentence, and `fix_command` holds a concrete remediation command. The refusal
  path discards both and prints the code instead.
- The refusal is raised through `_bad`, a Click parameter error, so it renders
  under an `Invalid value:` header rather than through the shared envelope's
  typed `Notice` channel. A missing profile fact is a workflow-state refusal,
  not bad operator input.

Not every calendar warning is a profile field. `_calendar_warnings.py:270`,
`:344`, `:375` and `:395` construct warnings whose `code` is a genuine warning
code (censo enrolment, unverified justificante, AEAT evidence conflict, M303
simplificado forfait), not a profile selector. Any enrichment must resolve the
profile-field subset and leave the rest as-is rather than assuming every code is
a selector.

The refusal CONDITION (`warnings and not allow_incomplete`) is not touched by
this: these are message defects, class one above.

### A2. The same three verbs also refuse on an undeclared taxpayer model, generically

**Added after the initial inventory, during the honesty review.** The first pass
recorded only the completeness-warning refusal on these verbs and missed the
refusal sitting a few lines above each of them, at `_overview.py:413`, `:674`
and `:745`.

Each raises `_bad(... or tr("cli.overview.taxpayer_model_undeclared"))`, whose
text is "The active profile does not declare this taxpayer model; update the
profile or rerun with the incomplete-profile override." It names no field, no
label and no legal basis, and like the completeness refusal it is raised as a
Click parameter error.

The blocking facts are precisely identifiable. `taxpayer_model_is_declared` in
the deadlines domain treats the model as declared when `entity_type` is set
and, for a natural person only, at least one IRPF income category is present.
Both are schema fields: `entity_type` declares selector `taxpayer.entity_type`
(`schema.toml:413`) and `irpf_income_categories` declares
`taxpayer.irpf_income_categories` (`schema.toml:536`), so both resolve through
the selector-to-path lookup.

Because the predicate has two branches, an enrichment must name only the
absent fact. A natural person who declared an entity type but no income
category would otherwise be pointed back at a field they already filled in.

### B. `app modelo requires` warns with raw registry binding ids

`src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py:578` renders its
missing-profile-coefficient warning as
`", ".join(sorted(str(binding_id) for binding_id in checklist.unresolved_profile_bindings))`.

The operator receives registry binding ids. The corresponding profile keys are
recoverable: `unresolved_profile_bindings` is populated in
`src/cadrumo/application/modelo/_data_inventory.py:174` from bindings whose
`source` is `BindingSourceKind.PROFILE`, and every such binding names its
consumed profile keys in its selector. `_selector_profile_keys` in
`src/cadrumo/domain/calculations/registry/_profile_grounding.py:123` already
performs exactly that extraction, but is private to that module.

This site DOES already emit through the typed `Notice` channel, so only the
schema-derivation half is missing.

### C. The diagnostics profile-readiness summary is a bare count

`src/cadrumo/application/diagnostics.py:976` renders its summary through
`cli.diagnostics.summary.profile_missing_keys`, whose text is
"Profile is missing %{count} required key(s)" - a count with no field named.

Unlike A and B, the underlying data is not lost: the same `DiagnosticCheck`
carries `findings`, one `DiagnosticFinding` per missing key. But each finding's
`summary` is itself the raw key (`:965`, `:969`), so no operator label or legal
basis reaches the operator through either channel.

Note this check is one of the three surfaces whose VERDICT was deliberately
deferred. The verdict question and the message question are separable here: the
set of keys the check reports is decided upstream in
`assess_active_profile_health`, and relabelling those keys does not change which
keys are in the set.

## Selector-to-field resolution is the one missing primitive

Sites A and B both hold a `model_selectors` TOKEN (`has_employees`) or a binding
selector key, not a `section.field` path. `build_profile_preflight_requirement`
resolves a path, and falls back to returning the raw string unchanged when the
argument is not a dotted path naming a real schema field - which is precisely
what these sites would hand it.

The schema declares the mapping in the other direction: in
`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`, the field at
`:1085` has `key = "has_employees"` inside the `withholding` section (`:1079`)
and declares `model_selectors = ["has_employees"]`. So the token resolves to
`withholding.has_employees`, but no by-selector index exists:
`domain/user_profile/_schema.py` offers `derived_selector_for_path` (path to
selector) and `ProfileSchemaDefinition.field(path)`, and
`ProfilePreflightService._selector_for_path` (`_preflight.py:297`) is likewise
path-to-selector. The inverse lookup is the one primitive this work needs to
add before A and B can route through the canonical builder.

## Out of scope, recorded so it is not re-derived

The wrong `orden-hac-1347-2024:art-4` citation on Modelo 100 declarant-identity
bindings and the schema fields that inherited it is a real, corpus-verified
legal-provenance defect already documented under the
`profile-requirement-grounding` feature. It is human-reviewed filing-grade work,
deliberately left unfixed. Work here must not propagate it further: enriching a
refusal with a field's existing `legal_refs` surfaces whatever the registry
already carries, which is the correct behaviour for this mechanism, but no new
citation should be authored or copied onto a field as part of this work.
