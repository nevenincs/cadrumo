"""Extract BOE article API responses without merging their dated redactions."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from xml.etree.ElementTree import ParseError, tostring

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from .schema import PreprocessUnit
from .sidecar import PreprocessSidecarError

_ORDINAL_ANCHOR = re.compile(
    r"^(?P<ordinal>primero|segundo|tercero|cuarto|quinto|sexto|s[eé]ptimo|octavo|noveno|d[eé]cimo)\.",
    re.IGNORECASE,
)


def _source_stated_ordinal_anchor(unit: PreprocessUnit) -> str | None:
    """Derive a corpus fragment from an explicit ordinal-provision heading."""
    match = _ORDINAL_ANCHOR.match(unit.title or "")
    if match is None:
        return None
    return "#" + match.group("ordinal").casefold().replace("é", "e")


def article_response_units(
    markup: str,
    *,
    segment: Callable[[str], list[PreprocessUnit]],
) -> tuple[PreprocessUnit, ...]:
    """Read explicit BOE blocks and versions; never select a version implicitly."""
    try:
        response = fromstring(markup, forbid_dtd=True)
    except (ParseError, DefusedXmlException) as exc:
        raise PreprocessSidecarError("malformed BOE article XML response") from exc
    if response.tag != "response" or response.findtext("status/code") != "200":
        raise PreprocessSidecarError("BOE article XML must declare a successful response")
    blocks = response.findall("data/bloque")
    if not blocks:
        raise PreprocessSidecarError("BOE article XML has no legal blocks")
    units: list[PreprocessUnit] = []
    identities: set[tuple[str, str, str]] = set()
    for block in blocks:
        block_id = block.get("id", "").strip()
        title = block.get("titulo", "").strip()
        versions = block.findall("version")
        if not block_id or not title or not versions:
            raise PreprocessSidecarError("BOE article block lacks identity, title or versions")
        for version in versions:
            instrument = version.get("id_norma", "").strip()
            effective = version.get("fecha_vigencia", "").strip()
            if re.fullmatch(r"BOE-A-\d{4}-\d+", instrument) is None or re.fullmatch(r"\d{8}", effective) is None:
                raise PreprocessSidecarError("BOE article version lacks instrument or effective date")
            try:
                effective_date = datetime.strptime(effective, "%Y%m%d").date()
            except ValueError as exc:
                raise PreprocessSidecarError("BOE article version has an invalid effective date") from exc
            identity = (block_id, instrument, effective)
            if identity in identities:
                raise PreprocessSidecarError("BOE article XML repeats a version identity")
            identities.add(identity)
            # Reuse legal heading/ordinal segmentation inside each version;
            # never hand the response envelope or adjacent versions to it.
            version_markup = "".join(tostring(child, encoding="unicode") for child in version)
            version_units = segment(version_markup)
            if not version_units:
                raise PreprocessSidecarError("BOE article version has no legal text")
            version_label = f"{instrument} | fecha_vigencia={effective_date.isoformat()}"
            for unit in version_units:
                unit_title = unit.title or title
                units.append(
                    unit.model_copy(
                        update={
                            "title": f"{unit_title} | {version_label}" if len(versions) > 1 else unit_title,
                            "section": f"{unit_title} | {version_label}",
                            "anchor": (
                                unit.anchor
                                or _source_stated_ordinal_anchor(unit)
                                or (f"#{block_id}" if len(version_units) == 1 else None)
                            ),
                        }
                    ),
                )
    return tuple(units)


def article_version_units(
    markup: str,
    *,
    segment: Callable[[str], list[PreprocessUnit]],
) -> tuple[PreprocessUnit, ...]:
    """Read one already-sliced BOE ``version`` without losing its identity."""
    try:
        version = fromstring(markup, forbid_dtd=True)
    except (ParseError, DefusedXmlException) as exc:
        raise PreprocessSidecarError("malformed BOE article version XML") from exc
    if version.tag != "version":
        raise PreprocessSidecarError("BOE article version XML must have a version root")
    instrument = version.get("id_norma", "").strip()
    effective = version.get("fecha_vigencia", "").strip()
    published = version.get("fecha_publicacion", "").strip()
    if (
        re.fullmatch(r"BOE-A-\d{4}-\d+", instrument) is None
        or re.fullmatch(r"\d{8}", effective) is None
        or re.fullmatch(r"\d{8}", published) is None
    ):
        raise PreprocessSidecarError("BOE article version lacks instrument, publication or effective date")
    try:
        effective_date = datetime.strptime(effective, "%Y%m%d").date()
        published_date = datetime.strptime(published, "%Y%m%d").date()
    except ValueError as exc:
        raise PreprocessSidecarError("BOE article version has an invalid date") from exc
    version_markup = "".join(tostring(child, encoding="unicode") for child in version)
    units = segment(version_markup)
    if not units:
        raise PreprocessSidecarError("BOE article version has no legal text")
    label = (
        f"{instrument} | fecha_publicacion={published_date.isoformat()} | fecha_vigencia={effective_date.isoformat()}"
    )
    return tuple(
        unit.model_copy(
            update={
                "title": unit.title or label,
                "section": f"{unit.title} | {label}" if unit.title else label,
                "anchor": unit.anchor or _source_stated_ordinal_anchor(unit),
            }
        )
        for unit in units
    )
