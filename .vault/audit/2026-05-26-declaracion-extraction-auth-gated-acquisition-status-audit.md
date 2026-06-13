---
tags:
  - '#audit'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# Declaration Extraction Auth-Gated Acquisition Status

## Scope

Reviewed the remaining declaration-PDF acquisition rows after the convention
hardening wave:

- `W05.P18.S105` Modelo 180
- `W05.P18.S106` Modelo 190
- `W05.P18.S107` Modelo 036
- `W05.P18.S108` Modelo 369
- `W05.P18.S109` Modelo 720
- `W05.P18.S110` Modelo 840 value-bearing coverage

## Finding

The repo already carries public official record-design, BOE, and procedure
sources for these surfaces where available. Those sources are sufficient for
registry/export/layout authority but not for declaration-PDF parser label or
value round-trip proof when the plan explicitly requires a declaration PDF or
printed-form PDF fixture.

The public AEAT pages found during this pass describe electronic form,
preview, or filed-declaration flows. They do not expose taxpayer-free static
declaration PDFs equivalent to the imported Modelo 840 blank printed form.
Generating or retrieving the relevant PDFs would require one of these
gates:

- an operator-provided authorised filled fixture produced outside this
  automation session;
- an authenticated read of a previously filed declaration;

Synthetic data must not be sent to Sede or AEAT-hosted form surfaces. Live
form preview/download flows are therefore not an available acquisition path
for this work, even if the surface would technically accept arbitrary input.

## Status

No additional declaration PDF fixture was acquired in this pass. Rows
`W05.P18.S105` through `W05.P18.S110` remain open. The next execution step that
touches these rows should stop for operator authentication only when it needs
read-only access to taxpayer-specific filed declarations. It must not use live
AEAT preview/PDF generation with synthetic data.

## Authenticated Read Follow-Up

Read-only Sede listing was attempted after operator approval on 2026-05-26
through `aeat app live filed list` with `AEAT_LIVE_TESTS_ENABLED=1`. No live
write, submission, payment, or form-preview generation command was run.

Results:

- Modelo 180, years 2024-2026: `row_count=0`.
- Modelo 190, years 2024-2026: one filed row for exercise 2024, period `0A`,
  expediente `2024190003820000301503`, status `ALTA`, presented at
  `2025-03-27T20:31:00+00:00`; available surfaces were
  `submitted_file=True`, `declaration_copy=False`, `justificante=True`.
- Modelo 036, years 2024-2026: `row_count=0`.
- Modelo 369, years 2024-2026: `row_count=0`.
- Modelo 720, years 2024-2026: `row_count=0`.
- Modelo 840, years 2024-2026: `row_count=0`.

The follow-up single-row Modelo 190 capture was not completed. It failed before
artifact download because the local registry has no snapshot for exercise 2024:
`src/aeat/_data/registry/aeat/modelos/190.toml` currently declares only
revision `2025-y-siguientes` with `period_selector = { year_from = 2025,
periods = ["0A"] }`.

Legal/source grounding for the required 2024 backlog is available but not yet
registered as a 2024 revision in the model registry:

- BOE `BOE-A-2024-26484`, Orden HAC/1432/2024, modifies Orden EHA/3127/2009
  for Modelo 190. Its final provision makes the order generally applicable
  first to the Modelo 190 filing corresponding to exercise 2024 whose filing
  window starts from 2025-01-01, while expressly deferring article-unique
  section one to exercise 2025 filings whose window starts from 2026-01-01.
- The local AEAT record-design manifest already contains
  `DISENOS_LOGICOS_190-2024.pdf`, retrieved 2026-05-03, sha256
  `20bc8086525ce850063b9ae8644b8514483e5c34f90c8e47cfadc6c52cf7390e`.

Follow-up implementation closed `W05.P18.S106` and `W05.P18.S121` by adding
reviewed legal/source entries for Orden HAC/1432/2024 and AEAT DR 190-2024,
adding an observation-focused 2024 Modelo 190 registry revision, and using the
existing sanitized `src/aeat/tests/fixtures/justificantes/190/2024-0A.pdf`
fixture for parser round-trip verification. The authenticated filed row was
not captured because the sanitized fixture was sufficient to close the parser
coverage blocker without pulling taxpayer-specific Sede artifacts.

## Post-Authentication Acquisition Matrix

Rechecked the remaining open acquisition rows after the Modelo 190 closure.
This pass did not acquire, generate, or submit any live form artifact. It only
reviewed local official corpus coverage, registry source refs, fixture
presence, and the read-only Sede listing result already recorded above.

| Modelo | Open rows | Verified local authority | Local fixture state | Authenticated listing | Status | Required next action |
| --- | --- | --- | --- | --- | --- | --- |
| 180 | `W03.P06.S20`, `W05.P11.S34`, `W05.P11.S92`, `W05.P18.S105` | `aeat-dr-180-2023`, `aeat-dr-180-2014`, `boe-modelo-180-2014-form`, `boe-modelo-180-2023-form`, and AEAT procedure/help pages ground record/export and calculation surfaces. | No `src/aeat/tests/fixtures/justificantes/180/` fixture directory; corpus files are record designs, not a declaration PDF or current printed-form copy. | `row_count=0` for 2024-2026. | Blocked. | Acquire an authorised declaration PDF or official printed-form layout before authoring a `declaracion_pdf` profile or parser round-trip test. |
| 036 | `W05.P11.S36`, `W05.P11.S94`, `W05.P18.S107` | `aeat-dr-036-2025`, `aeat-modelo-036-procedure`, Orden EHA/1274/2007, Orden HAC/1526/2024, and RGAT arts. 9-11 ground the censal registry and event-period snapshots. | No `src/aeat/tests/fixtures/justificantes/036/` fixture directory; local corpus has record-design workbooks and procedure HTML, not a value-bearing printed-form PDF. | `row_count=0` for 2024-2026. | Blocked. | Wait for an operator-provided authorised printed-form/declaration fixture or read-only filed declaration artifact. Do not use live AEAT paper/PDF generation with synthetic data. |
| 369 | `W05.P11.S38`, `W05.P11.S96`, `W05.P18.S108` | `aeat-dr-369-2021`, `aeat-modelo-369-procedure`, `boe-modelo-369-2021-form`, Orden HAC/610/2021, and LIVA special-regime articles ground the OSS/IOSS registry and record-design workbook. | No `src/aeat/tests/fixtures/justificantes/369/` fixture directory; local corpus has the record-design workbook and procedure HTML, not an Esquema Union declaration PDF. | `row_count=0` for 2024-2026. | Blocked. | Acquire an authorised Esquema Union printed-form/declaration PDF fixture or read-only filed-copy artifact. Do not use live preview/download with synthetic data. |
| 720 | `W05.P11.S39`, `W05.P11.S97`, `W05.P18.S109` | `aeat-dr-720`, `aeat-modelo-720-procedure`, `boe-modelo-720-2013-form`, Orden HAP/72/2013, LGT art. 93, and RGAT foreign-asset articles ground the informative registry and export layout. | No `src/aeat/tests/fixtures/justificantes/720/` fixture directory; local corpus has a record-design PDF, not a declaration PDF with submitted or generated values. | `row_count=0` for 2024-2026. | Blocked. | Acquire an authorised declaration PDF fixture before asserting parser round-trip coverage. |
| 840 | `W05.P11.S40`, `W05.P11.S98`, `W05.P18.S110` | `aeat-dr-840`, `aeat-modelo-840-printed-form`, `boe-modelo-840-2003-form`, Orden HAC/2572/2003, TRLRHL art. 90, and the verified static AEAT form ground the printed labels already used by `W05.P18.S111`. | Static blank printed form is in corpus, but no value-bearing `src/aeat/tests/fixtures/justificantes/840/` fixture exists for parser round-trip assertions. | `row_count=0` for 2024-2026. | Partially grounded, still blocked for value-bearing coverage. | Obtain a generated/submitted declaration PDF or approved filled-form fixture before closing parser round-trip coverage. |

Conclusion: no remaining open row can be closed from the current local corpus or
the completed authenticated read. The next executable step for these rows
requires either operator-provided fixtures or read-only retrieval of an
operator-owned filed-copy artifact. Synthetic preview/download through Sede or
AEAT-hosted form surfaces is prohibited.

Operator context update 2026-05-26: the active authenticated profile is not
expected to contain filed data for the remaining special/current forms because
the operator is an autónomo and those forms are not on the operator's normal
filing schedule. Future authenticated reads may still be useful as
opportunistic read-only checks, but they are no longer the primary planned
unblocker for these rows. The practical unblocker is an operator-provided
authorised fixture, an official taxpayer-free static printed-form layout where
one exists, or a future real filed-copy artifact for a profile that legally
files the relevant model.

## No-Synthetic-Sede Follow-Up Closure

The no-synthetic-Sede constraint surfaced a cross-feature policy conflict
outside the declaration-acquisition slice. That follow-up is now closed by
`W05.P18.S124` and the accepted
`2026-05-26-no-synthetic-sede-live-surfaces-adr`.

Current state:

- Modelo 100 `modelo-100-renta-web-open` remains an `open_simulator` surface
  but declares `synthetic_data_allowed = false`.
- Modelo 349 `modelo-349-groi-spanish-counterparty-check` remains an
  `authenticated_simulator` surface but declares
  `synthetic_data_allowed = false`.
- Modelo 349 `modelo-349-ixvi-foreign-counterparty-check` remains an
  `authenticated_simulator` surface but declares
  `synthetic_data_allowed = false`.
- Direct outbound GROI and NIF-IVA Sede guard policies now also declare
  `synthetic_data_allowed = false`.

The remaining acquisition rows still require authorised real fixtures or
read-only filed artifacts. Synthetic preview/download through Sede or
AEAT-hosted form surfaces remains prohibited.
