"""Mission-critical safety tests for the Renta WEB Open driver.

These tests are the third defense layer (the runtime guard +
page-level safety net are layers 1 and 2). They enforce at the SOURCE
level that the driver code can never bypass the click-time safety
check, so an inadvertent refactor that introduces a raw
``locator.click()`` lands as a CI failure rather than a real filing.

The tests run as plain unit tests (no live AEAT access) — they read the
driver source files and assert structural invariants.
"""

from __future__ import annotations

import re

import pytest

from ......core.paths import PROJECT_ROOT
from ......domain.calculations.registry import AEAT_WRITE_FORBIDDEN_VERB_TOKENS
from .._renta_web_open_safety import (
    ALLOWED_CLICK_OVERRIDES,
    FORBIDDEN_CLICK_TOKENS,
    FORBIDDEN_URL_FRAGMENTS,
    _matches_forbidden_token,
    _normalise,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_click_tokens_include_canonical_write_verb_tokens() -> None:
    """The click-time denylist MUST cover every canonical write-verb token.

    Both the URL/method guard in ``_remote_state_guard._FORBIDDEN_TOKENS``
    and this click-time denylist derive from
    ``AEAT_WRITE_FORBIDDEN_VERB_TOKENS``. If a future refactor accidentally
    drops the canonical core from the click set, the safety net silently
    weakens — this regression test breaks the build first.
    """

    missing = AEAT_WRITE_FORBIDDEN_VERB_TOKENS - FORBIDDEN_CLICK_TOKENS
    assert not missing, f"FORBIDDEN_CLICK_TOKENS is missing canonical write verbs: {sorted(missing)}"


_SEDE_DIR = PROJECT_ROOT / "src" / "aeat" / "adapters" / "outbound" / "aeat" / "sede"
_DRIVER_FILE = _SEDE_DIR / "_renta_web_open.py"


def test_forbidden_token_set_carries_every_high_risk_action() -> None:
    """The denylist must include every Spanish-language word for filing /
    signing / payment / submission AEAT might surface in a button label."""
    required = {
        "presentar",
        "firmar",
        "enviar",
        "pagar",
        "guardar",
        "transmitir",
        "tgvi",
        "anular",
        "modificar",
        # Pre-presentation validation surface — denied as defense-in-depth
        # (the read-only driver never needs to click Validar).
        "validar",
    }
    for token in required:
        assert token in FORBIDDEN_CLICK_TOKENS, f"required forbidden token {token!r} missing"


def test_validar_button_label_is_blocked_by_safety_guard() -> None:
    """The 'Validar' button surfaces on the live Resumen toolbar (button
    [12] in the latest button inventory). The driver never needs to click
    it — the registry's typed bindings + parity oracle do all validation.
    Locking it as forbidden prevents accidental clicks from triggering
    AEAT-side validation state changes."""
    matched_validar = _matches_forbidden_token(_normalise("Validar"))
    matched_validacion = _matches_forbidden_token(_normalise("Validación"))
    matched_loud = _matches_forbidden_token(_normalise("VALIDAR DECLARACIÓN"))
    # Pin both the match-vs-None contract AND that the matched token's
    # normalised form is the prefix the input shares with the forbidden
    # set — a regression that returned a non-matching token would slip
    # past `is not None` alone.
    assert matched_validar is not None and _normalise(matched_validar) in _normalise("Validar")
    assert matched_validacion is not None and _normalise(matched_validacion) in _normalise("Validación")
    assert matched_loud is not None and _normalise(matched_loud) in _normalise("VALIDAR DECLARACIÓN")


def test_normalise_folds_accents_and_lowercases() -> None:
    assert _normalise("Presentación") == "presentacion"
    assert _normalise("FIRMAR") == "firmar"
    assert _normalise("  Pagar  ") == "pagar"


def test_matches_forbidden_token_catches_substring_in_button_label() -> None:
    """Real button labels often combine words: 'Presentar declaración',
    'Firmar y enviar', 'Pagar con tarjeta'. The matcher must catch these."""
    assert _matches_forbidden_token(_normalise("Presentar declaración")) is not None
    assert _matches_forbidden_token(_normalise("Firmar y enviar")) is not None
    assert _matches_forbidden_token(_normalise("Pagar con tarjeta")) is not None
    assert _matches_forbidden_token(_normalise("Confirmar presentación")) is not None
    # Read-only labels stay safe
    assert _matches_forbidden_token(_normalise("Continuar con la declaración")) is None
    assert _matches_forbidden_token(_normalise("Apartados declaración")) is None
    assert _matches_forbidden_token(_normalise("Buscar casilla")) is None
    # Validar moved to the denylist as defense-in-depth — see
    # ``test_validar_button_label_is_blocked_by_safety_guard``.
    assert _matches_forbidden_token(_normalise("Ver datos fiscales")) is None
    assert _matches_forbidden_token(_normalise("Vista previa")) is None
    assert _matches_forbidden_token(_normalise("Notas")) is None
    assert _matches_forbidden_token(_normalise("Aceptar")) is None  # identification only


def test_allowed_click_overrides_is_empty_by_default() -> None:
    """No overrides should ship by default. Adding one requires audit."""
    assert frozenset() == ALLOWED_CLICK_OVERRIDES


def test_forbidden_url_fragments_cover_filing_endpoints() -> None:
    required = {"/presentar", "/firmar", "/pagar", "/sign", "/submit"}
    for fragment in required:
        assert fragment in FORBIDDEN_URL_FRAGMENTS


def test_driver_routes_every_click_through_assert_click_target_safe() -> None:
    """The driver source must never call ``locator.click()`` directly.

    Every click is required to flow through ``_click_expected`` (which
    delegates to ``assert_click_target_safe`` before dispatching). This
    test scans the driver file for raw click calls — the only allowed
    occurrence is inside ``_click_expected`` itself (the canonical click
    site).
    """
    text = _DRIVER_FILE.read_text(encoding="utf-8")
    raw_clicks = [m for m in re.finditer(r"\.click\(", text)]
    canonical_click_site = re.search(r"async def _click_expected\b", text)
    assert canonical_click_site is not None, "_click_expected wrapper missing — safety guard cannot enforce"
    # Find the boundaries of _click_expected: everything inside its body
    # is the canonical click site. Other occurrences are forbidden.
    body_start = canonical_click_site.start()
    next_def = re.search(r"\nasync def \w+|\ndef \w+", text[body_start + 10 :])
    body_end = body_start + 10 + (next_def.start() if next_def else len(text))
    # Each raw click must be inside the canonical body window.
    forbidden_sites: list[str] = []
    for m in raw_clicks:
        if not (body_start <= m.start() <= body_end):
            line = text.count("\n", 0, m.start()) + 1
            forbidden_sites.append(f"line {line}: raw .click( at offset {m.start()}")
    assert not forbidden_sites, (
        "raw locator.click() found outside _click_expected — SAFETY VIOLATION:\n  " + "\n  ".join(forbidden_sites)
    )


def test_driver_imports_safety_module() -> None:
    """The driver source must import the safety module — refactors that
    drop the import would silently disable the click-time guard."""
    text = _DRIVER_FILE.read_text(encoding="utf-8")
    assert "from ._renta_web_open_safety import" in text, "driver missing safety-module import — safety guard disabled"
    assert "assert_click_target_safe" in text
    assert "install_page_safety_net" in text


def test_click_expected_calls_assert_click_target_safe_before_click() -> None:
    """Within ``_click_expected``, the safety check must precede the click.

    Even a single inverted call order (click first, check after) defeats
    the guard. This source-level test pins the order.
    """
    text = _DRIVER_FILE.read_text(encoding="utf-8")
    body_start = text.find("async def _click_expected")
    assert body_start >= 0
    next_def = re.search(r"\nasync def \w+|\ndef \w+", text[body_start + 10 :])
    body_end = body_start + 10 + (next_def.start() if next_def else len(text))
    body = text[body_start:body_end]
    safety_pos = body.find("assert_click_target_safe")
    click_pos = body.find(".click(")
    assert 0 <= safety_pos < click_pos, (
        f"_click_expected has the safety check at {safety_pos} and click at "
        f"{click_pos} — safety check must precede click"
    )


def test_install_page_safety_net_is_called_at_session_start() -> None:
    """The safety net must be installed at session creation (after
    ``context.new_page``), before any user-driven interaction."""
    text = _DRIVER_FILE.read_text(encoding="utf-8")
    new_page_pos = text.find("await context.new_page")
    install_pos = text.find("install_page_safety_net(page)")
    first_navigate_pos = text.find("browser_session.navigate(page,")
    assert new_page_pos >= 0 and install_pos >= 0 and first_navigate_pos >= 0
    assert new_page_pos < install_pos < first_navigate_pos, (
        "install_page_safety_net must be called AFTER page creation but "
        "BEFORE the first navigate(); current ordering is unsafe"
    )
