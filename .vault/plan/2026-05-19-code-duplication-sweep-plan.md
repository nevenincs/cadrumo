---
tags:
  - '#plan'
  - '#code-duplication-sweep'
date: '2026-05-19'
tier: L3
related:
  - '[[2026-05-19-code-duplication-sweep-research]]'
  - '[[2026-05-19-code-duplication-sweep-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `code-duplication-sweep` `Code Duplication Sweep Remediation Plan` plan

## Wave `W01` - Minor Symbol Segregations

Unify minor colliding and shadowed identifiers under unique canonical names, ensuring no shadowed imports or catching bugs exist.

### Phase `W01.P01` - Consolidate Shadowed Exception Hierarchies and Identifier Naming Collisions

Resolve import shadows and exception-catching bugs across WorkUnitNotFoundError, CCAA, and ModeloRepository.

- [x] `W01.P01.S01` - Consolidate WorkUnitNotFoundError to actions.py and raise it in reconcile.py; `src/aeat/application/modelo/_reconcile.py`.
- [x] `W01.P01.S02` - Rename calendar-specific CCAA enum to CalendarCCAA to prevent collision with profile CCAA; `src/aeat/domain/deadlines/_festivos.py`.
- [x] `W01.P01.S03` - Rename read-only static ModeloRepository facade to StaticModeloRepository; `src/aeat/core/resources/_repos/modelos.py`.

## Wave `W02` - Boilerplate Consolidation

Consolidate repeated repository structures and drivers into generic base classes, and unify third-party dependencies under common modules.

### Phase `W02.P02` - Consolidate SecureObjectRepository Boilerplate

Create a reusable generic persistence repository baseline to replace repeated pathing, locking, and serialization logic.

- [x] `W02.P02.S04` - Implement generic SecureBoundRepository baseline class; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [x] `W02.P02.S05` - Refactor FilingDraftRepository to inherit from SecureBoundRepository; `src/aeat/domain/filing/_repository.py`.
- [x] `W02.P02.S06` - Refactor SubmissionRepository to inherit from SecureBoundRepository; `src/aeat/domain/submission/_repository.py`.
- [ ] `W02.P02.S07` - Extract shared repository roundtrip testing utility to replace duplicate assertions; `src/aeat/adapters/persistence/storage/conftest.py`.

### Phase `W02.P03` - Consolidate External Integrations

Unify copy-pasted pdfplumber extraction logic, logging control suppression, and live oracle checker drivers.

- [ ] `W02.P03.S08` - Migrate all PDF text extraction calls to canonical pdfplumber utility and implement the shared `_suppress_pdfminer_debug_logging` control to eliminate PDF logging noise globally; `src/aeat/adapters/inbound/pdf/_pdfplumber.py`.
- [ ] `W02.P03.S09` - Refactor borrador parser to use shared PDF text extraction utility; `src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py`.
- [ ] `W02.P03.S10` - Refactor declaracion parser to use shared PDF text extraction utility; `src/aeat/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py`.
- [ ] `W02.P03.S11` - Extract BaseCheckerOracle and shared JSON-decoding replay driver under live parity backend; `src/aeat/domain/calculations/registry/_live_parity.py`.
- [ ] `W02.P03.S12` - Refactor AeatNifIvaCheckerOracle to inherit from BaseCheckerOracle; `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py`.
- [ ] `W02.P03.S13` - Refactor GroiCheckerOracle to inherit from BaseCheckerOracle; `src/aeat/domain/calculations/registry/_groi_oracle.py`.

## Wave `W03` - Acronym & Term Standardization

Standardize the dual-acronym structures (VAT vs IVA) and triple-terminology divides (Filing vs Modelo vs Declaración), deprecating redundant draft persistence blocks.

### Phase `W03.P04` - Consolidate Value-Added Tax (VAT vs IVA)

Establish a uniform terminology glossary and merge overlapping classification logic into a canonical VAT domain package.

- [ ] `W03.P04.S14` - Create canonical Value-Added Tax classification schema under domain/vat package; `src/aeat/domain/vat/_classification.py`.
- [ ] `W03.P04.S15` - Consolidate duplicate IVA classification references into unified VatClassification schema; `src/aeat/domain/invoices/_iva_classification.py`.

### Phase `W03.P05` - Unify Draft Persistence and Deprecate Local file-based Snapshotting

Retire the insecure local file-based borrador.py snapshotting strategy and consolidate all Modelo 100 draft persistence under borrador_100.py.

- [ ] `W03.P05.S16` - Migrate all active commands from local file-based borrador storage to secure borrador_100 object repository; `src/aeat/application/live/_borrador_100.py`.
- [ ] `W03.P05.S17` - Delete deprecated local filesystem-based borrador parser file-caching implementation; `src/aeat/application/live/_borrador.py`.
