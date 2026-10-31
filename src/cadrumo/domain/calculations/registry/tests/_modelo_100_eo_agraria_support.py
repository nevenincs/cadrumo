"""Shared fixture for the Modelo 100 agrarian estimación objetiva worked-example tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from .....core.casilla_id import CasillaId
from .....core.resources.bundled_data import bundled_path
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..relations import relation_prefill_bindings_for_period
from .modelo_100_registry_support import M100_NO_DESCENDANT_MATERNIDAD_BINDINGS
from .registry_tree import bundled_modelo_components
from .snapshot_support import build_snapshot


def neutral_binding_values() -> dict[str, Decimal]:
    """The minimal neutral binding set every M100 2025 calculate run needs.

    A childless, unmarried, estimación-directa-normal individual filer with no
    prior-year carry, so the chain under test is isolated from unrelated
    axes.
    """
    return {
        # Agricultural activity is económica; the production profile resolver
        # supplies this predicate as 1/0 from taxpayer_type.irpf_income_categories.
        "renta-profile-has-economic-activity": Decimal("1"),
        "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-profile-declaration-type": Decimal("1"),
        "renta-profile-marriage-full-year": Decimal("0"),
        "renta-profile-marriage-month-start": Decimal("0"),
        "renta-profile-marriage-month-end": Decimal("0"),
        "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
        "renta-profile-madrid-nacimiento-adopcion-eligible-count": Decimal("0"),
        # Art. 75 Ley 19/1994 / Art. 7.p) LIRPF maritime-worker exemption operands;
        # neutral zero when the chain under test is unrelated (the path itself is false).
        "renta-maritime-gross-navigation-income": Decimal("0"),
        "renta-maritime-annual-salary": Decimal("0"),
        "renta-maritime-qualifying-days": Decimal("0"),
        # The Art. 81.1 maternidad deducción of an edition that computes casilla 0611;
        # neutral zero for a scenario with no descendants.
        **M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
        "renta-profile-unidad-familiar-otros-miembros-base": Decimal("0"),
        "renta-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
    }


def calculate_neutral_modelo_100_2025(
    inputs: Mapping[CasillaId, Decimal],
    *,
    text_inputs: Mapping[str, str] | None = None,
) -> RegistryCalculationResult:
    """Calculate the 2025 Modelo 100 annual snapshot for the neutral filer with the given casilla inputs."""
    modelo, catalogues = bundled_modelo_components("100")
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="0A")
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=neutral_binding_values(),
        boolean_binding_values={"renta-maritime-path-rebeca": False},
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        relation_values={
            binding.id: Decimal("0")
            for binding, _provider in relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period)
        },
        date_binding_values={"renta-profile-taxpayer-birth-date": date(1980, 1, 1)},
        date_context={"filing_period": date(2025, 12, 31)},
        text_inputs=text_inputs,
    )
