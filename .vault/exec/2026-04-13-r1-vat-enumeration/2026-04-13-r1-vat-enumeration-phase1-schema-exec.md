---
name: r1-vat-enumeration-phase1-schema
description: Execution record for phase 1 — schema, errors, settings, env alignment.
type: exec
tags:
  - "#exec"
  - "#r1-vat-enumeration"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-r1-vat-enumeration-plan]]"
  - "[[2026-04-13-r1-vat-enumeration-adr]]"
---

# r1-vat-enumeration phase 1 — schema

## what was done

- Created `src/aeat/domain/financial/__init__.py` as a minimal subpackage
  root (docstring + empty `__all__`). No cross-subpackage re-exports.
- Created `src/aeat/domain/financial/vat/_schema.py` with strict pydantic v2
  base classes `_StrictFrozen` / `_StrictMutable`, the four closed
  enumerations (`VATCategory` 16 members, `EUMemberState` 27 members,
  `VATRateKind`, `CitationSource`) and the `VATRate`, `Citation`,
  `VATRegulation`, `VATCatalogue`, `VerificationIssue`,
  `VerificationReport` models. Trilingual invariants enforced by a
  `_require_spanish` helper called from an `after`-mode model
  validator.
- Created `src/aeat/domain/financial/vat/errors.py` with the `VatError`
  hierarchy rooted at `aeat.core.errors.AeatError`.
- Added `aeat_vat_catalogue_root: Path` to `src/aeat/config.py` and
  the matching `AEAT_VAT_CATALOGUE_ROOT=corpus/financial/vat` entry
  to `env/.env.example`.

## files touched

- `src/aeat/domain/financial/__init__.py` (new)
- `src/aeat/domain/financial/vat/__init__.py` (new — see phase 2)
- `src/aeat/domain/financial/vat/_schema.py` (new)
- `src/aeat/domain/financial/vat/errors.py` (new)
- `src/aeat/config.py`
- `env/.env.example`

## gate results

Deferred to end-of-feature consolidated run — see the phase-1 summary.
