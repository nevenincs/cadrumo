---
tags:
  - '#plan'
  - '#filing-architecture-docs'
date: '2026-06-08'
modified: '2026-06-08'
tier: L3
related:
  - '[[2026-06-08-filing-architecture-docs-research]]'
  - '[[2026-06-01-docs-educational-surface-adr]]'
  - '[[2026-06-02-docs-educational-surface-audit]]'
  - '[[2026-05-30-docs-architecture-adr]]'
---








# `filing-architecture-docs` `Filing Architecture Documentation` plan

## Wave `W01` - Config and Ledger Surfaces

Discover and document profile, censo, authentication, and ledger transaction surfaces, generalizing taxpayer identity terminology.


### Phase `W01.P01` - Config and Profile Discovery

Inspect CLI config verbs and profile schema files.

- [x] `W01.P01.S01` - Discover taxpayer profile setup flags and schema options; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [x] `W01.P01.S02` - Discover AEAT authentication provider types; `src/aeat/entrypoints/cli/_config/_profile_bundle.py`.

### Phase `W01.P02` - Ledger and Evidence Discovery

Inspect transactions, classifications, and evidence attachment CLI verbs.

- [x] `W01.P02.S03` - Discover ledger statement import and update verbs; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P02.S04` - Discover transaction categories and classification logic; `src/aeat/entrypoints/cli/_ledger_classify_cli.py`.

### Phase `W01.P03` - Profile and Ledger Documentation

Author and refine configuration and ledger docs under \docs/how-to/\.

- [x] `W01.P03.S05` - Author taxpayer profile setup guide with generic NIF/CIF/NIE/DNI nomenclature; `docs/how-to/profile-setup.md`.
- [x] `W01.P03.S06` - Author bank statement import and manual ledger updates guide; `docs/how-to/import-bank-statements.md`.
- [x] `W01.P03.S07` - Author transaction category and classification guide; `docs/how-to/classify-transactions.md`.

### Phase `W01.P04` - Review and Verification

Perform editorial and newcomers clarity review on the updated guides.

- [x] `W01.P04.S08` - Review profile, import, and classification guides against the newcomer clarity lens; `review reports`.
- [x] `W01.P04.S09` - Re-verify command examples against the live CLI using the conformance gate; `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`.

## Wave `W02` - Modelo Workspace Lifecycle

Discover and document work unit lifecycle, registry calculations, and manual inputs, focusing on general filing subjects in Spain.

### Phase `W02.P05` - Workspace and Registry Discovery

Inspect work unit commands and registry schema bindings.

- [x] `W02.P05.S10` - Discover work unit create, calculate, revisions, and status verbs; `src/aeat/entrypoints/cli/_modelo_work.py`.
- [x] `W02.P05.S11` - Discover registry formulas and bindings matching different taxpayer types; `src/aeat/domain/calculations/registry/`.

### Phase `W02.P06` - Workspace and Registry Documentation

Author and refine work unit lifecycle, calculations, and input guides.

- [x] `W02.P06.S12` - Author quickstart guide for producing first tax return; `docs/how-to/quickstart.md`.
- [x] `W02.P06.S13` - Author work unit lifecycle and revision modeling guide; `docs/how-to/filing-spine.md`.
- [x] `W02.P06.S14` - Author guide for supplying manual inputs and casillas; `docs/how-to/review-calculation-values.md`.

### Phase `W02.P07` - Review and Verification

Perform technical and editorial reviews on the workspace lifecycle documentation.

- [x] `W02.P07.S15` - Perform technical and newcomer clarity review over workspace lifecycle pages; `review reports`.
- [x] `W02.P07.S16` - Re-verify commands in quickstart, filing spine, and reviews; `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`.

## Wave `W03` - Live Observations and Reconciliations

Discover and document read-only live AEAT observations, notification snapshots, and justificante reconciliation.

### Phase `W03.P08` - Live and Reconciliation Discovery

Inspect live-read command sub-families and PDF parsing logic.

- [x] `W03.P08.S17` - Discover live observations, DEHu notification snapshots, and filed declarations; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `W03.P08.S18` - Discover PDF parser and justificante matching algorithms; `src/aeat/entrypoints/cli/_modelo_reconcile_cli.py`.

### Phase `W03.P09` - Live and Reconciliation Documentation

Author and refine live notifications, censo updates, and justificante reconciliation guides.

- [x] `W03.P09.S19` - Author censo update and AEAT live authentication guides; `docs/how-to/censo-update.md`.
- [x] `W03.P09.S20` - Author justificante PDF reconciliation guide; `docs/how-to/reconcile.md`.
- [x] `W03.P09.S21` - Author DEHu notifications guide; `docs/how-to/check-aeat-notifications.md`.

### Phase `W03.P10` - Review and Verification

Perform final verification gates, conformance checking, and reviews.

- [x] `W03.P10.S22` - Perform newcomer clarity and editorial reviews on live and reconciliation documentation; `review reports`.
- [x] `W03.P10.S23` - Verify complete corpus links and Sphinx build gates; `src/aeat/tests/test_docs_build.py`.

## Wave `W04` - High-Level Overviews and User Education

Create and refine narrative, simple-language overview documentation that connects the filing lifecycle and introduces the user to more advanced topics gradually.

### Phase `W04.P11` - Overview Discovery & Framing

Discover and audit narrative gaps and transitions between different stages of the filing lifecycle.

- [x] `W04.P11.S24` - Discover/audit current narrative links and structure; `docs/index.md` and `docs/how-to/index.md`.
- [x] `W04.P11.S25` - Identify areas where conceptual transitions (e.g. from ledger/classification to draft/verification) are abrupt or underdescribed; `audit reports`.

### Phase `W04.P12` - Overview and Narrative Content Production

Author and refine story-driven narrative pages that guide the user step-by-step.

- [x] `W04.P12.S26` - Create or refine narrative overview guides explaining the ledger-to-registry model and files; `docs/explanation/ledger-to-calculation.md`.
- [x] `W04.P12.S27` - Add step-by-step cross-referencing and contextual links between how-to guides and tutorials to improve newcomer progression; `docs/`.

### Phase `W04.P13` - Review and Verification

Perform newcomer clarity reviews, link verification, and Sphinx build gates on narrative pages.

- [x] `W04.P13.S28` - Perform clarity and language-simplicity reviews on narrative pages; `review reports`.
- [x] `W04.P13.S29` - Verify all links and commands using the conformance and build gates; `src/aeat/tests/test_docs_build.py`.

## Description

This plan outlines the systematic discovery and documentation audit of the Spanish AEAT text filing architecture. The goal is to ensure full, generic documentation coverage of the tax preparation, verification, and local filing lifecycle surfaces. All identity and taxpayer terminology is generalized (using CIF, NIF, DNI, NIE, or NII instead of specific single-group tokens) to fit all Spanish filing entities, while maintaining simple persona-based tutorials for clarity.

## Parallelization

Waves W01, W02, W03, and W04 are strictly sequential to allow codebase discovery and structural updates to naturally feed the narrative overview drafting and review cycles. Within each Wave, discovery and authoring phases can run in parallel where possible, but review and verification phases must run sequentially.

## Verification

- Conformance test suite `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` passes.
- Documentation Sphinx build gate `src/aeat/tests/test_docs_build.py` runs and passes successfully.
- Every modified or created document passes the zero-context newcomer and editorial reviews.
