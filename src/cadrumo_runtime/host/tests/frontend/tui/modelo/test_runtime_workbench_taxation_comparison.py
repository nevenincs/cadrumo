"""The workbench source reads the comparison through its pinned session and keeps a refusal's recorded words.

The transport boundary is replaced by a controller that settles as the test says;
the settlement rules under test are the source's own: only a successful, no-effect
receipt yields a result, the result must name the pinned profile and the declaration
asked about, and a refusal surfaces as the registered error the executor recorded,
so the screen can show its served words and verdict.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from cadrumo.application.modelo.taxation_comparison import (
    TaxationComparisonRefusal,
    TaxationRecommendation,
    TaxationRecommendationReason,
    taxation_comparison_refusal,
)
from cadrumo.application.modelo.taxation_comparison_operation import (
    ModeloTaxationComparisonProjection,
    ModeloTaxationComparisonRequest,
)
from cadrumo.application.modelo.taxation_comparison_words import (
    individual_branch_caveat_words,
    recommendation_reason_words,
)
from cadrumo.application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
from cadrumo.core.config import override_settings
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection, OperationTerminalCondition
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.modelos.work_unit import WorkUnitState
from cadrumo.entrypoints.tui.refusal.served import served_refusal
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .....frontend.tui.modelo import runtime_workbench_reads as reads

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORK_UNIT = "c" * 64
_YEAR = newest_authored_edition("100")


@dataclass
class _ClientIdentity:
    profile_id: UUID = field(default_factory=uuid4)
    session_id: UUID = field(default_factory=uuid4)
    frontend: OperationFrontendProjection = OperationFrontendProjection.TUI


def _projection(
    profile_id: UUID, *, work_unit_id: str = _WORK_UNIT, modelo: str = "100"
) -> ModeloTaxationComparisonProjection:
    joint, individual, delta = Decimal("500.00"), Decimal("620.00"), Decimal("120.00")
    reason = TaxationRecommendationReason.CONJUNTA_LOWER_RESULT
    return ModeloTaxationComparisonProjection(
        profile_id=profile_id,
        work_unit_id=work_unit_id,
        filing_year=_YEAR,
        modelo=modelo,
        revision="synthetic-revision",
        conjunta_cuota_resultante="900.00",
        individual_cuota_resultante="1000.00",
        conjunta_resultado=str(joint),
        individual_resultado=str(individual),
        delta_resultado=str(delta),
        recommendation=TaxationRecommendation.CONJUNTA,
        recommendation_reason=reason,
        recommendation_reason_words=recommendation_reason_words(
            reason,
            conjunta_resultado=joint,
            individual_resultado=individual,
            delta_resultado=delta,
            language=OutputLanguage.EN,
        ),
        words_language=OutputLanguage.EN,
        individual_branch_single_earner_only=True,
        individual_branch_caveat=individual_branch_caveat_words(OutputLanguage.EN),
    )


class _Controller:
    """One settled operation: the receipt, the recorded detail and the result the test serves."""

    def __init__(self, *, detail: OperationErrorDetailV1 | None, result: ModeloTaxationComparisonProjection | None):
        self.detail = detail
        self.result = result
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def settled_error_detail(self, _projection: object) -> OperationErrorDetailV1 | None:
        return self.detail

    async def read_settled_result(self, _projection: object, result_type: type, **_kwargs: object) -> object:
        assert result_type is ModeloTaxationComparisonProjection and self.result is not None
        return self.result


def _source(
    monkeypatch: pytest.MonkeyPatch,
    *,
    condition: OperationTerminalCondition,
    effect: OperationEffect = OperationEffect.NONE,
    refusal_ref: str | None = None,
    detail: OperationErrorDetailV1 | None = None,
    result_of: Callable[[UUID], ModeloTaxationComparisonProjection] | None = None,
) -> tuple[reads.RuntimeModeloWorkbenchSource, _ClientIdentity, list[dict[str, object]]]:
    client = _ClientIdentity()
    submitted: list[dict[str, object]] = []
    result = None if result_of is None else result_of(client.profile_id)
    controller = _Controller(detail=detail, result=result)

    class _Submitter:
        @staticmethod
        async def submit(_client: object, **kwargs: object) -> _Controller:
            submitted.append(kwargs)
            return controller

    async def terminal(_controller: object, **_kwargs: object) -> object:
        return SimpleNamespace(
            terminal_condition=condition, effect=effect, refusal_ref=refusal_ref, failure_error_code=None
        )

    monkeypatch.setattr(reads, "OperationController", _Submitter)
    monkeypatch.setattr(reads, "await_terminal_projection", terminal)
    source = reads.RuntimeModeloWorkbenchSource(
        cast(FrontendClient, client),
        DeclarationsWorkspaceDeclarationRefV1(
            work_unit_id=_WORK_UNIT,
            modelo="100",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, "0A"),
            state=WorkUnitState.BORRADOR,
            has_current_calculation=True,
            has_current_filing=False,
        ),
    )
    return source, client, submitted


def test_a_successful_no_effect_receipt_yields_the_result_naming_the_pinned_profile_and_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, client, submitted = _source(
        monkeypatch, condition=OperationTerminalCondition.SUCCEEDED, result_of=_projection
    )

    served = source.compare_taxation()

    assert served.profile_id == client.profile_id and served.work_unit_id == _WORK_UNIT
    request = submitted[0]["payload"]
    assert isinstance(request, ModeloTaxationComparisonRequest)
    assert request.profile_id == client.profile_id
    assert request.work_unit_id == _WORK_UNIT
    assert submitted[0]["definition_id"] == "modelo.work.compare_taxation"
    assert submitted[0]["expected_session_id"] == client.session_id


@pytest.mark.parametrize(
    "mismatch",
    [
        lambda _profile_id: _projection(uuid4()),
        lambda profile_id: _projection(profile_id, work_unit_id="d" * 64),
        lambda profile_id: _projection(profile_id, modelo="303"),
    ],
    ids=["other profile", "other declaration", "other modelo"],
)
def test_a_result_that_names_another_profile_or_declaration_is_refused(
    monkeypatch: pytest.MonkeyPatch, mismatch: Callable[[UUID], ModeloTaxationComparisonProjection]
) -> None:
    source, _, _ = _source(monkeypatch, condition=OperationTerminalCondition.SUCCEEDED, result_of=mismatch)

    with pytest.raises(RefusalError) as refused:
        source.compare_taxation()

    assert refused.value.reason == RefusalCode.INVALID_FRAME.value


def test_a_receipt_that_records_an_effect_is_not_a_read_and_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    source, _, _ = _source(
        monkeypatch,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UNKNOWN,
        result_of=_projection,
    )

    with pytest.raises(RefusalError):
        source.compare_taxation()


def test_a_refusal_surfaces_as_the_error_it_recorded_with_its_served_words_and_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = taxation_comparison_refusal(
        TaxationComparisonRefusal.UNRESOLVED_BOXES, casilla_ids=("0001", "0002"), work_unit_id=_WORK_UNIT
    )
    detail = build_operation_error_detail(original)
    assert detail is not None
    source, _, _ = _source(
        monkeypatch,
        condition=OperationTerminalCondition.REFUSED,
        refusal_ref="REFUSED_TAXATION_COMPARISON",
        detail=detail,
    )

    with override_settings(cadrumo_output_language="en"), pytest.raises(RecordedRegisteredError) as refused:
        source.compare_taxation()
    again = build_operation_error_detail(refused.value)
    assert again is not None
    served = served_refusal(again)
    original_served = served_refusal(detail)

    assert again.error_code == detail.error_code
    assert again.context_mapping()["casilla_ids"] == "0001, 0002"
    assert served is not None and original_served is not None
    assert served.verdict == original_served.verdict and served.verdict is not None
    assert served.refusal_words is not None and served.refusal_words.words


def test_a_refusal_with_no_recorded_detail_is_the_runtimes_refusal_code(monkeypatch: pytest.MonkeyPatch) -> None:
    source, _, _ = _source(
        monkeypatch, condition=OperationTerminalCondition.REFUSED, refusal_ref="REFUSED_TAXATION_COMPARISON"
    )

    with pytest.raises(FrontendRefusedError) as refused:
        source.compare_taxation()

    assert refused.value.reason == "REFUSED_TAXATION_COMPARISON"
