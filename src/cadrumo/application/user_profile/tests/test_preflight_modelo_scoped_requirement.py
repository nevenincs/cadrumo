"""The modelo-scoped requirement is demanded of its modelo, of no other, and only when its conditions hold.

``ProfileFieldDefinition.required`` is a property of the field across the whole
profile: it drives completeness, overview and presentation. Marking a field
required to satisfy one modelo's filing preflight therefore demands the fact
from every taxpayer, including those with no such obligation.
``required_for_modelos`` carries that requirement instead, and only this walk
consults it -- which is precisely what these tests pin.

A blanket modelo-scoped requirement is still a blanket one inside that modelo.
The conditional axis narrows it to the taxpayers the fact can concern, and these
tests exercise the three readings through the real preflight walk: conditions
holding demands the fact, an unanswered condition demands that condition's own
fact instead, and a positively absent condition demands nothing. The conditions
here are an arbitrary payer fact and IAE group fact the shipped authority
already carries, because this file pins the MECHANISM; the shipped Modelo 111
declaration that uses it is pinned against the compiled registry sources in
``dev/registry/tests/test_modelo_111_colegio_concertado_requirement.py``.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.classification.policies import SensitivityClass
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_profile_schema,
)
from ....domain.user_profile.schema import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ..preflight import ProfilePreflightService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_PROFILE_ID = "6d1e4b90-2c77-4a53-8e14-9b0f5a2c7d31"
_PERIOD = Period.from_year_and_code(2024, "1T")
_FIELD_PATH = "withholding.colegio_concertado"
_CONDITION_FACT = "pays_capital_income_with_retencion"
_CONDITION_PATH = f"withholding.{_CONDITION_FACT}"
_EPIGRAPH_PATH = "activities.iae_epigraph"
_GROUPS_FACT = "rd-439-2007-art-75:iae-grupos-arrendamiento-inmuebles-urbanos"
#: Inside and outside the group the fact declares, per the shipped authority.
_IN_GROUP = "861.1"
_OUT_OF_GROUP = "741.1"


def _schema(*, conditioned: bool) -> ProfileSchemaDefinition:
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
                        required_for_modelos=(Modelo("111"),),
                        required_for_modelos_when_payer_facts=(_CONDITION_FACT,) if conditioned else (),
                        required_for_modelos_when_activity_iae_groups_fact=_GROUPS_FACT if conditioned else None,
                        required_for_modelos_when_activity_iae_epigraph_path=_EPIGRAPH_PATH if conditioned else None,
                    ),
                    ProfileFieldDefinition(
                        key=_CONDITION_FACT,
                        type=ProfileFieldType.BOOLEAN,
                        required=False,
                        sensitivity=SensitivityClass.FINANCIAL,
                        description="Whether the taxpayer pays capital income with withholding",
                        model_selectors=(_CONDITION_FACT,),
                    ),
                ),
            ),
            ProfileSectionDefinition(
                key="activities",
                title="Business activities",
                sensitivity=SensitivityClass.IDENTITY,
                repeatable=True,
                fields=(
                    ProfileFieldDefinition(
                        key="iae_epigraph",
                        type=ProfileFieldType.STRING,
                        required=False,
                        sensitivity=SensitivityClass.IDENTITY,
                        description="IAE section/group/epigraph where applicable",
                        model_selectors=(_EPIGRAPH_PATH,),
                    ),
                ),
            ),
        ),
    )


def _missing_paths(
    modelo: str,
    *,
    conditioned: bool = False,
    facts: tuple[UserProfileFact, ...] = (),
) -> tuple[str, ...]:
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=facts,
        context=leased_profile_create_context(),
    )
    report = ProfilePreflightService(schema=_schema(conditioned=conditioned)).report(
        record=record,
        modelo=modelo,
        revision_id="2024-0a",
        period=_PERIOD,
    )
    return tuple(f"{requirement.section_key}.{requirement.field_key}" for requirement in report.missing)


def test_the_declaring_modelo_is_asked_for_the_fact() -> None:
    assert _FIELD_PATH in _missing_paths(Modelo("111").value)


def test_a_modelo_that_does_not_declare_it_is_never_asked() -> None:
    """The whole point: an unrelated modelo must not inherit the requirement."""
    for modelo in (Modelo("303"), Modelo("100"), Modelo("115")):
        assert _FIELD_PATH not in _missing_paths(modelo.value), modelo


def test_conditions_holding_still_demand_the_fact() -> None:
    missing = _missing_paths(
        Modelo("111").value,
        conditioned=True,
        facts=(
            UserProfileFact(path=_CONDITION_PATH, value="true"),
            UserProfileFact(path=_EPIGRAPH_PATH, value=_IN_GROUP),
        ),
    )

    assert _FIELD_PATH in missing


def test_an_absent_condition_demands_nothing() -> None:
    """A taxpayer the fact cannot concern is asked for neither it nor its conditions."""
    missing = _missing_paths(
        Modelo("111").value,
        conditioned=True,
        facts=(
            UserProfileFact(path=_CONDITION_PATH, value="false"),
            UserProfileFact(path=_EPIGRAPH_PATH, value=_IN_GROUP),
        ),
    )

    assert _FIELD_PATH not in missing
    assert _CONDITION_PATH not in missing


def test_an_absent_activity_condition_demands_nothing_either() -> None:
    missing = _missing_paths(
        Modelo("111").value,
        conditioned=True,
        facts=(
            UserProfileFact(path=_CONDITION_PATH, value="true"),
            UserProfileFact(path=_EPIGRAPH_PATH, value=_OUT_OF_GROUP),
        ),
    )

    assert _FIELD_PATH not in missing


def test_an_unanswered_condition_is_asked_before_the_fact_it_gates() -> None:
    """The defect's shape: the gated attestation must not be asked first."""
    missing = _missing_paths(
        Modelo("111").value,
        conditioned=True,
        facts=(UserProfileFact(path=_EPIGRAPH_PATH, value=_IN_GROUP),),
    )

    assert _FIELD_PATH not in missing
    assert _CONDITION_PATH in missing


def test_an_unanswered_activity_classification_is_asked_before_the_fact_it_gates() -> None:
    missing = _missing_paths(
        Modelo("111").value,
        conditioned=True,
        facts=(UserProfileFact(path=_CONDITION_PATH, value="true"),),
    )

    assert _FIELD_PATH not in missing
    assert _EPIGRAPH_PATH in missing


def test_the_registry_declares_the_requirement_rather_than_a_code_branch() -> None:
    """The shipped schema carries the axis, so no handler needs a modelo branch."""
    schema = published_profile_schema()
    declared = tuple(
        field for section in schema.sections for field in section.fields if Modelo("111") in field.required_for_modelos
    )
    assert declared, "the shipped schema must declare the Modelo 111 requirement"
    assert all(not field.required for field in declared), (
        "a modelo-scoped requirement must not also be globally required, "
        "or completeness and presentation would demand it of every profile"
    )
