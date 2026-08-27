"""A pulled AEAT filing history changes what the engine computes.

The question this answers is whether a profile whose AEAT filing history was
fetched from the declarations register computes the same figures as a profile with
no history at all. It does not: on a channel whose source modelo the register
serves, the pulled figures reach the annual casilla and the two profiles diverge.

The channel exercised is the annual IRPF credit for pagos fraccionados, Modelo
100 casilla ``0604``. Its registry formula sums two cross-model relations, and
the Modelo 130 leg materialises into a ``relation_prefill`` binding resolved by
:class:`~application.calculations.RelationPrefillSourceResolver` from the
encrypted observation store. Modelo 130 declares a filed-declarations read
surface, so the register can serve it.

Both poles run through the production surfaces end to end. The history pole
persists through :func:`~application.live.persist_filed_calculation_observation`
-- the function the single, bulk and source capture routes all reach through the
filed-capture finalizer -- rather than writing an observation with a hand-chosen
provenance, so the persisted provenance is the one the real pull stamps. Both
poles then run the live operator calculate path over the SAME law-resolved
revision, resolved from ``(modelo, filing_year, period)`` and never injected.

Real behaviour throughout: real encrypted-SQLite observation store, real registry
authority, real relation resolver, real source mesh, real calculation engine. No
mock, stub, fake, skip or xfail.

Neither expected figure is computed from the formula under test. The
no-history pole expects ABSENCE, which no formula can produce a number for, and
the history pole expects the sum of the values the synthetic AEAT register row
carries -- an input to the run, chosen by this module, not read back out of it.

Why divergence rather than equality is the assertion: the observation store's
read path applies no provenance filter, so an ``aeat_sede_justificante`` row is
consumed exactly where an ``app_filing`` row is. A test asserting the two poles
agree would pass only if that filter existed, and it does not.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    ObservedCasillaValue,
)
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import CasillaId, CasillaValueKind, Modelo, Period, validated_casilla_id
from ....core.config import Settings
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...live.filed_observation_persistence import persist_filed_calculation_observation
from ...modelo._calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from ...modelo._work_lifecycle import create_work_unit
from .._observations_repository import CalculationObservationRepository, ObservationSourceKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NO_HISTORY_BUCKET = "10006041-0000-4000-8000-000000000001"
_PULLED_HISTORY_BUCKET = "10006041-0000-4000-8000-000000000002"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_YEAR = 2024
_M100_ANNUAL_PERIOD = "0A"
_M130_QUARTERS = ("1T", "2T", "3T", "4T")

# What the synthetic AEAT declarations-register row reports for Modelo 130
# casilla 19 ("Resultado a ingresar") in each quarter. These are INPUTS to the
# run, declared here, not values read back from the engine.
_PULLED_C19_BY_QUARTER: dict[str, Decimal] = {
    "1T": Decimal("412.55"),
    "2T": Decimal("298.10"),
    "3T": Decimal("530.00"),
    "4T": Decimal("175.35"),
}
_PULLED_C19_TOTAL = Decimal("1416.00")

_M130_SOURCE_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_SOURCE_CASILLA")
_M100_PAGOS_CASILLA: CasillaId = validated_casilla_id("0604", surface="_M100_PAGOS_CASILLA")
_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "1391",
    surface="_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA",
)
_RELATION_PREFILL_SOURCE = "relation_prefill"
_M130_PAGOS_RELATION_ID = "renta-2024-rel-130-pagos-fraccionados"
_OPTIONAL_PAYEE_RETENCIONES_BINDINGS: frozenset[BindingId] = frozenset(
    {"renta-2024-certificado-trabajo-retenciones"},
)
_SYNTHETIC_TAX_ID = "12345678Z"


def _synthetic_register_row(period_code: str) -> FiledDeclaracionObservation:
    """One Modelo 130 declarations-register row as the pull would observe it.

    Synthetic register data, not a test double: the observation is the adapter's
    own typed boundary model, and it is pushed through the real persistence
    function rather than standing in for it. ``extraction_coverage`` is complete
    because the persistence path refuses a partially-extracted filing outright,
    so an incomplete value here would test the refusal instead of the carry.
    """
    body = f"130-{_YEAR}-{period_code}-submitted-file".encode()
    external = Settings.external_constants().aeat
    declarations_url = f"{external.domains.www6}{external.sede_paths.declarations_listing}"
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl(declarations_url),
        content_type="application/octet-stream",
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=_T0,
    )
    return FiledDeclaracionObservation(
        modelo=Modelo.M130.value,
        ejercicio=_YEAR,
        period=Period.from_year_and_code(_YEAR, period_code),
        expediente_id=f"130{_YEAR}{period_code}ABCD1234EFGH567",
        status="ALTA",
        presented_at=_T0,
        authenticated_identity=_SYNTHETIC_TAX_ID,
        artefacts=(artefact,),
        casillas=(
            ObservedCasillaValue(
                casilla_id=_M130_SOURCE_CASILLA,
                value=str(_PULLED_C19_BY_QUARTER[period_code]),
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator=f"submitted-file:{_M130_SOURCE_CASILLA}",
                confidence=1.0,
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
    )


def _pull_the_m130_history() -> tuple[str, ...]:
    """Persist the four synthetic register rows through the production pull path.

    Returns the observation keys the persistence function reports, so the caller
    can assert the pull actually landed four rows before drawing any conclusion
    from what the engine then computes.
    """
    return tuple(persist_filed_calculation_observation(_synthetic_register_row(period)) for period in _M130_QUARTERS)


def _seed_taxpayer_profile(*, bucket_id: str) -> None:
    """Seed the declared profile facts the annual M100 revision's profile bindings need."""
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=bucket_id,
        facts=(
            UserProfileFact(path="identity.tax_id", value=_SYNTHETIC_TAX_ID),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Operator"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
            UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
            UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    seed_test_profile_record(record)


def _seed_prior_year_m100_zero_carry(secure_objects: SecureObjectRepository) -> None:
    """Zero the prior-year negative-base carry both poles share.

    Seeded identically on both poles, so it cannot be the thing they differ on.
    """
    CalculationObservationRepository(objects=secure_objects).save(
        CalculationObservationRepository(objects=secure_objects).prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=Modelo.M100.value,
                filing_year=_YEAR - 1,
                period=_M100_ANNUAL_PERIOD,
                observations=registry_grounded_observations(
                    modelo=Modelo.M100.value,
                    filing_year=_YEAR - 1,
                    period=_M100_ANNUAL_PERIOD,
                    casilla_values={_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: Decimal("0")},
                ),
            ),
            source_kind=ObservationSourceKind.APP_FILING,
            captured_at=_T0,
        )
    )


def _non_relation_zero_bindings() -> dict[BindingId, Decimal]:
    """Zero-default every M100 binding that is neither profile- nor source-resolved.

    The two ``relation_prefill`` pagos bindings are deliberately left UNSET so the
    enrolled relation resolver is the only thing that can fill them, which is what
    makes the comparison a statement about the observation store rather than about
    the caller channel.
    """
    snapshot = bundled_authority().snapshot(
        Modelo.M100.value,
        filing_year=_YEAR,
        period=_M100_ANNUAL_PERIOD,
    )
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.id not in _OPTIONAL_PAYEE_RETENCIONES_BINDINGS
        if binding.source
        not in (
            "profile",
            _RELATION_PREFILL_SOURCE,
            "ledger_renta_income_aggregation",
            "ledger_renta_gastos_estimacion_directa_aggregation",
            "ledger_iva_aggregation",
            "ledger_oss_aggregation",
            "collectible_invoice",
            "payable_invoice",
        )
    }


def _calculate_m100_annual(secure_objects: SecureObjectRepository, *, bucket_id: str):
    """Run the live operator calculate for M100 annual over the active bucket.

    The revision is resolved from ``(modelo, filing_year, period)`` through the
    authority and passed to work-unit creation, which asserts rather than selects
    on it, so the law determines which revision computes.
    """
    _seed_taxpayer_profile(bucket_id=bucket_id)
    _seed_prior_year_m100_zero_carry(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=bucket_id, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=bucket_id, objects=secure_objects)
    snapshot = bundled_authority().snapshot(
        Modelo.M100.value,
        filing_year=_YEAR,
        period=_M100_ANNUAL_PERIOD,
    )
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo=Modelo.M100.value,
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _M100_ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        binding_values=_non_relation_zero_bindings(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )
    return result, str(work_unit.revision_id)


@pytest.fixture
def no_history_profile(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """A profile that never pulled anything."""
    with isolated_runtime_profile(tmp_path=tmp_path / "no-history", bucket_id=_NO_HISTORY_BUCKET) as profile:
        yield profile.repository


def test_the_pulled_history_pole_lands_four_register_rows(tmp_path: Path) -> None:
    """The production pull path persists the four register rows with AEAT provenance.

    A positive control on the write half of the comparison. Without it, a history
    pole that silently persisted nothing would make the divergence test fail for
    a reason that has nothing to do with what the engine consumes.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PULLED_HISTORY_BUCKET) as profile:
        keys = _pull_the_m130_history()
        assert len(keys) == len(_M130_QUARTERS)
        assert len(set(keys)) == len(_M130_QUARTERS), f"each quarter must key distinctly; got {keys}"

        repository = CalculationObservationRepository(objects=profile.repository)
        for period_code in _M130_QUARTERS:
            payload = repository.load_observation(
                Modelo.M130.value,
                Period.from_year_and_code(_YEAR, period_code),
            )
            assert payload is not None, f"the pull must have landed M130 {_YEAR}/{period_code}"
            assert payload.source_kind is ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE
            assert payload.source_kind.is_official_aeat
            assert payload.observation.casilla_values[_M130_SOURCE_CASILLA] == _PULLED_C19_BY_QUARTER[period_code]


def test_no_history_profile_leaves_the_annual_pagos_credit_absent(
    no_history_profile: SecureObjectRepository,
) -> None:
    """With nothing pulled, casilla 0604 has no value and the gap is reported.

    The absence, not a zero: the engine declines to compute the credit and the
    relation is named on the diagnostics channel. This is one pole of the
    comparison, asserted on its own so a later change that starts producing a
    number here is attributed here rather than surfacing as a confusing
    divergence result.
    """
    result, _revision_id = _calculate_m100_annual(no_history_profile, bucket_id=_NO_HISTORY_BUCKET)

    assert _M100_PAGOS_CASILLA not in result.revision.casilla_values
    assert any(
        diagnostic.source_kind == _RELATION_PREFILL_SOURCE
        and diagnostic.relation_id == _M130_PAGOS_RELATION_ID
        and diagnostic.reason == "source_issue"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics


def test_pulled_history_and_no_history_profiles_compute_different_annual_credits(tmp_path: Path) -> None:
    """Two real runs over one law-resolved revision, and they do not agree.

    Both poles are calculated through the live operator path over the same
    ``(modelo, filing_year, period)``-resolved revision, differing only in whether
    the AEAT filing history was pulled. The pulled figures reach the annual credit;
    the profile without them has no credit at all.

    The revision equality assertion is what makes the comparison meaningful: two
    runs under different revisions could differ for reasons that have nothing to do
    with the history.
    """
    with isolated_runtime_profile(tmp_path=tmp_path / "no-history", bucket_id=_NO_HISTORY_BUCKET) as bare:
        bare_result, bare_revision_id = _calculate_m100_annual(bare.repository, bucket_id=_NO_HISTORY_BUCKET)
        bare_credit = bare_result.revision.casilla_values.get(_M100_PAGOS_CASILLA)

    with isolated_runtime_profile(tmp_path=tmp_path / "pulled", bucket_id=_PULLED_HISTORY_BUCKET) as pulled:
        pulled_keys = _pull_the_m130_history()
        assert len(pulled_keys) == len(_M130_QUARTERS)
        pulled_result, pulled_revision_id = _calculate_m100_annual(
            pulled.repository,
            bucket_id=_PULLED_HISTORY_BUCKET,
        )
        pulled_credit = pulled_result.revision.casilla_values.get(_M100_PAGOS_CASILLA)

    assert pulled_revision_id == bare_revision_id, (
        "both poles must compute under the one law-determined revision; "
        f"got {pulled_revision_id!r} against {bare_revision_id!r}"
    )
    assert bare_credit is None, f"the no-history pole must have no annual pagos credit; got {bare_credit}"
    assert pulled_credit is not None, (
        "the pulled-history pole must produce an annual pagos credit; the pull persisted "
        f"{len(pulled_keys)} register rows and the credit is still absent"
    )
    assert Decimal(pulled_credit) == _PULLED_C19_TOTAL, (
        f"the annual credit must equal the four pulled quarters ({_PULLED_C19_TOTAL}); got {pulled_credit}"
    )
    assert Decimal(pulled_credit) != Decimal("0"), (
        "a zero credit would be indistinguishable from the legally valid zero a "
        "genuine no-activity filer produces, so the divergence must be strictly non-zero"
    )

    # The divergence is CONSUMPTION, not a refusal that happened to yield a number.
    # Three runtime conditions can refuse a pulled filing on the way in -- an
    # incomplete extraction coverage, a non-canonical or ungrounded casilla, and a
    # divergent revision stamp -- and each would leave the relation unresolved and
    # named on this channel. A silent one would be indistinguishable from a clean
    # carry if only the value were asserted, so the absence of the refusal is
    # asserted separately from the presence of the value.
    refusals = tuple(
        diagnostic
        for diagnostic in pulled_result.source_diagnostics
        if diagnostic.relation_id == _M130_PAGOS_RELATION_ID
    )
    assert refusals == (), (
        "the pulled-history pole must carry NO diagnostic for the M130 relation; a "
        f"refusal here would mean the credit came from somewhere else. Got {refusals}"
    )
