"""Source-provenance hygiene for generated Modelo 100 schema fragments."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....core.resources._boundary import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M100_REVISIONS = bundled_path("registry", "aeat", "modelos", "100", "revisions")
_HEADER_RE = re.compile(r"Auto-generated casilla schema for revision (?P<year>\d{4})")
_SOURCE_RE = re.compile(r"diccionario-declaracion-individual-ejercicio-(?P<year>\d{4})")


def test_generated_casilla_schema_headers_match_revision_directory() -> None:
    offenders: list[str] = []

    for path in scan_directory(_M100_REVISIONS, pattern="*.toml", recursive=True):
        text = path.read_text(encoding="utf-8")
        matches = list(_HEADER_RE.finditer(text))
        if not matches:
            continue

        relative = path.relative_to(_M100_REVISIONS)
        revision_year = relative.parts[0]
        for match in matches:
            header_year = match.group("year")
            if "casillas" not in relative.parts:
                offenders.append(f"{_display(path)} declares generated casilla schema outside casillas/")
            if header_year != revision_year:
                offenders.append(f"{_display(path)} declares generated revision {header_year} under {revision_year}")

            header_window = text[match.end() : match.end() + 500]
            source_match = _SOURCE_RE.search(header_window)
            if source_match is not None and source_match.group("year") != revision_year:
                offenders.append(
                    f"{_display(path)} cites source year {source_match.group('year')} under {revision_year}"
                )

    assert not offenders, "\n".join(offenders)


def _display(path: Path) -> str:
    return path.relative_to(bundled_path()).as_posix()
