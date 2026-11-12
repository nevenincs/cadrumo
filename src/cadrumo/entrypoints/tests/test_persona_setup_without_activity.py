"""A persona without economic activity completes its setup as an operator would, and files its Modelo 100.

The installed journey refused these personas before any operation ran: the
profile overview page listed the IVA regime as missing, the CLI declined to
ask the setup promotion, and every Modelo 100 then stopped at the setup gate.
Each case leaves the replayed profile in setup, reads the overview page the CLI
and the desktop window read, completes the setup through the registered
operation without first judging it, and calculates the Modelo 100 the persona's
hand-grounded expectations state once its earlier-year statements are recorded.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ...application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from ...application.modelo.work_calculation_contracts import (
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from ...application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ...application.operations.public_period import PublicPeriod
from ...application.operations.public_scalar import restore_scalar
from ...application.user_profile.profile_operation_contracts import (
    PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
    ProfileCompleteSetupOperationRequest,
)
from ...application.user_profile.view_operation import (
    ProfileViewItem,
    ProfileViewMissingItem,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from ...application.user_profile.view_reader import read_profile_view_page
from ...domain.user_profile.values import ProfileSetupState
from ...tests.personas import ExpectedValue, YearEnvelope, values_in_force
from .persona_materialisation import (
    PERSONA_ACTOR,
    PersonaWorld,
    ReplayScope,
    load_profile_record,
    materialised_persona,
    run_operation,
    settle_operation,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MODELO = "100"
_WITHHOLDING_CASILLA = "0596"


def _overview_items(world: PersonaWorld) -> tuple[ProfileViewItem, ...]:
    """Every item of the overview page, read through the registered view's reader, page by page."""
    page = read_profile_view_page(
        ProfileViewOperationRequest(profile_id=world.profile_id, page_kind=ProfileViewPageKind.OVERVIEW),
        authority_operation=world.operation,
    )
    assert page.outcome == "page", page.refusal_code
    items = list(page.items)
    while page.next_cursor is not None:
        page = read_profile_view_page(
            ProfileViewOperationRequest(
                profile_id=world.profile_id,
                page_kind=ProfileViewPageKind.OVERVIEW,
                cursor=page.next_cursor,
                expected_revision=page.record_revision,
                expected_content_digest=page.content_digest,
            ),
            authority_operation=world.operation,
        )
        assert page.outcome == "page", page.refusal_code
        items.extend(page.items)
    return tuple(items)


def _calculated(world: PersonaWorld, *, year: int, period: str) -> dict[str, object]:
    created = settle_operation(
        world,
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        ModeloWorkCreateRequest(
            profile_id=world.profile_id,
            modelo=_MODELO,
            period=PublicPeriod(filing_year=year, code=period),
            actor=PERSONA_ACTOR,
        ),
    )
    outcome = getattr(created, "outcome", None)
    assert isinstance(outcome, ModeloWorkCreateSuccess), outcome
    work_unit_id = outcome.unit.work_unit_id
    calculated = run_operation(
        world,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        ModeloWorkCalculateRequest(work_unit_id=work_unit_id, actor=PERSONA_ACTOR),
        ModeloWorkCalculatePublicResultV3,
        subject=work_unit_id,
    )
    return {item.key: restore_scalar(item.value) for item in calculated.calculation.casilla_values}


def _stated_withholding(values: tuple[ExpectedValue, ...], envelope: YearEnvelope) -> ExpectedValue:
    """The withholding the persona states for the latest ejercicio it states one for."""
    stated = [
        (year, value)
        for year, value in values_in_force(values, envelope)
        if value.modelo == _MODELO
        and value.grounding != "unverified"
        and any(casilla == _WITHHOLDING_CASILLA for casilla, _amount in value.casillas)
    ]
    assert stated, "the persona states its Modelo 100 withholding"
    return max(stated, key=lambda item: item[0])[1]


@pytest.mark.parametrize("persona_id", ["arrendador-jubilado", "asalariada-familia"])
def test_a_persona_without_activity_completes_setup_and_reaches_its_modelo_100(tmp_path: Path, persona_id: str) -> None:
    with materialised_persona(
        persona_id, tmp_path / "setup", ReplayScope.FULL, reuse=True, complete_setup=False
    ) as replayed:
        world = replayed.world
        record = load_profile_record(world)
        assert record.setup_state is ProfileSetupState.INCOMPLETE

        missing = [item.path for item in _overview_items(world) if isinstance(item, ProfileViewMissingItem)]
        assert missing == []

        settle_operation(
            world,
            PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
            ProfileCompleteSetupOperationRequest(
                profile_id=world.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
            ),
        )
        assert load_profile_record(world).setup_state is ProfileSetupState.COMPLETE

    # The persona's own earlier-year statements (its carries' attested absence)
    # are recorded only after a completed setup, so the return is calculated in
    # the replay that completes it and then records them.
    with materialised_persona(persona_id, tmp_path / "history", ReplayScope.HISTORY, reuse=True) as filed:
        assert all(item.block != "setup" for item in filed.not_loaded)
        stated = _stated_withholding(filed.persona.expectations.values, filed.world.envelope)
        casillas = _calculated(filed.world, year=stated.year.resolve(filed.world.envelope), period=stated.period)

    expected = Decimal(dict(stated.casillas)[_WITHHOLDING_CASILLA])
    assert Decimal(str(casillas[_WITHHOLDING_CASILLA])) == expected
