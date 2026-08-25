"""Source mesh coverage for profile-backed calculation sources."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from functools import cache

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import (
    IVA_COMPENSATION_WALLET_URL,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
)
from ....core import CalculationSourceLineageRole, Period, RegistryAuthorityGrade
from ....core.resources import resources
from ....domain.calculations.registry import RegistrySnapshot
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ...calculations import IvaWalletDecisionSourceResolver, reconcile_iva_compensation_wallet
from ...modelo import resolve_profile_sourced_bindings
from .. import CalculationSourceContext, ProfileSourceResolver
from ._secure_objects_fixtures import secure_profile_backend  # noqa: F401

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)
_PROFILE_ID = "10010010-0100-4100-8100-100100100100"
_BUCKET_ID = _PROFILE_ID
_CCAA_BINDING = "renta-2025-profile-tax-residence-ccaa"
# Derived-fact profile bindings that unconditionally resolve a grounded value
# (zero/false for a childless, non-Madrid, non-anualidades profile) alongside
# the CCAA binding: minimo por descendientes estatal + autonomico (Art. 58/61
# LIRPF, with the autonomico half carrying a CCAA-conditional Madrid override),
# Madrid nacimiento/adopcion (casilla 1039, DL 1/2010), and the anualidades sin
# minimo separate-escala eligibility flag (Art. 64/75 LIRPF).
_DERIVED_FACT_PROFILE_BINDINGS = frozenset(
    {
        "renta-2025-profile-minimo-descendientes-estatal",
        "renta-2025-profile-minimo-descendientes-autonomico",
        "renta-2025-profile-has-economic-activity",
        "renta-2025-profile-madrid-nacimiento-adopcion-eligible-count",
        "renta-2025-profile-unidad-familiar-otros-miembros-base",
        "renta-2025-profile-anualidades-sin-minimo-descendientes",
    },
)


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


@cache
def _modelo_100_snapshot() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")


def _profile_with_ccaa(ccaa: str) -> UserProfileRecord:
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Ñ"),
            UserProfileFact(path="tax_residence.ccaa", value=ccaa),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _registered_modelo_profile() -> UserProfileRecord:
    """Supply one calculation-relevant fact for every registered modelo profile surface."""
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="censo.status", value="alta"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
            UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
            UserProfileFact(path="taxpayer_type.sal_reserva_especial_dotada", value=Decimal("0")),
            UserProfileFact(path="taxpayer_type.sal_capital_social", value=Decimal("5000")),
            UserProfileFact(path="taxpayer_type.country_of_fiscal_residence", value="FR"),
            UserProfileFact(path="iva.autoconsumo_promotor_base", value=Decimal("123")),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _wallet(amount: Decimal) -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif="12345678Z",
        authenticated_identity="12345678Z",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        rows=(
            IvaCompensationWalletRow(
                generation_year=2026,
                generation_period=Period.from_year_and_code(2026, "1T"),
                generated_amount=amount,
                applied_amount=Decimal("0"),
                pending_amount=amount,
                raw_label="2026 1T",
            ),
        ),
        total_pending=amount,
        source_url=AnyHttpUrl(IVA_COMPENSATION_WALLET_URL),
        captured_at=_CLOCK,
        raw_sha256="a" * 64,
    )


def test_profile_source_resolver_matches_direct_profile_binding_resolution() -> None:
    snapshot = _modelo_100_snapshot()
    profile_record = _profile_with_ccaa("madrid")

    direct_resolution = resolve_profile_sourced_bindings(
        snapshot,
        bucket_id=_BUCKET_ID,
        profile_record=profile_record,
    )
    resolution = ProfileSourceResolver(
        registry_snapshot=snapshot,
        profile_record=profile_record,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.binding_values == direct_resolution.binding_values
    assert resolution.enum_binding_values == direct_resolution.enum_binding_values
    assert resolution.source_transaction_ids == ()
    assert resolution.provenance
    assert {item.source_ref for item in resolution.provenance if item.contributor_source_kind == "profile"} == {
        f"profile:{_BUCKET_ID}:binding:{binding_id}"
        for binding_id in ({_CCAA_BINDING} | _DERIVED_FACT_PROFILE_BINDINGS)
    }
    assert {item.fingerprint for item in resolution.provenance if item.contributor_source_kind == "profile"} == {
        item.fingerprint for item in direct_resolution.provenance
    }


def test_profile_source_resolver_fingerprints_storage_loaded_profile(
    secure_profile_backend: None,  # noqa: F811
) -> None:
    snapshot = _modelo_100_snapshot()
    profile_record = _profile_with_ccaa("madrid")
    seed_test_profile_record(profile_record)

    resolution = ProfileSourceResolver(registry_snapshot=snapshot).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.enum_binding_values[_CCAA_BINDING] == "madrid"
    repeated = ProfileSourceResolver(registry_snapshot=snapshot).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=snapshot.revision,
        ),
    )
    assert {item.fingerprint for item in resolution.provenance if item.contributor_source_kind == "profile"} == {
        item.fingerprint for item in repeated.provenance
    }
    assert all(item.fingerprint for item in resolution.provenance)


def test_profile_source_resolver_respects_caller_owned_precedence() -> None:
    snapshot = _modelo_100_snapshot()
    profile_record = _profile_with_ccaa("cataluna")

    resolution = ProfileSourceResolver(
        registry_snapshot=snapshot,
        profile_record=profile_record,
        caller_binding_ids=(_CCAA_BINDING,),
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=snapshot.revision,
        ),
    )

    assert _CCAA_BINDING not in resolution.binding_values
    assert _CCAA_BINDING not in resolution.enum_binding_values
    # Only the CCAA binding is caller-owned here; the unconditional derived-fact
    # profile bindings (minimo por descendientes, Madrid nacimiento/adopcion,
    # anualidades sin minimo) still resolve their grounded zero/false values.
    assert {item.source_ref for item in resolution.provenance if item.contributor_source_kind == "profile"} == {
        f"profile:{_BUCKET_ID}:binding:{binding_id}" for binding_id in _DERIVED_FACT_PROFILE_BINDINGS
    }


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period", "binding_id", "channel", "expected_value"),
    (
        ("036", 2026, "alta", "modelo-036-profile-censo-status", "enum", "alta"),
        ("100", 2020, "0A", "renta-2020-profile-tax-residence-ccaa", "enum", "madrid"),
        ("100", 2021, "0A", "renta-2021-profile-tax-residence-ccaa", "enum", "madrid"),
        ("100", 2022, "0A", "renta-2022-profile-tax-residence-ccaa", "enum", "madrid"),
        ("100", 2023, "0A", "renta-2023-profile-tax-residence-ccaa", "enum", "madrid"),
        ("100", 2024, "0A", "renta-2024-profile-tax-residence-ccaa", "enum", "madrid"),
        ("100", 2025, "0A", "renta-2025-profile-tax-residence-ccaa", "enum", "madrid"),
        (
            "200",
            2025,
            "0A",
            "modelo-200-2024-profile-incn-prior-12-months",
            "decimal",
            Decimal("500000"),
        ),
        (
            "202",
            2025,
            "1P",
            "modelo-202-2025-y-siguientes-incn-prior-12-months",
            "decimal",
            Decimal("500000"),
        ),
        ("210", 2025, "0A", "m210-2025-profile-country-of-fiscal-residence", "enum", "FR"),
        ("303", 2026, "1T", "modelo-303-autoconsumo-promotor-base", "decimal", Decimal("123")),
    ),
)
def test_profile_source_resolver_projects_each_registered_modelo_revision(
    modelo: str,
    filing_year: int,
    period: str,
    binding_id: str,
    channel: str,
    expected_value: Decimal | str,
) -> None:
    """Every registered profile-source revision projects its fact and provenance through the live mesh."""
    # Reading a profile FACT through the mesh needs only the rung that declares
    # bindings, and every registered modelo carries them at applicability grade.
    # Asking for filing here would refuse 036, which is censal and never filable,
    # and 200, whose filing boundary is deliberately shut while its revision spans
    # two layouts.
    snapshot = resources().modelos.authority.snapshot(
        modelo, filing_year=filing_year, period=period, grade=RegistryAuthorityGrade.APPLICABILITY
    )

    resolution = ProfileSourceResolver(
        registry_snapshot=snapshot,
        profile_record=_registered_modelo_profile(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, "AD-HOC" if modelo == "036" else period),
            revision=snapshot.revision,
        ),
    )

    resolved_values = resolution.enum_binding_values if channel == "enum" else resolution.binding_values
    assert resolved_values[binding_id] == expected_value
    assert f"profile:{_BUCKET_ID}:binding:{binding_id}" in {
        item.source_ref for item in resolution.provenance if item.contributor_source_kind == "profile"
    }


def test_live_iva_wallet_source_resolution_carries_decision_fingerprint() -> None:
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        wallet=_wallet(Decimal("1200")),
        local_recurrence_amount=Decimal("1200"),
        decided_at=_CLOCK,
    )
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")

    resolution = IvaWalletDecisionSourceResolver(decision).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "2T"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200")}
    assert resolution.provenance
    primary = tuple(item for item in resolution.provenance if item.lineage_role is CalculationSourceLineageRole.PRIMARY)
    assert len(primary) == 1
    assert primary[0].fingerprint
    assert all(item.parent_source_ref == primary[0].source_ref for item in resolution.provenance[1:])
