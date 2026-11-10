"""A grade-capped retención credit is shown by the calculation and refused at check, export and recording.

The published registry caps no binding since the withholding credits were
promoted, so this module declares the cap in memory on the Modelo 130 casilla
06 binding, the binding it was first declared on. Each case runs the real
ledger renta-income resolver over synthetic ledger rows against that copy of
the published Modelo 130 revision, then the real post-merge emission, the real
durable projection a calculation persists, and the real calculation-note gate
on a revision stamped as a calculation under the published authority stamps it.
Every expected figure is invoice arithmetic worked out in the test.

The resolver states what a capped value rests on. A zero over rows that carry
no retención is a proven zero and withholds nothing. A zero over rows whose
retención was left out, a declared credit, and a capped value whose resolver
stated nothing all withhold checking, exporting and recording.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind, BindingValueOutcome
from ....core.casilla_id import CasillaId
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_grade_cap_reach import capped_binding_reach, snapshot_reach_date
from ....domain.calculations.registry.binding_targets import revision_bindings_by_id
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from ....domain.calculations.registry.tests.grade_cap_support import recapped_snapshot
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
from ...aggregation.tests.ledger_source_mesh_support import (
    InMemoryTransactionCatalogueRepository,
    cash_criterion_profile,
)
from ...aggregation.tests.renta_income_aggregation_support import actividad_transaction, catalogue_read_ports
from ...aggregation.tests.test_actividad_retencion_declared_credit import (
    BUCKET,
    declared_pair,
)
from ..advisory_binding_value import add_advisory_binding_value_diagnostics
from ..bucket_unrouted_source_issues import unrouted_source_issues
from ..calculation_note_gate import (
    ModeloCalculationBlockedError,
    calculation_filed_before_grade_cap,
    calculation_screen_outdated,
    filed_before_grade_cap,
    gate_refuses,
    require_work_unit_calculation_unblocked,
    saved_calculation_filed_before_grade_cap,
    saved_calculation_screen_outdated,
)
from ..calculation_notes import (
    CALCULATION_SCREEN_OUTDATED_REASON,
    FILED_BEFORE_GRADE_CAP_REASON,
    GATE_REFUSED_REASONS,
)
from ..calculation_screen import calculation_screen_stamp
from ..printed_boxes import snapshot_printed_boxes
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_CLOCK = datetime(_YEAR, 4, 2, 9, 0, tzinfo=UTC)
_QUARTER = "1T"
_CAPPED_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"
_CAPPED_BOX = "06"
# The 2025 Modelo 130 box a capped binding reaches: the stated retenciones casilla 06. The bank-dated
# income and expense casillas keep their grade once the imputation criterion is dated.
_CAPPED_BOXES = frozenset({_CAPPED_BOX})
_PROVEN_ZEROS = dict.fromkeys(_CAPPED_BOXES, Decimal("0"))
_REASON = "advisory_binding_value"
# Hand-derived: 150,00 at 15 % of 1.000,00 plus 140,00 at 7 % of 2.000,00.
_DECLARED_CREDIT = Decimal("290.00")
_BASE = Decimal("2000.00")
# Hand-derived: 21 % of 2.000,00.
_IVA = Decimal("420.00")
# Hand-derived: 2.000,00 + 420,00 - 300,00, the 15 % retención on 2.000,00 kept by the client.
_SHORT_PAID_CASH = Decimal("2120.00")


def _published(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    return operation.snapshot("130", filing_year=_YEAR, period=_QUARTER)


def _snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    """The published Modelo 130 revision with casilla 06's binding capped in memory."""
    return recapped_snapshot(_published(operation), _CAPPED_BINDING)


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
        name=f"130-{_YEAR}-1T",
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
            profile=cash_criterion_profile(_YEAR),
        )
    )


def _receipt(provider_id: str, cash: Decimal) -> TransactionCatalogue:
    """One activity receipt whose own record states a 2.000,00 base and 420,00 IVA at 21 %."""
    return TransactionCatalogue.from_transactions(
        (
            actividad_transaction(
                provider_id,
                value_date=date(_YEAR, 2, 10),
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
    """The stamp a calculation under the published authority carries, which the gate recomputes."""
    return calculation_screen_stamp(_published(operation), operation=operation)


def _revision(
    unit: WorkUnit,
    issues: tuple[CalculationSourceIssue, ...],
    *,
    stamp: CalculationScreenStamp | None,
    state: CalculationRevisionState = CalculationRevisionState.BORRADOR,
    casilla_values: dict[CasillaId, Decimal] | None = None,
) -> CalculationRevision:
    filed = state in {CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO}
    values = {} if casilla_values is None else casilla_values
    verified = filed or state is CalculationRevisionState.VERIFICADO_COMPLETO
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values=values,
            source_issues=issues,
            filing_instance_evidence=None,
            source_provenance=(),
            screen_stamp=stamp,
        ),
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=str(unit.modelo), revision_id=unit.revision_id, modelo_year=_YEAR, period=_QUARTER
        ),
        state=state,
        casilla_values=values,
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id, value=value, legal_refs=("rd-439-2007:art-110",), source_refs=("gate-test",)
            )
            for casilla_id, value in values.items()
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=issues,
        screen_stamp=stamp,
        verified_at=_CLOCK if verified else None,
        verified_by="operator" if verified else None,
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


def _refused_reasons(
    operation: PinnedAuthorityOperation, revision: CalculationRevision, unit: WorkUnit | None = None
) -> set[str] | None:
    """The reasons every gated action refuses with, or ``None`` when each admits the revision."""
    unit = _work_unit(_snapshot(operation)) if unit is None else unit
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


def _capped_notes(emitted: CalculationSourceResolution):
    return [diagnostic for diagnostic in emitted.diagnostics if diagnostic.reason == _REASON]


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
    # The proven zero persists with its stated outcome and sentence, so a reopened declaration still shows it.
    (issue,) = [issue for issue in persisted if issue.reason == _REASON]
    assert issue.casilla_id == _CAPPED_BOX
    assert issue.value_outcome is BindingValueOutcome.PROVEN_ZERO
    assert issue.fact is not None and issue.fact.sentence is CalculationNoteSentence.ADVISORY_VALUE_PROVEN_ZERO
    revision = _revision(_work_unit(snapshot), persisted, stamp=_stamp(snapshot, operation))
    assert _refused_reasons(operation, revision) is None


def test_a_zero_over_rows_whose_retencion_was_left_out_withholds(operation: PinnedAuthorityOperation) -> None:
    snapshot = _snapshot(operation)
    resolution = _resolve(snapshot, *_short_paid())

    assert resolution.binding_values[_CAPPED_BINDING] == Decimal("0")
    assert resolution.value_outcomes[_CAPPED_BINDING] is BindingValueOutcome.FROM_BEARING_ROWS
    emitted, persisted = _calculated(operation, resolution)

    (note,) = _capped_notes(emitted)
    assert note.value_outcome is BindingValueOutcome.FROM_BEARING_ROWS
    (issue,) = [issue for issue in persisted if issue.reason == _REASON]
    assert issue.casilla_id == _CAPPED_BOX
    assert issue.binding_source is BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION
    assert issue.value_outcome is BindingValueOutcome.FROM_BEARING_ROWS
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
    (shown,) = [item for item in form.calculation_notes if item.reason == _REASON]
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
    assert [issue.reason for issue in persisted if issue.reason == _REASON] == [_REASON]
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
            revision = _revision(unit, (), stamp=stamp, state=state, casilla_values=_PROVEN_ZEROS)
            assert _refused_reasons(operation, revision) is None, (state, stamp)


# Hand-derived: the 150,00 and 360,00 retenciones of two invoiced receipts, as a Modelo 130 casilla 06
# filed before the cap existed holds them.
_FILED_CAPPED_FIGURE = Decimal("510.00")


def _export_refusal(
    operation: PinnedAuthorityOperation, revision: CalculationRevision, unit: WorkUnit
) -> ModeloCalculationBlockedError:
    with pytest.raises(ModeloCalculationBlockedError) as refused:
        require_work_unit_calculation_unblocked(work_unit=unit, revision=revision, action="export", operation=operation)
    return refused.value


def test_a_revision_filed_before_the_cap_with_a_capped_figure_is_found_by_the_reach(
    operation: PinnedAuthorityOperation,
) -> None:
    """Under a revision that caps casilla 06, a filed unstamped figure there is the box export refuses on."""
    snapshot = _snapshot(operation)
    unit = _work_unit(snapshot)

    for state in (CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO):
        # The figure is named where it stands; with no value at all, some capped box is unresolved.
        for values, boxes in (
            ({**_PROVEN_ZEROS, _CAPPED_BOX: _FILED_CAPPED_FIGURE}, {_CAPPED_BOX}),
            ({}, _CAPPED_BOXES),
        ):
            revision = _revision(unit, (), stamp=None, state=state, casilla_values=values)
            assert filed_before_grade_cap(revision, snapshot, operation) in boxes, (state, values)
            # The published revision caps nothing, so the same filed revision exports.
            assert _refused_reasons(operation, revision) is None, (state, values)
            assert (
                calculation_filed_before_grade_cap(
                    revision, modelo="130", filing_year=_YEAR, period=unit.period, operation=operation
                )
                is None
            )
    assert gate_refuses(FILED_BEFORE_GRADE_CAP_REASON, None)
    assert FILED_BEFORE_GRADE_CAP_REASON not in GATE_REFUSED_REASONS, "the reason is derived, never persisted"


def test_a_revision_filed_before_the_cap_with_a_zero_or_a_stamp_exports(operation: PinnedAuthorityOperation) -> None:
    snapshot = _snapshot(operation)
    unit = _work_unit(snapshot)
    current = _stamp(snapshot, operation)
    other = CalculationScreenStamp(contract_version=current.contract_version, digest="0" * 64)
    capped = {**_PROVEN_ZEROS, _CAPPED_BOX: _FILED_CAPPED_FIGURE}
    filed = CalculationRevisionState.PRESENTADO

    unstamped_zero = _revision(unit, (), stamp=None, state=filed, casilla_values=_PROVEN_ZEROS)
    assert _refused_reasons(operation, unstamped_zero) is None
    for stamp in (current, other):
        stamped = _revision(unit, (), stamp=stamp, state=filed, casilla_values=capped)
        assert _refused_reasons(operation, stamped) is None, stamp
        found = calculation_filed_before_grade_cap(
            stamped, modelo="130", filing_year=_YEAR, period=unit.period, operation=operation
        )
        assert found is None
    # A revision not yet filed is the screen's to judge, never this reason's.
    unfiled = _revision(unit, (), stamp=None, state=CalculationRevisionState.VERIFICADO_COMPLETO, casilla_values=capped)
    assert _refused_reasons(operation, unfiled) == {CALCULATION_SCREEN_OUTDATED_REASON}


def test_a_revision_filed_before_the_cap_under_a_modelo_without_caps_exports(
    operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 303 caps no binding, so an unstamped filed 303 keeps exporting whatever its boxes hold."""
    snapshot = operation.snapshot("303", filing_year=_YEAR, period=_QUARTER)
    reach = capped_binding_reach(snapshot.revision, authority=operation, effective_date=snapshot_reach_date(snapshot))
    assert not reach
    period = Period.from_year_and_code(_YEAR, _QUARTER)
    revision_id = str(snapshot.revision.id)
    unit = _work_unit(_snapshot(operation)).model_copy(
        update={
            "modelo": ModeloCode("303"),
            "revision_id": revision_id,
            "work_unit_id": derive_work_unit_id(
                bucket_id=BUCKET, modelo="303", filing_year=_YEAR, period=period, revision_id=revision_id
            ),
        }
    )
    revision = _revision(unit, (), stamp=None, state=CalculationRevisionState.PRESENTADO, casilla_values={})

    assert _refused_reasons(operation, revision, unit) is None


def test_a_filed_revision_carrying_a_blocking_note_is_still_refused_at_export(
    operation: PinnedAuthorityOperation,
) -> None:
    """The filed state exempts the revision from the screen only: the note it was persisted with still refuses."""
    snapshot = _snapshot(operation)
    _, persisted = _calculated(operation, _resolve(snapshot, *declared_pair()))
    assert [issue.reason for issue in persisted if issue.reason == _REASON] == [_REASON]
    unit = _work_unit(snapshot)

    # Only a calculation that ran the screen can carry the note, so the revision is stamped.
    for state in (CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO):
        revision = _revision(unit, persisted, stamp=_stamp(snapshot, operation), state=state)
        with pytest.raises(ModeloCalculationBlockedError) as refused:
            require_work_unit_calculation_unblocked(
                work_unit=unit, revision=revision, action="export", operation=operation
            )
        context = refused.value.context or {}
        assert context["reason"] == _REASON, state
        assert context["box"] == _CAPPED_BOX, state


def test_the_stamp_reads_only_the_screen_declarations(operation: PinnedAuthorityOperation) -> None:
    """A change no screen reads keeps the stamp; a declared or changed cap moves it."""
    published = _published(operation)
    snapshot = _snapshot(operation)
    uncapped = calculation_screen_stamp(published, operation=operation)
    current = calculation_screen_stamp(snapshot, operation=operation)
    assert current != uncapped
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

    assert calculation_screen_stamp(snapshot.model_copy(update={"revision": unrelated}), operation=operation) == current
    assert calculation_screen_stamp(snapshot.model_copy(update={"revision": recapped}), operation=operation) != current


def test_an_instalment_period_without_a_date_span_is_read_at_the_close_of_its_ejercicio(
    operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 202 2P spans no calendar dates and caps no binding, so its screen and export gate need no span."""
    snapshot = operation.snapshot("202", filing_year=_YEAR, period="2P")
    period = Period.from_year_and_code(_YEAR, "2P")
    assert not period.has_date_span()
    assert snapshot_reach_date(snapshot) == date(_YEAR, 12, 31)
    assert not capped_binding_reach(
        snapshot.revision, authority=operation, effective_date=snapshot_reach_date(snapshot)
    )
    revision_id = str(snapshot.revision.id)
    unit = _work_unit(_snapshot(operation)).model_copy(
        update={
            "modelo": ModeloCode("202"),
            "period": period,
            "revision_id": revision_id,
            "work_unit_id": derive_work_unit_id(
                bucket_id=BUCKET, modelo="202", filing_year=_YEAR, period=period, revision_id=revision_id
            ),
        }
    )
    revision = _revision(unit, (), stamp=None, state=CalculationRevisionState.PRESENTADO, casilla_values={})
    assert _refused_reasons(operation, revision, unit) is None
    stamped = _revision(
        unit,
        (),
        stamp=calculation_screen_stamp(snapshot, operation=operation),
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
    )
    assert _refused_reasons(operation, stamped, unit) is None


def test_a_capped_modelo_keeps_the_reach_date_at_the_close_of_its_period(operation: PinnedAuthorityOperation) -> None:
    assert snapshot_reach_date(_snapshot(operation)) == date(_YEAR, 3, 31)


def test_the_income_box_fed_by_the_same_provider_kind_stays_filing_grade(operation: PinnedAuthorityOperation) -> None:
    """The cap is on one binding, so Modelo 130 casilla 01 and Modelo 100 casilla 0171 keep their grade."""
    for modelo, year, period, casilla in (
        ("130", _YEAR, _QUARTER, "01"),
        ("100", newest_authored_edition("100"), "0A", "0171"),
    ):
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
        assert binding.grade_cap is None
        reached = {
            str(casilla_id)
            for entry in capped_binding_reach(
                snapshot.revision, authority=operation, effective_date=snapshot_reach_date(snapshot)
            ).values()
            for casilla_id in entry.casilla_ids
        }
        assert casilla not in reached


def test_review_reads_a_revision_stale_exactly_as_the_gate_does(operation: PinnedAuthorityOperation) -> None:
    """The saved-calculation check and the gate answer the same for every stamp and state."""
    snapshot = _snapshot(operation)
    unit = _work_unit(snapshot)
    current = _stamp(snapshot, operation)
    other = CalculationScreenStamp(contract_version=current.contract_version, digest="0" * 64)
    states = (
        CalculationRevisionState.BORRADOR,
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
    )
    found = {}
    for state in states:
        for stamp in (current, None, other):
            revision = _revision(unit, (), stamp=stamp, state=state, casilla_values={_CAPPED_BOX: Decimal("0")})
            saved = saved_calculation_screen_outdated(
                revision, modelo="130", filing_year=_YEAR, period=unit.period, operation=operation
            )
            gated = calculation_screen_outdated(
                revision, modelo="130", filing_year=_YEAR, period=unit.period, operation=operation
            )
            assert saved is gated, (state, stamp)
            found[(state, stamp is current)] = saved
    assert found[(CalculationRevisionState.VERIFICADO_COMPLETO, False)] is True
    assert found[(CalculationRevisionState.VERIFICADO_COMPLETO, True)] is False
    assert found[(CalculationRevisionState.PRESENTADO, False)] is False


def test_a_revision_whose_snapshot_cannot_be_selected_is_stale_unless_filed(
    operation: PinnedAuthorityOperation,
) -> None:
    """With no snapshot to screen against, nothing shows an unfiled revision current."""
    unit = _work_unit(_snapshot(operation))
    current = _stamp(_snapshot(operation), operation)
    unfiled = _revision(unit, (), stamp=current, state=CalculationRevisionState.VERIFICADO_COMPLETO)
    filed = _revision(unit, (), stamp=None, state=CalculationRevisionState.PRESENTADO)

    def screened(revision: CalculationRevision) -> bool:
        return saved_calculation_screen_outdated(
            revision, modelo="999", filing_year=_YEAR, period=unit.period, operation=operation
        )

    assert screened(unfiled) is True
    assert screened(filed) is False
    assert (
        saved_calculation_filed_before_grade_cap(
            filed.model_copy(update={"casilla_values": {}}),
            modelo="999",
            filing_year=_YEAR,
            period=unit.period,
            operation=operation,
        )
        is True
    )
