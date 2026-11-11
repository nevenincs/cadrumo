"""The mother's cotizaciones are asked for only when the Art. 81.2 guardería increment applies.

Art. 81.2 LIRPF caps the guardería increment of the deducción por maternidad at the
mother's "cotizaciones y cuotas totales a la Seguridad Social y Mutualidades". The cap
binds only an increment that exists, so a filer with no qualifying descendant and no
guardería spend calculates without that figure, while a mother whose increment is
positive is refused until she states it. Each case runs the real profile resolver and
the real calculation over encrypted profile storage, for every supported filing year.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from ....application.modelo.profile_derived_facts import guarderia_cap_anual
from ....application.modelo.work_addressing import law_selected_revision_for_work_target
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_missing_input import ModeloWorkMissingInputError
from ....core.casilla_id import validated_casilla_id
from ....core.money.rounding import round_to_cents
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.contribuyente.guarderia_mensual import parse_guarderia_mensual
from ....domain.contribuyente.meses_trabajo import parse_meses_trabajo
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...adapter_composition_work_ports import build_work_lifecycle_ports
from .file_flow_test_support import calculation_ports_for_test
from .general_iva_profile_facts_support import renta_single_taxpayer_facts

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MODELO = "100"
_PERIOD = "0A"
_PROFILE_ID = "10010000-0000-4100-8100-000000000613"
_WORK_INCOME = validated_casilla_id("0003")
_CLOCK = datetime.now(UTC).replace(microsecond=0)
"""The run's own instant: storage refuses a record stamped after the moment it is written."""
_COTIZACIONES_BINDING: BindingId = "renta-profile-cotizaciones-ss-madre"
_INCREMENTO_FORMULA = "renta-incremento-guarderia-0613"
_MONTHLY_GUARDERIA_SPEND = Decimal("50")
_CALENDAR_MONTHS = 12
_NO_PENDING_NEGATIVE_BASES: dict[BindingId, Decimal] = {
    f"renta-base-liquidable-negativa-general-{origin}": Decimal("0")
    for origin in ("em4-pendiente-inicio", "em3-pendiente-inicio", "em2-pendiente-inicio", "anterior")
}
"""The pending negative general bases a filer states as none (LIRPF art. 50.3)."""


def _supported_years() -> tuple[int, ...]:
    catalogue = published_supported_filing_years()
    assert catalogue is not None, "the published authority declares no supported filing years"
    return catalogue.years


def _snapshot(filing_year: int) -> RegistrySnapshot:
    with bundled_indexed_authority().operation() as operation:
        return operation.reading_snapshot(_MODELO, filing_year=filing_year, period=_PERIOD)


def _cotizaciones_fact_path(snapshot: RegistrySnapshot) -> str | None:
    """The profile path the edition reads the mother's cotizaciones from, if its 0613 cap has that term."""
    for binding in snapshot.revision.bindings:
        if binding.id == _COTIZACIONES_BINDING:
            profile_key = getattr(binding.provider, "profile_key", None)
            assert isinstance(profile_key, str), binding.provider
            return profile_key
    return None


def _years_with_the_cotizaciones_cap() -> tuple[int, ...]:
    return tuple(year for year in _supported_years() if _cotizaciones_fact_path(_snapshot(year)) is not None)


def _incremento_target(snapshot: RegistrySnapshot) -> str | None:
    """The casilla the edition's guardería increment formula writes, if it declares one."""
    for formula in snapshot.revision.formulas:
        if formula.id == _INCREMENTO_FORMULA:
            return formula.target_casilla_id
    return None


def _all_cotizaciones_paths() -> tuple[str, ...]:
    paths = {_cotizaciones_fact_path(_snapshot(year)) for year in _supported_years()}
    return tuple(sorted(path for path in paths if path is not None))


def _nursery_child(filing_year: int) -> DescendantInfo:
    """A child under three all year, living with a mother who works every month, in a nursery every month."""
    return DescendantInfo(
        birth_date=date(filing_year - 1, 1, 15),
        meses_madre_trabajo=parse_meses_trabajo(f"1-{_CALENDAR_MONTHS}", field="test"),
        gastos_guarderia_euros=0,
        gastos_guarderia_mensuales=parse_guarderia_mensual(
            f"1-{_CALENDAR_MONTHS}:{_MONTHLY_GUARDERIA_SPEND}", field="test"
        ),
        segundo_ciclo_infantil_inicio_mes=None,
    )


def _mother_facts(filing_year: int) -> tuple[UserProfileFact, ...]:
    child_facts = tuple(
        UserProfileFact(path=path, value=value)
        for path, value in descendant_facts_from_list((_nursery_child(filing_year),))
    )
    return (
        UserProfileFact(path="renta_taxpayer.sex", value="M"),
        UserProfileFact(path="renta_family.minor_children_in_unit", value=True),
        *child_facts,
    )


def _seed_profile(filing_year: int, stated: tuple[UserProfileFact, ...]) -> None:
    single = tuple(
        fact
        for fact in renta_single_taxpayer_facts(birth_date=date(1985, 3, 15))
        if fact.path not in _all_cotizaciones_paths()
    )
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"),
                *single,
                *stated,
            ),
            without=("irpf.estimation_regime", "activities.", "censo.activity_start_date", *_all_cotizaciones_paths()),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


def _operator_answers(snapshot: RegistrySnapshot) -> tuple[dict[BindingId, Decimal], dict[RelationId, Decimal]]:
    """Zero the money and manual answers no profile fact, record or ledger owns, and state no pending stock."""
    answers = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source != "profile"
        and binding.source not in BUCKET_AGGREGATION_LOCK_SOURCES
        and binding.provider.kind != "previous_filing"
        and (binding.value.data_type == "money" or binding.source == "manual_input")
    }
    answers.update(_NO_PENDING_NEGATIVE_BASES)
    relations = {
        binding.id: Decimal("0")
        for binding, _provider in relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period)
    }
    return answers, relations


@contextmanager
def _profile(tmp_path: Path, filing_year: int, stated: tuple[UserProfileFact, ...]) -> Generator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile(filing_year, stated)
        yield


def _calculate(filing_year: int) -> CalculationRevision:
    period = Period.from_year_and_code(filing_year, _PERIOD)
    snapshot = _snapshot(filing_year)
    binding_values, relation_values = _operator_answers(snapshot)
    with bundled_indexed_authority().operation() as operation:
        work_unit_id = create_work_unit(
            bucket_id=_PROFILE_ID,
            modelo=_MODELO,
            filing_year=filing_year,
            period=period,
            revision_id=law_selected_revision_for_work_target(
                modelo=_MODELO, filing_year=filing_year, period=period, operation=operation
            ),
            ports=build_work_lifecycle_ports(bucket_id=_PROFILE_ID),
            operation=operation,
            clock=_CLOCK,
        ).work_unit_id
    with calculation_ports_for_test(
        bucket_id=_PROFILE_ID,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        bucket_event_repository=BucketEventHistoryRepository(),
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_id,
            actor=_PROFILE_ID,
            casilla_inputs={_WORK_INCOME: Decimal("40000.00")},
            binding_values=binding_values,
            relation_values=relation_values,
            ports=ports,
            clock=_CLOCK,
        ).revision


def _expected_incremento(snapshot: RegistrySnapshot) -> Decimal:
    """The seeded child's increment: a full year of the annual cap, bounded by the year's spend."""
    cap_anual = guarderia_cap_anual(snapshot)
    assert cap_anual is not None, snapshot.revision.id
    prorated_cap = round_to_cents(cap_anual / Decimal(_CALENDAR_MONTHS) * Decimal(_CALENDAR_MONTHS))
    return min(prorated_cap, _MONTHLY_GUARDERIA_SPEND * _CALENDAR_MONTHS)


def test_the_envelope_holds_an_edition_whose_cap_reads_the_cotizaciones() -> None:
    """Guard the population: an envelope without the cap term would make the mother cases vacuous."""
    assert _years_with_the_cotizaciones_cap(), _supported_years()


@pytest.mark.parametrize("filing_year", _supported_years())
def test_a_childless_filer_calculates_without_the_mothers_cotizaciones(tmp_path: Path, filing_year: int) -> None:
    with _profile(tmp_path, filing_year, ()):
        revision = _calculate(filing_year)

    target = _incremento_target(_snapshot(filing_year))
    if target is not None:
        assert revision.casilla_values[validated_casilla_id(target)] == Decimal("0")
    assert _COTIZACIONES_BINDING not in revision.binding_overrides


@pytest.mark.parametrize("filing_year", _years_with_the_cotizaciones_cap())
def test_a_mother_owed_the_increment_is_refused_until_she_states_her_cotizaciones(
    tmp_path: Path, filing_year: int
) -> None:
    snapshot = _snapshot(filing_year)
    assert _expected_incremento(snapshot) > 0

    with (
        _profile(tmp_path, filing_year, _mother_facts(filing_year)),
        pytest.raises(ModeloWorkMissingInputError) as refused,
    ):
        _calculate(filing_year)

    assert refused.value.binding_id == _COTIZACIONES_BINDING


@pytest.mark.parametrize("filing_year", _years_with_the_cotizaciones_cap())
@pytest.mark.parametrize("cotizaciones", [Decimal("450"), Decimal("5000")], ids=["cotizaciones-bind", "spend-binds"])
def test_stated_cotizaciones_cap_the_increment(tmp_path: Path, filing_year: int, cotizaciones: Decimal) -> None:
    snapshot = _snapshot(filing_year)
    path = _cotizaciones_fact_path(snapshot)
    target = _incremento_target(snapshot)
    assert path is not None
    assert target is not None
    stated = (*_mother_facts(filing_year), UserProfileFact(path=path, value=cotizaciones))

    with _profile(tmp_path, filing_year, stated):
        revision = _calculate(filing_year)

    expected = min(_expected_incremento(snapshot), cotizaciones)
    assert revision.casilla_values[validated_casilla_id(target)] == expected
