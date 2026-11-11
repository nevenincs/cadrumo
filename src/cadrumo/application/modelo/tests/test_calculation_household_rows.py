"""The household a profile states reaches a calculation's row channel, through the real channel resolution.

The registry revision, the profile resolver and the precedence overlay are the
published ones. The rows the profile states join the rows of the source mesh as
one exclusive set, so a row two sources both state is refused. A household
declared empty carries its source trace and no rows; one never answered carries
neither, so it stays unknown.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from cadrumo.domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ...aggregation.errors import AggregationValidationError
from ..calculation_resolution import (
    ResolvedCalculationChannels,
    calculation_row_binding_values,
    resolve_calculation_binding_channels,
)
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE_ID = "10000000-0000-4000-8000-000000000915"
_PERIOD = "0A"
_CLOCK = datetime(1980, 5, 21, 10, 0, 0, tzinfo=UTC)
_CHILD_NAME = "renta-family-descendant-display-name"
_CHILD_BIRTH = "renta-family-descendant-birth-date"
_PARENT_NAME = "renta-family-ascendant-display-name"


def _snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    year = operation.supported_filing_years().floor
    return published_snapshot("100", filing_year=year, period=_PERIOD)


def _work_unit(snapshot: RegistrySnapshot) -> WorkUnit:
    year = snapshot.snapshot_ref.modelo_year
    period = Period.from_year_and_code(year, _PERIOD)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_PROFILE_ID, modelo="100", filing_year=year, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=_PROFILE_ID,
        modelo="100",
        filing_year=year,
        period=period,
        revision_id=snapshot.revision.id,
        name="household-rows",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _channels(operation: PinnedAuthorityOperation, *household: UserProfileFact) -> ResolvedCalculationChannels:
    snapshot = _snapshot(operation)
    profile = ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_PROFILE_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                *RENTA_UNMARRIED_TAXPAYER_FACTS,
                *household,
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
            context=operation.profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )
    return resolve_calculation_binding_channels(
        work_unit=_work_unit(snapshot),
        snapshot=snapshot,
        casilla_inputs={},
        caller_binding_values={},
        caller_enum_binding_values={},
        backend_binding_values={},
        borrador_snapshot_id=None,
        borrador_snapshot_repository=None,
        operation=operation,
        profile=profile,
    )


def _row_traces(channels: ResolvedCalculationChannels) -> set[str]:
    return {
        ref.source_ref.rsplit(":", 1)[1] for ref in channels.profile_source_provenance if ":rows:" in ref.source_ref
    }


def test_the_stated_household_reaches_the_row_channel_with_its_traces(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    born = date(_snapshot(authority_operation).filing_year - 9, 3, 14)
    channels = _channels(
        authority_operation,
        UserProfileFact(path="renta_family.descendientes_count", value="1"),
        UserProfileFact(path="renta_family.descendiente.0.birth_date", value=born.isoformat()),
        UserProfileFact(path="renta_family.descendiente.0.apellidos_nombre", value="Ortega Navarro Pablo"),
        UserProfileFact(path="renta_family.ascendientes_count", value="1"),
        UserProfileFact(
            path="renta_family.ascendiente.0.birth_date", value=born.replace(year=born.year - 60).isoformat()
        ),
        UserProfileFact(path="renta_family.ascendiente.0.apellidos_nombre", value="Navarro Gil Carmen"),
    )

    rows = calculation_row_binding_values({}, channels)

    assert rows[(_CHILD_NAME, 1)] == "Ortega Navarro Pablo"
    assert rows[(_CHILD_BIRTH, 1)] == born.isoformat()
    assert rows[(_PARENT_NAME, 1)] == "Navarro Gil Carmen"
    assert {_CHILD_NAME, _CHILD_BIRTH, _PARENT_NAME} <= _row_traces(channels)


def test_a_household_declared_empty_has_its_traces_and_no_rows(authority_operation: PinnedAuthorityOperation) -> None:
    channels = _channels(
        authority_operation,
        UserProfileFact(path="renta_family.descendientes_count", value="0"),
        UserProfileFact(path="renta_family.ascendientes_count", value="0"),
    )

    assert calculation_row_binding_values({}, channels) == {}
    assert {_CHILD_NAME, _PARENT_NAME} <= _row_traces(channels)


def test_an_unanswered_household_has_neither_rows_nor_traces(authority_operation: PinnedAuthorityOperation) -> None:
    channels = _channels(authority_operation)

    assert calculation_row_binding_values({}, channels) == {}
    assert not _row_traces(channels) & {_CHILD_NAME, _PARENT_NAME}


def test_the_mesh_rows_and_the_profile_rows_join_and_a_row_both_state_is_refused(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    born = date(_snapshot(authority_operation).filing_year - 9, 3, 14)
    channels = _channels(
        authority_operation,
        UserProfileFact(path="renta_family.descendientes_count", value="1"),
        UserProfileFact(path="renta_family.descendiente.0.birth_date", value=born.isoformat()),
        UserProfileFact(path="renta_family.descendiente.0.apellidos_nombre", value="Ortega Navarro Pablo"),
    )
    mesh_row = ("renta-activity-asset-disposal-row-transmission-date-1631", 1)

    joined = calculation_row_binding_values({mesh_row: "x"}, channels)

    assert joined[mesh_row] == "x"
    assert joined[(_CHILD_NAME, 1)] == "Ortega Navarro Pablo"
    with pytest.raises(AggregationValidationError):
        calculation_row_binding_values({(_CHILD_NAME, 1): "Otro Nombre"}, channels)


def test_household_notes_reach_the_calculation_through_its_profile_diagnostics(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    born = date(_snapshot(authority_operation).filing_year - 78, 1, 8)
    channels = _channels(
        authority_operation,
        UserProfileFact(path="renta_family.ascendientes_count", value="2"),
        UserProfileFact(path="renta_family.ascendiente.0.birth_date", value=born.isoformat()),
        UserProfileFact(path="renta_family.ascendiente.0.apellidos_nombre", value="Navarro Gil Carmen"),
    )

    reasons = sorted(
        diagnostic.reason for diagnostic in channels.profile_diagnostics if diagnostic.reason.startswith("household_")
    )

    # One ascendant is stored without the NIF the design requires, and one more is stated than stored.
    assert reasons == ["household_row_fact_unstated", "household_rows_incomplete"]
    assert _PARENT_NAME in {key[0] for key in calculation_row_binding_values({}, channels)}
