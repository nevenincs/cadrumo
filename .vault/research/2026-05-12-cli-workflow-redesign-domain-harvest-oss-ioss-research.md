---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `domain-harvest-oss-ioss`

## Findings

Modelo 369 OSS/IOSS is partially implemented, but the controlling ADR is
still not accepted. The centralization ADR is `proposed` at
`2026-05-06-modelo-369-vat-centralization-adr.md`, while current code already
contains the OSS/IOSS substrate, registry source kind, Modelo 369 TOML,
resolver tests, and profile gate. The child ADR should declare a hard
precondition: either accept or supersede the 2026-05-06 Modelo 369 ADR before
locking execution.

Use `aeat app modelo`, not a new OSS/IOSS mini-app. Apex section 5.1 says
Modelo 369 is registry-only and the backend gap is that `domain/vat/_oss.py`
has no binding consumer; section 8 targets `domain/vat/_oss.py` at Modelo 369
calculation and `aeat app modelo` with a 369 selector. The app-modelo ADR
already owns work units, bindings, calculation revisions, verify, file,
export, and history.

Application wrapper API should be a Modelo calculation-path binding provider,
not a public VAT wrapper. Keep `src/aeat/domain/vat/_oss.py` as pure
substrate: it exposes `OssIossRegime`, `IossFilerRole`, `DeductionScope`,
`REGIME_PERIODICITY`, and `regime_allows_deduction`. Keep the registry resolver
pure: `resolve_ledger_oss_aggregation_binding_values(revision, observations)`
filters substrate-tagged `OssIossLedgerObservation` records and returns binding
values. The application wrapper should load bucket, profile, and ledger facts,
produce real `OssIossLedgerObservation` rows, resolve
`ledger_oss_aggregation`, feed bound casillas into registry calculate, persist
the calculation revision, and emit the modelo calculation event.

Per-destination-country rate resolution belongs in the VAT substrate. Current
`lookup_rate(member_state, kind, on_date)` resolves by EU member state, rate
kind, and date; the rate model is keyed by `EUMemberState` and `VATRateKind`.
The 2026-05-06 ADR wants destination-country OSS/IOSS rate windows in
`registry/aeat/vat/rates.toml`, not a separate regime table. Current
`OssIossLedgerObservation` assumes VAT amount already applied at destination
member-state rate, so the app wrapper must resolve and validate that rate
before observation creation or reject lines whose persisted IVA does not match
the substrate-derived rate.

Modelo 369 binding should flow through calculate, not a separate command. TOML
declares `ledger_oss_aggregation` bindings for exterior, union, and importacion
revisions, with selectors containing `regime`, `destination_member_state`,
`rate_kind`, `invoice_direction`, `transaction_kinds`, and `fact`. Existing
tests demonstrate the chain: ledger observations to bindings to
`calculate_registry_snapshot`.

OSS/IOSS regime config belongs in profile/config, with Modelo 369 using profile
predicates. Current profile schema has `iva.regime` and `iva.oss_enrolled`;
Modelo 369 schedules gate on `iva.oss_enrolled`. Config init requires
`--iva-regime`; config profile is the ongoing profile surface. Do not put
OSS/IOSS enrollment under `app modelo`.

Output/event contract: `bindings list` and `bindings preview` are read-only
and emit no bucket event. `calculate` creates or refreshes a calculation
revision, material transitions emit bucket events. JSON output fields should
include `operation`, `work_unit_id`, `modelo`, `year`, `period`,
`schema_revision_id`, `calculation_revision_id`, `revision_state`,
`resolved_binding_ids`, `missing_requirements`, and `event_id`.

Rejected shapes: no root `oss` or `ioss`, no `app vat oss`, no direct CLI calls
into `_oss.py`, no compatibility shim, no Decimal-only binding path for
structured OSS selectors, and no conflation with ledger VAT classification.
