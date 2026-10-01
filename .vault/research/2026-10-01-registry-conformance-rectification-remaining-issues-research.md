---
tags:
  - '#research'
  - '#registry-conformance-rectification'
date: '2026-10-01'
modified: '2026-10-01'
body_schema: 'body-v2'
body_hash: 'sha256:4a566600325998046c30fb4496202a64c80cf2a9d05786f503620cf9d02dff0f'
related:
  - "[[2026-09-27-registry-conformance-rectification-plan]]"
  - "[[2026-09-27-registry-conformance-rectification-research]]"
---
# `registry-conformance-rectification` research: `remaining registry issues`

The remaining filing and historical-coverage risks were investigated against current authored data and official sources on 2026-10-01. The initial Modelo 200 measurement found distinct official concepts mapped to a single bare casilla ID; Modelo 190's 2025 totals still use Modelo 111 instead of its own records; Madrid coverage needs a consumer correction as well as historical evidence. The 2023 agraria reduction is supported at 15%. The Modelo 100 documentation example still has a valid Modelo 130 relation. The operator directed repair with the support floor and capability preserved. The confirmed Modelo 200 collisions below have now been repaired and published; the larger candidate inventory remains under adjudication.

## Findings

### Modelo 200's 2025 mapping debt reaches the generated filing layout

The canonical loader, semantic-map loader and official record-design parser were used together. Captured modelo, mapping, design and compiler inputs stayed stable during measurement. The current 2025 AEAT workbook was downloaded from its enrolled URL: 11,527,168 bytes, SHA-256 `92392cdb46d8e7c7f6e4e6477306570e15edfd64d5ea3e6d631e5cf847dd5509`, identical to the held corpus. The debt is not explained by a newer workbook. Its source identity is enrolled at `src/cadrumo/_data/registry/aeat/legal/is.toml:1661`.

Pre-repair measurement (the generated 2024 target was not yet installed):

| Edition | Bare IDs used on multiple sheets | Text mismatches needing adjudication | On liquidación sheets | Also in generated layout | Raw references needing canonical normalization |
| --- | --- | --- | --- | --- | --- |
| 2024 | 763 | 2,022 | 133 | 0 | 180 |
| 2025-y-siguientes | 763 | 2,015 | 130 | 2,015 | 0 |

The 2025 text mismatches comprise 1,897 differing descriptions, 116 possible echoes and two cases without an identified home description. These are candidates, not a count of proven errors. Description equality was normalized for accents, punctuation and printed box tokens; an echo-pattern match does not establish legal identity.

Three distinct-concept collisions are independently clear from the official workbook. On DP200001, 00004, 00005 and 00006 are entity-character flags; on DP200012 they denote, respectively, an Impuesto Complementario adjustment and the increases/decreases for vehicle and charging-point free depreciation. Before repair, each pair shared one input ID. For 00004, the source anchors are DP200001 row 37, ordinal 32, offset 171, length 1, and DP200012 row 14, ordinal 9, offset 64, length 17. The pre-repair mappings named the same `00004` at `dev/registry/mappings/modelo_200/2025/0002-dp200001.toml:413` and `dev/registry/mappings/modelo_200/2025/0015-dp200012.toml:114`. That shared input could not independently represent those two concepts.

The cross-sheet detector previously ignored casillas with no segmento, and explicitly listed three unresolved 00501/00573 equity collisions. Those six independently confirmed collisions have now been repaired: five existing home identities are sheet-qualified, three distinct equity cells are authored once at the 2022 floor, and three distinct tax-adjustment cells are authored once at their first evidenced year. Later editions contain only source/evidence differences. Genuine applied-total echoes are retained. Coupled formula, verification, completeness, construct and application references were updated together.

The six concepts were checked against every held supported design through the canonical parser. The regenerated targets pass the real target validator at each edition's existing capability. The alleged 180 undeclared 2024 IDs were raw, unpadded mapping references: the canonical semantic join resolves them to existing padded IDs. Both complete joins passed; no duplicate casillas were authored for them. The 2024 sign failure was reproduced, then repaired using its own DP200014B notes at A102 and A106 and the signed-cents statement at DP200001!A121. The analogous DP200019 applicability pointer was grounded at A239. This correction preserves the official sign, scale and width.

The generic Modelo 200 converter's fresh proof, apply and no-op cycle reports complete assessment, effective equivalence, minimal authoring and no changed files, with zero redundant overrides, unresolved duplication or blocked revisions. Both targets were installed through the transactional publication owner and reproduced as current. Packing and first-appearance corrections were validated and installed; an independent typed comparison preserves the relative order and other content of every existing member in all four editions. The initial generation `fbeff3c9` is historical evidence. Corrected generation `a5b486f5643d41213afedaf47c2cabd72eff5c02f0939149537921b234fea530` was published before the replacement pytest run. A subsequent concurrent main merge changed compiler inputs, so publication and affected acceptance checks are being repeated before final currency is claimed.

Post-repair measurement uses the complete canonical semantic join, including the 180 normalized map references in the earlier design. Its denominator differs from the earlier raw-map screen; count changes alone do not measure repaired errors.

| Edition | Mapped cells | Bare identities across sheets | Text candidates | On liquidación sheets | Present in generated layout |
| --- | --- | --- | --- | --- | --- |
| 2024 | 5,473 | 769 | 2,048 | 130 | 2,048 |
| 2025-y-siguientes | 5,549 | 760 | 2,012 | 127 | 2,012 |

The canonical joins pass at the retained calculation and filing grades respectively. The current candidate worklist retains sheet, source row, export field, casilla, printed description, label and screening classification. Each candidate still needs official concept adjudication; applied totals are not independent concepts merely because their descriptions differ. Receipts and the detailed worklist are in `C:/Users/hello/AppData/Local/Temp/modelo200-repair-01-10-2026-6ad7ab369bcf4d3d883bd8e7f21ae2a0/final-mapping-inventory.json` and `final-mapping-suspects.tsv`.

The next paired-context checks can start with `aeat-dr-200-2025` DP200014B rows 70, 71 and 62. They print administrative-criterion discrepancy total 00031, its Estado amount 00032 and I+D+i abono Estado amount 00083, while their bare declarations are labelled capital-risk entities, regional industrial-development companies and emerging-company reduced-rate flags. These are explicit source/label pairs in the worklist, rather than an unexplained aggregate count. Confirm both official homes and each supported design's first appearance before authoring their independent identities; a latest-design match alone does not establish the baseline year.

The new tests discover years from the canonical legal support range and select baseline, delta and projected contexts through temporal authority. They inspect independent bytes from the published authority, including both flag-only and adjustment-only inputs and differently valued equity cells sharing a printed number. The complete broader run recorded 9,592 passes and 13 failures; introduced packing/origin omissions and stale fixtures were repaired, while the whole-catalogue literal legal-anchor ratchet remains visible at 82 against its 79 ceiling. The subsequent focused acceptance recorded 304 passes and one failure: the new calculation-grade tree correctly refuses the test's requested filing grade. The corrected test derives exact expected refusals from declared capability and requires filing-grade targets to pass full check mode. All 12 affected generated-target checks and 12 published-store/runtime checks pass. The 29 historical/corpus checks and final exhaustive Modelo 038 window case pass, and eleven historical-test type errors are corrected through assertions on actual support and corpus values. Full type, style and format checks pass without casts or ignores. Actual receipts are recorded in the execution ledger. P05.S50 remains open for the larger candidate inventory.

### Modelo 190's 2025 formulas implement the questionable 111 fold

Hydrated 2025 `modelo-190-percepciones-total` sums nine `modelo-190-111-*` bindings, while `modelo-190-retenciones-total` copies `modelo-190-111-retenciones-anual`. Their overrides are at `src/cadrumo/_data/registry/aeat/modelos/190/revisions/2025-y-siguientes/revision.toml:1189` and line 1196. The 2022 baseline already has row-derived versions at `src/cadrumo/_data/registry/aeat/modelos/190/revisions/2022/formulas/0001-declarations.toml:13`.

AEAT's current 2025 instructions, page 5, define boxes 02 and 03 over every declared perception record, including the specified incapacidad amounts and signed reimbursements. The instructions also include income without an effective withholding. They do not establish blanket equality with four Modelo 111 filings. This is a formula-grounding gap, not merely an unused dependency. Before repair, trace the retained perceptor-row bindings and reconciliation separately; detector cases should include an exempt perception, incapacidad amounts and a negative reimbursement. This investigation did not execute a counterexample through the filing engine.

### Madrid's missing years require a consumer change and cohort-specific rules

AEAT's 2022 and 2023 Madrid help pages are publicly available. The 2022 page specifies 600 euros and the birth/adoption year plus two following periods. The 2023 page distinguishes births/adoptions from 2023 (721.70 euros, with updated income limits) from 2021/2022 cohorts (600 euros and earlier limits). An earlier cohort can remain eligible in a later filing year, so applying one new amount to every eligible child would overstate that carry-in.

The live applicability fact still contains the single scalar year 2025 at `src/cadrumo/_data/registry/aeat/facts/0108-madrid-nacimiento-adopcion-applicability.toml:6`. The consumer compares `filing_year == declared_year` at `src/cadrumo/application/modelo/profile_binding.py:1039`. Changing that scalar to 2022 alone would transfer the exclusion to other years. The legal entries for arts. 4 and 18 still use a 2025 manual and a 2023 effective boundary at `src/cadrumo/_data/registry/aeat/legal/irpf-autonomica-madrid.toml:44`.

Follow-up must capture and enroll the historical sources, ground the historical legal redactions, select eligibility from canonical temporal authority, and represent the birth/adoption cohort where amounts and limits differ. Existing family tests use a 2025 authority context; their generic three-period arithmetic is not proof of historical authority coverage (`src/cadrumo/domain/contribuyente/tests/test_madrid_nacimiento_adopcion.py:32`). No source or filing grade was extended here.

### The 2023 agraria reduction is supported at 15%

Orden HAC/348/2024 art. 2 explicitly increases the 2023 general reduction for Anexo I activities to 15%. AEAT's 2023 novedades page confirms the increase from 10% to 15%. This supports the current implementation despite the older percentage in its worked example. The registry's citation is at `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/revision.toml:9025`, and the existing test explains the example discrepancy at `dev/registry/tests/test_modelo_100_eo_agraria_engine_ordenes_2022_2024.py:22`. The evidence does not support changing the engine to 10%.

### S52 should retain the supported Modelo 130 relation example

The current 2025 Modelo 100 still inherits `renta-modelo-130-pagos-fraccionados`: `relation_prefill`, `cross_model_output`, `instalment_to_final_settlement`, summing Modelo 130 box 19 for the four quarters. Its baseline declaration is at `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/bindings/0001-declarations.toml:24`. The documentation contract supplies that binding, not a withdrawn annual-summary relation (`docs/_sequences/contracts/how-to/review-calculation-values/review-values-relation.seq:7`). Removing the example solely because annual-summary relations were withdrawn would discard a supported use case. Regenerate and replay it against the final authority before deciding whether any expectation needs correction. The sequence was subsequently regenerated through the owning generator and replayed successfully, with the supported Modelo 130 relation preserved. Final currency is rechecked after publication of the corrected authority.

### The 151 cutoff remains unresolved after checking the general extension rule

The 2022 window intentionally has no payment cutoff. Its source comment identifies June 25 in Orden HAP/2783/2015 art. 4.2 and June 27 in AEAT's 2023 calendar (`src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/deadline_windows/0001-declarations.toml:12`). The historical June 2023 redaction of Orden EHA/1658/2009 still states June 25 for 151. Its art. 3.2.b extends a domiciliation deadline when the declaration's presentation deadline is extended for a nonworking day; June 30, 2023 was a Friday. That provision alone does not establish the calendar's two-day difference. A specific exception or authoritative clarification is still needed; no date was guessed.

### The other decision items remain separate work

| Item | Current evidence or remaining prerequisite |
| --- | --- |
| Modelo 200 2022/2023 calculation and Modelo 202 prior-year reads | Both editions explicitly remain applicability-grade; preserve the refusal until their own calculation coverage is grounded. |
| Modelo 303 promotor inputs | The rate-specific input/interface choice remains pending; preserve refusal for an unsplit base. |
| Modelo 390 accepted decision | Its Consequences still prescribe base times 21%; reconcile through an authorized amendment, preserving the accepted quarterly-fold decision and its history. |
| Lineage and older editions | The named not_examined/pending_review inventory needs official per-year evidence and continuity adjudication; existing counts are orientation, not new coverage. |
| Modelo 490, DA 20 and Baleares | Published inspection shows the 2022-1t layout already contains both substantive records (46 and 127 fields) and both envelope records, so the partial-layout claim is obsolete. No formula in the supported Modelo 100 editions reads DA 20 box 0525; the progressivity counterexample and the Baleares age-minimum correction remain open. |
| Tooling/source debt | The authoring command reference now names the real published-store admission, runtime boundary, companion distribution and installed-cohort gates in place of two removed test paths; it uses the authority root reported by the publisher. Published 222 revisions use their own 2019-2022 and 2023-2024 designs and no casilla cites the 2025 design; the 2025 mention is an absence comment. The 220 T22001000 sidecar already contains 88 numbered rows. The 184 historical art. 23 citation still needs temporal adjudication. |

### Acceptance of the original plan remains a separate boundary

The order restorations are committed in `b7c49338dd`; their published generation is `2e106bda4c2f4b7851832bcc3dc9b427459ebbd14d5901e7cfe835485c2ced50`. Existing logs show 226 focused tests and the 32-test commit gate passing. The new source measurement completed with exit 0 and stable captured inputs. With `CADRUMO_AUTHORITY_ROOT` explicitly selecting `.authority`, the canonical runtime reader admitted that generation and enumerated 58 modelos. An unconfigured raw Python process instead refused the absent packaged descriptor; that is a development-environment boundary, not permission to compile source at runtime.

The full-inventory quiet round completed with all 58 modelos minimal, zero redundant overrides and gaps, and passing equivalence/facts/indexed/cache/readiness checks; P04.S11 closed from that proof. The subsequent Modelo 200 repair is installed and published as a semantic correction. Its final scoped collapse is complete, input-stable and non-mutating: four editions equivalent/minimal, zero redundant overrides/repeated values/gaps, 722 governed-fact queries, 159 indexed revisions, 3,477 temporal and capability coordinates, cache parity/invalidation and publication readiness pass. The scoped tool correctly leaves registry_rollout incomplete. Its candidate logical generation matches active `a5b486f5`; only the active descriptor/database establish publication. The final full sequence replay is clean, S51/S52 are closed, and the merged Verification baseline has the same 33 binding finding keys/severities, zero errors and zero limitations. The plan has 55 of 56 steps closed; S50 remains open for the larger mapping campaign. Review remains PENDING for full rollout because package adoption did not reach installed behavior: one test passed and nine setup errors report the locked pikepdf macOS arm64 wheel boundary. The whole-catalogue literal legal-anchor ratchet remains at 82 against 79. No threshold, platform policy, support floor or capability was changed to clear those failures. `just init` earlier refused to mutate the virtual environment held by MCP/RAG (exit 6); those processes were preserved. The main merge is now committed at 93b6999f44; its earlier staged-file boundary is historical.

## Sources

- `src/cadrumo/_data/registry/aeat/legal/is.toml:1661`
- `dev/registry/mappings/modelo_200/2025/0002-dp200001.toml:413`
- `dev/registry/mappings/modelo_200/2025/0015-dp200012.toml:114`
- `dev/registry/tests/test_modelo_200_reused_box_numbers_keep_their_own_concept.py:106`
- `src/cadrumo/_data/registry/aeat/modelos/190/revisions/2025-y-siguientes/revision.toml:1189`
- `src/cadrumo/_data/registry/aeat/modelos/190/revisions/2022/formulas/0001-declarations.toml:13`
- `src/cadrumo/_data/registry/aeat/facts/0108-madrid-nacimiento-adopcion-applicability.toml:6`
- `src/cadrumo/application/modelo/profile_binding.py:1039`
- `src/cadrumo/_data/registry/aeat/legal/irpf-autonomica-madrid.toml:44`
- `src/cadrumo/domain/contribuyente/tests/test_madrid_nacimiento_adopcion.py:32`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/revision.toml:9025`
- `dev/registry/tests/test_modelo_100_eo_agraria_engine_ordenes_2022_2024.py:22`
- `docs/_sequences/contracts/how-to/review-calculation-values/review-values-relation.seq:7`
- `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/deadline_windows/0001-declarations.toml:12`
- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2022/revision.toml:6` and `revisions/2023/revision.toml:7`
- `2026-06-02-m390-annual-autoconsumo-promotor-source-adr`, Consequences
- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-200-299.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_25/DR200e25.xls
- https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/GI10/Instrucciones/instr_mod190_es_es.pdf (2025 instructions, page 5)
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-ayuda-presentacion/irpf-2022/10-cumplimentacion-irpf-deducciones-autonomicas/10_12-comunidad-madrid/10_12_1-nacimiento-adopcion-hijos.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-ayuda-presentacion/irpf-2023/10-cumplimentacion-irpf-deducciones-autonomicas/10_12-comunidad-madrid/10_12_1-nacimiento-adopcion-hijos.html
- https://www.boe.es/buscar/doc.php?id=BOE-A-2024-7804 (art. 2)
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2023/guia-principales-novedades/rendimiento-actividades-economicas.html
- https://www.boe.es/buscar/act.php?id=BOE-A-2009-10326&p=20230612&tn=1 (art. 3.2 and anexo II)
- https://sede.agenciatributaria.gob.es/static_files/Sede/Calendario_Contribuyente/Anyos_anteriores/Calendario_del_contribuyente_2023_eu_es.pdf (domiciliation table)
- Detailed source measurement and receipts: `C:/Users/hello/AppData/Local/Temp/registry-issues-0070e7903b324eddb6a3ebde2fb48c50/modelo200-investigation.json`; suspect-cell worklist: `modelo200-mapping-suspects.tsv` in the same directory. Command: `uv run --no-sync python .../measure_modelo200.py`, through the shared serial runner, exit 0 on 2026-10-01.

## Fresh requested verification

Fresh operator-requested verification ran against the working tree after main merge HEAD `93b6999f44`. Both Modelo 200 targets reproduce CURRENT, and authority `a5b486f5643d41213afedaf47c2cabd72eff5c02f0939149537921b234fea530` was republished before pytest under the shared serial lock. `just check-registry`, `just check-bindings` and `just check-registry-gate` pass: 58 modelos, 159 revisions, 1,483 legal references; all 33 binding warning identities/severities exactly match the measured merged baseline, with zero errors and limitations. Lifecycle coverage remains partial in three lanes: 119 owner-excluded targets, 673 bindings without a typed consumer and 120 placement gaps; 39 targets are current, zero stale/drifted and zero overlapping placements. `just test-registry` completed all four lanes with 9,613 passed, one failed, 65 skipped and zero errors (2,519 calculation passes; 7,094 conformance passes). Its only failure is `test_entries_whose_anchor_is_absent_from_their_files_ids_only_shrink`: 82 literal absent anchors against ceiling 79. The complete failure message and 82-member population exactly match the earlier full run; no ceiling or matching rule was changed. All 25 declaration/corpus screens completed observationally; the delta census finds zero unchanged restatements and 3,935 unchecked rows without lineage. The fresh shipped-catalogue module passes all 14 tests. Evidence: `.logs/test-runs/2026-10-01/20261001T123125.639385Z-test-registry-83352-3b61e140/run.log`, `fresh-registry-verification-receipt.json`, `fresh-binding-baseline-comparison.json`, `fresh-anchor-baseline-comparison.json` and `fresh-registry-supplement.json` in the owned repair root. S50 remains open for the larger mapping inventory; this registry suite does not establish installed-package adoption.
