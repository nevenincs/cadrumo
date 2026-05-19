"""Read-only VAT regulation catalogue registry."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from pydantic import ValidationError

from ...core.i18n import Translatable as tr
from ...core.resources import bundled_path
from ._schema import IvaCatalogue, IvaCategory, IvaCitation, IvaCitationSource, IvaRegulation
from .errors import IvaCatalogueError

def load_vat_catalogue(path: Path) -> IvaCatalogue:
    """Load one VAT catalogue TOML file."""

    resolved = path.resolve()
    stat = resolved.stat()
    return _load_vat_catalogue_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=32)
def _load_vat_catalogue_cached(path: str, byte_count: int, modified_ns: int) -> IvaCatalogue:
    del byte_count, modified_ns
    target = Path(path)
    try:
        with target.open("rb") as fh:
            payload = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise IvaCatalogueError(f"{target}: invalid VAT catalogue TOML: {exc}") from exc
    except OSError as exc:
        raise IvaCatalogueError(f"{target}: cannot read VAT catalogue: {exc}") from exc

    raw_regulations = payload.get("regulations")
    if not isinstance(raw_regulations, list) or not raw_regulations:
        raise IvaCatalogueError(f"{target}: missing [[regulations]] entries")

    regulations: dict[IvaCategory, IvaRegulation] = {}
    for index, raw_regulation in enumerate(raw_regulations, start=1):
        if not isinstance(raw_regulation, dict):
            raise IvaCatalogueError(f"{target}: regulations[{index}] must be a table")
        try:
            regulation = _parse_regulation(raw_regulation)
        except (ValidationError, ValueError) as exc:
            raise IvaCatalogueError(f"{target}: invalid regulations[{index}]: {exc}") from exc
        if regulation.category in regulations:
            raise IvaCatalogueError(f"{target}: duplicate VAT category {regulation.category.value!r}")
        regulations[regulation.category] = regulation

    missing = sorted(category.value for category in set(IvaCategory) - set(regulations))
    if missing:
        raise IvaCatalogueError(f"{target}: VAT catalogue missing categories: {missing}")
    return IvaCatalogue(regulations=regulations)


def load_iva_catalogues(root: Path | None = None) -> Mapping[int, IvaCatalogue]:
    """Load every year-keyed VAT catalogue under ``root``.

    Resolves the bundled catalogues directory on every call when
    no override is supplied; the ``bundled_path`` boundary is the
    single resolution surface.
    """

    target = root if root is not None else bundled_path("registry", "aeat", "vat", "catalogues")
    resolved = target.resolve()
    paths = tuple(sorted(resolved.glob("*.toml")))
    fingerprint = tuple(_file_fingerprint(path) for path in paths)
    return _load_vat_catalogues_cached(str(resolved), fingerprint)


def _file_fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return (path.name, stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=8)
def _load_vat_catalogues_cached(
    root: str,
    fingerprint: tuple[tuple[str, int, int], ...],
) -> Mapping[int, IvaCatalogue]:
    root_path = Path(root)
    catalogues: dict[int, IvaCatalogue] = {}
    for filename, _byte_count, _modified_ns in fingerprint:
        path = root_path / filename
        try:
            year = int(path.stem)
        except ValueError as exc:
            raise IvaCatalogueError(f"{path}: VAT catalogue filename must be a year") from exc
        catalogues[year] = load_vat_catalogue(path)
    if not catalogues:
        raise IvaCatalogueError(f"{root_path}: no VAT catalogue TOML files found")
    return MappingProxyType(catalogues)


def resolve_catalogue(*, on: date) -> IvaCatalogue:
    """Return the exact VAT catalogue for ``on``."""

    catalogue = load_iva_catalogues().get(on.year)
    if catalogue is None:
        raise IvaCatalogueError(f"no VAT catalogue registered for year={on.year}")
    return catalogue


def _to_str_dict(raw: Mapping) -> dict[str, object]:
    """Convert a Mapping with unknown key types to a str-keyed dict."""
    result: dict[str, object] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            raise IvaCatalogueError("TOML table keys must be strings")
        result[k] = v
    return result


def _parse_regulation(raw_regulation: object) -> IvaRegulation:
    if not isinstance(raw_regulation, dict):
        raise IvaCatalogueError("regulation entry must be a table")
    data = _to_str_dict(raw_regulation)
    category = IvaCategory(str(data.get("category")))
    raw_citations = data.get("citations", ())
    if not isinstance(raw_citations, list | tuple):
        raise IvaCatalogueError("citations must be a list")
    raw_boe = data.get("boe_references")
    boe_refs: Sequence[object] = raw_boe if isinstance(raw_boe, list) else []
    raw_manual = data.get("manual_references")
    manual_refs: Sequence[object] = raw_manual if isinstance(raw_manual, list) else []
    return IvaRegulation.model_validate(
        {
            "category": category,
            "label": tr(str(data.get("label"))),
            "description": tr(str(data.get("description"))),
            "triggers_when": tr(str(data.get("triggers_when"))),
            "iva_treatment": tr(str(data.get("iva_treatment"))),
            "requires_reverse_charge": data.get("requires_reverse_charge"),
            "requires_supplier_vat_id": data.get("requires_supplier_vat_id"),
            "boe_references": tuple(boe_refs),
            "manual_references": tuple(manual_refs),
            "citations": tuple(_parse_citation(raw_citation) for raw_citation in raw_citations),
            "notes": data.get("notes", ""),
        }
    )


def _parse_citation(raw_citation: object) -> IvaCitation:
    if not isinstance(raw_citation, dict):
        raise IvaCatalogueError("citation entry must be a table")
    data = _to_str_dict(raw_citation)
    source = IvaCitationSource(str(data.get("source")))
    return IvaCitation.model_validate(
        {
            "source": source,
            "article": data.get("article"),
            "url": data.get("url"),
            "quoted_text": tr(str(data.get("quoted_text"))),
            "retrieval_date": data.get("retrieval_date"),
        }
    )


__all__ = [
    "load_vat_catalogue",
    "load_iva_catalogues",
    "resolve_catalogue",
]
