"""The modelo-scoped requirement is demanded of its modelo and of no other.

``ProfileFieldDefinition.required`` is a property of the field across the whole
profile: it drives completeness, overview and presentation. Marking a field
required to satisfy one modelo's filing preflight therefore demands the fact
from every taxpayer, including those with no such obligation.
``required_for_modelos`` carries that requirement instead, and only this walk
consults it -- which is precisely what these tests pin.
"""

from __future__ import annotations

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ....core.classification import SensitivityClass
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.schema import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileRecord
from ..preflight import ProfilePreflightService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "6d1e4b90-2c77-4a53-8e14-9b0f5a2c7d31"
_PERIOD = Period.from_year_and_code(2024, "1T")
_FIELD_PATH = "withholding.colegio_concertado"


def _schema() -> ProfileSchemaDefinition:
    """One NOT-globally-required field that Modelo 111 alone requires."""
    return ProfileSchemaDefinition(
        id="cadrumo.modelo_scoped_probe",
        version=1,
        title="Modelo-scoped requirement probe",
        snapshot_policy=ProfileSnapshotPolicy.IMMUTABLE_SECURE_SNAPSHOT_HASH,
        remove_policy=ProfileRemovePolicy.LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS,
        sections=(
            ProfileSectionDefinition(
                key="withholding",
                title="Withholding",
                sensitivity=SensitivityClass.FINANCIAL,
                fields=(
                    ProfileFieldDefinition(
                        key="colegio_concertado",
                        type=ProfileFieldType.BOOLEAN,
                        required=False,
                        sensitivity=SensitivityClass.FINANCIAL,
                        description="Whether the withholder is a colegio concertado",
                        model_selectors=("colegio_concertado",),
                        required_for_modelos=(Modelo.M111,),
                    ),
                ),
            ),
        ),
    )


def _missing_paths(modelo: str) -> tuple[str, ...]:
    record = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=_PROFILE_ID, facts=())
    report = ProfilePreflightService(schema=_schema()).report(
        record=record,
        modelo=modelo,
        revision_id="2024-0a",
        period=_PERIOD,
    )
    return tuple(f"{requirement.section_key}.{requirement.field_key}" for requirement in report.missing)


def test_the_declaring_modelo_is_asked_for_the_fact() -> None:
    assert _FIELD_PATH in _missing_paths(Modelo.M111.value)


def test_a_modelo_that_does_not_declare_it_is_never_asked() -> None:
    """The whole point: an unrelated modelo must not inherit the requirement."""
    for modelo in (Modelo.M303, Modelo.M100, Modelo.M115):
        assert _FIELD_PATH not in _missing_paths(modelo.value), modelo


def test_the_registry_declares_the_requirement_rather_than_a_code_branch() -> None:
    """The shipped schema carries the axis, so no handler needs a modelo branch."""
    schema = load_user_profile_schema()
    declared = tuple(
        field for section in schema.sections for field in section.fields if Modelo.M111 in field.required_for_modelos
    )
    assert declared, "the shipped schema must declare the Modelo 111 requirement"
    assert all(not field.required for field in declared), (
        "a modelo-scoped requirement must not also be globally required, "
        "or completeness and presentation would demand it of every profile"
    )
