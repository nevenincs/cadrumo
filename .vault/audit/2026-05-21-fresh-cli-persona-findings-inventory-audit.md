---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-21-fresh-cli-persona-testimonials-audit]]'
  - '[[2026-05-21-fresh-cli-persona-testimonial-wave-plan]]'
---

# Fresh CLI persona findings inventory

Coordinator inventory for the fresh persona wave.

## Verified Findings

| ID | Severity | Finding | Evidence | Disposition |
|---|---|---|---|---|
| FRESH-001 | major | Direct S.L. profile creation misparses `--legal-entity-form sl` as an IRPF income category | `config profile create ... --entity-type legal_entity --legal-entity-form sl` exits with `Valor no reconocido para Categorías de renta IRPF: sl` | repair plan |
| FRESH-002 | major | `casillas --form-number 69` does not match Modelo 303 casilla number 69 | unfiltered computed list includes `iva.resultado 69`; filtered command returns only header | repair plan |
| FRESH-003 | major | Export recovery hint points to nonexistent `aeat app modelo verify` | export refusal says `Ejecuta aeat app modelo verify primero`; actual command is under `work verify` | repair plan |
| FRESH-004 | major | Manual/source explainability is not discoverable by the expected `app manual` route | `aeat app manual --help` exits with `No such command 'manual'` | capability plan |
| FRESH-005 | major | Legal/source ids have no obvious CLI drill-down from formula output | `formulas --explain` emits ids such as `ley-37-1992:art-99` and `aeat-dr-303-2025` without title/link/detail expansion | capability plan |
| FRESH-006 | major | Modelo 111 practical required-input guidance is missing | `casillas 111 --required` returns only headers while operators still need retention bucket guidance | capability plan |
| FRESH-007 | major | Profile-filtered obligation explanation is not explicit enough | personas inferred applicability from model creation/listing rather than an `applies because` explanation | capability plan |
| FRESH-009 | blocker | Global legal-corpus validation blocks focused modelo CLI reruns | `formulas 111 --period 1T --explain` and `casillas 111 --required` fail before command execution because Ley 37/1992 articles 94, 95, 122, 123, and 124 have registry references without corpus files | repair plan |
| FRESH-010 | major | Source-reference drill-down remained too generic after legal drill-down repair | focused rerun found `source_ref_command` only pointed to `aeat app registry manuals list` for `aeat-dr-303-2025` and `boe-modelo-303-2008-form` | repair plan |
| FRESH-011 | local-state blocker | Shared profile readiness can be blocked by an undecryptable stored draft object | focused rerun of `modelo readiness 111` failed on `aeat.domain.filing.drafts/#340` with recovery `aeat config repair integrity objects` | triaged as local state integrity, not Modelo 111 logic |

## Needs Investigation

| ID | Severity | Finding | Evidence | Coordinator Status |
|---|---|---|---|---|
| FRESH-008 | retired and guarded | `SecureObjectUnreadable` import error reported across work create/calculate/verify/list paths | five personas reported the same internal import error | not reproduced in isolated coordinator smoke; public SQL export now has a regression guard |

## Repair Wave P01 Update

- FRESH-001 was rechecked through the real CLI and the existing
  regression test `test_legal_entity_form_flag_populates_the_legal_entity_form_field`.
  Direct S.L. creation now succeeds, so the finding is treated as
  stale/transient and guarded rather than newly patched.
- FRESH-002 is fixed: `casillas --form-number` now also matches the
  printed numeric `number` column, so Modelo 303 casilla 69 is returned.
- FRESH-003 is fixed: export recovery now points to
  `aeat app modelo work verify`.

## Repair Wave P02 Update

- FRESH-005 and FRESH-006 have focused regression coverage and passing
  command-level tests for formula drill-down hints, Modelo 111 empty
  required-casilla guidance, and readiness scope wording.
- FRESH-009 was discovered during the real CLI rerun for the same P02
  surfaces. It blocks focused persona reproduction until the missing
  legal corpus entries are restored or explicitly retired from the
  registry.
- FRESH-005 is fixed through `aeat app registry legal view REF` and
  `formulas --explain` now emits that command for each calculation
  `legal_ref`.
- FRESH-006 is fixed with guidance rows for the Modelo 111 structural
  empty required-casilla set.
- FRESH-009 is fixed: registry verification passes and the focused
  Modelo 111/303 CLI reruns execute after the Ley 37/1992 corpus files
  are present.

## Focused Rerun Update

- FRESH-010 is fixed through `aeat app registry sources view REF`.
  `formulas --explain` now emits that command for source refs such as
  `aeat-dr-303-2025`.
- FRESH-011 was triaged with an isolated readiness smoke. In a clean
  `AEAT_LOCAL_STORAGE_ROOT`, `modelo readiness --modelo 111
  --revision-id 2019-y-siguientes --year 2026 --period 1T` reports the
  intended readiness scope and `ready True`. The shared-profile failure
  is an existing secure-object integrity condition with an actionable
  repair command, not a Modelo 111 readiness regression.

## Repair Wave P03 Update

- FRESH-008 is retired as an already-fixed import-boundary break. The
  current public import `from aeat.adapters.persistence.storage.sql import
  SecureObjectUnreadable` succeeds.
- Isolated smoke in `AEAT_LOCAL_STORAGE_ROOT=var/tmp/fresh-p03-secure-smoke-seq`
  exercised `filing-record list`, `verification-report list`, `work
  create`, `work calculate`, `work verify`, and `work list` without the
  reported import error. `work verify` refused on draft readiness rather
  than crashing.
- Added a focused public-surface guard so `SecureObjectUnreadable` remains
  exported from the SQL package surface.

## Confirmed Non-Defects Or Lower-Risk Friction

- Modelo 130 calculation and verification completed cleanly when required
  bindings were supplied.
- Modelo 303 creation and calculation completed cleanly in coordinator
  reproduction.
- `filing-record list` and `verification-report list` returned normal
  empty listings in coordinator reproduction.
- Profile creation missing `--activity` is a usable refusal; the recovery
  message names the missing flag.

## Coordinator Reproduction Commands

- `uv run aeat config profile create coord --quiet --accept-defaults --tax-id 12345678Z --name Coord --surnames Tester --activity consultoria --iva-regime GENERAL --irpf-estimation-regime directa_simplificada --tax-residence-ccaa madrid`
- `uv run aeat app modelo work create --modelo 303 --year 2026 --period 1T --revision 2009-y-siguientes --name "Coord 303" --by coord`
- `uv run aeat app modelo work calculate 82a4a70ceb7e5f72b334f8a303f6103f638d068eaec709c12514ed3a440075e7 --by coord`
- `uv run aeat app modelo work verify a620f2633ad83c7723aacc9f61a62437d313484601f9e32496808b672fe318e4 --by coord`
- `uv run aeat app modelo filing-record list`
- `uv run aeat app modelo verification-report list`
- `uv run aeat app modelo casillas 303 --period 1T --form-number 69`
- `uv run aeat config profile create bruno-sl --quiet --accept-defaults --tax-id B12345674 --activity "Consultoria informatica" --entity-type legal_entity --legal-entity-form sl`
- `uv run aeat app manual --help`
- `uv run aeat app modelo casillas 111 --required`
