"""The activity-asset quarter is admitted by the Modelo 130's declared periods, as the terminal admits it.

The door here refuses or admits the quarter the way the installed runtime does: the
filing handoff request is admitted under a pinned authority, and a refusal travels
back through its public projection to the domain error the screen shows.
"""

from __future__ import annotations

from typing import override
from uuid import UUID

import pytest
from textual.widgets import Button, Input, Static

from .....application.actividad_asset.activity_asset_contracts import ActivityAssetFilingHandoffRequest
from .....application.actividad_asset.activity_asset_executors import activity_asset_executors_refusal
from .....application.actividad_asset.filing_handoff import ActivityAssetFilingHandoff
from .....application.actividad_asset.registered_operations import project_refusal
from .....application.modelo.registry_discovery import declared_modelo_period_tokens
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language
from .....core.period import Period, PeriodError
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.calculations.registry.form_codes import form_for_role
from .....domain.renta.actividad_asset.errors import ActividadAssetError
from ...components.host import ScreenHostApp
from ...tests.settling import settle, settle_until
from ..actividad_asset import ActivityAssetScreen
from ..controller import LedgerWorkspaceController
from ..models_actividad_asset import ActivityAssetFilingRequestV1
from ..workspace_injection import LedgerWorkspaceInjection
from .actividad_asset_fixtures import REGISTER_YEAR, ActivityAssetActionStub, activity_asset_revision
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERIOD_CODES = ("0A", "1P", "2P", "3P", "4P", "01", "07", "12", "1T", "2T", "3T", "4T")
"""Codes the period type names; the registry decides which of them the Modelo 130 declares."""


class _AdmittingDoor(ActivityAssetActionStub):
    """A door that admits the stated quarter as the installed runtime's filing handoff does."""

    @override
    def filing_handoff(self, request: ActivityAssetFilingRequestV1) -> ActivityAssetFilingHandoff:
        wire = ActivityAssetFilingHandoffRequest(
            profile_id=UUID(int=1),
            tax_year=int(request.tax_year),
            m130_period=None if request.m130_period is None else str(request.m130_period.code),
        )
        with bundled_indexed_authority().operation() as operation:
            try:
                wire.requested_period(operation=operation)
            except ActividadAssetError as error:
                refusal = project_refusal(activity_asset_executors_refusal(error, OutputLanguage(output_language())))
                assert refusal is not None
                raise refusal.to_domain_error(context={}) from None
        return super().filing_handoff(request)


def _declared_quarters() -> tuple[str, ...]:
    with bundled_indexed_authority().operation() as operation:
        modelo = form_for_role("renta.direct_instalment", authority=operation)
        return declared_modelo_period_tokens(modelo, operation=operation)


def _undeclared_period(declared: tuple[str, ...]) -> str:
    """A code that makes a period of the year but that the Modelo 130 does not declare."""
    for code in _PERIOD_CODES:
        if code in declared:
            continue
        try:
            Period.from_year_and_code(REGISTER_YEAR, code)
        except PeriodError:
            continue
        return code
    raise AssertionError("every period code is a Modelo 130 period")


async def _handoff(quarter: str) -> tuple[str, _AdmittingDoor]:
    door = _AdmittingDoor(activity_asset_revision("tui-quarter-admission"))
    screen = ActivityAssetScreen(
        LedgerWorkspaceController(
            ledger_context(),
            ledger_projection(),
            LedgerWorkspaceInjection(review_action=ledger_review_action(), activity_asset_actions=door),
        )
    )
    shown = ""

    def published() -> bool:
        nonlocal shown
        shown = str(screen.query_one("#asset-result", Static).render()).strip()
        return shown.startswith(("refused", "filing_handoff"))

    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 60)) as pilot:
            screen.query_one("#asset-filing-tax-year", Input).value = str(REGISTER_YEAR)
            screen.query_one("#asset-filing-m130-period", Input).value = quarter
            screen.query_one("#asset-filing-handoff", Button).focus()
            await pilot.press("enter")
            await settle(pilot)
            await settle_until(pilot, published, "the filing handoff result")
    return shown, door


@pytest.mark.asyncio
async def test_a_quarter_the_modelo_130_does_not_declare_is_refused_naming_the_declared_ones() -> None:
    declared = _declared_quarters()
    assert declared

    shown, _door = await _handoff(_undeclared_period(declared))

    assert shown.startswith("refused\t")
    assert all(code in shown for code in declared)


@pytest.mark.asyncio
async def test_a_declared_quarter_states_both_modelos() -> None:
    declared = _declared_quarters()

    shown, door = await _handoff(declared[-1])

    assert shown.startswith("filing_handoff\t")
    assert "m130_material=" in shown
    ((_, request),) = door.requests
    assert isinstance(request, ActivityAssetFilingRequestV1)
    assert request.m130_period == Period.from_year_and_code(REGISTER_YEAR, declared[-1])
