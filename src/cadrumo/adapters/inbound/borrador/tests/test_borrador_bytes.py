"""In-memory parsing uses the established PDF backend and one shared text pass."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from .....domain.calculations.registry.schema_references import TemporalSupportEnvelope
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from .. import parser as module
from ..errors import BorradorParseError
from ..parser import parse_borrador
from ..schema import ArtefactKind, BorradorParseMode
from .test_modelo_100_summary import PRINTED_EXERCISE, modelo_100_summary_profile, render_borrador_pdf_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _published_support() -> TemporalSupportEnvelope:
    support = published_supported_filing_years()
    assert support is not None
    return support


@pytest.mark.parametrize("kind", ["BORRADOR", "PREDECLARACION", "DECLARACION"])
def test_bytes_parser_matches_canonical_path_values_profile_and_digest(tmp_path: Path, kind: str) -> None:
    payload = render_borrador_pdf_bytes(artefact_kind=kind, csv="MNOP4321QRST8765" if kind == "DECLARACION" else None)
    path = tmp_path / "synthetic.pdf"
    path.write_bytes(payload)
    profile = modelo_100_summary_profile()
    expected = parse_borrador(
        path,
        filing_year=PRINTED_EXERCISE,
        supported_filing_years=_published_support(),
        extraction_profile=profile,
        parse_mode=BorradorParseMode.REGISTRY_PROFILE,
    )
    actual = parse_borrador(
        payload,
        filing_year=PRINTED_EXERCISE,
        supported_filing_years=_published_support(),
        extraction_profile=profile,
        parse_mode=BorradorParseMode.REGISTRY_PROFILE,
    )
    assert actual.model_dump(exclude={"parsed_at"}) == expected.model_dump(exclude={"parsed_at"})
    assert actual.source_pdf_sha256 == sha256(payload).hexdigest()
    assert actual.artefact_kind.value == kind


def test_bytes_detection_and_extraction_share_exactly_one_real_backend_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = render_borrador_pdf_bytes()
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
    result = parse_borrador(payload, filing_year=PRINTED_EXERCISE, supported_filing_years=_published_support())
    assert calls == 1 and result.artefact_kind is ArtefactKind.BORRADOR
    assert result.values and result.source_pdf_sha256 == sha256(payload).hexdigest()


def test_every_year_the_published_envelope_declares_reads_without_rewriting_the_printed_year() -> None:
    support = _published_support()
    for year in support.years:
        result = parse_borrador(render_borrador_pdf_bytes(), filing_year=year, supported_filing_years=support)
        assert result.ejercicio == str(PRINTED_EXERCISE)


def test_a_year_past_the_authored_horizon_stays_admitted_while_no_ceiling_is_declared() -> None:
    support = _published_support()
    assert support.hard_ceiling is None
    result = parse_borrador(
        render_borrador_pdf_bytes(), filing_year=support.horizon + 1, supported_filing_years=support
    )
    assert result.ejercicio == str(PRINTED_EXERCISE)


def _refuses_before_pdf_work(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(
        pdf_bytes: bytes,
        *,
        error_class: type[Exception],
        pdf_label: str,
        source_label: str,
    ) -> tuple[str, ...]:
        raise AssertionError("unsupported policy must refuse before PDF backend work")

    monkeypatch.setattr(module, "extract_pages_text_from_bytes", unexpected)


def test_a_year_below_the_floor_refuses_before_pdf_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuses_before_pdf_work(monkeypatch)
    support = _published_support()
    with pytest.raises(BorradorParseError, match="outside the supported filing years"):
        parse_borrador(b"unused", filing_year=support.floor - 1, supported_filing_years=support)


def test_a_year_above_a_declared_ceiling_refuses_before_pdf_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuses_before_pdf_work(monkeypatch)
    envelope = filing_year_envelope()
    support = TemporalSupportEnvelope(floor=envelope.floor, horizon=envelope.horizon, hard_ceiling=envelope.horizon)
    with pytest.raises(BorradorParseError, match="outside the supported filing years"):
        parse_borrador(b"unused", filing_year=envelope.horizon + 1, supported_filing_years=support)


def test_a_missing_registry_profile_refuses_before_pdf_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuses_before_pdf_work(monkeypatch)
    support = _published_support()
    with pytest.raises(BorradorParseError, match="requires a registry extraction profile"):
        parse_borrador(
            b"unused",
            filing_year=support.floor,
            supported_filing_years=support,
            parse_mode=BorradorParseMode.REGISTRY_PROFILE,
        )
