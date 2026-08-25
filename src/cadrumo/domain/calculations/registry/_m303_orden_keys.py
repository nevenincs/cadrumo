"""Canonical legal-axis keys for annual Orden registry projections."""

from __future__ import annotations

from typing import Literal

from .m303_orden_raw_models import M303AnnualOrdenSourceCensus
from .m303_orden_source import annual_orden_raw_activity_identity


def annual_orden_legal_keys(census: M303AnnualOrdenSourceCensus) -> set[str]:
    return {
        *(activity_legal_key(annual_orden_raw_activity_identity(item)) for item in census.activities),
        *(agricultural_index_legal_key(index) for index, _ in enumerate(census.agricultural_indexes)),
        *(agricultural_ingreso_legal_key(index) for index, _ in enumerate(census.agricultural_ingresos_a_cuenta)),
        *(
            non_agricultural_ingreso_legal_key(index)
            for index, _ in enumerate(census.non_agricultural_ingresos_a_cuenta)
        ),
        *(seasonal_index_legal_key(index) for index, _ in enumerate(census.seasonal_indexes)),
        difficult_justification_legal_key("agricola"),
        difficult_justification_legal_key("no_agricola"),
        *(() if census.lorca_2022_reduction is None else (lorca_2022_reduction_legal_key(),)),
    }


def activity_legal_key(identity: str) -> str:
    return f"activity:{identity}"


def agricultural_index_legal_key(index: int) -> str:
    return f"agricultural-index:{index}"


def agricultural_ingreso_legal_key(index: int) -> str:
    return f"agricultural-ingreso:{index}"


def non_agricultural_ingreso_legal_key(index: int) -> str:
    return f"iae-ingreso:{index}"


def seasonal_index_legal_key(index: int) -> str:
    return f"seasonal-index:{index}"


def difficult_justification_legal_key(cohort: Literal["agricola", "no_agricola"]) -> str:
    return f"difficult-justification:{cohort}"


def lorca_2022_reduction_legal_key() -> str:
    return "lorca-2022-reduction"
