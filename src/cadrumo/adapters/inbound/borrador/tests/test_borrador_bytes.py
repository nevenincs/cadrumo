"""In-memory parsing uses the established PDF backend and one shared text pass."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from .. import parser as module
from ..errors import BorradorParseError
from ..parser import parse_borrador
from ..schema import ArtefactKind, BorradorParseMode
from .test_modelo_100_summary import _profile, _render_borrador_pdf_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize("kind", ["BORRADOR", "PREDECLARACION", "DECLARACION"])
def test_bytes_parser_matches_canonical_path_values_profile_and_digest(tmp_path: Path, kind: str) -> None:
    payload = _render_borrador_pdf_bytes(artefact_kind=kind, csv="MNOP4321QRST8765" if kind == "DECLARACION" else None)
    path = tmp_path / "synthetic.pdf"
    path.write_bytes(payload)
    profile = _profile()
    expected = parse_borrador(
        path, año_override=2025, extraction_profile=profile, parse_mode=BorradorParseMode.REGISTRY_PROFILE
    )
    actual = parse_borrador(
        payload, año_override=2025, extraction_profile=profile, parse_mode=BorradorParseMode.REGISTRY_PROFILE
    )
    assert actual.model_dump(exclude={"parsed_at"}) == expected.model_dump(exclude={"parsed_at"})
    assert actual.source_pdf_sha256 == sha256(payload).hexdigest()
    assert actual.artefact_kind.value == kind


def test_bytes_detection_and_extraction_share_exactly_one_real_backend_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _render_borrador_pdf_bytes()
    original = module.extract_pages_text_from_bytes
    calls = 0

    def extract(
        pdf_bytes: bytes,
        *,
        error_class: type[Exception],
        pdf_label: str,
        source_label: str,
    ) -> tuple[str, ...]:
        nonlocal calls
        calls += 1
        assert pdf_bytes is payload
        return original(pdf_bytes, error_class=error_class, pdf_label=pdf_label, source_label=source_label)

    monkeypatch.setattr(module, "extract_pages_text_from_bytes", extract)
    result = parse_borrador(payload, año_override=2025)
    assert calls == 1 and result.artefact_kind is ArtefactKind.BORRADOR
    assert result.values and result.source_pdf_sha256 == sha256(payload).hexdigest()


@pytest.mark.parametrize("year", [2021, 2022, 2023, 2024, 2025])
def test_bytes_parser_uses_explicit_supported_year_without_rewriting_printed_year(year: int) -> None:
    result = parse_borrador(_render_borrador_pdf_bytes(), año_override=year)
    assert result.ejercicio == "2025"


def test_unregistered_year_and_missing_registry_profile_refuse_before_pdf_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected(
        pdf_bytes: bytes,
        *,
        error_class: type[Exception],
        pdf_label: str,
        source_label: str,
    ) -> tuple[str, ...]:
        raise AssertionError("unsupported policy must refuse before PDF backend work")

    monkeypatch.setattr(module, "extract_pages_text_from_bytes", unexpected)
    with pytest.raises(BorradorParseError, match="no Modelo 100 observed-value extractor"):
        parse_borrador(b"unused", año_override=2026)
    with pytest.raises(BorradorParseError, match="requires a registry extraction profile"):
        parse_borrador(b"unused", parse_mode=BorradorParseMode.REGISTRY_PROFILE)
