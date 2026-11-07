---
tags:
  - '#plan'
  - '#modelo-corrective-filing'
date: '2026-11-06'
tier: L1
related:
  - '[[2026-09-17-filing-chain-reconciliation-adr]]'
  - '[[2026-11-01-export-parity-observation-filing-kind-adr]]'
  - '[[2026-10-23-desktop-modelo-workspace-adr]]'
  - '[[2026-09-30-modelo-editor-workbench-adr]]'
modified: '2026-11-06'
body_schema: body-v2
body_hash: 'sha256:3cb8dda698cb72cf5158571f93ff85c5331361576ba1013fef93025f32797344'
---

# `modelo-corrective-filing` plan

## Description

Approved 2026-11-06

Authorization: user dispatch task_0e343ba1e01b authorizes covered fixes and actual desktop/TUI implementation, and BOSS messages msg_2095fef7cfea and msg_9eff86ae8337 authorize this bounded plan. Direct user steering makes React desktop a primary deliverable and requires Storybook for the elements; TUI parity is secondary. No real filing submission or production taxpayer data changes are authorized.

Reuse the accepted chain, observation, amendment-context and registered-operation architecture. The filing-chain and observation-kind ADRs govern S01 and backend projections in S02; desktop workspace and workbench ADRs govern S02/S03. No replacement filing/calculation API, new legal kind enum, or new persistence architecture is planned. Unsupported legal mechanisms stay unavailable. A genuinely new costly policy decision must be presented with evidence before dependent implementation.

Existing behavior and evidence: amendment_actions.py, filing_chain_reconciliation.py and filing_revision_persistence.py already preserve immutable calculation revision references, origin and confirmation states, links and centralized reconciliation. Justificante target binding and replay idempotence are already tested. observation_fold.py consumes one effective observation per coordinate; M130-to-M100 totals use cumulative prior-paid plus positive incremental result. Desktop WorkspaceScreen.tsx, CorrectionDialog.tsx and HistoryView.tsx already read amendment_context, bind a base, preflight and submit correction, and show filed/proposed values. DeclarationsPage.tsx lacks explicit related-filing coupling; the TUI recorded workbench has no equivalent actionable correction flow. Discovery used targeted code reading after semantic search reported an unpublished index; no index was built.

Design: React declarations rows disclose related filings through backend-served relationship and state words. A shared related-filings element in list/detail offers a keyboard-accessible selector or paired navigation to base and subsequent corrections, keeps status and correction kind visible, and preserves list focus on return. Details retain immutable filed values and show proposed or selected corrective values side by side with absent values distinct from zero. Reuse CorrectionDialog for legally permitted kind/motive selection and preflight. Display downstream effects only from backend facts; never calculate tax effects in React. Loading, failed reads, missing base, ambiguous receipt and unsupported transitions have explicit states. Storybook covers these elements and their interactions using canonical generated scenarios, not committed envelope copies. TUI adds a corresponding context/review flow through existing operation settlement, retaining the read-only original and returning focus to the workbench.

Legal support matrix, qualified evidence retrieved by Luna 2026-11-06: M303 September/3T 2024 onward uses own-model rectificativa and full corrected data with prior justificante, previous positive result in 70 and previously agreed refund in 109 (AEAT errors page and 2025 instructions). M100 Renta2025 and M200 Sociedades2024 manuals support whole-return rectificativa and prior justificante; this evidence alone does not establish every historical edition. M130/131 official instructions retain complementaria for increases, restate correct fields and deduct accumulated prior same-period results to pay, with prior justificante; decreases use a distinct rectification procedure. M349 file instructions distinguish omitted-operation complementaria from full sustitutiva, while online form help describes full current records and replacement, so channel matters. M390 annual instructions address rectified amounts and exclusion of amounts regularized in earlier years, but the inspected extract alone does not prove every standalone correction mode. M369 Orden HAC/610/2021 article 7.5 forbids modifying a filed period and places adjustments in later periods within three years; article 7.6 is a separate payment mechanism.

Exact official source URLs:
- https://sede.agenciatributaria.gob.es/Sede/iva/presentar-declaracion-iva-modelo-303/errores-declaracion.html
- https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-303-iva-autoliquidacion_/instrucciones-2025.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf (release 2026-03-27, p1238)
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/Sociedades/Manual_Sociedades_2024.pdf
- https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-renta-personas-fisicas/modelo-130-irpf______esionales-estimacion-directa-fraccionado_/instrucciones.html
- https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-renta-personas-fisicas/modelo-131-irpf______esionales-estimacion-objetiva-fraccionado_/instrucciones.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/GI28/instr_mod_349.pdf
- https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/declaraciones-informativas-ayuda-tecnica/modelos-349-720.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G412/Instrucciones_modelo_390-2025.pdf
- https://www.boe.es/buscar/doc.php?id=BOE-A-2021-10161 (published 2021-06-18, effective 2021-07-01)

Pinned provenance in facts/0135-amendment-regime-policy.toml source_refs: aeat-dr-303-2024-late (retrieved 2026-05-03, SHA256 2095dd633413f4aed28053bc88402461d80865f454156c01ebc4a2ab68cb76a8), aeat-dr-303-2025 (2026-05-06, 6c3d7eeb714e0deb52f91d7e8dbadeb83f16c1d32d25f9e871756f3ddf0117e6), aeat-dr-303-2026 (2026-05-03, 0be8b156da2250c6b11f6253e0165221ed2e549ec4c65a562021bec6b9b8489b), aeat-dr-200-2024 (2026-05-03, ed4df89a451abc2184bc60a1d13ff53a3d38e9a6201698fb635cf0b8ee455218), boe-modelo-369-2021-form (2026-05-06, 69423013b661ae0b5c302b97d9d6ba244ae5f11e345dd3ffca04f6f6dd36bdcf). These are discovery evidence, not proof of candidate runtime adoption.

Follow-up verified Dec31 boundaries are period-end encodings, not defects. Global pre/post kind sets may overpermit kinds; any restriction requires exact modelo/revision/channel evidence. Do not make all informative models sustitutiva-only: M349 file-channel complementaria is evidenced. Missing M220/M714 coverage is a hypothesis outside immediate patches until directly grounded.
## Steps

- [ ] `S01` - Prove and correct demonstrated reconciliation and successive-correction calculation gaps while preserving immutable filed snapshots and model-specific policy; `application/modelo and calculations with adjacent focused tests`.
- [ ] `S02` - Expose and render linked original and corrective filing navigation and comparisons in desktop lists and details using existing operations; `modelo declarations and filing projections, desktop modelo components and wire contracts, corresponding locales and scenarios`.
- [ ] `S03` - Connect TUI filing history to exact saved original and corrective details with bidirectional navigation and saved-value comparison; `src/cadrumo/entrypoints/tui/modelo and composition ports, corresponding locale keys and workbench tests`.
- [ ] `S04` - Validate coherent backend desktop and TUI candidate, resolve review findings and hand committed candidate to CHECKS2 for integration; `focused integration and UI scenario tests, feature ledger and audit, integration evidence`.

## Parallelization

Astra owns session/design and desktop/TUI implementation. Luna owns bounded read-only discovery; completed helpers settle before replacement. Sol high owns backend code/tests for demonstrated gaps and required existing-contract projections. Maximum two helpers; current checkout only. S01 backend and S02 frontend may overlap only after contract shape is agreed, with disjoint ownership; S03 follows the shared projection. Parent alone owns vault metadata and commits, serialized at Step boundaries. No Terra work is currently needed.

FIXTURES owns amendment timing, work_plazo and deadline paths and overlapping amendment_actions.py, external_import_actions.py, filing_revision_persistence.py and work_form_service.py: coordinate exact paths before edits. FRONTEND owns fixture generators, build/config files and tests/support/windowFixtures.ts; request canonical correction scenarios before generator edits. O2 owns ledger fixture modules. CHECKS2 is sole integrator to feature/tui. RESOURCE admits publication and builds separately; use own .venv, .authority, .tmp and build/windows-x64 only.
## Verification

Focused regression evidence must cover ordinary filings, unsupported kinds, missing/duplicate/ambiguous justificantes, wrong taxpayer/modelo/period, import-before-base, repeated synchronization, older records, immutable history and base/child navigation both ways. Prove successive corrections and branched local/official histories without summing snapshots: for one M130 quarter totals 100 then 130 then 150, the last complementaria has prior-paid130 plus incremental20 and contributes150 once; add independent quarters and verify annual aggregate, pending-local clean-state blocks, supersession and dependency staleness. Use actual model-specific semantics and hand-derived oracles.

React acceptance includes linked declarations list and detail flows, correction type/status, base/modified comparison, supported actions from application facts, nested corrections and downstream-impact disclosure. Implement Storybook stories and interactions for normal, nested, missing/ambiguous base or justificante, unsupported, loading and error states; exercise keyboard focus and accessible names. Generate scenarios through the owned canonical builder after coordination. Run frontend check and focused scenario/Storybook checks using enrolled outputs. TUI acceptance covers bidirectional saved-filing navigation and immutable recorded values at compact and normal sizes, including cancellation and late-read protection. Correction authoring remains in the existing React typed preflight and amendment flow; the user clarified that React and Storybook are primary, and this bounded session does not introduce a separate TUI amendment editor.

Run relevant Python tests and configured style/type/import checks for touched paths, then required coherent-candidate gates once inputs are stable. Distinguish unavailable test infrastructure from failures; do not claim UI proof from static inspection. Record actual authority descriptor/database identity and consumed generation. Formal integrated review at plan close/handoff, resolve critical/high findings, commit each cohesive Step, send reviewed candidate to CHECKS2, and retire checkout only after confirmed merge. No full repeated suite without changed inputs or concrete concerns.

## Execution checkpoint 2026-11-06

Accepted coverage is reused unchanged. The optional dated kind restriction intersects the existing registry-owned regime; it changes no storage or public protocol. The accepted observation-kind decision and pinned 130/131 designs already require original/complementaria only for the supported revisions from 2019. Source fact0135 now declares that restriction with canonical citations; broader modelo and channel rules remain unchanged. Source-only parser, application guard and provenance tests: 67 passed. Canonical references include aeat-modelo-130-instructions, aeat-dr-130-2019-v12, aeat-modelo-131-instructions and the five 131 designs through 2026-late; source hashes and quoted marker/instruction spans are verified by dev/registry/tests/test_amendment_kind_restrictions_authored_fact.py.

Backend projection/context25, staleness/evidence66 and receipt45 focused tests passed; corrected successive-correction group20 passed. The initial eight-file run had110 passes and one new test oracle failure: fresh source reseeding correctly changes provenance and calculation ID even when annual amount stays280; the regression now checks persisted original identity/content and the hand-derived280 amount. Scoped backend ty/Ruff and31 quick import contracts passed. These are focused results, not full candidate acceptance.

Own authority publication succeeded: descriptor SHA256 69b015951a63f9e408d5b02f65b82ea51c11c3838b9aa9dd7b376c8797b3200f; database SHA256 0566f726bef7930861b38247b5a088c00c6dad0f59786a3ff9d215ffde0a2161,121561088 bytes; logical generation b510ccda73c1a907e78a6016a201486a0a745d05c1ee156ec4ba61a5f4e85931. Previous immutable database remains available. No production taxpayer data or filing submission was used.

Merged FRONTEND's verified prerequisite fd1f721593 with ancestry as owner requested. Own configure generated build/windows-x64 and selected own .venv interpreter, setup exited0, TypeScript contract regeneration exited0. First generated target exited1 on missing new chrome-key enrollment; enrolled the keys and retried using completed agent prerequisite outputs. Canonical operation-backed original/confirmed correction/pending second-correction fixtures and four-language contexts are implemented; generation, React checks, Storybook/browser proof and TUI focused execution remain pending. TUI source scoped type and Ruff checks passed.

### Canonical fixture regression discovered during UI validation

The operation-backed correction fixture revealed a calculation defect not covered by the earlier projection and aggregate tests: amendment_actions copies saved casilla_values and overlays the requested entries without evaluating dependent formulas. Formula observations and replay maps retain the prior results. With original04=733.02,06=0,13=100,17=633.02, changing06 to150 should yield07=583.02 and17=483.02 before prior-payment deduction and must be refused as a decrease under the supported130 complementaria procedure. The old operation instead admits the correction with07/17/19 unchanged. Saved before-fix fixture receipts are retained under .tmp/corrective-filing/stale-calculation-before until reviewed evidence is consolidated.

The repair remains within the existing engine and accepted decision coverage: recompute dependent outputs and provenance from saved typed inputs, preserve genuine operator overrides and immutable originals, derive same-period deductions only from confirmed prior payments, and compare total liability consistently rather than confusing a smaller incremental payment with a decrease. FIXTURES owns amendment timing; exact function ownership is being agreed before overlapping edits. Source identity was reproduced under the actual nested producer environment: own Python, cadrumo, amendment_actions and filing_record_view_operation all resolve to this checkout. This is a demonstrated calculation defect, not a donor-source discrepancy.

Successful UI fixtures will use income01=10000 then11000. Independent formula expectations are first17=853.42,18=633.02,19=220.40, then after confirmation second17=1043.42,18=853.42,19=190.00. Without first confirmation, second18 remains633.02 and19=410.40. These expectations derive from saved expenses4982, the pinned5percent provision and20percent payment rules, not from observed buggy outputs. React and Storybook scenario inputs are being aligned with these examples; all actual browser and Storybook acceptance remains pending.

Focused TUI saved-history navigation and late-response tests passed8 cases, with4 existing integration cases separately passing. A prior run hung in the new test synchronization helper and was stopped; explicit bounded events corrected that test. These results do not cover the newly discovered amendment arithmetic defect. Canonical filing-view projection also now accepts valid long CasillaId identifiers through the existing shared type, with21 focused tests passing. Remaining generic sustitutiva permissiveness for303/100/200 has bounded source evidence recorded; no unsupported channel inference or349 restriction is authorized from that discovery alone.
