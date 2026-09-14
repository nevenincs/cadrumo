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
                            "anchor": unit.anchor or (f"#{block_id}" if len(version_units) == 1 else None),
                        }
                    ),
                )
    return tuple(units)
