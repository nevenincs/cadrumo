---
tags:
  - '#reference'
  - '#user-profile-deadline-dependencies'
date: '2026-05-07'
modified: '2026-05-07'
related: []
---



# `user-profile-deadline-dependencies` reference: `User Profile Deadline Dependencies`

Topic: deadline, schedule, calendar, enrollment, and regime surfaces that
consume profile information to decide model applicability and filing cadence.

Audit surface: deadline domain models, profile mapping helpers, registry
schedule predicates, overview calendar, deadline CLI loading, setup answers, and
registry deadline conditions.

Rewrite scope: this document records current dependencies and replacement
requirements. Runtime alias maps and split profile stores are teardown targets.

## Findings

### Deadline scheduling is centered on a separate profile model

Deadline scheduling uses `AutonomoProfile`, not the setup profile key schema.
The model carries `tax_id`, `iva_regime`, withholding flags, intracommunity
flags, 347/720 flags, nested IVA facts, and nested enrollment facts.

Overview calendar builds an `AutonomoProfile` from active `UserCliState`
profile values, while the deadline CLI loads a secure setup
`AutonomoProfile` envelope. These are separate sources of truth.

Evidence anchors: `src/aeat/domain/deadlines/_models.py:69`,
`src/aeat/domain/deadlines/_models.py:86`,
`src/aeat/entrypoints/cli/_overview.py:53`,
`src/aeat/entrypoints/cli/_common.py`,
`src/aeat/entrypoints/cli/deadlines/_helpers.py:47`,
`src/aeat/application/setup/_env_writer.py:140`.

### Current mapping uses aliases and inconsistent key normalization

`autonomo_profile_from_mapping` maps persisted strings and booleans into
deadline facts, accepting both snake-case and dotted aliases for many fields.
`UserCliState` key normalization lowercases and replaces underscores with
dots. That breaks nested underscore leaf keys such as
`iva.intracommunity_operations_exceed_50000_eur`, which the deadline mapper
expects exactly.

Evidence anchors: `src/aeat/domain/deadlines/_profiles.py:13`,
`src/aeat/domain/deadlines/_profiles.py:24`,
`src/aeat/domain/deadlines/_profiles.py:39`,
`src/aeat/domain/deadlines/_profiles.py:61`,
`src/aeat/application/user_cli.py:40`.

### Registry deadlines depend on enrollment and obligation facts

Modelo 111 uses `enrollment.large_company` and
`enrollment.public_administration_budget_gt_6000000` for monthly versus
quarterly cadence. Modelo 349 uses `does_intracomunitario` and
`iva.intracommunity_operations_exceed_50000_eur` for cadence.

Modelo applicability uses withholding and IRPF facts: `has_employees`,
`pays_professionals_with_retencion`, `pays_rent_with_retencion`,
`pays_capital_income_with_retencion`,
`professional_income_withholding_ge_70pct`, and
`uses_objective_estimation_irpf`.

Evidence anchors: `registry/aeat/modelos/111.toml:18`,
`registry/aeat/modelos/111.toml:1640`,
`registry/aeat/modelos/349.toml:336`,
`registry/aeat/modelos/130.toml:1423`,
`registry/aeat/modelos/115.toml:879`,
`registry/aeat/modelos/123.toml:1114`,
`registry/aeat/modelos/131.toml:5946`.

### Captured facts are not fully wired

Setup captures a partial business profile but omits some deadline fields in
the wizard. Fields such as `pays_capital_income_with_retencion`,
`uses_objective_estimation_irpf`, enrollment flags, and the 349 threshold can
default false without an explicit user answer. Fields for 347 and 720 are
captured in `AutonomoProfile` but are not clearly wired into registry
applicability.

Evidence anchors: `src/aeat/application/setup/_models.py:86`,
`src/aeat/application/setup/_wizard.py`,
`src/aeat/domain/deadlines/_profiles.py:13`,
`registry/aeat/modelos/347.toml`,
`registry/aeat/modelos/720.toml`.

## Requirements

Canonical profile sections required for calendar are `census/enrollment`,
`activities`, `irpf/withholding`, `iva`, `properties/rental`, and
`provenance/effective dating`.

Schedule predicates must use canonical profile selectors only. Runtime alias
maps and broad underscore-to-dot normalization should be removed from deadline
construction.

Calendar preflight must validate required enrollment facts before computing
deadlines: large company, public-administration budget flag where applicable,
IVA regime/frequency, intracommunity threshold, withholding payer flags,
rental-withholding flag, capital-income withholding flag, IRPF estimation
regime, and period-effective activity state.

Effective dating is required because census enrollment, activity starts/stops,
IVA regime, intracommunity thresholds, and large-company status can change
within or between filing periods.

Setup and CLI profile commands must write through the centralized profile API
and secure DB backend, not a separate `AutonomoProfile` store.

## Risks And Open Questions

The ADR must decide whether the profile stores raw census facts and derives
obligations, or stores explicit obligation flags with provenance. The cleaner
schema may need both raw census declarations and derived filing facts.

Mid-period changes need a deterministic rule: reject until disambiguated,
split by effective dates, or derive period facts from census history.

The 347/720 threshold flags need a registry decision. They are captured but not
currently authoritative for applicability.
