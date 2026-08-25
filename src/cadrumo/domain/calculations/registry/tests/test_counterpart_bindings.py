"""Modelo-agnostic tests for counterpart aggregation binding resolution.

Counterpart aggregation bindings let IVA-relevant modelos aggregate facts from the
user's counterpart aggregation source without owning the ledger schema. The CounterpartAggregationObservation
model is the wire-format every modelo shares; the resolver evaluates a
revision's counterpart bindings against a stream of observations.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp
from ..binding_selector_utils import selector_as_dict
from ..bindings import (
    CounterpartAggregationObservation,
    counterpart_binding_requirements,
    resolve_counterpart_binding_row_values,
    resolve_counterpart_binding_values,
)
from ..errors import RegistryValidationError
from ..schema import DataBindingDefinition, ModeloRevision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_349_revision() -> ModeloRevision:
    modelo, _catalogues = _committed_modelo("349")
    return modelo.revisions["2020-y-siguientes"]


def _binding(binding_id: str) -> DataBindingDefinition:
    return next(item for item in _modelo_349_revision().bindings if item.id == binding_id)


def _other_source_binding() -> DataBindingDefinition:
    modelo, _catalogues = _committed_modelo("130")
    revision = modelo.revisions["2019-y-siguientes"]
    return next(item for item in revision.bindings if item.source != "ledger_transaction")


def _revision(*bindings: DataBindingDefinition) -> ModeloRevision:
    return _modelo_349_revision().model_copy(update={"bindings": bindings})


def _with_selector(binding: DataBindingDefinition, **updates: object) -> DataBindingDefinition:
    return binding.model_copy(update={"selector": {**selector_as_dict(binding), **updates}})


def _with_aggregation(binding: DataBindingDefinition, op: BindingAggregationOp) -> DataBindingDefinition:
    return binding.model_copy(update={"aggregation": BindingAggregation(op=op)})


def _observation(
    *,
    party: str,
    country: str,
    base: str,
    clave: str | None,
    # 349 bindings declare source="collectible_invoice"; observations
    # must match for the counterpart resolver to aggregate them.
    source_kind: str = "collectible_invoice",
    is_rectification: bool = False,
    previous: str | None = None,
    period: str | None = None,
    year: int | None = None,
) -> CounterpartAggregationObservation:
    return CounterpartAggregationObservation.model_validate(
        {
            "source_kind": source_kind,
            "source_id": f"inv-{party}-{base}",
            "party_tax_id": party,
            "country_code": country,
            "transaction_date": date(2026, 3, 15),
            "base_amount": Decimal(base),
            "intracommunity_clave": clave,
            "is_rectification": is_rectification,
            "rectified_base_previous": Decimal(previous) if previous is not None else None,
            "rectified_period": period,
            "rectified_year": year,
        },
    )


def test_counterpart_observation_validates_country_and_clave_enums() -> None:
    with pytest.raises(ValidationError, match=r"country_code must be uppercase"):
        CounterpartAggregationObservation(
            source_id="inv-1",
            party_tax_id="DE123",
            country_code="de",
            transaction_date=date(2026, 1, 1),
            base_amount=Decimal("1"),
        )
    with pytest.raises(ValidationError, match=r"intracommunity_clave .* is not an AEAT clave de operacion"):
        CounterpartAggregationObservation(
            source_id="inv-1",
            party_tax_id="DE123",
            country_code="DE",
            transaction_date=date(2026, 1, 1),
            base_amount=Decimal("1"),
            intracommunity_clave="X",
        )


def test_counterpart_observation_rejects_inconsistent_rectification_metadata() -> None:
    with pytest.raises(
        ValidationError,
        match=r"rectification observation must declare rectified_year and rectified_period",
    ):
        CounterpartAggregationObservation(
            source_id="inv-1",
            party_tax_id="DE1",
            country_code="DE",
            transaction_date=date(2026, 1, 1),
            base_amount=Decimal("1"),
            is_rectification=True,
        )
    with pytest.raises(
        ValidationError,
        match=r"non-rectification observation must not declare rectified_base_previous",
    ):
        CounterpartAggregationObservation(
            source_id="inv-1",
            party_tax_id="DE1",
            country_code="DE",
            transaction_date=date(2026, 1, 1),
            base_amount=Decimal("1"),
            rectified_base_previous=Decimal("2"),
        )


def test_resolve_counterpart_binding_values_aggregates_operator_count_distinct_per_clave_set() -> None:
    revision = _revision(
        _with_selector(
            _binding("iva-349-declarante-numero-operadores"),
            claves=("E", "M"),
            rectification_scope="exclude_rectifications",
        ),
    )
    observations = (
        _observation(party="DE1", country="DE", base="100", clave="E"),
        _observation(party="DE1", country="DE", base="200", clave="E"),  # same operator+clave deduped
        _observation(party="FR1", country="FR", base="50", clave="M"),
        _observation(party="IT1", country="IT", base="75", clave="A"),  # outside selected claves
    )

    resolved = resolve_counterpart_binding_values(revision, observations)

    assert resolved == {"iva-349-declarante-numero-operadores": Decimal("2")}


def test_resolve_counterpart_binding_values_counts_one_record_per_operator_clave_pair() -> None:
    """Per Orden EHA/769/2010 Anexo 138-146: count is "Número de registros de tipo 2".

    A single operator with operations under multiple claves contributes one
    Tipo 2 record per clave, so the count must include the clave dimension.
    """
    revision = _revision(
        _with_selector(
            _binding("iva-349-declarante-numero-operadores"),
            claves=("E", "S"),
            rectification_scope="exclude_rectifications",
        ),
    )
    observations = (
        _observation(party="DE1", country="DE", base="100", clave="E"),  # 1 record (DE1, E)
        _observation(party="DE1", country="DE", base="50", clave="S"),  # 2 records: (DE1, E) + (DE1, S)
        _observation(party="DE1", country="DE", base="25", clave="S"),  # still 2 records (S accumulated)
        _observation(party="FR1", country="FR", base="10", clave="E"),  # 3 records
    )

    resolved = resolve_counterpart_binding_values(revision, observations)

    # 3 Tipo 2 records: (DE1, E), (DE1, S), (FR1, E)
    assert resolved == {"iva-349-declarante-numero-operadores": Decimal("3")}


def test_resolve_counterpart_binding_values_sums_base_amounts_within_selector_scope() -> None:
    revision = _revision(
        _with_selector(
            _binding("iva-349-declarante-importe-operaciones"),
            claves=("E", "M", "T"),
            rectification_scope="exclude_rectifications",
        ),
    )
    observations = (
        _observation(party="DE1", country="DE", base="1000.50", clave="E"),
        _observation(party="FR1", country="FR", base="500.25", clave="T"),
        _observation(party="IT1", country="IT", base="999.99", clave="A"),  # filtered out
        _observation(
            party="ES1",
            country="ES",
            base="200",
            clave="E",
            is_rectification=True,
            previous="180",
            period="1T",
            year=2025,
        ),  # rectification, excluded by scope
    )

    resolved = resolve_counterpart_binding_values(revision, observations)

    assert resolved == {"iva-349-declarante-importe-operaciones": Decimal("1500.75")}


def test_resolve_counterpart_binding_values_computes_rectification_delta_sum() -> None:
    revision = _revision(
        _with_selector(
            _binding("iva-349-declarante-importe-rectificaciones"),
            claves=("E",),
            rectification_scope="only_rectifications",
        ),
    )
    observations = (
        _observation(
            party="DE1",
            country="DE",
            base="1100",
            clave="E",
            is_rectification=True,
            previous="1000",
            period="1T",
            year=2025,
        ),
        _observation(
            party="FR1",
            country="FR",
            base="450",
            clave="E",
            is_rectification=True,
            previous="500",
            period="2T",
            year=2025,
        ),
        _observation(party="IT1", country="IT", base="200", clave="E"),  # not a rectification
    )

    resolved = resolve_counterpart_binding_values(revision, observations)

    assert resolved == {"iva-349-declarante-importe-rectificaciones": Decimal("50")}


def test_resolve_counterpart_binding_values_rejects_unsupported_fact() -> None:
    # The strict _InvoiceSelector pydantic model is the authoritative
    # gate for fact values: its Literal field rejects unknown facts as
    # a malformed selector before the resolver inspects the fact.
    revision = _revision(_with_selector(_binding("iva-349-declarante-importe-operaciones"), fact="not_a_fact"))
    with pytest.raises(RegistryValidationError, match=r"has malformed invoice selector"):
        resolve_counterpart_binding_values(revision, ())


def test_resolve_counterpart_binding_values_rejects_op_mismatch_for_fact() -> None:
    revision = _revision(_with_aggregation(_binding("iva-349-declarante-numero-operadores"), BindingAggregationOp.SUM))
    with pytest.raises(
        RegistryValidationError,
        match=r"fact 'operator_count' requires aggregation op 'count_distinct'",
    ):
        resolve_counterpart_binding_values(revision, ())


def test_counterpart_binding_requirements_groups_bindings_by_clave_and_scope() -> None:
    revision = _revision(
        _with_selector(
            _binding("iva-349-declarante-numero-operadores"),
            claves=("E", "M"),
            rectification_scope="exclude_rectifications",
        ),
        _with_selector(
            _binding("iva-349-declarante-importe-operaciones"),
            claves=("E", "M"),
            rectification_scope="exclude_rectifications",
        ),
        _with_selector(
            _binding("iva-349-declarante-importe-rectificaciones"),
            claves=("E",),
            rectification_scope="only_rectifications",
        ),
    )

    requirements = counterpart_binding_requirements(revision)

    assert len(requirements) == 2
    by_scope = {req.rectification_scope: req for req in requirements}
    assert by_scope["exclude_rectifications"].binding_ids == (
        "iva-349-declarante-importe-operaciones",
        "iva-349-declarante-numero-operadores",
    )
    assert by_scope["exclude_rectifications"].claves == ("E", "M")
    assert by_scope["only_rectifications"].binding_ids == ("iva-349-declarante-importe-rectificaciones",)
    assert by_scope["only_rectifications"].claves == ("E",)


def test_counterpart_binding_requirements_keep_source_kind_cohorts_distinct() -> None:
    payable_binding = _binding("iva-349-declarante-importe-operaciones").model_copy(
        update={"source": "payable_invoice"},
    )
    collectible_binding = _binding("iva-349-declarante-numero-operadores").model_copy(
        update={"source": "collectible_invoice"},
    )
    revision = _revision(payable_binding, collectible_binding)

    requirements = counterpart_binding_requirements(revision)

    by_source = {req.source_kinds: req.binding_ids for req in requirements}
    assert by_source == {
        ("collectible_invoice",): ("iva-349-declarante-numero-operadores",),
        ("payable_invoice",): ("iva-349-declarante-importe-operaciones",),
    }


def test_resolve_counterpart_binding_values_filters_by_source_kind() -> None:
    binding = _binding("iva-349-declarante-importe-operaciones").model_copy(update={"source": "payable_invoice"})
    revision = _revision(binding)
    observations = (
        _observation(party="DE1", country="DE", base="100", clave="E", source_kind="payable_invoice"),
        _observation(party="DE1", country="DE", base="999", clave="E", source_kind="ledger_transaction"),
    )

    resolved = resolve_counterpart_binding_values(revision, observations)

    assert resolved == {"iva-349-declarante-importe-operaciones": Decimal("100")}


def test_resolve_counterpart_binding_values_ignores_non_counterpart_bindings() -> None:
    counterpart_binding = _with_selector(
        _binding("iva-349-declarante-importe-operaciones"),
        claves=("E",),
    )
    other_binding = _other_source_binding()
    revision = _revision(counterpart_binding, other_binding)

    resolved = resolve_counterpart_binding_values(
        revision,
        (_observation(party="DE1", country="DE", base="100", clave="E"),),
    )

    assert resolved == {"iva-349-declarante-importe-operaciones": Decimal("100")}


def test_resolve_counterpart_binding_row_values_groups_by_operator_and_clave_summing_bases() -> None:
    revision = _revision(
        _with_selector(
            _binding("iva-349-operador-row-codigo-pais"),
            claves=("E", "S"),
            rectification_scope="exclude_rectifications",
        ),
        _with_selector(
            _binding("iva-349-operador-row-clave"),
            claves=("E", "S"),
            rectification_scope="exclude_rectifications",
        ),
        _with_selector(
            _binding("iva-349-operador-row-base"),
            claves=("E", "S"),
            rectification_scope="exclude_rectifications",
        ),
    )
    observations = (
        _observation(party="DE111", country="DE", base="1000.00", clave="E"),
        _observation(party="DE111", country="DE", base="500.00", clave="E"),  # same group, summed
        _observation(party="FR222", country="FR", base="200.00", clave="S"),
    )

    resolved = resolve_counterpart_binding_row_values(revision, observations)

    # Groups sorted by (country_code, party_tax_id, clave): (DE, DE111, E), (FR, FR222, S)
    assert resolved == {
        ("iva-349-operador-row-codigo-pais", 1): "DE",
        ("iva-349-operador-row-clave", 1): "E",
        ("iva-349-operador-row-base", 1): Decimal("1500.00"),
        ("iva-349-operador-row-codigo-pais", 2): "FR",
        ("iva-349-operador-row-clave", 2): "S",
        ("iva-349-operador-row-base", 2): Decimal("200.00"),
    }


def test_resolve_counterpart_binding_row_values_does_not_treat_non_counterpart_source_as_wildcard() -> None:
    binding = _with_selector(
        _binding("iva-349-operador-row-base").model_copy(update={"source": "manual_input"}),
        claves=("E",),
        rectification_scope="exclude_rectifications",
    )
    revision = _revision(binding)
    observations = (
        _observation(party="DE111", country="DE", base="1000.00", clave="E", source_kind="collectible_invoice"),
    )

    resolved = resolve_counterpart_binding_row_values(revision, observations)

    assert resolved == {}


def test_resolve_counterpart_binding_row_values_period_grouping_carries_rectification_metadata() -> None:
    revision = _revision(
        _with_selector(
            _binding("iva-349-rectificacion-row-codigo-pais"),
            claves=("E",),
            rectification_scope="only_rectifications",
        ),
        _with_selector(
            _binding("iva-349-rectificacion-row-ejercicio"),
            claves=("E",),
            rectification_scope="only_rectifications",
        ),
        _with_selector(
            _binding("iva-349-rectificacion-row-periodo"),
            claves=("E",),
            rectification_scope="only_rectifications",
        ),
        _with_selector(
            _binding("iva-349-rectificacion-row-base-rectificada"),
            claves=("E",),
            rectification_scope="only_rectifications",
        ),
        _with_selector(
            _binding("iva-349-rectificacion-row-base-anterior"),
            claves=("E",),
            rectification_scope="only_rectifications",
        ),
    )
    observations = (
        _observation(
            party="IT333",
            country="IT",
            base="200.00",
            clave="E",
            is_rectification=True,
            previous="180.00",
            period="4T",
            year=2025,
        ),
        _observation(
            party="DE111",
            country="DE",
            base="1100.00",
            clave="E",
            is_rectification=True,
            previous="1000.00",
            period="2T",
            year=2025,
        ),
    )

    resolved = resolve_counterpart_binding_row_values(revision, observations)

    # Sorted by (country_code, party_tax_id, clave, year, period): DE/2T first, IT/4T second.
    assert resolved == {
        ("iva-349-rectificacion-row-codigo-pais", 1): "DE",
        ("iva-349-rectificacion-row-ejercicio", 1): "2025",
        ("iva-349-rectificacion-row-periodo", 1): "2T",
        ("iva-349-rectificacion-row-base-rectificada", 1): Decimal("1100.00"),
        ("iva-349-rectificacion-row-base-anterior", 1): Decimal("1000.00"),
        ("iva-349-rectificacion-row-codigo-pais", 2): "IT",
        ("iva-349-rectificacion-row-ejercicio", 2): "2025",
        ("iva-349-rectificacion-row-periodo", 2): "4T",
        ("iva-349-rectificacion-row-base-rectificada", 2): Decimal("200.00"),
        ("iva-349-rectificacion-row-base-anterior", 2): Decimal("180.00"),
    }


def test_resolve_counterpart_binding_row_values_skips_scalar_bindings() -> None:
    revision = _revision(
        _with_selector(
            _binding("iva-349-declarante-importe-operaciones"),
            claves=("E",),
            rectification_scope="exclude_rectifications",
        ),
        _with_selector(
            _binding("iva-349-operador-row-clave"),
            claves=("E",),
            rectification_scope="exclude_rectifications",
        ),
    )
    observations = (_observation(party="DE1", country="DE", base="100", clave="E"),)

    rows = resolve_counterpart_binding_row_values(revision, observations)
    scalars = resolve_counterpart_binding_values(revision, observations)

    assert rows == {("iva-349-operador-row-clave", 1): "E"}
    assert scalars == {"iva-349-declarante-importe-operaciones": Decimal("100")}


def test_row_binding_rejects_inconsistent_grouping_for_period_only_field() -> None:
    revision = _revision(
        _with_selector(
            _binding("iva-349-rectificacion-row-ejercicio"),
            grouping="operator_clave",
            claves=("E",),
            rectification_scope="only_rectifications",
        ),
    )
    with pytest.raises(RegistryValidationError, match=r"requires grouping 'operator_clave_period'"):
        resolve_counterpart_binding_row_values(revision, ())


def test_row_binding_requires_only_rectifications_for_period_field() -> None:
    revision = _revision(
        _with_selector(
            _binding("iva-349-rectificacion-row-ejercicio"),
            claves=("E",),
            rectification_scope="exclude_rectifications",
        ),
    )
    with pytest.raises(RegistryValidationError, match=r"requires rectification_scope 'only_rectifications'"):
        resolve_counterpart_binding_row_values(revision, ())


def test_row_binding_period_grouping_requires_rectification_scope() -> None:
    revision = _revision(
        _with_selector(
            _binding("iva-349-operador-row-base"),
            grouping="operator_clave_period",
            claves=("E",),
            rectification_scope="exclude_rectifications",
        ),
    )
    with pytest.raises(RegistryValidationError, match=r"grouping 'operator_clave_period' requires"):
        resolve_counterpart_binding_row_values(revision, ())
