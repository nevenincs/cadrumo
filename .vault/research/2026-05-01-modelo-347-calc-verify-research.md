---
tags:
  - '#research'
  - '#modelo-347-calc-verify'
date: '2026-05-01'
related:
  - "[[2026-04-21-declaracion-extractor-research]]"
  - "[[2026-04-21-calc-verification-research]]"
  - "[[2026-04-27-modelo-390-calc-verify-research]]"
---

# `modelo-347-calc-verify` research: `tier-s per-counterparty summary parity`

Issue `#330` is the Tier-S calc-verify delegation for Modelo 347 under EPIC `#316`. This research covers the BOE-cited per-counterparty schema for ejercicios 2024 / 2025 / 2026, resumen totals casillas for parity, historical schema deltas, the current declaration-extractor MVP, verifier API fit, and the round-trip identity patterns already used by Modelo 111 and Modelo 390.

## Findings

## Modelo 347 in one paragraph

Modelo 347 is the annual informative return for operations with third parties. It is not a liquidation and does not produce an amount to pay or refund. Its verification invariant is therefore not a formula-ruleset invariant; it is a data-integrity invariant: every BOE-required per-counterparty record printed in the declaration must be extracted, and the sums of those records must equal the printed resumen totals to within the one-cent tolerance used elsewhere in the verification surface.

The current issue text is accurate: Tier-S should pass on per-counterparty schema plus resumen-totals parity, not on a synthetic formula ruleset.

## Primary sources reviewed

| Source | Evidence used |
| :--- | :--- |
| AEAT 347 logical design PDF, `https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_300_399/archivos/347.pdf` | Current official design for `Ejercicio 2025 y siguientes`; type 1 declarante resumen, type 2 declarado, type 2 inmueble. |
| BOE consolidated Orden EHA/3012/2008, `https://www.boe.es/buscar/act.php?id=BOE-A-2008-16973&p=20181031&tn=1` | Approves Modelo 347, its form parts, logical designs, presentation forms, and February filing window. |
| AEAT instructions, `cumplimentacion.html` | Human-facing field semantics for resumen, declared parties, operation keys, cash, annual and quarterly amounts. |
| AEAT instructions, `desglose.html` | Confirms quarterly breakdown is general rule; cash, cash-accounting IVA, and property-horizontal entities are annual-basis exceptions. |
| AEAT previous-years page, `ejercicios-anteriores.html` | Confirms 2024 remains a distinct previous-year presentation surface while 2025 current instructions are published and page-updated 2026-02-01. |
| AEAT historical logical design PDF, `ant_300_399/archivos/DLogicos_Registros_347.pdf` | Captures the pre-cash-accounting type-2 declared-record shape ending at position 264-500 blank. |

## BOE / AEAT schema: type 1 resumen

The 2025-and-following logical design states that each declarant has one type-1 record and as many type-2 records as declared parties and rented properties. Type 1 is the declarante identity plus declaration summary. The project-facing resumen casillas needed for parity are:

| Casilla / type-1 concept | Meaning | Parity source |
| :--- | :--- | :--- |
| `01` | Number of persons/entities related as declared parties. If the same declared party appears in several records, it is counted as many times as records. | Count type-2 declarado rows with operation keys `A` through `G`. |
| `02` | Total annual amount of related operations. | Sum `importe_anual_operaciones` over type-2 declarado rows with operation keys `A` through `G`. |
| `03` | Number of cash-collection records. | Count declared-party rows where `importe_percibido_metalico` is present / non-zero above the 6,000 euro reporting rule. |
| `04` | Total cash collected. | Sum `importe_percibido_metalico` over declared-party rows. |
| Rented-property count | Number of type-2 inmueble rows. | Count type-2 inmueble rows. |
| Rented-property total | Total local-business-rent operation amount. | Sum `importe_operacion` over type-2 inmueble rows. |

The existing 347 extractor only covers casillas `01` through `04`. Issue `#330` only names per-counterparty rows plus resumen totals; rented-property rows should be explicitly decided in the ADR because the BOE form treats them as a separate type-2 record family, while the current issue success moment says "per-counterparty record line".

## BOE / AEAT schema: type 2 declarado record

For ejercicios 2025 and following, the official 500-position type-2 `REGISTRO DE DECLARADO` record contains the following project-facing fields. A Pydantic model named `Modelo347RecordLine` should model these, with monetary fields as `Decimal`, year fields as `int`, flags as `bool` or constrained enum, and closed catalogues as `StrEnum`.

| Field | BOE positions | Suggested type | Notes |
| :--- | :--- | :--- | :--- |
| `tipo_registro` | 1 | literal `"2"` | Constant type-2 record. |
| `modelo` | 2-4 | literal `"347"` | Constant model code. |
| `ejercicio` | 5-8 | `int` | Same as type 1. |
| `nif_declarante` | 9-17 | constrained `str` | Same as type 1. |
| `nif_declarado` | 18-26 | constrained `str | None` | Spanish NIF only; incompatible with EU VAT operator field. |
| `nif_representante_legal` | 27-35 | constrained `str | None` | Only for declared minors under 14. |
| `nombre_razon_social_declarado` | 36-75 | constrained `str` | Person surname/name order or full legal name. |
| `provincia_codigo` | 76-77 | enum / constrained `str` | Spanish province code; non-resident without PE uses `99`. |
| `pais_codigo` | 78-79 | ISO-like constrained `str | None` | Used for non-residents. |
| `clave_operacion` | 80 | enum `A`..`G` | AEAT instructions map them to purchases, sales, third-party collections, public/private-social acquisitions, public subsidies, travel-agency sales, travel transport purchases. |
| `operacion_seguro` | 81 | `bool` | Insurance entities mark separately. |
| `arrendamiento_local_negocio` | 82 | `bool` | Local-business rental operations, separately declared. |
| `importe_percibido_metalico` | 83-98 | `Decimal | None` | Annual cash collections above 6,000 euros; signed subfield in the logical design but global note says all amounts are positive. |
| `importe_anual_operaciones` | 99-114 | `Decimal` | Annual total operations with the declared party, except records that must be separated. |
| `importe_anual_transmisiones_inmuebles_iva` | 116-131 | `Decimal | None` | Annual amounts received for IVA-subject real-estate transfers. |
| `ejercicio_origen_metalico` | 132-135 | `int | None` | Fiscal year where operations giving rise to cash collection were declared. |
| `importe_operaciones_1t` | 136-151 | `Decimal | None` | General quarterly amount; blank for property-horizontal entities and cash-accounting special cases. |
| `importe_transmisiones_inmuebles_iva_1t` | 152-167 | `Decimal | None` | First-quarter IVA-subject real-estate transfer amount. |
| `importe_operaciones_2t` | 168-183 | `Decimal | None` | Second-quarter amount. |
| `importe_transmisiones_inmuebles_iva_2t` | 184-199 | `Decimal | None` | Second-quarter real-estate transfer amount. |
| `importe_operaciones_3t` | 200-215 | `Decimal | None` | Third-quarter amount. |
| `importe_transmisiones_inmuebles_iva_3t` | 216-231 | `Decimal | None` | Third-quarter real-estate transfer amount. |
| `importe_operaciones_4t` | 232-247 | `Decimal | None` | Fourth-quarter amount. |
| `importe_transmisiones_inmuebles_iva_4t` | 248-263 | `Decimal | None` | Fourth-quarter real-estate transfer amount. |
| `nif_operador_comunitario` | 264-280 | structured value / `str | None` | EU country code plus VAT number; incompatible with `nif_declarado`. |
| `operaciones_criterio_caja_iva` | 281 | `bool` | Identifies cash-accounting IVA operations. |
| `operacion_inversion_sujeto_pasivo` | 282 | `bool` | Recipient-side reverse-charge operation per LIVA art. 84.Uno.2. |
| `operacion_deposito_distinto_aduanero` | 283 | `bool` | Goods linked to non-customs warehouse regime. |
| `importe_anual_criterio_caja_iva` | 284-299 | `Decimal | None` | Annual amount accrued under cash-accounting IVA criteria. |
| `numero_convocatoria_bdns` | 300-305 | constrained `str | None` | Only when `clave_operacion == "E"`. |

The current 2025+ design leaves 306-500 blank for this record. Every parser/generator should retain the distinction between absent blank fields and zero-valued numeric fields, because the AEAT instructions impose blank quarterly fields for cash-accounting and certain property-horizontal cases.

## Rented-property type-2 record

The 2025+ design also defines a separate type-2 `REGISTRO DE INMUEBLE` with `tipo_hoja == "I"`. Its fields include renter identity, annual rent amount, property situation key, cadastral reference, and a full address decomposition. This is not the same as a declared-party row. It matters for resumen parity only if the implementation includes rented-property count/total in scope. If issue `#330` remains strictly per-counterparty, the research recommendation is to leave inmueble extraction out of the first implementation and document a waiver/gap; if the ADR interprets "all BOE-required fields" as the full Modelo 347 record family, then `Modelo347RecordLine` is insufficient and a sibling `Modelo347InmuebleLine` is required.

## 2024 / 2025 / 2026 schema deltas

Conclusion: use the 2025+ logical design for 2025 and 2026; verify 2024 against the previous-year AEAT surface before implementing the extractor class. The current source explicitly says `Ejercicio 2025 y siguientes`, while AEAT exposes 2024 under `Ejercicios anteriores`.

Known historical deltas from official evidence:

| Period | Evidence | Impact |
| :--- | :--- | :--- |
| 2008 approval | BOE Orden EHA/3012/2008 approves Modelo 347 and the type-1 / type-2 logical design. | Establishes the record families and annual informative-return shape. |
| 2011 redesign | Historical BOE-A-2011-19397 logical-design PDF shows type-2 declared fields through quarterly amounts and then 264-500 blank. | Pre-cash-accounting record does not contain positions 264-305 now used by EU operator, cash-accounting, reverse-charge, non-customs warehouse, and BDNS fields. |
| 2014 first application | BOE consolidated note says the 2014 substitution applies first to informative returns corresponding to ejercicio 2014. | Cash-accounting / special flags are part of modern 347 before 2024. |
| 2025+ current design | AEAT current design PDF is labelled `Ejercicio 2025 y siguientes`. | 2025 and 2026 should be treated as structural siblings unless AEAT publishes a newer design. |
| 2024 previous-year surface | AEAT previous-years page exposes separate 2024 presentation and file-presentation links. | 2024 may share the same modern layout, but the implementation should anchor it against the 2024 downloadable/presented template or explicitly document that 2024 is assumed identical after manual inspection. |

No evidence found in the reviewed official sources that the 3,005.06 euro third-party threshold changed for ejercicios 2024, 2025, or 2026. The issue note "umbral cambió históricamente" should be preserved in the rule-delta manifest as historical context, but not treated as a 2024-2026 schema delta unless a BOE amendment is found.

## Current codebase state

The current implementation has a minimal 347 declaration extractor:

| Surface | Current state |
| :--- | :--- |
| `Modelo347V2025Extractor` | Registered only for template revision `(347, 2025, 2025.01)`. |
| Extracted casillas | `01`, `02`, `03`, `04` only. |
| Per-counterparty rows | Not extracted. The module docstring says per-counterparty detail lands in a later full scope, but issue `#330` now makes it the core requirement. |
| 2024 / 2026 extractor registration | Missing for Modelo 347. By contrast, Modelo 111, 115, 123, 130, 180, 303, and 390 have sibling year classes. |
| Ruleset | None, correctly absent for an informative return if Tier-S is implemented as parity rather than formulas. |
| Integration coverage | `docs/coverage/modelos.md` marks 347 as partial / MVP only; no 347 Kent import class exists in `tests/integration/test_kent_workflows.py`. |

The generic extractor is line-anchored around numbered casilla rows. That shape is suitable for the four resumen casillas, but it is not suitable for multi-column or table-like per-counterparty records. A 347 implementation likely needs a bespoke extractor that reads either structured table text or a generated fixture layout designed around row objects.

## Verifier API suitability

`verify_declaracion` currently requires a `Ruleset | None`. When `ruleset is None`, it returns `UNVERIFIABLE`. That behavior is correct for unknown formula-bearing modelos but wrong for Modelo 347 Tier-S, where there is no ruleset by design and the desired success state is `VERIFIED`.

Recommended verifier shape:

| Option | Fit |
| :--- | :--- |
| Add a fake formula ruleset for 347 | Reject. It would encode sums as formulas over synthetic casillas, obscure the record-line source of truth, and make tests tautological if the same projection produces rows and resumen. |
| Extend `verify_declaracion` with summary-return dispatch | Acceptable if the declaration schema can carry structured record lines alongside casillas. It preserves one CLI verification surface. |
| Add `verify_summary_declaracion` or `_verify_summary.py` | Best fit. A small pure helper can accept parsed `Modelo347Declaration` data, sum rows, compare to resumen fields, and return the existing `VerificationVerdict` schema with `ruleset_id=None` but status `VERIFIED` / `NEEDS_REVIEW`. |

The discrepancy classifier must be extended rather than reused verbatim. Existing `DiscrepancyCause.CORRECTNESS_DIVERGENCE` can represent material row-vs-resumen mismatch, and `EXTRACTION_UNRELIABLE` can represent low-confidence row extraction. A new cause such as `SUMMARY_PARITY_MISMATCH` would be clearer, but would expand the public enum; the ADR should decide whether enum churn is acceptable.

The reconciliation API under `aeat.application.filing.reconciliation` is not the right layer. Its own code documents that it compares only justificante metadata and totals printed on AEAT receipt PDFs, not declaration per-casilla or per-record content.

## Round-trip identity pattern from M111 / M390

The current Kent integration pattern is:

- Define a label map and a happy-path value map in `tests/integration/test_kent_workflows.py`.
- Render a synthetic L3 PDF with `QuarterlyGenParams` through the generic generator.
- Parse through `aeat filing import --from-declaracion`.
- Assert stable CLI markers: extraction status, verification status, optional cause token, and casilla id.
- For discrepancy cases, tamper only the printed value that should break a real invariant, not both sides of an invariant.

Modelo 111 uses `_M111_HAPPY` with formula-backed casillas `09`, `12`, `28`, and `30`. A drifted casilla such as `09` produces `NEEDS_REVIEW` and a `CORRECTNESS_DIVERGENCE`.

Modelo 390 uses `_M390_HAPPY` and `_synth_annual_pdf`, which is just the generic quarterly generator with `period_printed="0A"`. Its annual invariant is formula-backed for `104`, `105`, `190`, `191`, `192`, and `193`; the cumulation test separately demonstrates how four Modelo 303 quarterly maps can sum into annual 390 values.

Modelo 347 should follow the same test ergonomics but not the same scalar-only generator. The useful identity is:

`records + resumen -> generated PDF -> extractor -> records + resumen -> summary verifier`

The test data must avoid tautology by building resumen expectations independently from the rendered summary block in at least one test:

| Test | Non-tautological invariant |
| :--- | :--- |
| Happy path | Records are generated from a typed record list; resumen block is generated from an independently computed sum; extractor output equals original record list and verifier returns `VERIFIED`. |
| Tampered resumen | Same records are rendered, but resumen `02` or `04` is altered by 0.02 or more; extractor still returns the original records, verifier returns `NEEDS_REVIEW`. |
| Tampered row | Summary remains correct for original records, but one row amount is altered; extractor returns altered records and verifier returns `NEEDS_REVIEW`. |
| Partial / low-confidence extraction | Omit or duplicate a row label/identifier in the PDF; extractor emits warnings and verifier returns `NEEDS_REVIEW`. |
| Per-year classes | 2024 / 2025 / 2026 synthetic PDFs select their registered extractor class and produce the same parity outcome. |

## Recommended implementation path for the subsequent ADR / plan

- Model the declaration as a structured 347-specific payload rather than flattening row fields into fake casillas.
- Add `Modelo347RecordLine` for the type-2 declarado schema and decide separately whether `Modelo347InmuebleLine` is in issue `#330` scope.
- Add year sibling extractors for 2024, 2025, and 2026. Treat 2025 and 2026 as structural siblings; require explicit 2024 source anchoring or a waiver before claiming 2024 parity.
- Keep no formula ruleset for Modelo 347. Tier-S summary verification should return `VerificationVerdict` with `ruleset_id=None` and `VERIFIED` when parity holds.
- Implement the verifier as a dedicated summary/parity helper and have the CLI dispatch to it for Modelo 347 after declaration extraction.
- Extend the L3 generator with row support; avoid deriving expected test assertions from extractor output.
- Preserve one-cent tolerance for monetary parity, matching existing verification behavior.

## Open questions for ADR

- Is `REGISTRO DE INMUEBLE` inside issue `#330`, or explicitly deferred? BOE includes it in Modelo 347 type-2 records, but the issue success moment says per-counterparty rows.
- Should a new discrepancy cause be added for `SUMMARY_PARITY_MISMATCH`, or should parity failures reuse `CORRECTNESS_DIVERGENCE`?
- Should 2024 be implemented from a confirmed previous-year design artifact, or accepted as a modern-design sibling with an explicit rule-delta waiver?
- Should the extraction schema live under `aeat.adapters.inbound.declaracion` only, or should a public application-level `Modelo347Declaration` be introduced so `aeat.application.verification` does not depend on adapter-private details?
