---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:d1c6169befc8ba50af03fdb31e8f7094d8350eeaf92a133b44eef0cfc25f87c0'
step_id: 'S393'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Retire ExternalEvidenceKind from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos

## Scope

- `src/aeat/application/modelo/__init__.py`
- `src/aeat/entrypoints/cli/_modelo_records_cli.py`
- `src/aeat/application/calculations/tests/test_modelo_130_carry_forward_continuity.py`

## Description

- Landed together with S391/S392/S394 in one commit.
- Removed `ExternalEvidenceKind` from `application.modelo`'s import block and `__all__`; `application.modelo`'s own submodules already import it directly from `domain.modelos`.
- Repointed the two real consumer sites: `entrypoints/cli/_modelo_records_cli.py` (merged into its existing `domain.modelos` import block) and `application/calculations/tests/test_modelo_130_carry_forward_continuity.py`.
- Updated the module docstring's `ExternalEvidenceKind` cross-reference (it was already fully-qualified as `domain.modelos.ExternalEvidenceKind` in this docstring, so no further change needed there beyond the added ruling-5 note).

## Outcome

Committed at `b2d425a63`. `pytest --collect-only -q src/aeat` clean immediately before commit. `python dev/import_hygiene_scan.py` confirms `ExternalEvidenceKind` no longer appears in the Family-3 findings.

## Notes

None.
