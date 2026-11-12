"""The Art. 81 guardería increment: annual cap, months and spend, and before the reform the cotizaciones too.

Ley 31/2022 art. 64 rewrote LIRPF art. 81 from 2023-01-01. Apartado 2 lets the
deducción por maternidad grow by up to 1.000 euros for guardería custody spend, and
apartado 3 prorates that increase by the qualifying months and limits it to the
unsubsidised spend paid for the child. The earlier limit at the mother's cotizaciones
is gone, so from the reform's effective year casilla 0613 is computed without any
cotizaciones figure.

A supported year before it follows the earlier redaction, which the Manual práctico
de Renta 2022 states: the increment may not exceed, for each child, 1.000 euros a
year or the lesser of the cotizaciones y cuotas devengadas after the birth and the
unsubsidised spend. There the cotizaciones are a required figure, refused while
unstated and never read as zero, and asked for only when an increment exists. Each
case runs the real profile resolver and the real calculation over encrypted profile
storage, for every supported filing year.
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
from ....domain.user_profile.registry_contract import profile_binding_selectors
from ....domain.user_profile.schema import derived_selector_for_path
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
_INCREMENTO_FORMULA = "renta-incremento-guarderia-0613"
_INCREMENTO_BINDING: BindingId = "renta-profile-incremento-guarderia"
_INCREMENTO_SEMANTIC_ROLE = "irpf_incremento_maternidad_guarderia"
"""The official design's meaning of the box: the increase of the maternity deduction for custody spend."""
_REFORM = "ley-31-2022:art-64"
"""The legal reference that rewrote LIRPF art. 81; its effective year opens the rule."""
_CALENDAR_MONTHS = 12
_STATUTORY_ANNUAL_CAP = Decimal("1000")
"""Art. 81.2 LIRPF as rewritten by Ley 31/2022 art. 64: "hasta en 1.000 euros adicionales"."""
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


def _reform_year() -> int:
    """The first filing year governed by the rewritten art. 81, read from the horizon edition's legal references."""
    return _snapshot(_supported_years()[-1]).legal[_REFORM].effective_from.year


def _years_with_the_increment() -> tuple[int, ...]:
    """Every supported year from the reform's effective year to the horizon."""
    reform_year = _reform_year()
    return tuple(year for year in _supported_years() if year >= reform_year)


def _years_before_the_reform() -> tuple[int, ...]:
    """Every supported year the earlier redaction of art. 81 governs."""
    reform_year = _reform_year()
    return tuple(year for year in _supported_years() if year < reform_year)


def _incremento_target(snapshot: RegistrySnapshot) -> str | None:
    """The casilla the edition's guardería increment formula writes, if it declares one."""
    for formula in snapshot.revision.formulas:
        if formula.id == _INCREMENTO_FORMULA:
            return formula.target_casilla_id
    return None


def _designed_incremento_casilla(snapshot: RegistrySnapshot) -> str:
    """The casilla the year's official design carries for the increment, found by its meaning."""
    carriers = [
        casilla.id for casilla in snapshot.revision.casillas if casilla.semantic_role == _INCREMENTO_SEMANTIC_ROLE
    ]
    assert len(carriers) == 1, (snapshot.filing_year, carriers)
    return carriers[0]


def _nursery_child(
    filing_year: int,
    *,
    months: int,
    monthly_spend: Decimal,
    schedule: str | None = None,
    cotizaciones: Decimal | None = None,
) -> DescendantInfo:
    """A child under three all year, living with a mother who works every month, in a nursery from January.

    ``schedule`` states the paid months outright when they are not the first ``months`` of the year, and
    ``cotizaciones`` the mother's contributions after this child's birth.
    """
    return DescendantInfo(
        birth_date=date(filing_year - 1, 1, 15),
        meses_madre_trabajo=parse_meses_trabajo(f"1-{_CALENDAR_MONTHS}", field="test"),
        gastos_guarderia_euros=0,
        gastos_guarderia_mensuales=parse_guarderia_mensual(
            f"1-{months}:{monthly_spend}" if schedule is None else schedule, field="test"
        ),
        segundo_ciclo_infantil_inicio_mes=None,
        cotizaciones_ss_madre_euros=cotizaciones,
    )


def _mother_facts(
    filing_year: int,
    *,
    months: int,
    monthly_spend: Decimal,
    schedule: str | None = None,
    cotizaciones: Decimal | None = None,
) -> tuple[UserProfileFact, ...]:
    child = _nursery_child(
        filing_year, months=months, monthly_spend=monthly_spend, schedule=schedule, cotizaciones=cotizaciones
    )
    return _household_facts((child,))


def _household_facts(children: tuple[DescendantInfo, ...]) -> tuple[UserProfileFact, ...]:
    """The facts of a mother who states each of her children's rows."""
    child_facts = tuple(UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(children))
    return (
        UserProfileFact(path="renta_taxpayer.sex", value="M"),
        UserProfileFact(path="renta_family.minor_children_in_unit", value=True),
        *child_facts,
    )


def _seed_profile(filing_year: int, stated: tuple[UserProfileFact, ...]) -> None:
    single = renta_single_taxpayer_facts(birth_date=date(1985, 3, 15))
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
            without=("irpf.estimation_regime", "activities.", "censo.activity_start_date"),
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


def _expected_incremento(*, months: int, monthly_spend: Decimal, cotizaciones: Decimal | None = None) -> Decimal:
    """Art. 81.3: the annual cap prorated by the qualifying months, bounded by the spend paid.

    Before the reform the mother's cotizaciones bound it too, so a stated figure joins the minimum.
    """
    prorated_cap = _STATUTORY_ANNUAL_CAP / Decimal(_CALENDAR_MONTHS) * Decimal(months)
    bounds = [prorated_cap, monthly_spend * months]
    if cotizaciones is not None:
        bounds.append(cotizaciones)
    return min(bounds)


def test_the_envelope_holds_a_year_governed_by_the_rewritten_article() -> None:
    """Guard the population: an envelope without such a year would make the mother cases vacuous."""
    assert _years_with_the_increment(), _supported_years()


@pytest.mark.parametrize("filing_year", _years_with_the_increment())
def test_every_year_the_rule_applies_writes_the_increment_at_the_designed_casilla(filing_year: int) -> None:
    snapshot = _snapshot(filing_year)
    assert _incremento_target(snapshot) == _designed_incremento_casilla(snapshot)


@pytest.mark.parametrize("filing_year", _years_with_the_increment())
def test_the_registry_annual_cap_is_the_statutory_one(filing_year: int) -> None:
    assert guarderia_cap_anual(_snapshot(filing_year)) == _STATUTORY_ANNUAL_CAP


@pytest.mark.parametrize("filing_year", _supported_years())
def test_a_childless_filer_gets_no_increment(tmp_path: Path, filing_year: int) -> None:
    with _profile(tmp_path, filing_year, ()):
        revision = _calculate(filing_year)

    target = _incremento_target(_snapshot(filing_year))
    if filing_year in _years_with_the_increment():
        assert target is not None
        assert revision.casilla_values[validated_casilla_id(target)] == Decimal("0")


@pytest.mark.parametrize("filing_year", _years_with_the_increment())
@pytest.mark.parametrize(
    ("months", "monthly_spend"),
    [(_CALENDAR_MONTHS, Decimal("50")), (_CALENDAR_MONTHS, Decimal("150")), (6, Decimal("200"))],
    ids=["spend-binds", "annual-cap-binds", "proration-binds"],
)
def test_a_mother_calculates_the_increment_without_any_cotizaciones_fact(
    tmp_path: Path, filing_year: int, months: int, monthly_spend: Decimal
) -> None:
    target = _incremento_target(_snapshot(filing_year))
    assert target is not None

    with _profile(tmp_path, filing_year, _mother_facts(filing_year, months=months, monthly_spend=monthly_spend)):
        revision = _calculate(filing_year)

    expected = _expected_incremento(months=months, monthly_spend=monthly_spend)
    assert expected > 0
    assert revision.casilla_values[validated_casilla_id(target)] == expected


def test_the_envelope_holds_a_year_governed_by_the_earlier_redaction() -> None:
    """Guard the population: an envelope without such a year would make the pre-reform cases vacuous."""
    assert _years_before_the_reform(), _supported_years()


@pytest.mark.parametrize("filing_year", _years_before_the_reform())
def test_every_year_before_the_reform_writes_the_increment_at_the_designed_casilla(filing_year: int) -> None:
    snapshot = _snapshot(filing_year)
    assert _incremento_target(snapshot) == _designed_incremento_casilla(snapshot)


@pytest.mark.parametrize("filing_year", _years_before_the_reform())
def test_the_registry_annual_cap_before_the_reform_is_the_statutory_one(filing_year: int) -> None:
    assert guarderia_cap_anual(_snapshot(filing_year)) == _STATUTORY_ANNUAL_CAP


def _cotizaciones_bindings(snapshot: RegistrySnapshot) -> dict[BindingId, tuple[str, ...]]:
    """Every binding of the edition that names the cotizaciones, in its id or in a profile path, with its paths."""
    named: dict[BindingId, tuple[str, ...]] = {}
    for binding in snapshot.revision.bindings:
        selectors = profile_binding_selectors(binding.provider)
        if "cotizaciones" in binding.id or any("cotizaciones" in selector for selector in selectors):
            named[binding.id] = selectors
    return named


@pytest.mark.parametrize("filing_year", _supported_years())
def test_no_edition_asks_for_the_cotizaciones_as_a_household_figure(filing_year: int) -> None:
    """The limit is per child, so it lives on each child's row and no binding carries one household figure.

    An edition may bind the engine's per-child fold, a derived path; it may not bind a stated fact.
    """
    with bundled_indexed_authority().operation() as operation:
        derived = operation.profile_decode_context().schema.derived_selectors
    stated = [
        binding_id
        for binding_id, selectors in _cotizaciones_bindings(_snapshot(filing_year)).items()
        if not selectors or any(derived_selector_for_path(selector, derived) is None for selector in selectors)
    ]
    assert not stated


@pytest.mark.parametrize("filing_year", _years_before_the_reform())
def test_a_childless_filer_calculates_without_the_cotizaciones_before_the_reform(
    tmp_path: Path, filing_year: int
) -> None:
    target = _incremento_target(_snapshot(filing_year))
    assert target is not None

    with _profile(tmp_path, filing_year, ()):
        revision = _calculate(filing_year)

    assert revision.casilla_values[validated_casilla_id(target)] == Decimal("0")


@pytest.mark.parametrize("filing_year", _years_before_the_reform())
def test_a_mother_owed_the_increment_is_refused_until_she_states_her_cotizaciones(
    tmp_path: Path, filing_year: int
) -> None:
    monthly_spend = Decimal("50")
    assert _expected_incremento(months=_CALENDAR_MONTHS, monthly_spend=monthly_spend) > 0
    mother = _mother_facts(filing_year, months=_CALENDAR_MONTHS, monthly_spend=monthly_spend)

    with _profile(tmp_path, filing_year, mother), pytest.raises(ModeloWorkMissingInputError) as refused:
        _calculate(filing_year)

    limited = _cotizaciones_bindings(_snapshot(filing_year))
    assert _INCREMENTO_BINDING in limited
    assert refused.value.binding_id in limited


@pytest.mark.parametrize("filing_year", _years_before_the_reform())
@pytest.mark.parametrize(
    ("months", "monthly_spend", "cotizaciones"),
    [
        (_CALENDAR_MONTHS, Decimal("50"), Decimal("5000")),
        (_CALENDAR_MONTHS, Decimal("150"), Decimal("5000")),
        (6, Decimal("200"), Decimal("5000")),
        (_CALENDAR_MONTHS, Decimal("150"), Decimal("450")),
    ],
    ids=["spend-binds", "annual-cap-binds", "proration-binds", "cotizaciones-bind"],
)
def test_a_mother_calculates_the_increment_bounded_by_her_stated_cotizaciones(
    tmp_path: Path, filing_year: int, months: int, monthly_spend: Decimal, cotizaciones: Decimal
) -> None:
    target = _incremento_target(_snapshot(filing_year))
    assert target is not None
    stated = _mother_facts(filing_year, months=months, monthly_spend=monthly_spend, cotizaciones=cotizaciones)

    with _profile(tmp_path, filing_year, stated):
        revision = _calculate(filing_year)

    expected = _expected_incremento(months=months, monthly_spend=monthly_spend, cotizaciones=cotizaciones)
    assert expected > 0
    assert revision.casilla_values[validated_casilla_id(target)] == expected


@pytest.mark.parametrize("filing_year", _years_before_the_reform())
def test_each_childs_own_cotizaciones_limit_that_childs_increment(tmp_path: Path, filing_year: int) -> None:
    """One child's limit binds without touching the other's, and a larger figure on one cannot cover the other."""
    target = _incremento_target(_snapshot(filing_year))
    assert target is not None
    spend, other_spend = Decimal("150"), Decimal("200")
    limited = _nursery_child(filing_year, months=_CALENDAR_MONTHS, monthly_spend=spend, cotizaciones=Decimal("450"))
    free = _nursery_child(filing_year, months=6, monthly_spend=other_spend, cotizaciones=Decimal("5000"))

    with _profile(tmp_path, filing_year, _household_facts((limited, free))):
        revision = _calculate(filing_year)

    expected = _expected_incremento(
        months=_CALENDAR_MONTHS, monthly_spend=spend, cotizaciones=Decimal("450")
    ) + _expected_incremento(months=6, monthly_spend=other_spend, cotizaciones=Decimal("5000"))
    assert revision.casilla_values[validated_casilla_id(target)] == expected


@pytest.mark.parametrize("filing_year", _years_with_the_increment())
def test_a_stated_cotizaciones_figure_does_not_limit_a_year_that_retired_the_limit(
    tmp_path: Path, filing_year: int
) -> None:
    target = _incremento_target(_snapshot(filing_year))
    assert target is not None
    months, monthly_spend = _CALENDAR_MONTHS, Decimal("150")
    stated = _mother_facts(filing_year, months=months, monthly_spend=monthly_spend, cotizaciones=Decimal("1"))

    with _profile(tmp_path, filing_year, stated):
        revision = _calculate(filing_year)

    assert revision.casilla_values[validated_casilla_id(target)] == _expected_incremento(
        months=months, monthly_spend=monthly_spend
    )


@pytest.mark.parametrize("filing_year", _years_with_the_increment())
def test_a_month_without_a_paid_fee_is_not_prorated(tmp_path: Path, filing_year: int) -> None:
    """The manual counts only the months whose fee is paid for the whole month, so an unpaid August is not one."""
    target = _incremento_target(_snapshot(filing_year))
    assert target is not None
    paid_months = _CALENDAR_MONTHS - 1
    monthly_spend = Decimal("220")
    mother = _mother_facts(
        filing_year,
        months=paid_months,
        monthly_spend=monthly_spend,
        schedule=f"1-7:{monthly_spend};9-12:{monthly_spend}",
    )

    with _profile(tmp_path, filing_year, mother):
        revision = _calculate(filing_year)

    expected = _expected_incremento(months=paid_months, monthly_spend=monthly_spend)
    assert expected == (_STATUTORY_ANNUAL_CAP / Decimal(_CALENDAR_MONTHS) * Decimal(paid_months))
    assert revision.casilla_values[validated_casilla_id(target)] == expected.quantize(Decimal("0.01"))
