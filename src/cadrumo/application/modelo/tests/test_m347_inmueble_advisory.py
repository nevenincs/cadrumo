"""The Modelo 347 advisory for a letting filer whose inmueble records Cadrumo does not produce.

A 347 fichero carries no inmueble record, so a lessor of business premises
(RD 1065/2007 art. 34.1.d) would file an incomplete return without a word. The
one profile fact that says a filer lets property is the capital inmobiliario
income category; the advisory fires on it, for the ejercicio it is declared
for, on Modelo 347 alone. The registry authority and the profile projection are
the real ones; the profile record is synthetic.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...aggregation.source_mesh import CalculationSourceDiagnostic
from .._m347_inmueble_advisory import (
    M347_INMUEBLE_RECORD_UNSUPPORTED_SOURCE_KIND,
    collect_m347_inmueble_record_diagnostics,
)
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "cd7a6304-2000-4200-8200-000000000347"
_PERIOD = "0A"


def _profile(
    operation: PinnedAuthorityOperation,
    categories: str,
    *,
    valid_from: date | None = None,
    valid_to: date | None = None,
) -> ModeloWorkProfile:
    record = create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=_BUCKET_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(
                path="taxpayer_type.irpf_income_categories",
                value=categories,
                valid_from=valid_from,
                valid_to=valid_to,
            ),
        ),
    )
    return ModeloWorkProfile(record=record, profile_decode_context=operation.profile_decode_context())


def _diagnostics(
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile,
    *,
    modelo: str = "347",
    year: int = 2025,
) -> tuple[CalculationSourceDiagnostic, ...]:
    return collect_m347_inmueble_record_diagnostics(
        modelo=modelo,
        period_token=_PERIOD,
        filing_year=year,
        bucket_id=_BUCKET_ID,
        operation=operation,
        profile=profile,
    )


def test_a_filer_letting_property_is_told_the_inmueble_record_is_missing(operation: PinnedAuthorityOperation) -> None:
    diagnostics = _diagnostics(operation, _profile(operation, "actividad_economica,capital_inmobiliario"))

    assert len(diagnostics) == 1
    advisory = diagnostics[0]
    assert advisory.reason == "source_issue"
    assert advisory.source_kind == M347_INMUEBLE_RECORD_UNSUPPORTED_SOURCE_KIND
    assert advisory.asserted_legal_refs == ("rd-1065-2007:art-34.1.d",)
    assert "arrendamiento de local de negocio is not yet supported" in advisory.message
    assert advisory.remedy is not None and "outside Cadrumo" in advisory.remedy


def test_a_filer_without_rental_income_is_silent(operation: PinnedAuthorityOperation) -> None:
    assert _diagnostics(operation, _profile(operation, "actividad_economica")) == ()


def test_only_modelo_347_carries_the_advisory(operation: PinnedAuthorityOperation) -> None:
    profile = _profile(operation, "capital_inmobiliario")

    assert _diagnostics(operation, profile, modelo="100") == ()


def test_the_category_is_read_for_the_filing_ejercicio(operation: PinnedAuthorityOperation) -> None:
    """A category in force only from 2026 does not speak for the 2025 return."""
    profile = _profile(operation, "capital_inmobiliario", valid_from=date(2026, 1, 1))

    assert _diagnostics(operation, profile, year=2025) == ()
    assert len(_diagnostics(operation, profile, year=2026)) == 1
