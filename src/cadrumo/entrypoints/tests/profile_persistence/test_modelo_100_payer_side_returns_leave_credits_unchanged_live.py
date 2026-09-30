"""A withholding agent's own returns credit nothing in Modelo 100 (LIVE path).

The annual IRPF declaration credits the withholding and the payments on account
the taxpayer BORE. Modelos 111, 115, 123, 180, 190 and 193 report withholding
the taxpayer PRACTISED on other people: in law that is the perceptor's credit,
evidenced by the certificate the payer issues, and never the payer's own
(LIRPF arts. 99 and 105; RIRPF arts. 76 and 108).

This module proves the invariant end to end on the LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`) for
a taxpayer who is simultaneously a withholding agent and an autonomo: filing all
six withholding-agent returns leaves every credit casilla of the annual
declaration exactly where it stands without them.

The credit set is not hand-listed. It is the operand set of the registry formula
that totals the payments on account into casilla ``0609``, read from the
published authority, so a casilla added to or removed from that total reaches
these assertions with no test edit.

The two personas differ only in whether the six payer-side returns are filed.
Both assert the same oracle, hand-derived below from the seeded Modelo 130
quarters and the keyed salary certificate:

* ``0596`` = the salary certificate the operator keys (perceptor-side evidence).
* ``0604`` = the four seeded Modelo 130 casilla 19 quarters, plus a Modelo 131
  true zero.
* every other credit casilla = 0, because this persona bore no other withholding.
* ``0609`` = ``0596`` + ``0604``.

Real-behaviour, real-adapter (real encrypted-SQLite observation store via
:class:`SecureObjectRepository`, real published authority, real calculation
engine, real relation resolver, real source mesh -- no mocks, stubs, skips, or
xfail). Every figure is synthetic.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....application.aggregation.source_mesh import (
    CallerOverrideDisposition,
    precedence_ladder_sources,
)
from ....application.calculations.observations_repository import APP_FILING_SOURCE_KIND
from ....application.modelo.calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.runtime_graph import expression_casilla_refs
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
    revision_id_for_observation,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from ._fold_in_assertions_support import _assert_distinct_positive
from .file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "5b4c1d92-8f37-4c0a-9d61-2a7e4c8b0f13"


__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


_YEAR = newest_authored_edition("100")
_T0 = datetime(_YEAR + 1, 6, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(_YEAR + 1, 6, 10, 11, 0, tzinfo=UTC)
_ANNUAL_PERIOD = "0A"
_QUARTERS: tuple[str, ...] = ("1T", "2T", "3T", "4T")
_RELATION_PREFILL_SOURCE = "relation_prefill"

_M100_TOTAL_PAGOS_A_CUENTA_CASILLA: CasillaId = validated_casilla_id(
    "0609",
    surface="_M100_TOTAL_PAGOS_A_CUENTA_CASILLA",
)
_M100_TRABAJO_CASILLA: CasillaId = validated_casilla_id("0596", surface="_M100_TRABAJO_CASILLA")
_M100_PAGOS_FRACCIONADOS_CASILLA: CasillaId = validated_casilla_id(
    "0604",
    surface="_M100_PAGOS_FRACCIONADOS_CASILLA",
)
_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "1391",
    surface="_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA",
)

_SALARY_CERTIFICATE_BINDING: BindingId = "renta-certificado-trabajo-retenciones"
# The withholding the taxpayer's own employer certifies as borne. Perceptor-side
# evidence, so this is the only work-income credit the declaration may carry.
_SALARY_CERTIFICATE_RETENCIONES = Decimal("1234.56")

# Four DISTINCT Modelo 130 casilla 19 quarters. This taxpayer does file 130, so
# the pagos fraccionados remain a filing-grade credit; distinctness makes the
# fold unmistakable and keeps the oracle from being an all-zero comparison.
_M130_C19_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("120.00"),
    "2T": Decimal("280.00"),
    "3T": Decimal("95.50"),
    "4T": Decimal("350.00"),
}
_M130_PAGOS_OUTPUT: CasillaId = validated_casilla_id("19", surface="_M130_PAGOS_OUTPUT")
_M131_PAGOS_OUTPUT: CasillaId = validated_casilla_id("15", surface="_M131_PAGOS_OUTPUT")

# Hand-derived: 120.00 + 280.00 + 95.50 + 350.00, plus a Modelo 131 true zero.
_EXPECTED_PAGOS_FRACCIONADOS = Decimal("845.50")
# Hand-derived: the keyed certificate plus the pagos fraccionados.
_EXPECTED_TOTAL_PAGOS_A_CUENTA = Decimal("2080.06")

# The six withholding-agent returns this taxpayer files, with the source casilla
# each one's retenciones total occupies. None of them may reach a credit casilla.
_M111_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id("28", surface="_M111_RETENCIONES_OUTPUT")
_M115_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id("03", surface="_M115_RETENCIONES_OUTPUT")
_M123_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id("09", surface="_M123_RETENCIONES_OUTPUT")
_ANNUAL_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id(
    "decl.retenciones-total",
    surface="_ANNUAL_RETENCIONES_OUTPUT",
)

# Distinct quarterly amounts, and annual totals that match them, so a fold of any
# one of the six returns into any credit casilla would show up as a recognisable
# figure rather than a coincidence.
_M111_C28_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("155.00"),
    "2T": Decimal("320.75"),
    "3T": Decimal("88.50"),
    "4T": Decimal("445.25"),
}
_M115_C03_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("61.00"),
    "2T": Decimal("122.50"),
    "3T": Decimal("33.25"),
    "4T": Decimal("204.75"),
}
_M123_C09_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("15.60"),
    "2T": Decimal("72.30"),
    "3T": Decimal("8.40"),
    "4T": Decimal("51.70"),
}
# Hand-derived quarter sums, reused as the annual summary totals the taxpayer files.
_M111_ANNUAL_TOTAL = Decimal("1009.50")
_M115_ANNUAL_TOTAL = Decimal("421.50")
_M123_ANNUAL_TOTAL = Decimal("148.00")


def _payer_side_amounts() -> frozenset[Decimal]:
    """Every figure the six payer-side returns carry, quarterly and annual."""
    return frozenset(
        {
            *_M111_C28_BY_PERIOD.values(),
            *_M115_C03_BY_PERIOD.values(),
            *_M123_C09_BY_PERIOD.values(),
            _M111_ANNUAL_TOTAL,
            _M115_ANNUAL_TOTAL,
            _M123_ANNUAL_TOTAL,
        }
    )


def _seed_filing(
    *,
    obs_repo: CalculationObservationRepository,
    source_modelo: str,
    period: str,
    casilla_id: CasillaId,
    value: Decimal,
) -> None:
    """Persist one filed source-modelo period carrying a single source casilla id.

    Persisted through the production observation-persistence API, the same write
    path the local-file carry flow uses, stamped with the non-official
    ``app_filing`` source_kind.
    """

    def observation() -> RegistryModeloObservation:
        return RegistryModeloObservation(
            modelo=source_modelo,
            filing_year=_YEAR,
            period=period,
            observations=registry_grounded_observations(
                modelo=source_modelo,
                filing_year=_YEAR,
                period=period,
                casilla_values={casilla_id: value},
            ),
        )

    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            observation(),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
            stamped_revision_id=revision_id_for_observation(observation()),
        )
    )


def _seed_pagos_quarters(*, obs_repo: CalculationObservationRepository) -> None:
    """Seed the Modelo 130 (four distinct quarters) and Modelo 131 (true zero) legs."""
    for period in _QUARTERS:
        _seed_filing(
            obs_repo=obs_repo,
            source_modelo="130",
            period=period,
            casilla_id=_M130_PAGOS_OUTPUT,
            value=_M130_C19_BY_PERIOD[period],
        )
        _seed_filing(
            obs_repo=obs_repo,
            source_modelo="131",
            period=period,
            casilla_id=_M131_PAGOS_OUTPUT,
            value=Decimal("0"),
        )


def _seed_payer_side_returns(*, obs_repo: CalculationObservationRepository) -> None:
    """File all six withholding-agent returns for the exercise.

    Quarterly: 111 (rendimientos del trabajo), 115 (arrendamientos), 123
    (capital mobiliario). Annual summaries: 180 (over 115), 190 (over 111), 193
    (over 123). Every one of them reports withholding practised on other people.
    """
    for period in _QUARTERS:
        _seed_filing(
            obs_repo=obs_repo,
            source_modelo="111",
            period=period,
            casilla_id=_M111_RETENCIONES_OUTPUT,
            value=_M111_C28_BY_PERIOD[period],
        )
        _seed_filing(
            obs_repo=obs_repo,
            source_modelo="115",
            period=period,
            casilla_id=_M115_RETENCIONES_OUTPUT,
            value=_M115_C03_BY_PERIOD[period],
        )
        _seed_filing(
            obs_repo=obs_repo,
            source_modelo="123",
            period=period,
            casilla_id=_M123_RETENCIONES_OUTPUT,
            value=_M123_C09_BY_PERIOD[period],
        )
    for source_modelo, annual_total in (
        ("180", _M115_ANNUAL_TOTAL),
        ("190", _M111_ANNUAL_TOTAL),
        ("193", _M123_ANNUAL_TOTAL),
    ):
        _seed_filing(
            obs_repo=obs_repo,
            source_modelo=source_modelo,
            period=_ANNUAL_PERIOD,
            casilla_id=_ANNUAL_RETENCIONES_OUTPUT,
            value=annual_total,
        )


def _seed_prior_year_m100_zero_carry(secure_objects: SecureObjectRepository) -> None:
    repository = CalculationObservationRepository(objects=secure_objects)

    def observation() -> RegistryModeloObservation:
        return RegistryModeloObservation(
            modelo="100",
            filing_year=_YEAR - 1,
            period=_ANNUAL_PERIOD,
            observations=registry_grounded_observations(
                modelo="100",
                filing_year=_YEAR - 1,
                period=_ANNUAL_PERIOD,
                casilla_values={_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: Decimal("0")},
            ),
        )

    repository.save(
        repository.prepare_observation_envelope(
            observation(),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
            stamped_revision_id=revision_id_for_observation(observation()),
        )
    )


def _seed_taxpayer_unit_profile(secure_objects: SecureObjectRepository) -> None:
    """Seed the single-taxpayer profile record the annual profile bindings consume."""
    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
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
            UserProfileFact(path="censo.activity_start_date", value=date(_YEAR - 5, 1, 1)),
            UserProfileFact(path="withholding.colegio_concertado", value=False),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(_YEAR - 45, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
            UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
        ),
        created_at=_T0,
        updated_at=_T0,
        context=_profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


def _caller_binding_values() -> dict[BindingId, Decimal]:
    """Supply the caller-owned annual bindings: zero, plus the salary certificate.

    ``profile`` and ``relation_prefill`` sources are resolved by the live mesh
    and must stay out of ``binding_values``; the bucket-locked kinds are derived
    from the caller-override ladder rather than hand-listed. What remains is the
    caller's own channel, zero for a persona with no other prior activity.
    """
    snapshot = published_authority_operation().snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
    resolved_elsewhere = frozenset({"profile", _RELATION_PREFILL_SOURCE}) | {
        kind.value for kind in precedence_ladder_sources(CallerOverrideDisposition.LOCK)
    }
    values = {
        binding.id: Decimal("0") for binding in snapshot.revision.bindings if binding.source not in resolved_elsewhere
    }
    values[_SALARY_CERTIFICATE_BINDING] = _SALARY_CERTIFICATE_RETENCIONES
    return values


def _credit_casilla_ids() -> tuple[CasillaId, ...]:
    """Read the credit set from the registry formula that totals it into 0609."""
    snapshot = published_authority_operation().snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
    total = next(
        formula
        for formula in snapshot.revision.formulas
        if formula.target_casilla_id == _M100_TOTAL_PAGOS_A_CUENTA_CASILLA
    )
    return expression_casilla_refs(total.expression)


def _calculate_m100_annual(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> BucketAggregationCalculationResult:
    """Run the live annual Modelo 100 calculate over the seeded bucket."""
    _seed_taxpayer_unit_profile(secure_objects)
    _seed_prior_year_m100_zero_carry(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    snapshot = published_authority_operation().snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo,
            bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        ),
        clock=_T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        work_unit_repository=wu_repo,
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            binding_values=_caller_binding_values(),
            ports=ports,
            clock=_T1,
        )


def _assert_credit_oracle(result: BucketAggregationCalculationResult) -> None:
    """Assert every credit casilla against the hand-derived oracle."""
    values = result.revision.casilla_values
    expected: dict[CasillaId, Decimal] = {
        _M100_TRABAJO_CASILLA: _SALARY_CERTIFICATE_RETENCIONES,
        _M100_PAGOS_FRACCIONADOS_CASILLA: _EXPECTED_PAGOS_FRACCIONADOS,
    }
    actual = {casilla_id: Decimal(values[casilla_id]) for casilla_id in _credit_casilla_ids()}
    assert actual == {casilla_id: expected.get(casilla_id, Decimal("0")) for casilla_id in actual}, (
        f"credit casillas must match the perceptor-side oracle; got {actual}"
    )
    assert Decimal(values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA]) == _EXPECTED_TOTAL_PAGOS_A_CUENTA


def test_credit_casillas_carry_only_perceptor_side_evidence(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """Baseline: with no payer-side return filed, the credits are the keyed evidence.

    Legal grounding: LIRPF art. 99 with RIRPF arts. 109 and 110 for the pagos
    fraccionados, and LIRPF arts. 99 and 101 with RIRPF arts. 80 and 86 for the
    certified salary withholding.
    """
    assert _assert_distinct_positive(_M130_C19_BY_PERIOD) == _EXPECTED_PAGOS_FRACCIONADOS
    _seed_pagos_quarters(obs_repo=CalculationObservationRepository())

    _assert_credit_oracle(_calculate_m100_annual(secure_objects, operation=operation))


def test_filed_payer_side_returns_leave_every_credit_casilla_unchanged(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """Filing 111, 115, 123, 180, 190 and 193 moves no credit casilla.

    The same persona as the baseline test, now also filing all six
    withholding-agent returns for the exercise. Every credit casilla must hold
    the identical oracle value, and no credit casilla may carry any figure those
    six returns report, whether a quarter or an annual summary total.

    Legal grounding: the credit belongs to the perceptor (LIRPF arts. 99 and 105;
    RIRPF arts. 76 and 108), so a return the declarant files as payer supplies
    none of it.
    """
    obs_repo = CalculationObservationRepository()
    _seed_pagos_quarters(obs_repo=obs_repo)
    _seed_payer_side_returns(obs_repo=obs_repo)

    result = _calculate_m100_annual(secure_objects, operation=operation)

    _assert_credit_oracle(result)
    values = result.revision.casilla_values
    reported_by_payer_returns = _payer_side_amounts()
    leaked = {
        casilla_id: Decimal(values[casilla_id])
        for casilla_id in _credit_casilla_ids()
        if Decimal(values[casilla_id]) in reported_by_payer_returns
    }
    assert not leaked, f"credit casillas must carry no payer-side figure; got {leaked}"
