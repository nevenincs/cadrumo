"""Tests for committed Modelo 117/126/128/136 registry foundations.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Bundled-registry loader used to validate the promoted definitions.
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_snapshot`
        Snapshot fixture used for committed-form arithmetic tests.
    :class:`~domain.calculations.registry.RegistryValidator`
        Registry integrity gate proving each promoted TOML tree is loadable.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Formula runtime entry point used for official form arithmetic.
    :class:`~domain.calculations.registry.ModeloRevision`
        Registry revision carrier whose construct-owned formulas are asserted.
    :class:`~domain.calculations.registry.CasillaId`
        Typed casilla identifier used for arithmetic inputs and expectations.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import NamedTuple

import pytest

from .....core import CasillaId, RegistryAuthorityGrade, validated_casilla_id
from .....core.resources import bundled_path
from ..formula_runtime import calculate_registry_snapshot
from ..validate import RegistryValidator
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _ModeloArithmeticCase(NamedTuple):
    modelo_id: str
    revision_id: str
    filing_year: int
    period: str
    formula_ids: frozenset[str]
    inputs: dict[CasillaId, Decimal]
    expected_values: dict[CasillaId, Decimal]
    filing_period: date


_CASES = (
    _ModeloArithmeticCase(
        modelo_id="117",
        revision_id="2019-y-siguientes",
        filing_year=2025,
        period="1T",
        formula_ids=frozenset({"modelo-117-total-liquidacion", "modelo-117-resultado-ingresar"}),
        # 09 = [03] + [06] + [08]; 11 = [09] - [10].
        inputs={
            validated_casilla_id("03", surface="test_modelo_117_126_128_136_registry"): Decimal("1000.00"),
            validated_casilla_id("06", surface="test_modelo_117_126_128_136_registry"): Decimal("300.00"),
            validated_casilla_id("08", surface="test_modelo_117_126_128_136_registry"): Decimal("200.00"),
            validated_casilla_id("10", surface="test_modelo_117_126_128_136_registry"): Decimal("100.00"),
        },
        expected_values={
            validated_casilla_id("09", surface="test_modelo_117_126_128_136_registry"): Decimal("1500.00"),
            validated_casilla_id("11", surface="test_modelo_117_126_128_136_registry"): Decimal("1400.00"),
        },
        filing_period=date(2025, 3, 31),
    ),
    _ModeloArithmeticCase(
        modelo_id="126",
        revision_id="2019-y-siguientes",
        filing_year=2025,
        period="1T",
        formula_ids=frozenset({"modelo-126-total-liquidacion", "modelo-126-resultado-ingresar"}),
        # 10 = [02] + [06]; 12 = [10] - [11].
        inputs={
            validated_casilla_id("02", surface="test_modelo_117_126_128_136_registry"): Decimal("800.00"),
            validated_casilla_id("06", surface="test_modelo_117_126_128_136_registry"): Decimal("200.00"),
            validated_casilla_id("11", surface="test_modelo_117_126_128_136_registry"): Decimal("150.00"),
        },
        expected_values={
            validated_casilla_id("10", surface="test_modelo_117_126_128_136_registry"): Decimal("1000.00"),
            validated_casilla_id("12", surface="test_modelo_117_126_128_136_registry"): Decimal("850.00"),
        },
        filing_period=date(2025, 3, 31),
    ),
    _ModeloArithmeticCase(
        modelo_id="128",
        revision_id="2019-y-siguientes",
        filing_year=2025,
        period="1T",
        formula_ids=frozenset({"modelo-128-resultado-ingresar"}),
        # 07 = [03] - [06].
        inputs={
            validated_casilla_id("03", surface="test_modelo_117_126_128_136_registry"): Decimal("900.00"),
            validated_casilla_id("06", surface="test_modelo_117_126_128_136_registry"): Decimal("100.00"),
        },
        expected_values={validated_casilla_id("07", surface="test_modelo_117_126_128_136_registry"): Decimal("800.00")},
        filing_period=date(2025, 3, 31),
    ),
    _ModeloArithmeticCase(
        modelo_id="136",
        revision_id="2026",
        filing_year=2026,
        period="1T",
        formula_ids=frozenset(
            {
                "modelo-136-base-imponible",
                "modelo-136-cuota-gravamen-especial",
                "modelo-136-resultado-ingresar",
            },
        ),
        # 04 = [02] - [03]; 05 = 20 % of [04]; 07 = [05] - [06].
        inputs={
            validated_casilla_id("02", surface="test_modelo_117_126_128_136_registry"): Decimal("100000.00"),
            validated_casilla_id("03", surface="test_modelo_117_126_128_136_registry"): Decimal("40000.00"),
            validated_casilla_id("06", surface="test_modelo_117_126_128_136_registry"): Decimal("0.00"),
        },
        expected_values={
            validated_casilla_id("04", surface="test_modelo_117_126_128_136_registry"): Decimal("60000.00"),
            validated_casilla_id("05", surface="test_modelo_117_126_128_136_registry"): Decimal("12000.00"),
            validated_casilla_id("07", surface="test_modelo_117_126_128_136_registry"): Decimal("12000.00"),
        },
        filing_period=date(2026, 3, 31),
    ),
)


@pytest.mark.parametrize("case", _CASES, ids=[case.modelo_id for case in _CASES])
def test_modelo_117_126_128_136_validators_accept_committed_definitions(case: _ModeloArithmeticCase) -> None:
    modelo, catalogues = _committed_modelo(case.modelo_id)
    assert modelo.id == case.modelo_id
    assert modelo.revisions, f"{case.modelo_id} must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


@pytest.mark.parametrize("case", _CASES, ids=[case.modelo_id for case in _CASES])
def test_modelo_117_126_128_136_formulas_are_owned_by_constructs(case: _ModeloArithmeticCase) -> None:
    modelo, _ = _committed_modelo(case.modelo_id)
    revision = modelo.revisions[case.revision_id]
    owned = set().union(*(set(construct.formulas) for construct in revision.constructs))
    assert case.formula_ids <= owned


@pytest.mark.parametrize("case", _CASES, ids=[case.modelo_id for case in _CASES])
def test_modelo_117_126_128_136_official_form_arithmetic(case: _ModeloArithmeticCase) -> None:
    # The CALCULATION rung, because that is the question: this runs the
    # revision's formulas against AEAT's own worked figures. The FILING rung
    # additionally demands an export layout, which modelo 136 cannot have --
    # its export family is declared not applicable because AEAT publishes no
    # positional record design for it -- so asking for filing capability made
    # an arithmetic test refuse on a capability it never uses.
    snapshot = _committed_snapshot(
        case.modelo_id,
        case.filing_year,
        case.period,
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs=case.inputs,
        date_context={"filing_period": case.filing_period},
    )

    for casilla_id, expected in case.expected_values.items():
        assert result.values[casilla_id] == expected
