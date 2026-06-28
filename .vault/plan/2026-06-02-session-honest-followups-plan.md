---
tags:
  - '#plan'
  - '#session-honest-followups'
date: '2026-06-02'
modified: '2026-06-02'
tier: L2
related:
  - '[[2026-06-02-suite-redgreen-2026-06-02-plan]]'
  - '[[2026-06-02-m303-parser-engine-totals-impedance-adr]]'
  - '[[2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr]]'
  - '[[2026-06-04-session-honest-followups-adr]]'
  - '[[2026-06-04-session-honest-followups-research]]'
---








# `session-honest-followups` `Session-honest follow-ups and substrate hardening` plan

### Phase `P01` - Architectural blockers untracked

Capture and drive M303 chain, entrypoints cluster, M721 887 grounding to closure via teammate dispatch



- [x] `P01.S01` - Verify M303 Route A landing closes 47 verification_chain reds; `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`.
- [x] `P01.S02` - Dispatch peer adjudication on M151/M714/M721 stub-refusal trio post Phase-A registry landing; `src/aeat/entrypoints/cli/test_modelo_{151,714,721}_stub_refusal.py`.
- [x] `P01.S03` - Fix wizard-catalogue startup ordering for cli_runner.invoke path; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `P01.S04` - Adjudicate bare-invocation bucket-session gate per ADR; `src/aeat/entrypoints/cli/test_profile_output_language.py`.
- [x] `P01.S05` - Ground orden-hfp-887-2023:art-3 via BOE OR update test_explain_721 assertion; `src/aeat/entrypoints/cli/test_overview_explain_verb.py`.

### Phase `P02` - Today fragile fixes regression risk

Re-verify the 9 commits landed this session for sibling regressions and silent coverage shrinkage

- [x] `P02.S06` - Verify M210 Phase-1 consumer modules exist; `check aeat.application.review et al; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/application_links/0001-application_links.toml`.
- [x] `P02.S07` - Author source_citations for modelo-200-base-imponible and -previa formulas; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/formulas.toml`.
- [x] `P02.S08` - Confirm M151 WT-only fix landed in peer M151 commit; `re-stage when peer dir tracked; `src/aeat/_data/registry/aeat/modelos/151/revisions/2015-y-siguientes/workbook_parity_refs/0001-workbook_parity_refs.toml`.
- [x] `P02.S09` - Add non-zero BIN coverage test for M200 base-determination chain; `src/aeat/application/filing/test_decimal_inputs_routing.py`.
- [x] `P02.S10` - Add non-zero BL-negativa coverage test for M100 renta taxation_comparison; `src/aeat/application/modelo/test_taxation_comparison.py`.
- [x] `P02.S11` - Re-strengthen attachment_id persistence proof; `src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py`.
- [x] `P02.S12` - Verify ErrorCode ModeloIvaWalletReconciliationBlocked locale strings against regulatory tone; `src/aeat/locales`.
- [x] `P02.S13` - Verify default_suggestion aeat app ledger iva wallet view CLI verb exists; `src/aeat/entrypoints/cli`.

### Phase `P03` - Substrate and infrastructure health

xdist collection skew, bash environment, synthetic-PDF generator gap, encrypted-column round-trip, wizard-catalogue startup ordering

- [x] `P03.S14` - Diagnose xdist collection-skew root cause and add deterministic test discovery gate; `pyproject.toml`.
- [x] `P03.S15` - Restore bash interpreter or formalize PowerShell mandate for this worktree; `CLAUDE.md`.
- [x] `P03.S16` - Document robust background-pytest capture pattern; `replace Tee Select-Object -Last 5 antipattern; `.claude/rules`.
- [x] `P03.S17` - Extend synthetic-PDF generator with M303 primitive form-field support; `src/aeat/tests/fixtures/justificantes/_generate.py`.
- [x] `P03.S18` - Clarify EncryptedString str-vs-bytes round-trip on object_key column; `src/aeat/adapters/persistence/storage/sql/_orm.py`.
- [x] `P03.S19` - Fix wizard-catalogue startup ordering for cli_runner.invoke path; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `P03.S20` - Add structural gate linking _COMPUTED_CASILLAS_M303 to actual M303 formula registry; `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`.
- [x] `P03.S21` - Audit plan exec-record Step-ID renumber-after-tier-promote drift across all 20 plans; `.vault/plan`.

### Phase `P04` - Deferred from existing plans

P04.S10 / P04.S12 / P07.S25 / M390 autoconsumo plus plan triage parents 143-147

- [x] `P04.S22` - Drive P04.S10 catalogue verification to closure; `src/aeat/domain/calculations/registry/test_catalogue_verification.py`.
- [x] `P04.S23` - Drive P04.S12 modelo parity coverage to closure; `src/aeat/domain/calculations/registry`.
- [x] `P04.S24` - Drive P07.S25 M303 golden SHA recompute with DR ground truth; `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`.
- [x] `P04.S25` - Drive task #154 M390 autoconsumo asymmetry closure or formal defer; `.vault/audit`.
- [x] `P04.S26` - Drive #143 plan-triage parent and child triage tasks #144-#147 to resolution; `.vault/plan`.

## Description


## Steps







## Parallelization


## Verification

