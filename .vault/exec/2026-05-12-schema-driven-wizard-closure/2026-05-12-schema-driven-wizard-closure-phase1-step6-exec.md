---
tags:
  - '#exec'
  - '#schema-driven-wizard-closure'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-closure-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# c6 final verification sweep

## scope

C6 is verification-only. The plan's final gate set is run against
the codebase state after C1 through C5 land. The stray
``aeat archive`` docstring reference in
``src/aeat/entrypoints/cli/test_archive_cli.py:1`` is corrected to
``aeat app archive`` -- the only source change in this step and
the only finding the C1 sweep missed.

## acceptance gates run

Each gate run against ``HEAD = 439ea17a`` plus the
``test_archive_cli.py`` docstring fix.

### gate 1 — root surface

``aeat --help`` lists exactly two top-level subgroups:

    | config  Gestionar configuración local y diagnósticos
    | app     Espacio de trabajo fiscal para libros, facturas y
    |         declaraciones

No ``version``, no ``archive``, no ``topic``, no ``help`` row.

### gate 2 — archive + topic help in every locale

``aeat app archive --help`` and ``aeat app topic --help`` render
translated, non-key text in en / es / ca / hu:

- ``cli.archive.app_help`` resolves to the English / Spanish /
  Catalan / Hungarian translation of the export-and-import summary
- ``cli.topic.app_help`` resolves to the English / Spanish / Catalan
  / Hungarian translation of the conceptual-help summary
- ``cli.app.modelo.app_help`` (within the broadened audit) resolves
  to the locale-appropriate registry-catalogue summary

### gate 3 — translation audit

``audit_cli_translations()`` returns ``()``. The audit walks every
``cli.<group>.*`` literal referenced under
``aeat.entrypoints.cli`` (524 unique keys) and asserts each
resolves to non-key text in all four locales.

### gate 4 — wizard- and revision-owned test surfaces

``pytest src/aeat/application/wizard/
src/aeat/application/test_config_parity.py
src/aeat/entrypoints/cli/test_workflow_surface.py -q`` — 126
passed, 0 failed.

The plan also names ``pytest src/aeat/application/ -q`` and
``pytest src/aeat/entrypoints/cli/ -q`` more broadly; both are
expected to carry pre-existing failures from concurrent agent work
on unrelated streams (renta-pipeline, cli-workflow-redesign WIP).
Those failures are not attributable to this closure.

### gate 5 — no stale invocation forms

``grep -rn 'aeat archive\b|aeat topic\b|aeat help <?slug'
src/aeat/`` — no matches.

The one residual reference at
``src/aeat/entrypoints/cli/test_archive_cli.py:1`` is rewritten
in this step to ``aeat app archive``.

### gate 6 — transient-meta phrases

``grep -rn
'historically|legacy|previously|formerly|replaces|UX-[0-9]'
src/aeat/application/ src/aeat/domain/ src/aeat/entrypoints/``
returns matches across the codebase. None of the matches live
in the three files C3 owned
(``_storage_namespaces.py``, ``_profiles.py``, ``_topic.py``).
The remaining matches are pre-existing transient-meta violations
in unrelated modules (e.g.,
``application/topics/__init__.py:3`` ``Closes UX-015``,
``application/overview/__init__.py:27,195`` ``UX-008 from the
2026-05-08 CLI gap audit``,
``application/workflow/_state.py:2`` ``All symbols previously
here were moved``,
``entrypoints/cli/_declaration.py:196`` ``UX-021``); they are
flagged for a separate hygiene sweep and explicitly out of this
closure's scope.

### gate 7 — vault check

``vaultspec-core vault check all`` runs on the worktree. Pre-existing
errors and warnings dominate (254 errors / 64 warnings, mostly
from concurrent agents' renta-pipeline and cli-workflow-redesign
work). The two warnings attributed to ``schema-driven-wizard-closure``
itself (no own ADR, no feature index) are inherent to the closure
plan's design — the plan deliberately re-uses the
``2026-05-12-schema-driven-wizard-adr`` parent ADR rather than
introducing a redundant ADR for a five-step cleanup.

No new findings are introduced by this closure work.

## files owned

- ``src/aeat/entrypoints/cli/test_archive_cli.py`` — module
  docstring updated from ``aeat archive`` to ``aeat app archive``
  to close the residue C1 missed

## notes

C1 through C5 land cleanly. Every second-loop reviewer finding is
addressed: N1 (stale invocation-form docstrings) is closed by C1
plus the C6 archive-cli-test sweep, N2 (cli.archive / cli.topic /
cli.app.modelo locale leak) is closed by C2's locale catalogue +
broadened audit, N3 (transient-meta phrasing reintroduced) is
closed by C3, N4 (top-level ``version`` command) is closed by
C4, N5 (wizard-caused test regressions) is closed by C5.

The wizard slice plus its revision are now ready for a third-loop
review with verdict ACCEPT.
