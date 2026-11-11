"""Record the year facts the backend serves, for the browser fixtures that stand in for it.

The window holds no year: the fixtures that answer for the register, the setup
operations and the ledger read the bounds, the support envelope and each tax
year's Modelo 100 edition from this recording, which the backend's own
resolvers write, with whether the register reads the year only as projected
past the last admitted one. Each edition is what ``pinned_edition`` reads in one authority
pin, from the year below the floor through every year a register plan can walk
to past the horizon, with the Modelo 100 and 130 boxes its handoff fills and
what each is called; a year the registry refuses records neither. Run after
publishing a changed authority:

    uv run --no-sync python -m dev.desktop_year_authority_fixture [--check | --output DIR]
"""

from __future__ import annotations

from cadrumo.application.actividad_asset.filing_box_names import box_name_for_kind, pinned_box_name
from cadrumo.application.actividad_asset.operations import pinned_edition, pinned_m130_periods
from cadrumo.application.actividad_asset.register_reads import WALK_YEARS_LIMIT, is_projected_year
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST
from cadrumo.core.period import StandardPeriodCode
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.bienes_inversion_catalogue import minimum_bien_inversion_acquisition_year
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.form_codes import form_for_role
from cadrumo.domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings import (
    activity_asset_amortization_casillas,
)
from cadrumo.domain.calculations.registry.ledger_renta_gastos_pago_fraccionado_bindings import (
    renta_gastos_pago_fraccionado_target_casilla,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import AssetKind
from dev.fixture_projections.location import family_directory
from dev.fixture_projections.producer_output import emit, producer_arguments
from dev.prettier_json import dump_json


def _handoff_boxes(operation: PinnedAuthorityOperation, tax_year: int) -> dict[str, object]:
    """Name the boxes a year's handoff fills, as the register's handoff names them, in every language."""
    name = pinned_box_name(operation)
    annual = form_for_role("renta.annual", authority=operation)
    instalment = form_for_role("renta.direct_instalment", authority=operation)
    period = StandardPeriodCode.ANNUAL.value
    boxes = activity_asset_amortization_casillas(
        operation.revision_for_context(annual, filing_year=tax_year, period=period)
    )
    m100 = {
        kind.value: {
            "casilla": str(casilla),
            "names": {language.value: name(annual, tax_year, period, casilla, language) for language in OutputLanguage},
        }
        for kind, casilla in boxes.items()
    }
    m130: list[dict[str, object]] = []
    for quarter in pinned_m130_periods(operation)(tax_year):
        casilla = renta_gastos_pago_fraccionado_target_casilla(
            operation.revision_for_context(instalment, filing_year=tax_year, period=quarter), modelo=instalment
        )
        m130.append(
            {
                "period": quarter,
                "casilla": str(casilla),
                "names": {
                    kind.value: {
                        language.value: box_name_for_kind(
                            name(instalment, tax_year, quarter, casilla, language), kind, language
                        )
                        for language in OutputLanguage
                    }
                    for kind in AssetKind
                },
            }
        )
    return {"m100": m100, "m130": m130}


def render_fixture() -> str:
    """Read every year fact the fixtures need through the backend's resolvers."""
    with bundled_indexed_authority().operation() as operation:
        support = operation.supported_filing_years()
        edition = pinned_edition(operation)
        editions: list[dict[str, object]] = []
        for tax_year in range(support.floor - 1, support.horizon + WALK_YEARS_LIMIT + 1):
            stance = {
                "tax_year": tax_year,
                "admitted": support.admits_filing_year(tax_year),
                "beyond_last_admitted": is_projected_year(tax_year, support.projection_coordinate),
            }
            try:
                resolved, _ = edition(tax_year)
            except RegistryError:
                editions.append({**stance, "edition": None, "handoff": None})
                continue
            editions.append(
                {**stance, "edition": resolved.model_dump(mode="json"), "handoff": _handoff_boxes(operation, tax_year)}
            )
        return dump_json(
            {
                "four_digit_year": {"first": FOUR_DIGIT_YEAR_FIRST, "last": FOUR_DIGIT_YEAR_LAST},
                "supported_filing_years": {"floor": support.floor, "horizon": support.horizon},
                "bien_inversion_minimum_acquisition_year": minimum_bien_inversion_acquisition_year(),
                "asset_editions": editions,
            }
        )


def main() -> None:
    """Write, verify or redirect the year-authority recording."""
    arguments = producer_arguments(__doc__)
    emit(
        {family_directory("desktop-year-authority") / "yearAuthority.json": render_fixture()},
        arguments,
        remedy="just fixtures-seed desktop-year-authority",
    )


if __name__ == "__main__":
    main()
