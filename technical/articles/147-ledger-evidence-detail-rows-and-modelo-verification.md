# ledger evidence, detail rows and modelo verification

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-147` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope

This chunk covers 13 files, 3,405 manifest-counted lines, 143,159 bytes, and 32,097 measured tokens. All six bounded pages were read through their listed ranges. This is static inspection only; I did not import or execute the application, modify `src/`, run tests, or independently verify legal rules or registry content.

## Product capabilities

The ledger filing snapshot stores a fingerprint per contributing transaction plus an aggregate snapshot digest. Its companion evidence bundle stores the tax-relevant facts, legal/source references, evidence locators, and operator-entered fact-basis entries needed to reconstruct what a filing relied on. The fact fields include IVA amounts and classifications, recargo, deduction/prorrata inputs, IRNR details, counterparty data, and invoice/document references. A staleness verdict compares saved fingerprints to supplied live fingerprints and reports changed, removed, and unchanged contributors snapshot and diff (`src/cadrumo/domain/modelos/ledger_filing_snapshot.py`) ledger evidence bundle (`src/cadrumo/domain/modelos/ledger_filing_snapshot.py`).

The participation index supplies the inverse audit lookup from a ledger transaction to finalized calculation revisions, filing records, and receipt references. Its per-transaction entry is described as a rebuildable read-side cache co-written atomically with revisions; the revision catalogue remains its source of truth. Repository protocols expose revisioned reads and compare-and-swap writes for singleton catalogues, plus atomic co-commit hooks for associated secure objects participation index (`src/cadrumo/domain/modelos/participation_index.py`) repository ports (`src/cadrumo/domain/modelos/protocols.py`).

Repeated-row support covers Modelo 184 member allocations, Modelo 232 related-party operations, Modelo 349 operators and rectifications, Modelo 347 counterparties, and Modelo 210 annual grouped rents. Registry-owned mappings define row ownership, slot capacity, M232 field-to-casilla projection, M349 period and prefix policy, M190 perceptor clave scope, and M210 grouping/payer exceptions. Cross-row validators enforce M184 share totals, aggregate M347 thresholds per NIF, and M210 grouping consistency. The M184 row deliberately leaves country optional where its upstream source has no country fact and refuses an unresolved clave-A reduction rather than treating the citation as settled typed row families (`src/cadrumo/domain/modelos/row_models.py`) M349 row materialization (`src/cadrumo/domain/modelos/m232_row_materialisation.py`) perceptor clave scope (`src/cadrumo/domain/modelos/perceptor_clave_scope.py`) cross-row validations (`src/cadrumo/domain/modelos/row_models.py`).

Verification reports persist complete, incomplete, or blocked outcomes; typed findings carry locale-neutral identity facts and legal/source references, while presentation text is kept outside the finding payload. A report is content-addressed by calculation revision, completeness status, ordered findings, and actor. Its validator ensures “granted complete” means status COMPLETE with no blocking findings and prevents casillas being both resolved and missing finding contract (`src/cadrumo/domain/modelos/verification_report.py`) report identity and invariants (`src/cadrumo/domain/modelos/verification_report.py`).

Work units are stable bucket/model/year/period/registry-revision handles with deterministic IDs, display names, current/filed pointers, and a discard lifecycle. Other helpers resolve dated Modelo facts and calculate the DT 12ª pension reduction or SAL/SLL reserve allocation using governed rates and explicit numeric guards work-unit identity and state (`src/cadrumo/domain/modelos/work_unit.py`) Modelo fact context (`src/cadrumo/domain/modelos/modelo_fact_context.py`) SAL reserve calculation (`src/cadrumo/domain/modelos/sal_reserva_especial.py`).

## How it works and knowledge

Snapshot diffing is pure and does not read the live ledger. It treats a saved contributor missing from the supplied map as removed and distinguishes changed from unchanged fingerprints. Fingerprint field-set versions preserve what older revisions actually observed; the evidence model mirrors that version and fills fields absent from old snapshots with `None`. Scope and legal catalogue contents come from registry authority, while the transaction-aware capture and secure persistence implementations are outside this chunk versioned snapshot fields (`src/cadrumo/domain/modelos/ledger_filing_snapshot.py`) pure fingerprint diff (`src/cadrumo/domain/modelos/ledger_filing_snapshot.py`).

The M190 scope projection resolves its mapping on the annual period end, parses `CLAVE` or `CLAVE.NN` tokens, maps record fields back to row bindings, and reports missing in-scope values while exempting rows outside the declared scope. M349 rectification validation uses its filing-year/period coordinate for prefix rules, distinguishing transition-period `GB` use from Northern Ireland `XI` goods-only cases. In contrast, the general M232 row-materialization function and M349 NIF-format helper resolve some declarations with `today_madrid()` rather than a filing-period date. That may be appropriate for current operator entry, but callers doing historical or future-year preparation should be checked for the intended temporal coordinate scope token resolution (`src/cadrumo/domain/modelos/perceptor_clave_scope.py`) M349 period-aware context (`src/cadrumo/domain/modelos/row_models.py`) M232 current-date lookup (`src/cadrumo/domain/modelos/m232_row_materialisation.py`) M349 current-date NIF lookup (`src/cadrumo/domain/modelos/row_models.py`).

## Security and implementation assessment

Evidence records carry digests, immutable source identities, typed legal/source references, and field-set versions rather than raw PDF or ledger bytes. Repository ports separate domain types from encrypted adapter-backed storage and expose guarded revisions where a whole singleton catalogue is rewritten. M190/M349/M232 scope declarations fail closed for missing or unsupported catalogue values, and the annual M347 threshold aggregates split rows before applying the dated threshold secure repository protocol (`src/cadrumo/domain/modelos/protocols.py`) aggregate threshold (`src/cadrumo/domain/modelos/row_models.py`).

One local consistency gap affects old snapshot reporting: `LedgerFilingStalenessVerdict.covers_current_fact_set` defaults to `True`, but `diff_ledger_fingerprints` does not set it from the snapshot’s `fingerprint_field_set_version`. As written, that helper can return “unchanged” with `covers_current_fact_set=True` even for a version-1 snapshot whose own documentation says it watched a narrower fact set. Verify that no application wrapper corrects the field; otherwise pass the current field-set version into the diff and mark older snapshots as incomplete coverage coverage flag (`src/cadrumo/domain/modelos/ledger_filing_snapshot.py`) diff return (`src/cadrumo/domain/modelos/ledger_filing_snapshot.py`).

The participation record’s `revision_state` is a bounded arbitrary string rather than a `CalculationRevisionState` enum or an explicit finalized-state validator. Its documentation says entries represent finalized revisions, yet the model’s local validator checks only the period/year agreement. A malformed or draft state can therefore be accepted into this cache unless the rebuilding/writing application layer restricts it state type (`src/cadrumo/domain/modelos/participation_index.py`) participation validation (`src/cadrumo/domain/modelos/participation_index.py`).

The verification report identity excludes `resolved_casilla_ids`, `missing_required_casilla_ids`, and `registry_snapshot_ref`. If these fields can differ while revision/status/findings/actor stay constant, catalogue upsert will address them under the same content ID; confirm that the verification producer makes them deterministic for that identity tuple. The `WorkUnit` model similarly validates its own ID and metadata but does not join its current/filed pointers to revision or filing catalogues inside this file, leaving cross-store pointer integrity to workflow boundaries report identity fields (`src/cadrumo/domain/modelos/verification_report.py`) report payload fields (`src/cadrumo/domain/modelos/verification_report.py`) work-unit pointers (`src/cadrumo/domain/modelos/work_unit.py`).

No tests are included in the assigned chunk. Static inspection cannot verify whether caller workflows provide the right dates, whether secure writes co-commit all derived indexes, or whether registry and evidence payloads match current published designs.

## Dependencies and follow-up

Confirm that the ledger diff caller sets `covers_current_fact_set` correctly for historical field-set versions. Check that participation-index producers emit only verified or filed revisions and that cache rebuilds preserve the same constraint. Trace M232 and M349 row validation dates through their callers, and verify verification-report identity inputs are deterministic. Cross-check that work-unit pointers and filing-record chains are validated within the application’s guarded write operations.

## Complete assigned-file coverage

- modelos/ledger_filing_snapshot.py (`src/cadrumo/domain/modelos/ledger_filing_snapshot.py`)
- modelos/m232_row_materialisation.py (`src/cadrumo/domain/modelos/m232_row_materialisation.py`)
- modelos/modelo_fact_context.py (`src/cadrumo/domain/modelos/modelo_fact_context.py`)
- modelos/participation_index.py (`src/cadrumo/domain/modelos/participation_index.py`)
- modelos/perceptor_clave_scope.py (`src/cadrumo/domain/modelos/perceptor_clave_scope.py`)
- modelos/protocols.py (`src/cadrumo/domain/modelos/protocols.py`)
- modelos/repository.py (`src/cadrumo/domain/modelos/repository.py`)
- modelos/row_models.py (`src/cadrumo/domain/modelos/row_models.py`)
- modelos/sal_reserva_especial.py (`src/cadrumo/domain/modelos/sal_reserva_especial.py`)
- modelos/verification_report.py (`src/cadrumo/domain/modelos/verification_report.py`)
- modelos/verification_repository.py (`src/cadrumo/domain/modelos/verification_repository.py`)
- modelos/work_unit.py (`src/cadrumo/domain/modelos/work_unit.py`)
- modelos/work_unit_repository.py (`src/cadrumo/domain/modelos/work_unit_repository.py`)
<!-- /preserved:article -->
