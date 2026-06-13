---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W70.P330..W70.P339'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-dev-environment-uv-windows-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-error-registry-exhaustiveness-invariant-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-list-vs-query-leaf-semantics-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-integrity-warning-stability-adr]]"
---

# `cli-workflow-redesign` W70 closeout (test-user audit closure)

Closed plan rows: every row of W70.P330..P339 (52 rows).

## Per-phase verification

Each phase's binding code already landed in earlier commits on
this branch. Plan-tick maintenance was deferred; this closeout
record applies the maintenance and pins the surface evidence.

- **P330 (Windows uv launcher)**: launcher relocated to
  `tools/` (commit `62ed3411`, then `03850d43`); stale-sync
  diagnostic row included in `aeat config repair` composite
  report.
- **P331 (error registry exhaustiveness invariant)**:
  `core/errors/test_registry_enforcement.py:34` walks every
  submodule via `pkgutil.walk_packages` and asserts every
  reachable `AeatError` subclass has a registry entry; the
  import-time invariant raises at module-import boundary.
- **P332 (ledger full-id / display-id)**: commit `19ccb0d5`
  added `full_id` and `display_id` resolution on every ledger
  CLI verb; mutating verbs accept either form and refuse
  ambiguous prefixes.
- **P333 (`aeat app ledger evidence` CRUD)**: commit
  `5b748069` registered the five-verb noun group
  (`add`/`remove`/`update`/`view`/`list`) wired to the receipt
  OCR application service with PDF/image-only fence.
- **P334 (doctor retirement + DiagnosticCheck discriminated
  union)**: no `aeat config doctor` Typer mount; `DiagnosticCheck`
  in `application/diagnostics.py:63` carries the
  `next_action xor dead_end` invariant via a Pydantic
  `model_validator`.
- **P335 (post-init hint leaf target)**: the `init` success
  message in `_register_wizard_commands` points at the
  `aeat app overview status` leaf; the hint construction emits
  through the canonical i18n surface and not a group target.
- **P336 (list-vs-query leaf semantics)**: commit `96372011`
  made the affected `list` leaves accept bare invocation with
  optional refining filters.
- **P337 (refusal tone)**: `core/errors/_registry.py:46` already
  emits `Refused.` (sentence case) rather than `REFUSED:`.
- **P338 (legacy-borrador cohort demotion)**: commit `e104f89b`
  demotes the cohort to `info` severity in the review queue and
  adds the drill verb against the migration-tagged cohort.
- **P339 (integrity-warning stability probes)**: commit
  `62ed3411` landed the determinism and schema-stability probes
  under `tools/`; the integrity-scan is a pure function of the
  secure-objects table state.

## Guards held

- No new metastate codification.
- Every Phase's work is real CLI / domain / application surface
  in HEAD; no NotImplementedError stubs or deferred-code
  markers.
- The earlier vault audits under
  `.vault/audit/2026-05-14-cli-workflow-redesign-S*-code-review.md`
  cover the per-step reviewer pass.
