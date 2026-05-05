"""Read-only VAT regulation catalogue registry."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from pydantic import ValidationError

from ...core.i18n import Translatable
from ...core.paths import PROJECT_ROOT
from ._schema import VATCatalogue, VATCategory, VatCitation, VatCitationSource, VATRegulation
from .errors import VatCatalogueError

_DEFAULT_CATALOGUE_ROOT = PROJECT_ROOT / "registry" / "aeat" / "vat" / "catalogues"


def load_vat_catalogue(path: Path) -> VATCatalogue:
    """Load one VAT catalogue TOML file."""

    try:
        with path.open("rb") as fh:
            payload = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise VatCatalogueError(f"{path}: invalid VAT catalogue TOML: {exc}") from exc
    except OSError as exc:
        raise VatCatalogueError(f"{path}: cannot read VAT catalogue: {exc}") from exc

    raw_regulations = payload.get("regulations")
    if not isinstance(raw_regulations, list) or not raw_regulations:
        raise VatCatalogueError(f"{path}: missing [[regulations]] entries")

    regulations: dict[VATCategory, VATRegulation] = {}
    for index, raw_regulation in enumerate(raw_regulations, start=1):
        if not isinstance(raw_regulation, dict):
            raise VatCatalogueError(f"{path}: regulations[{index}] must be a table")
        try:
            regulation = _parse_regulation(cast("Mapping[str, Any]", raw_regulation))
        except (ValidationError, ValueError) as exc:
            raise VatCatalogueError(f"{path}: invalid regulations[{index}]: {exc}") from exc
        if regulation.category in regulations:
            raise VatCatalogueError(f"{path}: duplicate VAT category {regulation.category.value!r}")
        regulations[regulation.category] = regulation

    missing = sorted(category.value for category in set(VATCategory) - set(regulations))
    if missing:
        raise VatCatalogueError(f"{path}: VAT catalogue missing categories: {missing}")
    return VATCatalogue(regulations=regulations)


def load_vat_catalogues(root: Path = _DEFAULT_CATALOGUE_ROOT) -> Mapping[int, VATCatalogue]:
    """Load every year-keyed VAT catalogue under ``root``."""

    catalogues: dict[int, VATCatalogue] = {}
    for path in sorted(root.glob("*.toml")):
        try:
            year = int(path.stem)
        except ValueError as exc:
            raise VatCatalogueError(f"{path}: VAT catalogue filename must be a year") from exc
        catalogues[year] = load_vat_catalogue(path)
    if not catalogues:
        raise VatCatalogueError(f"{root}: no VAT catalogue TOML files found")
    return MappingProxyType(catalogues)


def resolve_catalogue(*, on: date) -> VATCatalogue:
    """Return the exact VAT catalogue for ``on``."""

    catalogue = VAT_CATALOGUES_BY_YEAR.get(on.year)
    if catalogue is None:
        raise VatCatalogueError(f"no VAT catalogue registered for year={on.year}")
    return catalogue


def _parse_regulation(raw_regulation: Mapping[str, Any]) -> VATRegulation:
    category = VATCategory(str(raw_regulation.get("category")))
    return VATRegulation.model_validate(
        {
            "category": category,
            "label": Translatable(str(raw_regulation.get("label"))),
            "description": Translatable(str(raw_regulation.get("description"))),
            "triggers_when": Translatable(str(raw_regulation.get("triggers_when"))),
            "iva_treatment": Translatable(str(raw_regulation.get("iva_treatment"))),
            "requires_reverse_charge": raw_regulation.get("requires_reverse_charge"),
            "requires_supplier_vat_id": raw_regulation.get("requires_supplier_vat_id"),
            "boe_references": tuple(raw_regulation.get("boe_references", ())),
            "manual_references": tuple(raw_regulation.get("manual_references", ())),
            "citations": tuple(
                _parse_citation(cast("Mapping[str, Any]", raw_citation))
                for raw_citation in raw_regulation.get("citations", ())
            ),
            "notes": raw_regulation.get("notes", ""),
        }
    )


def _parse_citation(raw_citation: Mapping[str, Any]) -> VatCitation:
    source = VatCitationSource(str(raw_citation.get("source")))
    return VatCitation.model_validate(
        {
            "source": source,
            "article": raw_citation.get("article"),
            "url": raw_citation.get("url"),
            "quoted_text": Translatable(str(raw_citation.get("quoted_text"))),
            "retrieval_date": raw_citation.get("retrieval_date"),
        }
    )


VAT_CATALOGUES_BY_YEAR: Mapping[int, VATCatalogue] = load_vat_catalogues()

__all__ = [
    "VAT_CATALOGUES_BY_YEAR",
    "load_vat_catalogue",
    "load_vat_catalogues",
    "resolve_catalogue",
]
