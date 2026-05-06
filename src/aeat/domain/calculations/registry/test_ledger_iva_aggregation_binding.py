"""Tests for the ledger_iva_aggregation binding source kind.

Generic counterpart to ledger_oss_aggregation for the standard IVA
modelos (303, 322, 353, 309, 390). Aggregates ledger lines by the
canonical IVA classification triple (VATCategory, VATRateKind,
IvaFlowDirection).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache

import pytest
from pydantic import ValidationError

from aeat.core.paths import PROJECT_ROOT
from aeat.domain.calculations.registry import load_registry_tree
from aeat.domain.calculations.registry._bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
    validate_ledger_iva_aggregation_binding_definition,
)
from aeat.domain.calculations.registry._errors import RegistryValidationError
from aeat.domain.calculations.registry._schema import DataBindingDefinition, ModeloRevision
from aeat.domain.vat import (
    IvaFlowDirection,
    VATCategory,
    VATRateKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@lru_cache(maxsize=1)
def _modelo_303_revision() -> ModeloRevision:
    modelos, _catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "303")
    return modelo.revisions["2009-y-siguientes"]


def _binding(binding_id: str = "modelo-303-iva-repercutido-general-cuota") -> DataBindingDefinition:
    return next(item for item in _modelo_303_revision().bindings if item.id == binding_id)


def _with_selector(binding: DataBindingDefinition, **updates: object) -> DataBindingDefinition:
    return binding.model_copy(update={"selector": {**binding.selector, **updates}})


def _with_aggregation(binding: DataBindingDefinition, op: str) -> DataBindingDefinition:
    return binding.model_copy(update={"aggregation": {"op": op}})


def _observation(
    *,
    ledger_id: str = "ledger-1",
    txn_date: date = date(2025, 6, 15),
    category: VATCategory = VATCategory.DOMESTIC_GENERAL_21,
    rate_kind: VATRateKind = VATRateKind.GENERAL,
    flow: IvaFlowDirection = IvaFlowDirection.REPERCUTIDO,
    base: Decimal = Decimal("1000"),
    iva: Decimal = Decimal("210"),
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=txn_date,
        category=category,
        rate_kind=rate_kind,
        flow_direction=flow,
        base_amount=base,
        iva_amount=iva,
    )


def _revision_with_bindings(*bindings: DataBindingDefinition) -> ModeloRevision:
    return _modelo_303_revision().model_copy(update={"bindings": bindings})


def test_validate_accepts_canonical_iva_repercutido_binding() -> None:
    validate_ledger_iva_aggregation_binding_definition(_binding())


def test_validate_rejects_unknown_category() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), categories=("bogus",)))


def test_validate_rejects_unknown_rate_kind() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), rate_kinds=("medium",)))


def test_validate_rejects_unknown_flow_direction() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), flow_direction="unknown"))


def test_validate_rejects_empty_categories() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), categories=()))


def test_validate_rejects_empty_rate_kinds() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), rate_kinds=()))


def test_validate_rejects_non_sum_aggregation() -> None:
    with pytest.raises(RegistryValidationError, match="aggregation op 'sum'"):
        validate_ledger_iva_aggregation_binding_definition(_with_aggregation(_binding(), "max"))


def test_validate_rejects_unknown_fact() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), fact="bogus"))


def test_validate_rejects_wrong_source_kind() -> None:
    binding = _binding().model_copy(update={"source": "invoice"})
    with pytest.raises(RegistryValidationError, match="not a ledger_iva_aggregation"):
        validate_ledger_iva_aggregation_binding_definition(binding)


def test_resolve_filters_by_flow_direction_repercutido() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [
        _observation(flow=IvaFlowDirection.REPERCUTIDO, iva=Decimal("210")),
        _observation(flow=IvaFlowDirection.SOPORTADO, iva=Decimal("105")),
        _observation(flow=IvaFlowDirection.AUTOREPERCUTIDO, iva=Decimal("90")),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-repercutido-general-cuota": Decimal("210")}


def test_resolve_filters_by_flow_direction_soportado() -> None:
    revision = _revision_with_bindings(_binding("modelo-303-iva-soportado-interiores-cuota"))
    observations = [
        _observation(flow=IvaFlowDirection.REPERCUTIDO, iva=Decimal("210")),
        _observation(flow=IvaFlowDirection.SOPORTADO, iva=Decimal("105")),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-soportado-interiores-cuota": Decimal("105")}


def test_resolve_filters_by_flow_direction_autorepercutido() -> None:
    revision = _revision_with_bindings(_binding("modelo-303-iva-autorepercutido-intracomunitaria-cuota"))
    observations = [
        _observation(
            category=VATCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.AUTOREPERCUTIDO,
            iva=Decimal("42"),
        ),
        _observation(
            category=VATCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("99"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("42")}


def test_resolve_filters_by_category_set() -> None:
    """The selector's categories tuple is interpreted as a SET match —
    observations whose category is in the tuple count, others don't."""
    observations = [
        _observation(
            category=VATCategory.DOMESTIC_GENERAL_21,
            rate_kind=VATRateKind.GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("210"),
        ),
        _observation(
            category=VATCategory.DOMESTIC_REDUCED_10,
            rate_kind=VATRateKind.REDUCED,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("100"),
        ),
        _observation(
            category=VATCategory.RECARGO_EQUIVALENCIA,
            rate_kind=VATRateKind.GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("999"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(
        _revision_with_bindings(
            _binding(
                "modelo-303-iva-soportado-interiores-cuota",
            )
        ),
        observations,
    )
    assert result["modelo-303-iva-soportado-interiores-cuota"] == Decimal("310")


def test_resolve_supports_base_amount_sum_fact() -> None:
    revision = _revision_with_bindings(_with_selector(_binding(), fact="base_amount_sum"))
    observations = [
        _observation(base=Decimal("1000"), iva=Decimal("210")),
        _observation(base=Decimal("500"), iva=Decimal("105")),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-repercutido-general-cuota": Decimal("1500")}


def test_resolve_returns_zero_when_no_observation_matches() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [_observation(category=VATCategory.RECARGO_EQUIVALENCIA, iva=Decimal("999"))]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-repercutido-general-cuota": Decimal("0")}


def test_resolve_handles_multiple_bindings_independently() -> None:
    revision = _revision_with_bindings(
        _binding("modelo-303-iva-repercutido-general-cuota"),
        _binding("modelo-303-iva-soportado-interiores-cuota"),
    )
    observations = [
        _observation(flow=IvaFlowDirection.REPERCUTIDO, iva=Decimal("210")),
        _observation(flow=IvaFlowDirection.SOPORTADO, iva=Decimal("63")),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-repercutido-general-cuota": Decimal("210"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("63"),
    }


def test_iva_ledger_observation_is_strict_and_frozen() -> None:
    obs = _observation()
    with pytest.raises(ValidationError):
        obs.iva_amount = Decimal("999")  # type: ignore[misc]
