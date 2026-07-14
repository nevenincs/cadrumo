# Cross-period dependency suppression is grounded in registry classification, never the schedule

## Rule

A cross-period dependency may be scoped out of the clean-state gate (not-applicable)
ONLY on a registry signal on the dependency's own `DependencyClassificationDefinition`:
`taxpayer_files_source = false` (taxpayer never files the source, e.g. suffered
retenciones 111/115/123/180/184/190/193) or `conditional_on_economic_activity = true`
combined with a fail-closed `taxpayer_files_economic_activity is False` (pagos-
fraccionados 130/131). The suppression set MUST derive from
`snapshot.revision.dependency_classifications`, never from the deadline-engine
obligation schedule. A taxpayer who DOES file the source, and the undeclared case, stay
enforced (fail-closed).

## Why

The C3 M100-reachability defect was first patched (Option 1) by scoping out a
dependency absent from the deadline-engine schedule; the full-tree gate proved the
schedule an INCOMPLETE signal that over-suppressed OTHER targets' enforced sources
(180/190/193/200/202), breaking `test_cross_period_clean_state_enforcement` — Option 1
was reverted. The grounded fix classifies each dependency in the registry (the
authority the calc engine consumes), scoping suppression to exactly the not-filed
sources while preserving enforcement of filed sources. ADR
`2026-06-19-m100-dependent-modelo-applicability-adr` (Updates 1-3); proven by
`test_m100_suffered_retencion_deps_scoped_out_self_filed_enforced` and
`test_m100_pagos_fraccionados_conditional_on_economic_activity`.

## How

- **Good:** mark a suffered-retencion source `taxpayer_files_source = false` — the gate
  reads `dependency_classifications` and scopes it out as a visible not-applicable
  advisory (never silent); a pagos-fraccionados source
  `conditional_on_economic_activity = true` scopes out ONLY when
  `taxpayer_files_economic_activity` (from `TaxpayerProfile.irpf_income_categories`,
  `None` when undeclared) is explicitly `False`.
- **Bad:** scoping out because the source modelo is missing from the deadline-engine
  schedule (reverted Option 1); or suppressing on an undeclared/absent profile signal
  (fail-open), laundering a real autónomo past the M130->M100 evidence gate.

## Source

ADR `2026-06-19-m100-dependent-modelo-applicability-adr` and research. Companion:
`full-tree-gate-must-distinguish-owner`, `no-silent-under-declaration`,
`aeat-registry-authority-flow`.
