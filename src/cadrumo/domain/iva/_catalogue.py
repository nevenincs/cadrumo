"""Read-only IVA regulation catalogue registry.

:func:`load_iva_catalogue` validates one committed TOML file into an
:class:`IvaCatalogue` whose entries are keyed by :class:`IvaCategory` and
stored as :class:`IvaRegulation`; :func:`resolve_catalogue` selects the year
catalogue used by filing-date consumers.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from pydantic import ValidationError

from ...core import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER, read_toml
from ...core.directory_scan import scan_directory
from ...core.paths import file_stat_fingerprint
from ...core.resources import bundled_path
from ._schema import IvaCatalogue, IvaCategory, IvaCitation, IvaCitationGrounding, IvaRegulation
from .errors import IvaCatalogueError


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
    for index, raw_regulation in enumerate(OBJECT_TUPLE_ADAPTER.validate_python(raw_regulations), start=1):
        if not isinstance(raw_regulation, Mapping):
            raise IvaCatalogueError(f"{target}: regulations[{index}] must be a table")
        try:
            regulation = _parse_regulation(STR_KEYED_MAPPING_ADAPTER.validate_python(raw_regulation))
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
    paths = scan_directory(resolved, pattern="*.toml")
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
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw_regulation)
    category = IvaCategory(str(data.get("category")))
    raw_citations = data.get("citations", ())
    if not isinstance(raw_citations, list | tuple):
        raise IvaCatalogueError("citations must be a list")
    raw_manual = data.get("manual_references")
    manual_refs = OBJECT_TUPLE_ADAPTER.validate_python(raw_manual) if isinstance(raw_manual, list) else ()
    return IvaRegulation.model_validate(
        {
            "category": category,
            "requires_reverse_charge": data.get("requires_reverse_charge"),
            "requires_supplier_iva_id": data.get("requires_supplier_iva_id"),
            "manual_references": tuple(manual_refs),
            "citations": tuple(
                _parse_citation(raw_citation) for raw_citation in OBJECT_TUPLE_ADAPTER.validate_python(raw_citations)
            ),
            "notes": data.get("notes", ""),
            "legal_basis_exempt": bool(data.get("legal_basis_exempt", False)),
        },
    )


def _parse_citation(raw_citation: object) -> IvaCitation:
    if not isinstance(raw_citation, dict):
        raise IvaCatalogueError("citation entry must be a table")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw_citation)
    return IvaCitation.model_validate(
        {
            "legal_reference": data.get("legal_reference"),
            # Inline authoritative Spanish, never resolved through a
            # translation key: verifying a quotation against the bundled
            # corpus needs the literal text at the citation site.
            "quoted_text": str(data.get("quoted_text") or ""),
            "grounding": IvaCitationGrounding(str(data.get("grounding") or "verified")),
            "unresolved_reason": str(data.get("unresolved_reason") or ""),
        },
    )


__all__ = [
    "load_iva_catalogue",
    "load_iva_catalogues",
    "resolve_catalogue",
]
