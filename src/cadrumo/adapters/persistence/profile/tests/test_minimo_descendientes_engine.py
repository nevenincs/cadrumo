"""Profile-persistence integration for the mínimo por descendientes engine.

The application test owner covers the derived-fact policy with deterministic
fact indexes.  These cases exercise the outer profile binding and calculation
seams against a real encrypted bucket, proving that persisted descendant facts
reach the estatal/autonómico channels and the downstream tariff calculation.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pytest

from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)

from .....application.modelo.profile_binding import resolve_profile_sourced_bindings
from .....core.casilla_id import validated_casilla_id
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from .....domain.calculations.registry.formula_runtime_ops import resolve_parameter
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from .....domain.contribuyente.descendant import DescendantInfo
from .....domain.contribuyente.descendant_facts import descendant_facts_from_list
from .....domain.user_profile.values import ProfileSetupState, UserProfileFact
from .....domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from ...storage.tests.profile_capsule_runtime import seed_test_profile_record
from ...storage.tests.secure_sql import isolated_runtime_profile
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one generation for each persisted profile resolution."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _supported_filing_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no supported filing years"
    assert support.years, "the published support envelope admits no filing year"
    return tuple(support.years)


def _authored_renta_filing_year() -> int:
    """Return the newest supported year whose Renta revision is authored for that year.

    A year the envelope admits only by projecting an earlier revision forward
    carries no dated thresholds of its own.
    """
    for year in sorted(_supported_filing_years(), reverse=True):
        valid_to = published_snapshot("100", filing_year=year, period="0A").revision.valid_to
        if valid_to is None or valid_to.year >= year:
            return year
    raise AssertionError("no supported filing year has an authored Renta revision")


_FILING_YEAR = _authored_renta_filing_year()
#: The worked example's figures (7,900 of mínimo, 3,097 of cuota) are the
#: Cataluña computation for this Renta campaign, so its year is part of the
#: example rather than a coordinate the test may move.
_WORKED_EXAMPLE_FILING_YEAR = 2024
_BUCKET = "00000000-0000-4000-8000-000000000516"
_PROFILE_LABEL = "M100 minimo descendientes engine profile"
_T0 = datetime(max(_supported_filing_years()), 7, 2, 10, 0, tzinfo=UTC)


@lru_cache
def _snapshot(year: int) -> RegistrySnapshot:
    return published_authority_operation().snapshot("100", filing_year=year, period="0A")


def _registry_tranches(snapshot: RegistrySnapshot, *, ccaa_infix: str | None = None) -> tuple[list[Decimal], Decimal]:
    """Read the four birth-order amounts and menor-3 supplement from the revision."""
    year = snapshot.filing_year
    suffixes = ("primer-hijo", "segundo-hijo", "tercer-hijo", "cuarto-y-siguientes")
    date_context = {"filing_period": date(year, 12, 31)}
    by_id = {parameter.id: parameter for parameter in snapshot.revision.parameters}

    def _resolve(suffix: str) -> Decimal:
        if ccaa_infix is not None:
            specific_id = f"renta-minimo-descendientes-{ccaa_infix}-{suffix}"
            if specific_id in by_id:
                return resolve_parameter(by_id[specific_id], date_context)
        return resolve_parameter(by_id[f"renta-minimo-descendientes-{suffix}"], date_context)

    return [_resolve(suffix) for suffix in suffixes], _resolve("menor-tres-anos")


def _binding_id_for_estatal(snapshot: RegistrySnapshot) -> str:
    matches = [
        binding.id
        for binding in snapshot.revision.bindings
        if binding.id.endswith("profile-minimo-descendientes-estatal")
    ]
    assert len(matches) == 1
    return matches[0]


def _binding_id_for_autonomico(snapshot: RegistrySnapshot) -> str:
    matches = [
        binding.id
        for binding in snapshot.revision.bindings
        if binding.id.endswith("profile-minimo-descendientes-autonomico")
    ]
    assert len(matches) == 1
    return matches[0]


def test_profile_binding_resolution_routes_aggregate_into_decimal_channel(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL):
        descendientes = (DescendantInfo(birth_date=date(_FILING_YEAR - 12, 4, 1)),)
        facts = [UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(descendientes)]
        seed_test_profile_record(
            _create_profile_record_for_test(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET,
                facts=tuple(facts),
                created_at=_T0,
                updated_at=_T0,
                context=_profile_creation_context_for_test(),
            ),
        )
        snapshot = _snapshot(_FILING_YEAR)
        binding_id = _binding_id_for_estatal(snapshot)
        resolution = resolve_profile_sourced_bindings(snapshot, bucket_id=_BUCKET, operation=authority_operation)

    tranches, _ = _registry_tranches(snapshot)
    assert resolution.binding_values[binding_id] == tranches[0]


def test_profile_descendant_facts_feed_the_worked_example_minimo_and_downstream_tariff(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Real profile descendientes feed 0513/0514 and the downstream cuota path."""
    assert _WORKED_EXAMPLE_FILING_YEAR in _supported_filing_years()
    year = _WORKED_EXAMPLE_FILING_YEAR
    snapshot = _snapshot(year)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL):
        # One descendant of nine and one under three at the end of the campaign.
        descendientes = (
            DescendantInfo(birth_date=date(year - 9, 1, 1)),
            DescendantInfo(birth_date=date(year - 1, 1, 15)),
        )
        facts = [UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(descendientes)]
        seed_test_profile_record(
            _create_profile_record_for_test(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET,
                facts=(
                    *facts,
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="tax_residence.ccaa", value="cataluna"),
                    UserProfileFact(path="renta_filing.declaration_type", value="1"),
                    UserProfileFact(path="renta_taxpayer.birth_date", value=date(1975, 6, 15)),
                    UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                    UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
                    UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
                ),
                created_at=_T0,
                updated_at=_T0,
                context=_profile_creation_context_for_test(),
            ),
        )
        resolution = resolve_profile_sourced_bindings(snapshot, bucket_id=_BUCKET, operation=authority_operation)

    result = calculate_registry_snapshot(
        snapshot,
        inputs={validated_casilla_id("0003", surface="test_minimo_descendientes_engine.casilla"): Decimal("37400")},
        date_context={"filing_period": date(year, 12, 31)},
        binding_values={
            **resolution.binding_values,
            "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-modelo-111-retenciones-periodicas": Decimal("0"),
            "renta-modelo-123-retenciones-periodicas": Decimal("0"),
            "renta-modelo-193-retenciones-anuales": Decimal("0"),
            "renta-profile-guarderia-gastos-reales": Decimal("0"),
            "renta-profile-incremento-guarderia": Decimal("0"),
            "renta-profile-cotizaciones-ss-madre": Decimal("0"),
            "renta-profile-descendientes-guarderia": Decimal("0"),
            "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values=resolution.enum_binding_values,
        date_binding_values=resolution.date_binding_values,
        boolean_binding_values=resolution.boolean_binding_values,
        relation_values={
            "renta-modelo-111-retenciones-periodicas": Decimal("0"),
            "renta-modelo-123-retenciones-periodicas": Decimal("0"),
            "renta-modelo-193-retenciones-anuales": Decimal("0"),
            "renta-modelo-130-pagos-fraccionados": Decimal("0"),
            "renta-modelo-131-pagos-fraccionados": Decimal("0"),
        },
    )

    assert resolution.binding_values["renta-profile-minimo-descendientes-estatal"] == Decimal("7900.00")
    assert resolution.binding_values["renta-profile-minimo-descendientes-autonomico"] == Decimal("7900.00")
    assert result.values[validated_casilla_id("0513", surface="test_minimo_descendientes_engine.casilla")] == Decimal(
        "7900.00"
    )
    assert result.values[validated_casilla_id("0514", surface="test_minimo_descendientes_engine.casilla")] == Decimal(
        "7900.00"
    )
    assert result.values[validated_casilla_id("0545", surface="test_minimo_descendientes_engine.casilla")] == Decimal(
        "3097.00"
    )


def test_profile_binding_resolution_routes_madrid_autonomico_into_decimal_channel(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """End-to-end: a real Madrid profile resolves the Madrid-specific tranches."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL):
        descendientes = (
            DescendantInfo(birth_date=date(_FILING_YEAR - 19, 1, 1)),
            DescendantInfo(birth_date=date(_FILING_YEAR - 16, 1, 1)),
            DescendantInfo(birth_date=date(_FILING_YEAR - 12, 1, 1)),
        )
        facts = [UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(descendientes)]
        seed_test_profile_record(
            _create_profile_record_for_test(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET,
                facts=(*facts, UserProfileFact(path="tax_residence.ccaa", value="madrid")),
                created_at=_T0,
                updated_at=_T0,
                context=_profile_creation_context_for_test(),
            ),
        )
        snapshot = _snapshot(_FILING_YEAR)
        estatal_binding_id = _binding_id_for_estatal(snapshot)
        autonomico_binding_id = _binding_id_for_autonomico(snapshot)
        resolution = resolve_profile_sourced_bindings(snapshot, bucket_id=_BUCKET, operation=authority_operation)

    estatal_tranches, _ = _registry_tranches(snapshot)
    madrid_tranches, _ = _registry_tranches(snapshot, ccaa_infix="madrid")
    expected_estatal = estatal_tranches[0] + estatal_tranches[1] + estatal_tranches[2]
    expected_autonomico = madrid_tranches[0] + madrid_tranches[1] + madrid_tranches[2]
    estatal_resolved = resolution.binding_values[estatal_binding_id]
    autonomico_resolved = resolution.binding_values[autonomico_binding_id]
    assert isinstance(estatal_resolved, Decimal)
    assert isinstance(autonomico_resolved, Decimal)
    assert estatal_resolved == expected_estatal
    assert autonomico_resolved == expected_autonomico
    assert autonomico_resolved > estatal_resolved


__all__: list[str] = []
