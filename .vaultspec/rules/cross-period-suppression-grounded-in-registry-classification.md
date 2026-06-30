# Cross-period dependency suppression is grounded in registry classification, never the schedule

## Rule

A cross-period dependency may be scoped out of the clean-state gate (treated as
not-applicable) ONLY on a registry-authoritative signal carried by the dependency's
own `DependencyClassificationDefinition` — `taxpayer_files_source = false` (the
taxpayer never files the source modelo, e.g. suffered retenciones 111/115/123/180/
184/190/193) or `conditional_on_economic_activity = true` combined with an explicit,
fail-closed profile signal (`taxpayer_files_economic_activity is False` for the
pagos-fraccionados 130/131). The suppression set MUST be derived from
`snapshot.revision.dependency_classifications` (the snapshot's own authority), never
from the deadline-engine obligation schedule. A taxpayer who DOES file the source,
and the undeclared case, stay enforced (fail-closed).

## Why

The C3 Modelo-100-reachability defect was first patched (Option 1) by scoping out a
dependency when its source modelo was absent from the deadline-engine obligation
schedule. The full-tree gate proved that wrong: the schedule is an INCOMPLETE
"which modelos does the taxpayer file" signal, so it over-suppressed the
legitimately-enforced cross-period sources of OTHER targets (180/190/193/200/202),
breaking `test_cross_period_clean_state_enforcement`. Option 1 was reverted. The
grounded fix classifies each dependency in the registry (the same authority the
calculation engine consumes) and drives suppression from the snapshot's own
classifications plus a fail-closed profile-activity signal — so suppression is
per-modelo registry data, scoped to exactly the not-filed sources, and the
enforcement contract for filed sources is preserved. Recorded in ADR
`2026-06-19-m100-dependent-modelo-applicability-adr` (Updates 1-3); proven by
`test_m100_suffered_retencion_deps_scoped_out_self_filed_enforced` and
`test_m100_pagos_fraccionados_conditional_on_economic_activity`.

## How

- **Good:** mark a suffered-retencion source `taxpayer_files_source = false`; the gate
  reads `snapshot.revision.dependency_classifications` and scopes it out as a visible
  not-applicable advisory (never silent).
- **Good:** mark a pagos-fraccionados source `conditional_on_economic_activity = true`
  and pass `taxpayer_files_economic_activity` (derived from
  `TaxpayerProfile.irpf_income_categories`, `None` when undeclared) into the gate; it
  scopes out ONLY when the value is explicitly `False`.
- **Bad:** scope a dependency out because its source modelo is missing from the
  deadline-engine obligation schedule — the schedule is incomplete and over-suppresses
  other targets' enforced sources (the reverted Option 1).
- **Bad:** suppress on an undeclared/absent profile signal (fail-open) — a real autónomo
  who has not yet declared income categories would launder past the M130->M100 evidence
  gate.

## Source

ADR `2026-06-19-m100-dependent-modelo-applicability-adr`; research
`2026-06-19-m100-dependent-modelo-applicability-research`. Companion to
`full-tree-gate-must-distinguish-owner` (the gate that caught Option 1),
`no-silent-under-declaration`, and `aeat-registry-authority-flow`.
