"""The art. 40.3 election an instalment reads is the one in force when its periodo impositivo starts.

The election binds from the periodo impositivo it was made for until it is
renounced, so each instalment reads the value effective on the first day of its
own periodo impositivo; a value never stated stays ``None`` and is not guessed.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ..modelo202_instalment_evidence import art_40_3_election_reader

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "5aa00000-0000-4000-8000-0000000002f2"
_ELECTION_PATH = "taxpayer_type.pago_fraccionado_art_40_3_elected"
_LEGAL_ENTITY = (
    UserProfileFact(path="identity.tax_id", value="B00015016"),
    UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
)


def _record(operation: PinnedAuthorityOperation, *election: UserProfileFact) -> UserProfileRecord:
    return create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=_PROFILE_ID,
        facts=(*_LEGAL_ENTITY, *election),
        setup_state=ProfileSetupState.COMPLETE,
    )


def _instalment(year: int, code: str = "2P") -> Period:
    return Period.from_year_and_code(year, code)


def test_an_unstated_election_reads_as_none(authority_operation: PinnedAuthorityOperation) -> None:
    read = art_40_3_election_reader(_record(authority_operation), schema=authority_operation.profile_schema())
    assert {read(_instalment(year)) for year in filing_year_envelope().years} == {None}


@pytest.mark.parametrize("stated", [True, False])
def test_an_open_ended_answer_holds_in_every_year(authority_operation: PinnedAuthorityOperation, stated: bool) -> None:
    record = _record(authority_operation, UserProfileFact(path=_ELECTION_PATH, value=stated))
    read = art_40_3_election_reader(record, schema=authority_operation.profile_schema())
    assert {read(_instalment(year, code)) for year in filing_year_envelope().years for code in ("1P", "3P")} == {stated}


def test_a_renuncia_takes_effect_from_its_own_periodo_impositivo(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The year of the renuncia reads false in every instalment; the year before keeps the election."""
    horizon = filing_year_envelope().horizon
    record = _record(
        authority_operation,
        UserProfileFact(path=_ELECTION_PATH, value=True, valid_to=date(horizon - 1, 12, 31)),
        UserProfileFact(path=_ELECTION_PATH, value=False, valid_from=date(horizon, 1, 1)),
    )
    read = art_40_3_election_reader(record, schema=authority_operation.profile_schema())
    assert [read(_instalment(horizon - 1, code)) for code in ("1P", "2P", "3P")] == [True, True, True]
    assert [read(_instalment(horizon, code)) for code in ("1P", "2P", "3P")] == [False, False, False]


def test_an_election_made_mid_year_binds_from_the_next_periodo_impositivo(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Only the value in force on the first day of the periodo impositivo counts."""
    horizon = filing_year_envelope().horizon
    record = _record(
        authority_operation,
        UserProfileFact(path=_ELECTION_PATH, value=True, valid_from=date(horizon - 1, 2, 1)),
    )
    read = art_40_3_election_reader(record, schema=authority_operation.profile_schema())
    assert read(_instalment(horizon - 1)) is None
    assert read(_instalment(horizon)) is True
