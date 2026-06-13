---
tags:
  - '#exec'
  - '#aeat-verify'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-24-aeat-verify-plan]]"
  - "[[2026-04-24-aeat-verify-adr]]"
  - "[[2026-04-24-aeat-verify-phase1-summary-exec]]"
  - "[[2026-04-24-aeat-verify-phase2-summary-exec]]"
---



# `aeat-verify` `phase-3` `reconciliation-comparator`

Phase 3 of the `aeat-verify` plan lands the sealed
`aeat.application.filing.reconciliation` subpackage: the pure comparator that
walks a local `FilingDraft` against a remote `RemoteFiling` and emits
the Kent-observable terminal triad locked by the accepted ADR
(`MATCH` / `DIVERGENT` / `NOT_YET_FOUND`). Every record stays strict,
frozen, `extra="forbid"`; every monetary comparison runs on
`Decimal`; every Kent-facing string carries `es` / `en` / `hu`. The
Layer 3 grep guard is colocated under the new subpackage and follows
the Phase 1 sidecar-fixture pattern verbatim.

- Created: `src/aeat/application/filing/reconciliation/__init__.py` (sealed public API; alphabetised `__all__`).
- Created: `src/aeat/application/filing/reconciliation/_kind.py` (closed `FilingDivergenceKind` StrEnum, six variants).
- Created: `src/aeat/application/filing/reconciliation/_tolerance.py` (`RECONCILIATION_TOLERANCE: Final[Decimal] = Decimal("0.01")`).
- Created: `src/aeat/application/filing/reconciliation/_schema.py` (`ReconciliationStatus`, `CasillaDelta`, `FilingDraftRef`, `ReconciliationReport`, `KIND_TO_STATUS` static mapping).
- Created: `src/aeat/application/filing/reconciliation/_narrative.py` (trilingual `compose_delta_narrative` and `compose_report_narrative`).
- Created: `src/aeat/application/filing/reconciliation/_reconcile.py` (pure `reconcile(draft, remote, *, tolerance, now)` comparator).
- Created: `src/aeat/application/filing/reconciliation/_persist.py` (parallel `FilingReconciliationDivergenceRecord` plus `reconciliation_records()` adapter).
- Created: `src/aeat/application/filing/reconciliation/_errors.py` (`ReconciliationError` extending `aeat.core.errors.AeatError`).
- Created: `src/aeat/application/filing/reconciliation/test_kind.py`, `test_tolerance.py`, `test_schema.py`, `test_narrative.py`, `test_reconcile.py`, `test_persist.py` (75 unit cases).
- Created: `src/aeat/application/filing/reconciliation/test_no_write_surface.py` plus `_no_write_surface_fixture.txt` (Layer 3 grep guard, sidecar-fixture pattern).

## Description

### Sealed public API (3.1)

`__init__.py` exports exactly the seven symbols the plan locks plus
`ReconciliationError` (the project mandate requires every domain
error to inherit from `aeat.core.errors.AeatError`). `__all__` is
alphabetised per `RUF022` and rejects every English / Spanish
write-verb prefix the Layer 3 grep guard catalogues.

### Closed enum & shared tolerance (3.3, 3.4)

`FilingDivergenceKind` is an `enum.StrEnum` with the six variants the
ADR enumerates. The module docstring explicitly explains why the enum
is disjoint from `aeat.application.sync._divergence.DivergenceKind` (the
schema-level auto-heal contract must stay narrow). `RECONCILIATION_TOLERANCE`
is a `Final[Decimal]` mirroring `aeat.application.verification._verify._DEFAULT_TOLERANCE`
by value; the duplication is deliberate and the docstring documents
the cross-link. `test_tolerance_matches_verification_tolerance_by_value`
asserts the invariant so accidental drift fails the suite.

### Schema records & static kind-to-status table (3.2)

`_schema.py` declares `ReconciliationStatus` (StrEnum), `CasillaDelta`,
`FilingDraftRef`, and `ReconciliationReport`, all
`ConfigDict(strict=True, frozen=True, extra="forbid")` with
`AwareDatetime` for every timestamp. `KIND_TO_STATUS` is a
`MappingProxyType` binding each `FilingDivergenceKind` variant to the
`ReconciliationStatus` it implies; reviewers see the binding in one
place rather than scattered across conditional branches.

### Pure comparator (3.5)

`reconcile(draft, remote, *, tolerance, now)` is async-free and
free of any I/O. The empty-remote case (`remote is None`) emits a
single `FILING_NOT_YET_FOUND` sentinel delta and returns
`status=NOT_YET_FOUND` with `remote_ref=None`. Otherwise the
comparator builds local and remote casilla maps, walks the union of
casilla ids, and classifies each entry via `_classify_pair`. The
filing-status divergence is folded in by `_filing_status_delta`,
which encodes the lifecycle-state matrix the ADR sketches: `APPROVED`
/ `SUBMITTED` / `ACKNOWLEDGED` / `AMENDED` against the
terminal-clean remote set (`PRESENTADA` / `SUBSANADA` /
`COMPLEMENTARIA`); pre-upload local statuses always flag any remote
presence as divergent. The aggregate
status reduces through `KIND_TO_STATUS`. The triad is mutually
exclusive — `FILING_NOT_YET_FOUND` short-circuits per-casilla
comparison.

### Deviation from the plan: `remote` signature

The plan (3.5) proposed `reconcile(draft, remote: tuple[RemoteFiling, ...], ...)`.
The execution instead exposes `reconcile(draft, remote: RemoteFiling | None, ...)`
because:

1. The user-prompt non-negotiable §3.5 explicitly mandates
   `RemoteFiling | None` ("When `remote is None` -> emit
   `FILING_NOT_YET_FOUND` / `NOT_YET_FOUND`. Otherwise per-casilla
   walk producing `CasillaDelta`s").
2. The plan-text mention of multi-filing chains (original +
   complementarias) is collapsed at the caller boundary: the Phase 5
   sync-run integration is the natural place to pick the
   latest-by-`submitted_at` anchor before invoking the comparator.
   Pushing the multi-filing reduction into the comparator would
   couple it to AEAT's complementaria semantics; keeping it at the
   caller boundary preserves the comparator's purity.
3. The comparator is now a single-anchor function and its decision
   table is exhaustively walked by `test_reconcile.py`.

### Trilingual narratives (3.6)

`_narrative.py` exposes `compose_delta_narrative` (one trilingual
string per `FilingDivergenceKind` variant) and
`compose_report_narrative` (one trilingual string per
`ReconciliationStatus`). Mirrors the
`aeat.application.verification._verify._compose_narrative` pattern verbatim. No
partial localisation; `test_narrative.py` parametrises over every
variant and asserts non-empty `es` / `en` / `hu` strings for each.

### Persistence adapter (3.7)

`_persist.py` declares a parallel `FilingReconciliationPayload`
discriminated union and `FilingReconciliationDivergenceRecord`
wrapping record. The shape mirrors `aeat.application.sync.DivergenceRecord` (id +
detected_at + classification + payload + resolution_state + notes)
and re-uses `aeat.application.sync.DivergenceClassification` and
`aeat.application.sync.ResolutionState` enums verbatim — only the payload union
is forked, never the surrounding shells.

### Deviation from the plan: parallel record vs. payload injection

The plan (3.7) suggested defining a `FilingReconciliationPayload`
that "satisfies the existing `DivergencePayload` Protocol". On
inspection, `aeat.application.sync._divergence.DivergencePayload` is **not** a
Protocol — it is a closed `Annotated[Union, Field(discriminator="kind")]`
of ten concrete payload variants. Pydantic strict mode would reject
any payload outside that union. The plan's fork-rationale paragraph
governs this case ("the payload is persisted as a wrapping record
that satisfies the `DivergenceRecord.payload` type without cross-enum
pollution") so the execution emits a parallel
`FilingReconciliationDivergenceRecord` instead. The non-negotiable
constraint #8 ("do NOT modify `aeat.application.sync._divergence`") is fully
respected — `aeat.application.sync` files are untouched. Phase 5's sync-run
integration will route both record types into the same Kent-facing
sink.

`reconciliation_records(report)` returns an empty tuple for `MATCH`
reports (rounding-only deltas alone are non-blocking and not
persisted) and one record per non-rounding delta otherwise. Records
classify as `DivergenceClassification.BREAKING` because filing-instance
value divergence is by construction never auto-heal-safe.

### Layer 3 write-guard (3.9)

`_no_write_surface_fixture.txt` mirrors the Phase 1 sidecar
verbatim. `test_no_write_surface.py` replicates the Phase 1 walker
without importing the Phase 1 module — each subpackage owns its own
guard. The forbidden write-mode literal is composed at runtime from
fixture parts (`"mode" + "=" + '"' + "write" + '"'`) so the full
string never materialises in any Python source under
`src/aeat/application/filing/reconciliation/`. The walker auto-discovers every
`.py` file under the subpackage; no whitelisting and no per-file
exemption.

### Public-API discipline & relative imports

Every consumer-facing import lands through
`aeat.application.filing.reconciliation` directly; private modules carry the
leading underscore. All cross-subpackage imports are relative
(`from ...remote import ...`, `from ...sync import ...`,
`from .._schema import ...`) so the project's `check_relative_imports.py`
gate stays clean.

## Tests

- `just lint` — green (`ruff check .` plus the custom relative-imports check).
- `just typecheck` — green (`ty check src tests`).
- `just hooks` — green on every changed file (prek pre-commit hook chain).
- `uv run pytest src/aeat/application/filing/reconciliation/ -m unit` — 75 passed.
- `uv run pytest -m unit -k "remote or reconciliation"` — 681 passed,
  including marker-integrity walker over every new test module.
- Repository-wide `uv run pytest` — 3240 passed, 5 skipped, 29
  deselected; one pre-existing failure in
  `tests/test_marker_integrity.py::test_module_carries_valid_pytestmark[src/aeat/adapters/outbound/aeat/export/_formats/_test_fixtures.py]`
  that predates this branch (verified by Phase 1 and Phase 2
  summaries) and is explicitly out of Phase 3 scope per the executing
  prompt.

Layer 4 (charter #116 alignment via `AeatAccessGate` /
`AeatGateEnvSnapshot` propagation) and Layer 5 (live-test discipline)
remain owned by Phase 2; Phase 3 ships no live surface. Layers 1 / 2
/ 3 stay green.

No audit report has been generated yet for Phase 3; the mandatory
`vaultspec-code-reviewer` audit runs next and will land under
`.vault/audit/` once the reviewer persona has inspected the Phase 3
surface.
