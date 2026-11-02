"""The binding overlay of a real calculation, run end to end through ``resolve_calculation_binding_channels``.

The registry revision, the profile resolver and the overlay are the published
ones; only the operator's values are chosen here, so each expected value is the
one the test itself supplied.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from cadrumo.domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.modelos.source_disagreement import DisagreementEnumValue, SourceDisagreementRole
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ..calculation_resolution import (
    PRECEDENCE_TIER_DIVERGENCE_ADVISORY_REASON,
    ResolvedCalculationChannels,
    resolve_calculation_binding_channels,
)
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_PROFILE_ID = "10000000-0000-4000-8000-000000000591"
_PERIOD = "0A"
_CCAA_BINDING: BindingId = "renta-profile-tax-residence-ccaa"
_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)


def _latest_snapshot_declaring_the_ccaa_binding() -> RegistrySnapshot:
    """The newest supported Modelo 100 revision whose profile tier carries the residence CCAA."""
    support = published_supported_filing_years()
    assert support is not None
    for year in sorted(support.years, reverse=True):
        snapshot = published_snapshot("100", filing_year=year, period=_PERIOD)
        if any(binding.id == _CCAA_BINDING for binding in snapshot.revision.bindings):
            return snapshot
    raise AssertionError("no supported Modelo 100 revision declares the residence CCAA binding")


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
        name="precedence-screen",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _profile(ccaa: str, operation: PinnedAuthorityOperation) -> ModeloWorkProfile:
    return ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_PROFILE_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="tax_residence.ccaa", value=ccaa),
                *RENTA_UNMARRIED_TAXPAYER_FACTS,
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
            context=operation.profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )


def _resolve(
    operation: PinnedAuthorityOperation, *, profile_ccaa: str, caller_enums: Mapping[BindingId, str]
) -> ResolvedCalculationChannels:
    snapshot = _latest_snapshot_declaring_the_ccaa_binding()
    return resolve_calculation_binding_channels(
        work_unit=_work_unit(snapshot),
        snapshot=snapshot,
        casilla_inputs={},
        caller_binding_values={},
        caller_enum_binding_values=caller_enums,
        backend_binding_values={},
        borrador_snapshot_id=None,
        borrador_snapshot_repository=None,
        operation=operation,
        profile=_profile(profile_ccaa, operation),
    )


def test_the_profile_value_reaches_the_calculation_and_nothing_diverges(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    channels = _resolve(authority_operation, profile_ccaa="madrid", caller_enums={})

    assert channels.enum_bindings[_CCAA_BINDING] == "madrid"
    assert channels.precedence_diagnostics == ()


def test_an_operator_value_equal_to_the_profiles_is_silent(authority_operation: PinnedAuthorityOperation) -> None:
    channels = _resolve(authority_operation, profile_ccaa="madrid", caller_enums={_CCAA_BINDING: "madrid"})

    assert channels.enum_bindings[_CCAA_BINDING] == "madrid"
    assert channels.precedence_diagnostics == ()


def test_an_operator_value_over_a_different_profile_value_is_used_and_stated_with_both_values(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    channels = _resolve(authority_operation, profile_ccaa="madrid", caller_enums={_CCAA_BINDING: "cataluna"})

    assert channels.enum_bindings[_CCAA_BINDING] == "cataluna"
    (diagnostic,) = channels.precedence_diagnostics
    # Modelo 100 is laid out as an XML dictionary with no exported box, so no binding of it is filing-bound.
    assert diagnostic.reason == PRECEDENCE_TIER_DIVERGENCE_ADVISORY_REASON
    assert diagnostic.binding_id == _CCAA_BINDING
    assert "madrid" not in diagnostic.message
    assert "cataluna" not in diagnostic.message
    fact = diagnostic.disagreement
    assert fact is not None
    assert fact.selected_role is SourceDisagreementRole.CALLER
    assert fact.reached_casillas == ()
    assert [(source.role, source.value) for source in fact.sources] == [
        (SourceDisagreementRole.PROFILE, DisagreementEnumValue.model_validate({"token": "madrid"})),
        (SourceDisagreementRole.CALLER, DisagreementEnumValue.model_validate({"token": "cataluna"})),
    ]
    assert fact.sources[0].source_family == "profile"
    assert fact.sources[1].source_family == "operator_input"
