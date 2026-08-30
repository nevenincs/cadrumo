"""Option-set enumeration over the declaraciones register's own comboboxes.

Two fixtures, doing two different jobs. The SYNTHETIC one carries a small
hand-authored option set so the exact-equality assertions are readable and every
awkward case is present on purpose. The REAL bundled capture
(``declaraciones-modelo-100-2022.html``, 174 rendered option texts) is what
proves the classification survives markup nobody authored for it -- a synthetic
fixture written by the same hand as the parser can only confirm the author's own
assumptions.

The real capture earned its place immediately: it offers a modelo ``174`` whose
description is EMPTY, which an earlier pattern requiring a character after the
dash dropped out of the offered set. It also renders BOTH combobox popups into
one DOM snapshot, which is why the two option shapes are classified as disjoint
rather than by assuming only the open popup is present.

What these tests deliberately do NOT cover: the Playwright clicking that opens
each combobox. That needs a live authenticated session, no synthetic fixture can
honestly stand in for it, and no live probe is authorised here. The boundary is
stated rather than papered over: everything from a rendered snapshot through to
the assembled report is covered; the clicks are not.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ......application.auth.session_types import AeatSession, CertificateSessionDetail
from ......core import FiledHistoryDiscoverySignal
from ..declarations import (
    _combobox_option_texts,
    discover_filed_declaration_availability,
    filed_register_ejercicio_options,
    filed_register_modelo_options,
    walk_declarations_register,
)
from ..errors import SedeNavigationError, SedeParseError
from ..schema import FiledDeclarationAvailability, FiledDeclarationAvailabilityReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FIXTURE_ROOT = Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "aeat-sede"
_SYNTHETIC = _FIXTURE_ROOT / "declaraciones-register-comboboxes-synthetic.html"
_REAL_CAPTURE = _FIXTURE_ROOT / "declaraciones-modelo-100-2022.html"


def _synthetic_html() -> str:
    return _SYNTHETIC.read_text(encoding="utf-8")


def _real_html() -> str:
    return _REAL_CAPTURE.read_text(encoding="utf-8")


def test_modelo_options_match_the_hand_authored_fixture_exactly() -> None:
    assert filed_register_modelo_options(_synthetic_html()) == (
        "ATF",
        "DT2",
        "14A",
        "100",
        "174",
        "303",
    )


def test_ejercicio_options_match_the_hand_authored_fixture_exactly() -> None:
    assert filed_register_ejercicio_options(_synthetic_html()) == (2026, 2025, 2024)


def test_a_modelo_with_an_empty_description_is_still_offered() -> None:
    assert "174" in filed_register_modelo_options(_synthetic_html())
    assert "174" in filed_register_modelo_options(_real_html())


def test_the_placeholder_option_is_not_a_modelo() -> None:
    assert "--" not in filed_register_modelo_options(_synthetic_html())
    assert not any(code.startswith("-") for code in filed_register_modelo_options(_real_html()))


def test_an_ejercicio_below_the_supported_range_is_dropped() -> None:
    assert 1999 not in filed_register_ejercicio_options(_synthetic_html())


def test_the_two_option_shapes_stay_disjoint_on_real_markup() -> None:
    html = _real_html()
    modelos = filed_register_modelo_options(html)
    ejercicios = filed_register_ejercicio_options(html)
    assert modelos
    assert ejercicios
    assert not set(modelos) & {str(year) for year in ejercicios}


def test_real_markup_classifies_every_option_but_the_placeholder() -> None:
    html = _real_html()
    texts = _combobox_option_texts(html)
    modelo_shaped = sum(1 for text in texts if text.split("\xa0")[0] in filed_register_modelo_options(html))
    year_shaped = sum(1 for text in texts if text.strip().isdigit() and len(text.strip()) == 4)
    unclassified = len(texts) - modelo_shaped - year_shaped
    # Exactly the "-- Seleccione --" placeholder, once per rendered popup. Gated
    # as a property (every residual text IS the placeholder) rather than as a
    # tally, so a future capture with a third combobox does not need this edited.
    residual = [
        text
        for text in texts
        if text.split("\xa0")[0] not in filed_register_modelo_options(html)
        and not (text.strip().isdigit() and len(text.strip()) == 4)
    ]
    assert unclassified == len(residual)
    assert all("Seleccione" in text for text in residual)


def test_alpha_and_numeric_modelo_codes_both_survive_real_markup() -> None:
    codes = filed_register_modelo_options(_real_html())
    assert any(not code.isdigit() for code in codes)
    assert any(code.isdigit() for code in codes)


def test_an_empty_modelo_option_set_is_refused_rather_than_reported() -> None:
    # The register always offers modelos, so an empty modelo list means the form
    # did not render or AEAT changed the option shape. Reporting it as "nothing
    # offered" would turn a shape change into a silently empty filing history.
    with pytest.raises(SedeParseError, match="no modelo-shaped combobox option"):
        filed_register_modelo_options("<html><body><div>Sin resultados</div></body></html>")


def test_an_empty_ejercicio_option_set_is_a_legitimate_answer() -> None:
    # Unlike the modelo list, the register genuinely offers no ejercicio for a
    # modelo with nothing under it, so this returns empty rather than refusing.
    assert filed_register_ejercicio_options("<html><body><div>Sin resultados</div></body></html>") == ()


def _sessionless() -> AeatSession:
    """The smallest valid session carrying no persisted browser state."""
    authenticated_at = datetime(2026, 8, 7, 9, 0, tzinfo=UTC)
    return AeatSession(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + timedelta(hours=8),
        storage_state_path=None,
        identity_nif="12345678Z",
        provider_detail=CertificateSessionDetail(
            certificate_thumbprint="aabbcc",
            certificate_subject="CN=test",
        ),
    )


def test_availability_discovery_refuses_a_missing_session_exactly_as_capture_does() -> None:
    # Both entry points go through one register bring-up, so an operator who has
    # not authenticated gets the SAME refusal and the same remediation from the
    # new read as from the shipped walk -- not a discovery-specific error nobody
    # has seen before. Asserted on the error type AND the translated message key,
    # because a second bring-up copy would most plausibly diverge on the message.
    session = _sessionless()

    with pytest.raises(SedeNavigationError) as discovery_error:
        asyncio.run(discover_filed_declaration_availability(session))
    with pytest.raises(SedeNavigationError) as capture_error:
        asyncio.run(walk_declarations_register(session, modelo="303", ejercicio=2025))

    assert discovery_error.value.translated_message == capture_error.value.translated_message
    assert discovery_error.value.translated_message
    assert str(discovery_error.value) == str(capture_error.value)


def test_the_assembled_report_pins_the_register_options_provenance() -> None:
    html = _synthetic_html()
    report = FiledDeclarationAvailabilityReport(
        items=tuple(
            FiledDeclarationAvailability(modelo=modelo, ejercicios=filed_register_ejercicio_options(html))
            for modelo in filed_register_modelo_options(html)
        ),
        discovered_at=datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
    )
    assert report.signal is FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS
    assert report.offered_pairs[:4] == (
        ("ATF", 2026),
        ("ATF", 2025),
        ("ATF", 2024),
        ("DT2", 2026),
    )
    assert len(report.offered_pairs) == 6 * 3
