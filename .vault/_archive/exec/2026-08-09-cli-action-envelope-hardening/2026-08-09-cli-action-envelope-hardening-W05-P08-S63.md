---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:21123928d31d93021538bfe24b485b5b7f0a2fa93f02c79afece64c8a6c0ca7b'
step_id: 'S63'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Retire CadrumoError suggestion compatibility and classify the two internal bare-root validation carriers explicitly so unmigrated user-facing producers remain loud

## Scope

- `src/cadrumo/core/errors/__init__.py`
- `src/cadrumo/application/filing/_producer_snapshot.py`
- `src/cadrumo/core/_orden_anual_html.py`

## Description

- Reassess the two hygiene findings through semantic discovery and exact caller, boundary, MRO, and renderer inspection.
- Record class-local machine classifications without reparenting, registering, localizing, or restoring legacy suggestion compatibility.

## Outcome

- `CadrumoError` remains strict with no retired suggestion parameter or attribute.
- `FilingProducerSnapshotError` and `OrdenAnualHtmlParseError` now declare independent, stable bare-root classifications. Both retain `ValueError` semantics and cannot enter a `CadrumoError` envelope path.
- Exception hygiene plus producer-snapshot tests passed 38 tests. Direct rehoming validation, Ruff, format, and BasedPyright passed.

## Notes

- The Orden authority lane ran 103 tests with 102 passed. Its only failure is external registry-revision drift: `303/2023` has bounded `valid_to=2023-12-31` where the test expects an open end. No S63 source or fixture change was made.
- S63 remains open for independent review. No step closure was performed.
