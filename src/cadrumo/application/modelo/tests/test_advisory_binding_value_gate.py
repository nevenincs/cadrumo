"""A grade-capped retención credit is shown by the calculation and refused at check, export and recording.

The Modelo 130 casilla 06 binding is capped at calculation grade in the
published registry, because the year a suffered retención belongs to is not yet
grounded. Each case runs the real ledger renta-income resolver over synthetic
ledger rows against the published Modelo 130 revision, then the real
post-merge emission, the real durable projection a calculation persists, and
the real calculation-note gate on a revision stamped as a calculation stamps
it. Every expected figure is invoice arithmetic worked out in the test.

The resolver states what a capped value rests on. A zero over rows that carry
no retención is a proven zero and withholds nothing for that box. A zero over
rows whose retención was left out, a declared credit, and a capped value whose
resolver stated nothing all withhold checking, exporting and recording. The
income box beside it carries its own cap: a window with income stays withheld
through casilla 01 even when casilla 06 is a proven zero.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind, BindingValueOutcome
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_grade_cap_reach import capped_binding_reach, snapshot_reach_date
from ....domain.calculations.registry.binding_targets import revision_bindings_by_id
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_sources import CalculationNoteSentence, CalculationSourceIssue
from ....domain.modelos.calculation_screen_stamp import CalculationScreenStamp
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.transactions.models import TransactionCatalogue
from ...actividad_asset.tests.register_support import MemoryRepository
from ...aggregation.modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ...aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from ...aggregation.tests.ledger_source_mesh_support import InMemoryTransactionCatalogueRepository
from ...aggregation.tests.renta_income_aggregation_support import actividad_transaction, catalogue_read_ports
from ...aggregation.tests.test_actividad_retencion_declared_credit import (
    BUCKET,
    declared_pair,
)
from ..advisory_binding_value import add_advisory_binding_value_diagnostics
from ..calculation_bucket_actions import unrouted_source_issues
from ..calculation_note_gate import ModeloCalculationBlockedError, require_work_unit_calculation_unblocked
from ..calculation_notes import CALCULATION_SCREEN_OUTDATED_REASON, GATE_REFUSED_REASONS
from ..calculation_screen import calculation_screen_stamp
from ..printed_boxes import snapshot_printed_boxes
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_YEAR = 2026
_QUARTER = "1T"
_CAPPED_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"
_CAPPED_BOX = "06"
_INCOME_BOX = "01"
_REASON = "advisory_binding_value"
# Hand-derived: 150,00 at 15 % of 1.000,00 plus 140,00 at 7 % of 2.000,00.
_DECLARED_CREDIT = Decimal("290.00")
_BASE = Decimal("2000.00")
# Hand-derived: 21 % of 2.000,00.
_IVA = Decimal("420.00")
# Hand-derived: 2.000,00 + 420,00 - 300,00, the 15 % retención on 2.000,00 kept by the client.
_SHORT_PAID_CASH = Decimal("2120.00")


def _snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    return operation.snapshot("130", filing_year=_YEAR, period=_QUARTER)


def _work_unit(snapshot: RegistrySnapshot) -> WorkUnit:
    period = Period.from_year_and_code(_YEAR, _QUARTER)
    revision_id = str(snapshot.revision.id)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=BUCKET, modelo="130", filing_year=_YEAR, period=period, revision_id=revision_id
        ),
        bucket_id=BUCKET,
        modelo=ModeloCode("130"),
        filing_year=_YEAR,
        period=period,
        revision_id=revision_id,
        name="130-2026-1T",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _resolve(
    snapshot: RegistrySnapshot, transactions: TransactionCatalogue, invoices: InvoiceCatalogue
) -> CalculationSourceResolution:
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET)
    repository.save(transactions)
    resolver = LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=catalogue_read_ports(invoices=invoices, transactions=transactions),
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=BUCKET,
            modelo="130",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, _QUARTER),
            revision=snapshot.revision,
        )
    )


def _receipt(provider_id: str, cash: Decimal) -> TransactionCatalogue:
    """One activity receipt whose own record states a 2.000,00 base and 420,00 IVA at 21 %."""
    return TransactionCatalogue.from_transactions(
        (
            actividad_transaction(
                provider_id,
                value_date=date(2026, 2, 10),
                amount=cash,
                taxable_base=_BASE,
                iva_rate=Decimal("0.21"),
                iva_amount=_IVA,
            ),
        )
    )


def _fully_paid() -> tuple[TransactionCatalogue, InvoiceCatalogue]:
    """The cash covers base plus IVA, so nothing was withheld."""
    return _receipt("cobro-integro", _BASE + _IVA), InvoiceCatalogue()


def _short_paid() -> tuple[TransactionCatalogue, InvoiceCatalogue]:
    """The cash falls 300,00 short with no linked invoice: the retención is reconstructed and left out."""
    return _receipt("cobro-neto-sin-factura", _SHORT_PAID_CASH), InvoiceCatalogue()


def _stamp(snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation) -> CalculationScreenStamp:
    return calculation_screen_stamp(snapshot, operation=operation)


def _revision(
    unit: WorkUnit,
    issues: tuple[CalculationSourceIssue, ...],
    *,
    stamp: CalculationScreenStamp | None,
    state: CalculationRevisionState = CalculationRevisionState.BORRADOR,
) -> CalculationRevision:
    filed = state in {CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO}
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_issues=issues,
            filing_instance_evidence=None,
            source_provenance=(),
            screen_stamp=stamp,
        ),
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="130", revision_id=unit.revision_id, modelo_year=_YEAR, period=_QUARTER
        ),
        state=state,
        casilla_values={},
        observations=(),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=issues,
        screen_stamp=stamp,
        verified_at=_CLOCK if filed else None,
        verified_by="operator" if filed else None,
        filed_at=_CLOCK if filed else None,
        filed_by="operator" if filed else None,
        superseded_at=_CLOCK if state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO else None,
    )


def _calculated(
    operation: PinnedAuthorityOperation, resolution: CalculationSourceResolution
) -> tuple[CalculationSourceResolution, tuple[CalculationSourceIssue, ...]]:
    """Run the post-merge emission and the durable projection a calculation persists."""
    snapshot = _snapshot(operation)
    emitted = add_advisory_binding_value_diagnostics(snapshot, resolution, operation=operation)
    persisted = unrouted_source_issues(emitted.diagnostics, snapshot_printed_boxes(operation, snapshot))
    return emitted, persisted


def _refused_reasons(operation: PinnedAuthorityOperation, revision: CalculationRevision) -> set[str] | None:
    """The reasons every gated action refuses with, or ``None`` when each admits the revision."""
    unit = _work_unit(_snapshot(operation))
    refusals: list[set[str]] = []
    for action in ("verify", "export", "file"):
        try:
            require_work_unit_calculation_unblocked(
                work_unit=unit, revision=revision, action=action, operation=operation
            )
        except ModeloCalculationBlockedError as refused:
            refusals.append(set(str((refused.context or {})["reasons"]).split(",")))
    if not refusals:
        return None
    assert len(refusals) == 3, "verify, export and recording decide together"
    assert all(refusal == refusals[0] for refusal in refusals)
    return refusals[0]


def _capped_notes(emitted: CalculationSourceResolution, box: str = _CAPPED_BOX):
    """The advisory notes of one box: every capped binding of the calculation states its own."""
    return [
        diagnostic
        for diagnostic in emitted.diagnostics
        if diagnostic.reason == _REASON and diagnostic.casilla_id == box
    ]


def _persisted_for(persisted: tuple[CalculationSourceIssue, ...], box: str = _CAPPED_BOX):
    return [issue for issue in persisted if issue.reason == _REASON and issue.casilla_id == box]


def test_a_zero_over_rows_that_carry_no_retencion_is_proven_and_withholds_nothing(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = _snapshot(operation)
    resolution = _resolve(snapshot, *_fully_paid())

    assert resolution.binding_values[_CAPPED_BINDING] == Decimal("0")
    assert resolution.value_outcomes[_CAPPED_BINDING] is BindingValueOutcome.PROVEN_ZERO
    emitted, persisted = _calculated(operation, resolution)

    (note,) = _capped_notes(emitted)
    assert note.casilla_id == _CAPPED_BOX
    assert note.value_outcome is BindingValueOutcome.PROVEN_ZERO
    assert note.fact is not None and note.fact.sentence is CalculationNoteSentence.ADVISORY_VALUE_PROVEN_ZERO
    assert _persisted_for(persisted) == []
    # The income the receipt carries is capped on its own binding and still withholds.
    (income_note,) = _capped_notes(emitted, _INCOME_BOX)
    assert income_note.value_outcome is not BindingValueOutcome.PROVEN_ZERO
    (income_issue,) = _persisted_for(persisted, _INCOME_BOX)
    assert income_issue.binding_source is BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION
    revision = _revision(_work_unit(snapshot), persisted, stamp=_stamp(snapshot, operation))
    reasons = _refused_reasons(operation, revision)
    assert reasons is not None and _REASON in reasons


def test_a_zero_over_rows_whose_retencion_was_left_out_withholds(operation: PinnedAuthorityOperation) -> None:
    snapshot = _snapshot(operation)
    resolution = _resolve(snapshot, *_short_paid())

    assert resolution.binding_values[_CAPPED_BINDING] == Decimal("0")
    assert resolution.value_outcomes[_CAPPED_BINDING] is BindingValueOutcome.FROM_BEARING_ROWS
    emitted, persisted = _calculated(operation, resolution)

    (note,) = _capped_notes(emitted)
    assert note.value_outcome is BindingValueOutcome.FROM_BEARING_ROWS
    (issue,) = _persisted_for(persisted)
    assert issue.casilla_id == _CAPPED_BOX
    assert issue.binding_source is BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION
    reasons = _refused_reasons(operation, _revision(_work_unit(snapshot), persisted, stamp=_stamp(snapshot, operation)))
    assert reasons is not None and _REASON in reasons


def test_a_declared_credit_is_calculated_shown_and_refused_at_check_export_and_recording(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = _snapshot(operation)
    resolution = _resolve(snapshot, *declared_pair())

    assert resolution.binding_values[_CAPPED_BINDING] == _DECLARED_CREDIT
    emitted, persisted = _calculated(operation, resolution)

    (note,) = _capped_notes(emitted)
    assert note.fact is not None
    assert note.fact.sentence is CalculationNoteSentence.ADVISORY_IMPUTATION_PERIOD_UNGROUNDED
    assert set(note.asserted_legal_refs) == {"rd-439-2007:art-79", "rd-439-2007:art-7", "ley-35-2006:art-14"}
    revision = _revision(_work_unit(snapshot), persisted, stamp=_stamp(snapshot, operation))
    reasons = _refused_reasons(operation, revision)
    assert reasons is not None and _REASON in reasons

    # The form shows the note and withholds the file exactly where the gate refuses.
    form = built_form(operation, "130", _YEAR, _QUARTER, revision=revision)
    (shown,) = [item for item in form.calculation_notes if item.reason == _REASON and item.box == _CAPPED_BOX]
    assert shown.withholds_filing
    assert shown.box == _CAPPED_BOX


def test_a_capped_value_whose_resolver_stated_no_outcome_withholds(operation: PinnedAuthorityOperation) -> None:
    """Teeth for the proven-zero pass: the same zero without the resolver's statement is refused."""
    snapshot = _snapshot(operation)
    stated = _resolve(snapshot, *_fully_paid())
    silent = stated.model_copy(update={"value_outcomes": {}})

    emitted, persisted = _calculated(operation, silent)

    (note,) = _capped_notes(emitted)
    assert note.value_outcome is None
    assert [issue.reason for issue in _persisted_for(persisted)] == [_REASON]
    reasons = _refused_reasons(operation, _revision(_work_unit(snapshot), persisted, stamp=_stamp(snapshot, operation)))
    assert reasons is not None and _REASON in reasons


def test_a_revision_without_a_stamp_or_with_another_digest_is_outdated(operation: PinnedAuthorityOperation) -> None:
    snapshot = _snapshot(operation)
    unit = _work_unit(snapshot)
    current = _stamp(snapshot, operation)
    other = CalculationScreenStamp(contract_version=current.contract_version, digest="0" * 64)

    assert _refused_reasons(operation, _revision(unit, (), stamp=current)) is None
    assert _refused_reasons(operation, _revision(unit, (), stamp=None)) == {CALCULATION_SCREEN_OUTDATED_REASON}
    assert _refused_reasons(operation, _revision(unit, (), stamp=other)) == {CALCULATION_SCREEN_OUTDATED_REASON}
    assert CALCULATION_SCREEN_OUTDATED_REASON not in GATE_REFUSED_REASONS, "the reason is derived, never persisted"


def test_a_filed_revision_is_not_screened_again(operation: PinnedAuthorityOperation) -> None:
    """A filed revision without a stamp, or with another digest, is never refused as stale."""
    snapshot = _snapshot(operation)
    unit = _work_unit(snapshot)
    current = _stamp(snapshot, operation)
    other = CalculationScreenStamp(contract_version=current.contract_version, digest="0" * 64)

    for state in (CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO):
        for stamp in (None, other):
            assert _refused_reasons(operation, _revision(unit, (), stamp=stamp, state=state)) is None, (state, stamp)


def test_a_filed_revision_carrying_a_blocking_note_is_still_refused_at_export(
    operation: PinnedAuthorityOperation,
) -> None:
    """The filed state exempts the revision from the screen only: the note it was persisted with still refuses."""
    snapshot = _snapshot(operation)
    _, persisted = _calculated(operation, _resolve(snapshot, *declared_pair()))
    # Only the retención note is persisted here, so the refusal names its box.
    persisted = tuple(_persisted_for(persisted))
    assert [issue.reason for issue in persisted] == [_REASON]
    unit = _work_unit(snapshot)

    for state in (CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO):
        revision = _revision(unit, persisted, stamp=None, state=state)
        with pytest.raises(ModeloCalculationBlockedError) as refused:
            require_work_unit_calculation_unblocked(
                work_unit=unit, revision=revision, action="export", operation=operation
            )
        context = refused.value.context or {}
        assert context["reason"] == _REASON, state
        assert context["box"] == _CAPPED_BOX, state


def test_the_stamp_reads_only_the_screen_declarations(operation: PinnedAuthorityOperation) -> None:
    """A change no screen reads keeps the stamp; a changed cap moves it."""
    snapshot = _snapshot(operation)
    current = _stamp(snapshot, operation)
    revision = snapshot.revision
    unrelated = revision.model_copy(update={"legal_refs": (*revision.legal_refs, "ley-35-2006:art-14")})
    bindings = tuple(
        binding.model_copy(
            update={"grade_cap": binding.grade_cap.model_copy(update={"legal_refs": binding.grade_cap.legal_refs[:1]})}
        )
        if binding.grade_cap is not None
        else binding
        for binding in revision.bindings
    )
    recapped = revision.model_copy(update={"bindings": bindings})

    assert _stamp(snapshot.model_copy(update={"revision": unrelated}), operation) == current
    assert _stamp(snapshot.model_copy(update={"revision": recapped}), operation) != current


def test_the_income_box_fed_by_the_same_provider_kind_is_capped_on_its_own_binding(
    operation: PinnedAuthorityOperation,
) -> None:
    """Income is dated by the bank like the withholding beside it, so each box carries its own declared cap."""
    for modelo, year, period, casilla in (("130", _YEAR, _QUARTER, "01"), ("100", 2025, "0A", "0171")):
        snapshot = operation.snapshot(modelo, filing_year=year, period=period)
        bindings = revision_bindings_by_id(snapshot.revision)
        (bound,) = [
            item
            for item in snapshot.revision.casillas
            if str(item.id) == casilla and item.input_kind is InputKind.BOUND and item.binding is not None
        ]
        assert bound.binding is not None
        binding = bindings[bound.binding]
        assert binding.source is BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION
        assert binding.grade_cap is not None
        reached = {
            str(casilla_id)
            for entry in capped_binding_reach(
                snapshot.revision, authority=operation, effective_date=snapshot_reach_date(snapshot)
            ).values()
            for casilla_id in entry.casilla_ids
        }
        assert casilla in reached
