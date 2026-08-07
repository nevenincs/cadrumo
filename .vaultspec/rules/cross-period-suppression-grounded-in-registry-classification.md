# Cross-period suppression is grounded in registry classification, never the schedule

A cross-period dependency may be scoped out of the clean-state gate as
not-applicable ONLY on a registry signal carried by that dependency's own
`DependencyClassificationDefinition`: either `taxpayer_files_source = false` (the
taxpayer never files the source — suffered retenciones), or
`conditional_on_economic_activity = true` combined with a **fail-closed**
`taxpayer_files_economic_activity is False` (pagos fraccionados).

The suppression set MUST derive from `snapshot.revision.dependency_classifications`,
never from the deadline-engine obligation schedule. A taxpayer who DOES file the
source, and the undeclared case, stay enforced.

A reachability defect was first patched by scoping out a dependency absent from
the deadline-engine schedule; the full-tree gate proved the schedule an
INCOMPLETE signal that over-suppressed other targets' enforced sources, and that
patch was reverted. The grounded fix classifies each dependency in the registry —
the authority the calc engine already consumes — scoping suppression to exactly
the not-filed sources while preserving enforcement of filed ones.

## How

- **Good:** a suffered-retencion source is marked `taxpayer_files_source = false`
  and the gate scopes it out as a **visible** not-applicable advisory, never
  silently. A pagos-fraccionados source marked
  `conditional_on_economic_activity = true` scopes out ONLY when the profile
  signal is explicitly `False`.
- **Bad:** scoping out because the source modelo is missing from the
  deadline-engine schedule; or suppressing on an undeclared or absent profile
  signal, which fails open and launders a real filer past the evidence gate.

Source: ADR `2026-06-19-m100-dependent-modelo-applicability-adr`. Companions:
`full-tree-gate-must-distinguish-owner`, `no-silent-under-declaration`,
`aeat-registry-authority-flow`.
