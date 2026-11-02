"""The coarse media kind of an evidence source file follows its extension alone."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..evidence import MediaKind, media_kind_for_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("factura.pdf", MediaKind.PDF),
        ("FACTURA.PDF", MediaKind.PDF),
        ("factura.xml", MediaKind.PDF),
        ("foto.png", MediaKind.IMAGE),
        ("foto.JPG", MediaKind.IMAGE),
        ("foto.jpeg", MediaKind.IMAGE),
        ("foto.tif", MediaKind.IMAGE),
        ("foto.tiff", MediaKind.IMAGE),
        ("foto.webp", MediaKind.IMAGE),
        ("foto.heic", MediaKind.IMAGE),
        ("foto.heif", MediaKind.IMAGE),
        ("hoja.xlsx", None),
        ("sin_extension", None),
        ("archivo.pdf.exe", None),
    ],
)
def test_media_kind_follows_the_extension_for_text_and_path_sources(name: str, expected: MediaKind | None) -> None:
    assert media_kind_for_path(name) is expected
    assert media_kind_for_path(Path("carpeta") / name) is expected
