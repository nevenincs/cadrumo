"""Portfolio summaries read persisted calculations and isolate unavailable registry rows."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal

import pytest

from ....application.modelo.calculation_actions import calculate_modelo_revision
from ....application.modelo.declaration_summary import DeclarationSummaryState, declaration_summary
from ....application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from ....application.modelo.work_form_models import ModeloFormResultDirection
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.calculation_revision_amendment import (
    CalculationRevisionAmendmentIdentity,
    CalculationRevisionAmendmentKind,
)
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    derive_verification_report_id,
)
from ....domain.modelos.work_unit import WorkUnitState
from ..modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.fixture(scope="module", params=["13000", "0"])
def persisted(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Iterator[SeededOperatorWork]:
    with seeded_operator_work(tmp_path_factory.mktemp(f"summary-{request.param}")) as work:
        calculate_modelo_revision(
            work.work_unit_id,
            ports=work.ports,
            clock=SEEDED_AT,
            casilla_inputs={
                "01": Decimal(0),
                "02": Decimal(0),
                "06": Decimal(0),
                "08": Decimal(0),
                "10": Decimal(0),
                "16": Decimal(0),
                "18": Decimal(0),
            },
            binding_values={
                "irpf.previous_year_economic_activity_net_income": Decimal(request.param),
                "modelo-130-resultados-negativos-anteriores": Decimal(0),
            },
        )
        yield work


def _declaration(work: SeededOperatorWork):
    unit = work.work_unit
    return DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=unit.work_unit_id,
        modelo=unit.modelo,
        filing_year=unit.filing_year,
        period=unit.period,
        state=unit.state,
        has_current_calculation=True,
        has_current_filing=False,
    )


def test_a_persisted_zero_and_a_credit_keep_their_settlement_directions(persisted: SeededOperatorWork) -> None:
    head = persisted.require_head()

    summary = declaration_summary(
        _declaration(persisted),
        revisions={head.calculation_revision_id: head},
        verification=None,
        operation=persisted.operation,
    )

    assert summary.state is DeclarationSummaryState.CALCULATED
    assert summary.blocking_count is None, "without a check the blocking count is unknown, not zero"
    assert not summary.checked
    assert summary.result is not None
    # With no current income, previous-year income of EUR 13,000 gives no
    # deduction; EUR 0 gives a EUR 100 deduction and a negative instalment.
    previous = head.binding_overrides["irpf.previous_year_economic_activity_net_income"]
    expected = {"13000": Decimal(0), "0": Decimal(-100)}[previous]
    assert summary.result.value == expected
    assert summary.result.direction is (
        ModeloFormResultDirection.NIL if expected == 0 else ModeloFormResultDirection.TO_DEDUCT_LATER
    )


def test_a_draft_has_no_calculated_result_or_claim_of_having_been_checked(persisted: SeededOperatorWork) -> None:
    declaration = _declaration(persisted).model_copy(update={"has_current_calculation": False})

    summary = declaration_summary(declaration, revisions={}, verification=None, operation=persisted.operation)

    assert summary.state is DeclarationSummaryState.DRAFT
    assert summary.result is None and summary.blocking_count is None and not summary.checked


def test_the_summary_retains_correction_identity_instead_of_calling_it_an_original_draft(
    persisted: SeededOperatorWork,
) -> None:
    original = persisted.require_head()
    identity = CalculationRevisionAmendmentIdentity(
        kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        amends_filing_record_id="f" * 64,
        m303_rectificativa_motive=None,
    )
    correction = original.model_copy(
        update={"amendment_identity": identity, "amendment_reason": "Synthetic correction"}
    )
    for head, expected in ((original, False), (correction, True)):
        summary = declaration_summary(
            _declaration(persisted),
            revisions={head.calculation_revision_id: head},
            verification=None,
            operation=persisted.operation,
        )
        assert summary.is_correction is expected
        assert summary.result is not None


def test_an_absent_settlement_value_never_becomes_a_zero_result(persisted: SeededOperatorWork) -> None:
    head = persisted.require_head().model_copy(update={"casilla_values": {}})

    summary = declaration_summary(
        _declaration(persisted),
        revisions={head.calculation_revision_id: head},
        verification=None,
        operation=persisted.operation,
    )

    assert summary.result is None


@pytest.mark.parametrize(
    ("state", "recorded", "expected"),
    [
        (CalculationRevisionState.VERIFICADO_COMPLETO, False, DeclarationSummaryState.CHECKED),
        (CalculationRevisionState.PRESENTADO, True, DeclarationSummaryState.RECORDED),
        (CalculationRevisionState.PRESENTADO_SUPERSEDIDO, False, DeclarationSummaryState.SUPERSEDED),
    ],
)
def test_lifecycle_states_are_not_collapsed_into_one_filed_flag(
    persisted: SeededOperatorWork,
    state: CalculationRevisionState,
    recorded: bool,
    expected: DeclarationSummaryState,
) -> None:
    head = persisted.require_head().model_copy(update={"state": state})
    declaration = _declaration(persisted).model_copy(update={"has_current_filing": recorded})

    summary = declaration_summary(
        declaration, revisions={head.calculation_revision_id: head}, verification=None, operation=persisted.operation
    )

    assert summary.state is expected


def test_a_registry_refusal_is_confined_to_its_row_and_keeps_technical_details_private(
    persisted: SeededOperatorWork,
) -> None:
    head = persisted.require_head()
    declaration = _declaration(persisted)
    # Same current head, but a natural coordinate outside the published support.
    refused = declaration.model_copy(update={"modelo": "999"})

    bad = declaration_summary(
        refused, revisions={head.calculation_revision_id: head}, verification=None, operation=persisted.operation
    )
    good = declaration_summary(
        declaration, revisions={head.calculation_revision_id: head}, verification=None, operation=persisted.operation
    )

    assert bad.state is DeclarationSummaryState.UNREADABLE
    assert bad.result is None and bad.technical_reason
    assert "technical_reason" not in bad.model_dump()
    assert good.state is DeclarationSummaryState.CALCULATED and good.result is not None


def test_a_discarded_declaration_is_preserved_without_being_reported_as_filed(persisted: SeededOperatorWork) -> None:
    declaration = _declaration(persisted).model_copy(update={"state": WorkUnitState.DESCARTADO})

    summary = declaration_summary(declaration, revisions={}, verification=None, operation=persisted.operation)

    assert summary.state is DeclarationSummaryState.DISCARDED
    assert not summary.checked and summary.result is None


def test_a_different_stored_registry_revision_never_borrows_the_current_revisions_meaning(
    persisted: SeededOperatorWork,
) -> None:
    original = persisted.require_head()
    head = original.model_copy(
        update={
            "registry_snapshot_ref": original.registry_snapshot_ref.model_copy(
                update={"revision_id": "a-different-revision"},
            )
        }
    )

    summary = declaration_summary(
        _declaration(persisted),
        revisions={head.calculation_revision_id: head},
        verification=None,
        operation=persisted.operation,
    )

    assert summary.state is DeclarationSummaryState.UNREADABLE and summary.result is None


def test_only_the_latest_current_heads_check_supplies_its_blocking_count(persisted: SeededOperatorWork) -> None:
    head = persisted.require_head()
    blocking = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id="01",
        message_locale_key="application.modelo.verification.missing_required_casilla",
        legal_refs=head.observations[0].legal_refs,
    )

    def report(*, current: bool, findings: tuple[ModeloVerificationFinding, ...], minute: int):
        revision_id = head.calculation_revision_id if current else "f" * 64
        status = VerificationCompletenessStatus.BLOCKED if findings else VerificationCompletenessStatus.COMPLETE
        return VerificationReport(
            verification_report_id=derive_verification_report_id(
                calculation_revision_id=revision_id,
                completeness_status=status,
                findings=findings,
                verified_by="test:portfolio",
            ),
            calculation_revision_id=revision_id,
            registry_snapshot_ref=head.registry_snapshot_ref,
            completeness_status=status,
            findings=findings,
            run_at=SEEDED_AT + timedelta(minutes=minute),
            verified_by="test:portfolio",
            granted_verificado_completo=not findings,
        )

    previous = report(current=True, findings=(blocking,), minute=1)
    latest = report(current=True, findings=(), minute=2)
    unrelated = report(current=False, findings=(blocking,), minute=3)
    blocked = declaration_summary(
        _declaration(persisted),
        revisions={head.calculation_revision_id: head},
        verification=VerificationReportCatalogue(reports={previous.verification_report_id: previous}),
        operation=persisted.operation,
    )
    checked = declaration_summary(
        _declaration(persisted),
        revisions={head.calculation_revision_id: head},
        verification=VerificationReportCatalogue(
            reports={item.verification_report_id: item for item in (previous, latest, unrelated)}
        ),
        operation=persisted.operation,
    )

    assert blocked.state is DeclarationSummaryState.BLOCKED and blocked.blocking_count == 1
    assert checked.blocking_count == 0
    assert checked.state is DeclarationSummaryState.CALCULATED
