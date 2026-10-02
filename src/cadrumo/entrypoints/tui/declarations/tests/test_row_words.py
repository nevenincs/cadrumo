"""An unclassified result keeps its sign instead of implying a payment."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....application.modelo.declaration_summary import DeclarationSummary, DeclarationSummaryState
from .....application.modelo.declarations_list import DeclarationListGroup, DeclarationListRow
from .....application.modelo.work_form_models import ModeloFormResult, ModeloFormResultDirection
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ..row_words import row_lines
from .portfolio_fixtures import portfolio_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("language", "amount"),
    [
        (OutputLanguage.ES, "1.234,56\u00a0€"),
        (OutputLanguage.EN, "1,234.56\u00a0€"),
        (OutputLanguage.CA, "1.234,56\u00a0€"),
        (OutputLanguage.HU, "1\u00a0234,56\u00a0€"),
    ],
)
@pytest.mark.parametrize("direction", [ModeloFormResultDirection.UNKNOWN, ModeloFormResultDirection.TO_REFUND])
def test_negative_result_keeps_its_sign_until_a_declared_direction_carries_it(
    language: OutputLanguage, amount: str, direction: ModeloFormResultDirection
) -> None:
    workspace, _ = portfolio_projection()
    declaration = workspace.declarations[0].model_copy(
        update={
            "summary": DeclarationSummary(
                state=DeclarationSummaryState.CALCULATED,
                checked=False,
                blocking_count=None,
                result=ModeloFormResult(casilla_id="01", box="01", value=Decimal("-1234.56"), direction=direction),
            )
        }
    )
    row = DeclarationListRow(
        key=str(declaration.work_unit_id),
        modelo=str(declaration.modelo),
        period=declaration.period,
        state="calculated",
        group=DeclarationListGroup.IN_PROGRESS,
        declaration=declaration,
    )
    with override_settings(cadrumo_output_language=language.value):
        _, words = row_lines(row, language, can_open=True, can_create=False)
        key = "unknown" if direction is ModeloFormResultDirection.UNKNOWN else "to_refund"
        sign = "−" if direction is ModeloFormResultDirection.UNKNOWN else ""
        assert words[1] == tr("tui.modelo.workbench.header.result." + key) + " · " + sign + amount


@pytest.mark.parametrize("language", tuple(OutputLanguage))
@pytest.mark.parametrize(
    ("state", "has_calculation", "expected_key"),
    [
        (DeclarationSummaryState.DRAFT, False, "tui.modelo.workbench.origin.not_calculated_yet"),
        (DeclarationSummaryState.DRAFT, True, "tui.declarations.value.result_unknown"),
        (DeclarationSummaryState.CALCULATED, True, "tui.declarations.value.result_unknown"),
        (DeclarationSummaryState.UNREADABLE, False, "tui.declarations.value.result_unknown"),
    ],
)
def test_only_proven_uncalculated_drafts_use_not_calculated_yet(
    language: OutputLanguage, state: DeclarationSummaryState, has_calculation: bool, expected_key: str
) -> None:
    workspace, _ = portfolio_projection()
    declaration = workspace.declarations[0].model_copy(
        update={
            "has_current_calculation": has_calculation,
            "has_current_filing": False,
            "summary": DeclarationSummary(state=state),
        }
    )
    row = DeclarationListRow(
        str(declaration.work_unit_id),
        str(declaration.modelo),
        declaration.period,
        state.value,
        DeclarationListGroup.IN_PROGRESS,
        declaration=declaration,
    )
    with override_settings(cadrumo_output_language=language.value):
        _, words = row_lines(row, language, can_open=True, can_create=False)
        assert words[1] == tr(expected_key)
