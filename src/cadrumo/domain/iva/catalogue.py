"""Read-only IVA regulation catalogue registry.

The catalogue is ONE undated file. Nothing in it is year-dated: every citation
names a LIVA article and quotes it verbatim, so the year used to live in the
filename alone and admitting a filing year meant copying the whole table.

:func:`load_iva_catalogue` validates the committed TOML into an
:class:`IvaCatalogue` whose entries are keyed by :class:`IvaCategory` and stored
as :class:`IvaRegulation`. :func:`iva_catalogue_years` derives the resolvable
filing years from the citation windows, and :func:`resolve_catalogue` projects
the catalogue onto one of them, keeping only the citations asserted over it and
refusing a year the catalogue cannot ground.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from ...core import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER, read_toml
from ...core.citation_grounding import CitationGrounding
from ...core.resources import bundled_path
from ...core.validity_window import years_covered_by_every_group
from .errors import IvaCatalogueError
from .schema import IvaCatalogue, IvaCategory, IvaCitation, IvaRegulation


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


def bundled_iva_catalogue(path: Path | None = None) -> IvaCatalogue:
    """Load the committed IVA catalogue.

    Args:
        path: The catalogue file. Defaults to the bundled one, resolved through
            the ``bundled_path`` boundary that is the single resolution surface.

    Returns:
        The validated :class:`IvaCatalogue`, carrying every citation regardless
        of the span it is asserted over.
    """
    target = path if path is not None else bundled_path("registry", "aeat", "iva", "catalogues.toml")
    return load_iva_catalogue(target)


def iva_catalogue_years(path: Path | None = None) -> frozenset[int]:
    """Return every filing year the catalogue can be resolved for.

    A year counts only when EVERY grounded regulation has at least one citation
    asserted over it. A legal-basis-exempt regulation codifies no treatment and
    carries no citations, so it grounds nothing and is excluded rather than
    emptying the result.

    Returns:
        The derived set of resolvable filing years.
    """
    return years_covered_by_every_group(
        [citation.window for citation in regulation.citations]
        for regulation in bundled_iva_catalogue(path)
        if not regulation.legal_basis_exempt
    )


def resolve_catalogue(*, on: date) -> IvaCatalogue:
    """Return the IVA catalogue as grounded for the filing year of ``on``.

    Every regulation is projected onto the year: citations asserted over another
    span are dropped, so what the caller receives cites only evidence that
    speaks to the year asked for.

    Returns:
        The :class:`IvaCatalogue` for the year of ``on``.

    Raises:
        IvaCatalogueError: When the catalogue grounds no such year. There is no
            fallback to an adjacent year.
    """
    return _resolve_catalogue_cached(on.year, tuple(sorted(iva_catalogue_years())))


@lru_cache(maxsize=16)
def _resolve_catalogue_cached(year: int, grounded: tuple[int, ...]) -> IvaCatalogue:
    if year not in grounded:
        raise IvaCatalogueError(
            f"no IVA catalogue grounded for year={year}; the catalogue grounds {list(grounded)}. "
            "Ground the year against BOE or AEAT and add its citations -- never widen an existing "
            "citation's window to admit it.",
        )
    projected = {
        category: regulation.model_copy(
            update={
                "citations": tuple(citation for citation in regulation.citations if citation.window.covers_year(year)),
            },
        )
        for category, regulation in bundled_iva_catalogue().regulations.items()
    }
    return IvaCatalogue(regulations=projected)


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
            "grounding": CitationGrounding(str(data.get("grounding") or "verified")),
            "unresolved_reason": str(data.get("unresolved_reason") or ""),
            "valid_from": data.get("valid_from"),
            "valid_to": data.get("valid_to"),
        },
    )


__all__ = [
    "bundled_iva_catalogue",
    "iva_catalogue_years",
    "load_iva_catalogue",
    "resolve_catalogue",
]
