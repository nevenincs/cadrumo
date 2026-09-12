"""Generic tax-domain identifier mechanics backed by registry facts."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
import tomllib

__all__ = ["TaxDomain"]


_FACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "_data"
    / "registry"
    / "aeat"
    / "facts"
    / "0093-tax-domain-catalogue.toml"
)


def _catalogue_codes() -> tuple[str, ...]:
    with _FACT_PATH.open("rb") as stream:
        document = tomllib.load(stream)
    entries = document["fact"]["variants"][0]["payload"]["entries"]
    declarations = {str(entry["key"]): str(entry["value"]) for entry in entries}
    codes = tuple(token.strip() for token in declarations["catalogue.codes"].split(",") if token.strip())
    if not codes or len(codes) != len(set(codes)):
        raise ValueError("tax-domain catalogue codes must be unique and non-empty")
    return codes


TaxDomain = StrEnum(
    "TaxDomain",
    {code.upper(): code for code in _catalogue_codes()},
    module=__name__,
)
"""String-compatible tax-domain identifier type hydrated from canonical facts."""
