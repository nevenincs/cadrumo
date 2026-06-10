"""Read-only IVA regulation catalogue registry."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from pydantic import ValidationError

from ...core._toml import read_toml, to_str_keyed_dict
from ...core.i18n import Translatable as tr
from ...core.paths import file_stat_fingerprint
from ...core.resources import bundled_path
from ._errors import IvaCatalogueError
from ._schema import IvaCatalogue, IvaCategory, IvaCitation, IvaCitationSource, IvaRegulation


def load_iva_catalogue(path: Path) -> IvaCatalogue:
    """Load one IVA catalogue TOML file.

    Returns:
        The validated :class:`IvaCatalogue` from the file.
    """
    resolved = path.resolve()
    try:
        stat = resolved.stat()
    except OSError as exc:
        raise IvaCatalogueError(f"{resolved}: cannot stat IVA catalogue: {exc}") from exc
    return _load_iva_catalogue_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=32)
def _load_iva_catalogue_cached(path: str, byte_count: int, modified_ns: int) -> IvaCatalogue:
    del byte_count, modified_ns
    target = Path(path)
    payload = read_toml(target, error_factory=IvaCatalogueError)

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
            raise IvaCatalogueError(f"{target}: duplicate IVA category {regulation.category.value!r}")
        regulations[regulation.category] = regulation

    missing = sorted(category.value for category in set(IvaCategory) - set(regulations))
    if missing:
        raise IvaCatalogueError(f"{target}: IVA catalogue missing categories: {missing}")
    return IvaCatalogue(regulations=regulations)


def load_iva_catalogues(root: Path | None = None) -> Mapping[int, IvaCatalogue]:
    """Load every year-keyed :class:`IvaCatalogue` under ``root``.

    Resolves the bundled catalogues directory on every call when
    no override is supplied; the ``bundled_path`` boundary is the
    single resolution surface.
    """
    target = root if root is not None else bundled_path("registry", "aeat", "iva", "catalogues")
    resolved = target.resolve()
    paths = tuple(sorted(resolved.glob("*.toml")))
    fingerprint = tuple(file_stat_fingerprint(path) for path in paths)
    return _load_iva_catalogues_cached(str(resolved), fingerprint)


@lru_cache(maxsize=8)
def _load_iva_catalogues_cached(
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
            raise IvaCatalogueError(f"{path}: IVA catalogue filename must be a year") from exc
        catalogues[year] = load_iva_catalogue(path)
    if not catalogues:
        raise IvaCatalogueError(f"{root_path}: no IVA catalogue TOML files found")
    return MappingProxyType(catalogues)


def resolve_catalogue(*, on: date) -> IvaCatalogue:
    """Return the exact IVA catalogue for ``on``.

    Returns:
        The :class:`IvaCatalogue` for the year of ``on``.
    """
    catalogue = load_iva_catalogues().get(on.year)
    if catalogue is None:
        raise IvaCatalogueError(f"no IVA catalogue registered for year={on.year}")
    return catalogue


def _parse_regulation(raw_regulation: object) -> IvaRegulation:
    if not isinstance(raw_regulation, dict):
        raise IvaCatalogueError("regulation entry must be a table")
    data = to_str_keyed_dict(dict(raw_regulation.items()), error_factory=IvaCatalogueError)
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
            "requires_supplier_iva_id": data.get("requires_supplier_iva_id"),
            "boe_references": tuple(boe_refs),
            "manual_references": tuple(manual_refs),
            "citations": tuple(_parse_citation(raw_citation) for raw_citation in raw_citations),
            "notes": data.get("notes", ""),
        }
    )


def _parse_citation(raw_citation: object) -> IvaCitation:
    if not isinstance(raw_citation, dict):
        raise IvaCatalogueError("citation entry must be a table")
    data = to_str_keyed_dict(dict(raw_citation.items()), error_factory=IvaCatalogueError)
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
    "load_iva_catalogue",
    "load_iva_catalogues",
    "resolve_catalogue",
]
