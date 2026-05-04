"""Tests for the declaración parser boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from . import DeclaracionParseError, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_inbound,
    pytest.mark.fixture_tier_l3,
]


def test_parser_requires_registry_backed_extraction_after_template_resolution(tmp_path: Path) -> None:
    pdf_path = tmp_path / "synthetic.pdf"

    with pytest.raises(DeclaracionParseError, match="validated registry snapshots"):
        parse_declaracion(
            pdf_path,
            modelo_override="130",
            año_override=2025,
            template_revision_override="2025.01",
        )
