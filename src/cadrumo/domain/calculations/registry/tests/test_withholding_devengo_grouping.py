"""Modelo 193 type-2 grouping by pending flag and accrual year, and its declarant totals."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp, RetencionClave
from ..binding_value_contract import BindingDataType, BindingValueChannel, BindingValueContract
from ..errors import RegistryValidationError
from ..schema import BindingDefinition, ModeloRevision
from ..schema_references import PeriodSelector
from ..withholding_bindings import (
    WithholdingGrouping,
    WithholdingObservation,
    WithholdingProvider,
    resolve_withholding_binding_row_values,
    resolve_withholding_binding_values,
    validate_withholding_binding_selector_shape,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REFS = ("ley-35-2006:art-101", "orden-eha-3377-2011:art-1")
_SOURCE_REFS = ("aeat-dr-193-2025",)
_DEVENGO: WithholdingGrouping = "per_perceptor_clave_devengo"
_PENDING_NIF = "999999999"
_PENDING_NAME = "VALORES PENDIENTE DE ABONO"
_HOLDER_NIF = "11111111H"


def _row_binding(
    binding_id: str,
    row_field: str,
    data_type: BindingDataType,
    *,
    grouping: WithholdingGrouping = _DEVENGO,
) -> BindingDefinition:
    return BindingDefinition(
        id=binding_id,
        provider=WithholdingProvider(
            fact="row_field",
            row_field=row_field,
            grouping=grouping,
            record="perceptor",
        ),
        value=BindingValueContract(
            data_type=data_type,
            channel=BindingValueChannel.ROW_SET,
            row_grouping="withholding",
        ),
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _scalar_binding(
    binding_id: str,
    fact: str,
    op: BindingAggregationOp,
    *,
    grouping: WithholdingGrouping | None = None,
    row_field: str | None = None,
) -> BindingDefinition:
    is_count = op is BindingAggregationOp.COUNT_DISTINCT
    return BindingDefinition(
        id=binding_id,
        provider=WithholdingProvider(fact=fact, grouping=grouping, row_field=row_field),
        value=BindingValueContract(
            data_type=BindingDataType.INTEGER if is_count else BindingDataType.MONEY,
            channel=BindingValueChannel.INTEGER if is_count else BindingValueChannel.DECIMAL,
        ),
        aggregation=BindingAggregation(op=op),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _record_count(grouping: WithholdingGrouping = _DEVENGO) -> BindingDefinition:
    return _scalar_binding(
        "modelo-193-decl-total-perceptores",
        "grouped_row_count",
        BindingAggregationOp.COUNT_DISTINCT,
        grouping=grouping,
    )


def _base_total() -> BindingDefinition:
    return _scalar_binding(
        "modelo-193-decl-base-total",
        "grouped_row_sum",
        BindingAggregationOp.SUM,
        grouping=_DEVENGO,
        row_field="base_retenciones",
    )


def _retencion_total() -> BindingDefinition:
    return _scalar_binding(
        "modelo-193-decl-retenciones-total",
        "grouped_row_sum",
        BindingAggregationOp.SUM,
        grouping=_DEVENGO,
        row_field="retencion_practicada",
    )


def _distinct_nif_count() -> BindingDefinition:
    return _scalar_binding("modelo-193-distinct-nif", "perceptor_count", BindingAggregationOp.COUNT_DISTINCT)


def _revision_with(*bindings: BindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="2025-y-siguientes",
        localization_key="test.schema.revision.2025-y-siguientes.label",
        valid_from=date(2025, 1, 1),
        period_selector=PeriodSelector(year_from=2025, periods=("0A",)),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        bindings=bindings,
    )


def _observation(
    *,
    source_id: str,
    base: str,
    withholding: str,
    transaction_date: date,
    perceptor_tax_id: str = _HOLDER_NIF,
    perceptor_legal_name: str = "TITULAR SINTETICO",
    clave: str = "A",
    pendiente_flag: str | None = None,
    accrual_year: int | None = None,
) -> WithholdingObservation:
    amount = Decimal(base)
    return WithholdingObservation(
        source_id=source_id,
        source_allocation_id=f"{source_id}-allocation",
        perceptor_tax_id=perceptor_tax_id,
        perceptor_legal_name=perceptor_legal_name,
        transaction_date=transaction_date,
        clave=RetencionClave.from_registry(clave),
        percibido_dinerario=amount,
        retencion_practicada=Decimal(withholding),
        incapacity_cash_perception=Decimal("0"),
        incapacity_cash_withholding=Decimal("0"),
        incapacity_kind_value=Decimal("0"),
        incapacity_kind_ingreso_a_cuenta=Decimal("0"),
        incapacity_kind_repercutido=Decimal("0"),
        foral_retention_estatal=Decimal("0"),
        foral_retention_navarra=Decimal("0"),
        foral_retention_araba=Decimal("0"),
        foral_retention_gipuzkoa=Decimal("0"),
        foral_retention_bizkaia=Decimal("0"),
        pendiente_flag=pendiente_flag,
        accrual_year=accrual_year,
        base_retenciones=amount,
    )


def _pending(*, source_id: str, base: str, withholding: str, recognized_on: date) -> WithholdingObservation:
    """The prescribed PENDING representation the phase materialiser emits."""
    return _observation(
        source_id=source_id,
        base=base,
        withholding=withholding,
        transaction_date=recognized_on,
        perceptor_tax_id=_PENDING_NIF,
        perceptor_legal_name=_PENDING_NAME,
        pendiente_flag="X",
    )


def _row_indexes(row_keys: Iterable[tuple[str, int]], binding_id: str) -> set[int]:
    return {row_index for key_id, row_index in row_keys if key_id == binding_id}


def test_ordinary_pending_and_settled_rows_for_one_perceptor_and_clave_stay_three_records() -> None:
    """The pending flag and the accrual year are record identity, so nothing merges."""
    nif = _row_binding("modelo-193-perceptor-row-nif", "perceptor_tax_id", BindingDataType.TEXT)
    pendiente = _row_binding("modelo-193-perceptor-row-pendiente", "pendiente_flag", BindingDataType.TEXT)
    devengo = _row_binding("modelo-193-perceptor-row-devengo", "accrual_year", BindingDataType.INTEGER)
    base = _row_binding("modelo-193-perceptor-row-base", "base_retenciones", BindingDataType.MONEY)
    count = _record_count()
    revision = _revision_with(nif, pendiente, devengo, base, count)
    observations = (
        _observation(source_id="ordinary", base="100.00", withholding="19.00", transaction_date=date(2025, 3, 1)),
        _observation(
            source_id="pending",
            base="200.00",
            withholding="38.00",
            transaction_date=date(2025, 6, 30),
            pendiente_flag="X",
        ),
        _observation(
            source_id="settled",
            base="300.00",
            withholding="57.00",
            transaction_date=date(2025, 9, 15),
            accrual_year=2024,
        ),
    )

    row_values = resolve_withholding_binding_row_values(revision, observations)
    scalar_values = resolve_withholding_binding_values(revision, observations)

    assert _row_indexes(row_values, nif.id) == {1, 2, 3}
    assert scalar_values[count.id] == Decimal("3")
    records = {
        (row_values.get((pendiente.id, index)), row_values.get((devengo.id, index))): row_values[(base.id, index)]
        for index in (1, 2, 3)
    }
    assert records == {
        (None, None): Decimal("100.00"),
        ("X", None): Decimal("200.00"),
        (None, 2024): Decimal("300.00"),
    }


def test_the_clave_grouping_merges_the_same_phase_rows_into_one_record() -> None:
    """Teeth: the pre-existing grouping folds all three phases into one silent record."""
    nif = _row_binding(
        "modelo-190-perceptor-row-nif", "perceptor_tax_id", BindingDataType.TEXT, grouping="per_perceptor_clave"
    )
    base = _row_binding(
        "modelo-190-perceptor-row-base", "base_retenciones", BindingDataType.MONEY, grouping="per_perceptor_clave"
    )
    devengo = _row_binding(
        "modelo-190-perceptor-row-devengo", "accrual_year", BindingDataType.INTEGER, grouping="per_perceptor_clave"
    )
    count = _record_count(grouping="per_perceptor_clave")
    revision = _revision_with(nif, base, devengo, count)
    observations = (
        _observation(source_id="ordinary", base="100.00", withholding="19.00", transaction_date=date(2025, 3, 1)),
        _observation(
            source_id="pending",
            base="200.00",
            withholding="38.00",
            transaction_date=date(2025, 6, 30),
            pendiente_flag="X",
        ),
        _observation(
            source_id="settled",
            base="300.00",
            withholding="57.00",
            transaction_date=date(2025, 9, 15),
            accrual_year=2024,
        ),
    )

    row_values = resolve_withholding_binding_row_values(revision, observations)
    scalar_values = resolve_withholding_binding_values(revision, observations)

    assert _row_indexes(row_values, nif.id) == {1}
    assert row_values[(base.id, 1)] == Decimal("600.00")
    assert row_values[(devengo.id, 1)] == 2024
    assert scalar_values[count.id] == Decimal("1")


def test_pending_rows_of_different_accrual_years_stay_separate() -> None:
    """Every pending row shares 999999999; only its accrual year tells the records apart."""
    base = _row_binding("modelo-193-perceptor-row-base", "base_retenciones", BindingDataType.MONEY)
    count = _record_count()
    revision = _revision_with(base, count)
    observations = (
        _pending(source_id="pending-2025", base="200.00", withholding="38.00", recognized_on=date(2025, 12, 1)),
        _pending(source_id="pending-2026", base="50.00", withholding="9.50", recognized_on=date(2026, 1, 2)),
    )

    row_values = resolve_withholding_binding_row_values(revision, observations)

    assert row_values == {(base.id, 1): Decimal("200.00"), (base.id, 2): Decimal("50.00")}
    assert resolve_withholding_binding_values(revision, observations) == {count.id: Decimal("2")}


def test_rows_sharing_the_full_key_merge_into_one_record() -> None:
    """Two pending payments of one accrual year and clave are one type-2 record."""
    base = _row_binding("modelo-193-perceptor-row-base", "base_retenciones", BindingDataType.MONEY)
    retencion = _row_binding("modelo-193-perceptor-row-retencion", "retencion_practicada", BindingDataType.MONEY)
    count = _record_count()
    revision = _revision_with(base, retencion, count)
    observations = (
        _pending(source_id="pending-a", base="200.00", withholding="38.00", recognized_on=date(2025, 5, 1)),
        _pending(source_id="pending-b", base="50.00", withholding="9.50", recognized_on=date(2025, 11, 1)),
    )

    row_values = resolve_withholding_binding_row_values(revision, observations)

    assert row_values == {(base.id, 1): Decimal("250.00"), (retencion.id, 1): Decimal("47.50")}
    assert resolve_withholding_binding_values(revision, observations) == {count.id: Decimal("1")}


def test_declarant_totals_count_records_and_sum_the_emitted_rows() -> None:
    """One holder on two records counts twice; the distinct-NIF count does not."""
    count = _record_count()
    base_total = _base_total()
    retencion_total = _retencion_total()
    distinct_nif = _distinct_nif_count()
    revision = _revision_with(count, base_total, retencion_total, distinct_nif)
    observations = (
        _observation(source_id="ordinary-1", base="100.00", withholding="19.00", transaction_date=date(2026, 2, 1)),
        _observation(source_id="ordinary-2", base="40.00", withholding="7.60", transaction_date=date(2026, 8, 1)),
        _observation(
            source_id="settled",
            base="300.00",
            withholding="57.00",
            transaction_date=date(2026, 3, 10),
            accrual_year=2025,
        ),
        _observation(
            source_id="other-clave",
            base="10.00",
            withholding="1.90",
            transaction_date=date(2026, 4, 1),
            clave="B",
        ),
    )

    values = resolve_withholding_binding_values(revision, observations)

    # Records: holder/A/2026 (100 + 40), holder/A/devengo 2025, holder/B/2026.
    assert values[count.id] == Decimal("3")
    assert values[distinct_nif.id] == Decimal("1")
    assert values[count.id] != values[distinct_nif.id]
    assert values[base_total.id] == Decimal("450.00")
    assert values[retencion_total.id] == Decimal("85.50")


def test_declarant_totals_follow_the_selector_clave_scope() -> None:
    """The count and sums read the same clave-filtered rows the perceptor records do."""
    count = BindingDefinition(
        id="modelo-193-decl-total-perceptores",
        provider=WithholdingProvider(fact="grouped_row_count", grouping=_DEVENGO, claves=("A",)),
        value=BindingValueContract(data_type=BindingDataType.INTEGER, channel=BindingValueChannel.INTEGER),
        aggregation=BindingAggregation(op=BindingAggregationOp.COUNT_DISTINCT),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    revision = _revision_with(count)
    observations = (
        _observation(source_id="a", base="1.00", withholding="0.19", transaction_date=date(2025, 1, 1)),
        _observation(source_id="b", base="1.00", withholding="0.19", transaction_date=date(2025, 1, 1), clave="B"),
    )

    assert resolve_withholding_binding_values(revision, observations) == {count.id: Decimal("1")}


@pytest.mark.parametrize(
    ("binding", "message"),
    [
        (
            _scalar_binding("count-without-grouping", "grouped_row_count", BindingAggregationOp.COUNT_DISTINCT),
            "'grouped_row_count' requires a 'grouping' selector key",
        ),
        (
            _scalar_binding("count-as-sum", "grouped_row_count", BindingAggregationOp.SUM, grouping=_DEVENGO),
            "'grouped_row_count' requires aggregation op 'count_distinct'",
        ),
        (
            _scalar_binding(
                "count-with-field",
                "grouped_row_count",
                BindingAggregationOp.COUNT_DISTINCT,
                grouping=_DEVENGO,
                row_field="base_retenciones",
            ),
            "'grouped_row_count' counts rows and must not declare a 'row_field'",
        ),
        (
            _scalar_binding(
                "sum-without-grouping", "grouped_row_sum", BindingAggregationOp.SUM, row_field="base_retenciones"
            ),
            "'grouped_row_sum' requires a 'grouping' selector key",
        ),
        (
            _scalar_binding(
                "sum-as-count",
                "grouped_row_sum",
                BindingAggregationOp.COUNT_DISTINCT,
                grouping=_DEVENGO,
                row_field="base_retenciones",
            ),
            "'grouped_row_sum' requires aggregation op 'sum'",
        ),
        (
            _scalar_binding(
                "sum-of-identity",
                "grouped_row_sum",
                BindingAggregationOp.SUM,
                grouping=_DEVENGO,
                row_field="perceptor_tax_id",
            ),
            "'grouped_row_sum' requires an additive monetary 'row_field', not 'perceptor_tax_id'",
        ),
        (
            _scalar_binding("sum-without-field", "grouped_row_sum", BindingAggregationOp.SUM, grouping=_DEVENGO),
            "'grouped_row_sum' requires an additive monetary 'row_field', not None",
        ),
    ],
)
def test_malformed_grouped_fact_declarations_refuse(binding: BindingDefinition, message: str) -> None:
    """The build gate and the resolver both refuse, naming the broken invariant."""
    diagnostics = validate_withholding_binding_selector_shape(binding)

    assert len(diagnostics) == 1
    assert message in diagnostics[0]
    with pytest.raises(RegistryValidationError, match=re.escape(message)):
        resolve_withholding_binding_values(_revision_with(binding), ())


def test_well_formed_grouped_fact_declarations_pass_the_build_gate() -> None:
    for binding in (_record_count(), _base_total(), _retencion_total()):
        assert validate_withholding_binding_selector_shape(binding) == []


@pytest.mark.parametrize(
    "provider_fields",
    [
        {"fact": "grouped_row_total"},
        {"fact": "row_field", "row_field": "base_retenciones", "grouping": "per_perceptor_clave_ejercicio"},
        {"fact": "grouped_row_count", "grouping": "per_perceptor_devengo"},
    ],
)
def test_an_unknown_fact_or_grouping_literal_still_refuses(provider_fields: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        WithholdingProvider.model_validate(provider_fields)
