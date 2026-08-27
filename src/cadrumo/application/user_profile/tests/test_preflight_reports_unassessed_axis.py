"""The per-modelo preflight must distinguish "nothing matched" from "everything passed".

contract: ``ProfilePreflightReport.per_operation_requirements_assessed`` reports
whether the per-operation axis selected any schema-required field for the modelo.

The shipped schema declares no ``modelo_`` selector on any field, so the axis
selects nothing for every modelo and the flag is false throughout production
today. A test asserting only that false would pass under a flag hardcoded to
``False`` and prove nothing, so the discriminating case is built here: a real
schema whose required field DOES declare ``modelo_303``, driven through the real
service. The pair is the point — one case each side of the boundary.

Everything below uses real schema models and the real service; nothing is
stubbed.
"""

from __future__ import annotations

import pytest

from ....core import Period
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
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ..preflight import ProfilePreflightService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "6d1e4b90-2c77-4a53-8e14-9b0f5a2c7d31"
_PERIOD = Period.from_year_and_code(2024, "1T")


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=_PROFILE_ID, facts=facts)


def _schema_with_selector(selector: str) -> ProfileSchemaDefinition:
    """A minimal real schema whose one required field declares ``selector``."""
    return ProfileSchemaDefinition(
        id="cadrumo.axis_probe",
        version=1,
        title="Axis probe schema",
        snapshot_policy=ProfileSnapshotPolicy.IMMUTABLE_SECURE_SNAPSHOT_HASH,
        remove_policy=ProfileRemovePolicy.LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS,
        sections=(
            ProfileSectionDefinition(
                key="identity",
                title="Identity",
                sensitivity=SensitivityClass.IDENTITY,
                fields=(
                    ProfileFieldDefinition(
                        key="tax_id",
                        type=ProfileFieldType.STRING,
                        required=True,
                        sensitivity=SensitivityClass.IDENTITY,
                        description="Taxpayer NIF",
                        model_selectors=(selector,),
                    ),
                ),
            ),
        ),
    )


def _report(schema: ProfileSchemaDefinition, record: UserProfileRecord, modelo: str = "303"):
    return ProfilePreflightService(schema=schema).report(
        record=record,
        modelo=modelo,
        revision_id="2024-0a",
        period=_PERIOD,
    )


def test_axis_reports_assessed_when_a_required_field_declares_the_modelo_selector() -> None:
    """POSITIVE CONTROL: a matching selector means the axis genuinely assessed the modelo."""
    report = _report(_schema_with_selector("modelo_303"), _record())

    assert report.per_operation_requirements_assessed is True
    assert not report.ready, "the required field is absent, so the modelo is not ready"
    assert [f"{m.section_key}.{m.field_key}" for m in report.missing] == ["identity.tax_id"]


def test_axis_reports_assessed_even_when_the_selected_field_is_present() -> None:
    """Assessment tracks selection, not failure: all-present is still assessed."""
    declared = _record(UserProfileFact(path="identity.tax_id", value="12345678Z"))
    report = _report(_schema_with_selector("modelo_303"), declared)

    assert report.per_operation_requirements_assessed is True
    assert report.ready is True
    assert report.missing == ()


def test_axis_reports_unassessed_when_the_selector_names_a_different_modelo() -> None:
    """A selector for another modelo must not count as assessing this one."""
    report = _report(_schema_with_selector("modelo_130"), _record(), modelo="303")

    assert report.per_operation_requirements_assessed is False


def test_axis_reports_unassessed_for_a_non_operation_selector() -> None:
    """A plain field-path selector is not an operation token and assesses nothing.

    Guards the exact shape that made the shipped schema read as populated: it
    holds ``withholding.modelo_111_no_retenciones_periods``, which contains the
    substring but is a field path, so a ``in`` test rather than a prefix test
    would wrongly count it.
    """
    report = _report(_schema_with_selector("withholding.modelo_111_no_retenciones_periods"), _record(), modelo="111")

    assert report.per_operation_requirements_assessed is False


def test_the_shipped_schema_assesses_nothing_for_a_real_modelo() -> None:
    """The production case this signal exists for, stated as a fact about the shipped data.

    The shipped schema declares ``modelo_036``, ``modelo_100`` and
    ``modelo_303`` tokens onto the fields a live registry
    ``source = "profile"`` binding actually consumes, so the axis is not
    universally empty - see
    ``test_preflight_modelo_100_per_operation_axis_now_contributes`` in
    ``test_services.py`` for the modelo 100 positive case. This test still
    holds for modelo 303 specifically: the remaining authorable binding field
    (``iva.autoconsumo_promotor_base``) is conditionally required, while state
    attribution is a derived selector rather than an authorable profile field, so the
    required+prefix walk still selects nothing for modelo 303 and a profile
    declaring nothing is reported ``ready`` while nothing schema-required was
    examined. This asserts the flag exposes that, and is paired with the
    positive controls above so it cannot pass against a hardcoded ``False``.
    """
    report = _report(load_user_profile_schema(), _record())

    assert report.per_operation_requirements_assessed is False
    assert report.ready is True, "documents the current unassessed grant this signal makes visible"
