"""Offline contract tests for the AEAT NIF-IVA sede driver.

Exercises the parts of the driver that are implementable without live
browser access: the ``planned_operations`` enumeration, empty-input
rejection, the ``Pydantic`` observation/result models, and the
``extract_verdict_from_response_text`` parser.

Live navigation tests live behind ``@pytest.mark.live_read`` and require
``AEAT_LIVE_TESTS_ENABLED=1`` plus a working AEAT browser session.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aeat.adapters.outbound.aeat.sede._nif_iva_check import (
    DEFAULT_NIF_IVA_TIMEOUT_MS,
    NifIvaCheckObservation,
    NifIvaCheckResult,
    NifIvaCheckSedeDriver,
    _assert_query_browser_action,
    extract_verdict_from_response_text,
    is_aeat_auth_gate_redirect,
)
from aeat.core.config import Settings
from aeat.domain.calculations.registry import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def test_driver_mode_is_live() -> None:
    assert NifIvaCheckSedeDriver().mode == "live"


def test_planned_operations_lists_entry_form_open_per_nif_discard() -> None:
    driver = NifIvaCheckSedeDriver()

    operations = driver.planned_operations(
        b"",
        expected={"FR12345678901": "valid", "DE111222333": "valid"},
    )

    # Six steps: entry GET, form GET, open-form, two per-NIF checks (sorted), discard.
    assert len(operations) == 6
    _ext = Settings.external_constants()
    assert operations[0].kind == "http"
    assert operations[0].method == "GET"
    assert str(operations[0].url) == f"{_ext.aeat.domains.sede}{_ext.aeat.help_pages.nif_iva_landing}"
    assert operations[1].kind == "http"
    assert operations[1].method == "GET"
    assert str(operations[1].url) == _ext.aeat.oracles.nif_iva_verification
    assert operations[2].kind == "browser_action"
    assert operations[2].action == "open-nif-iva-form"
    # Per-NIF checks emitted in sorted order so the operation list is deterministic.
    assert operations[3].kind == "browser_action"
    assert operations[3].action == "check-nif-DE111222333"
    assert operations[4].kind == "browser_action"
    assert operations[4].action == "check-nif-FR12345678901"
    assert operations[5].kind == "browser_action"
    assert operations[5].action == "discard-session"


def test_planned_operations_rejects_empty_expected() -> None:
    driver = NifIvaCheckSedeDriver()

    with pytest.raises(RegistryValidationError, match="at least one expected NIF"):
        driver.planned_operations(b"", expected={})


def test_direct_driver_query_guard_rejects_unclassified_browser_action() -> None:
    _assert_query_browser_action("open-nif-iva-form")
    _assert_query_browser_action("check-nif-DE111222333")
    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        _assert_query_browser_action("new-unreviewed-nif-iva-action")


def test_default_timeout_is_thirty_seconds() -> None:
    """The per-stage timeout governs each navigation + form-fill + scrape stage."""

    assert DEFAULT_NIF_IVA_TIMEOUT_MS == 30_000


def test_observation_model_roundtrips_through_strict_frozen_pydantic() -> None:
    observation = NifIvaCheckObservation(
        nif="DE111222333",
        verdict="valid",
        raw_evidence_locator="https://www1.agenciatributaria.gob.es/wlpl/IXVI-JDIT/ConsultaIntracomunitarios",
    )
    rebuilt = NifIvaCheckObservation.model_validate(observation.model_dump())
    assert rebuilt == observation


def test_observation_model_rejects_unknown_verdict() -> None:
    with pytest.raises(ValidationError, match=r"verdict|Input should be"):
        NifIvaCheckObservation.model_validate({"nif": "DE111", "verdict": "maybe"})


def test_observation_model_rejects_empty_nif() -> None:
    with pytest.raises(ValidationError, match=r"nif|at least 1 character"):
        NifIvaCheckObservation(nif="", verdict="valid")


def test_observation_model_is_frozen() -> None:
    observation = NifIvaCheckObservation(nif="DE111", verdict="valid")
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        setattr(observation, "nif", "FR222")  # noqa: B010 — exercise frozen-model __setattr__


def test_result_model_defaults_to_empty_observations() -> None:
    result = NifIvaCheckResult()
    assert result.observations == ()


def test_extract_verdict_parses_valid_response_text() -> None:
    assert extract_verdict_from_response_text("Sí. Operador intracomunitario identificado") == "valid"
    assert extract_verdict_from_response_text("NIF-IVA válido") == "valid"


def test_extract_verdict_parses_invalid_response_text_before_positive_tokens() -> None:
    assert extract_verdict_from_response_text("No. Operador no identificado") == "invalid"
    assert extract_verdict_from_response_text("NIF-IVA no válido") == "invalid"


def test_extract_verdict_returns_unknown_for_unrecognized_response_text() -> None:
    assert extract_verdict_from_response_text("") == "unknown"


def test_auth_gate_detector_matches_aeat_4033_redirect() -> None:
    """The detector recognises AEAT's 4033 / 403 error landing URL exactly.

    Verified end-to-end via .tmp/probe_nif_iva_driver.py against live
    AEAT: navigating to ConsultaIntracomunitarios without authentication
    lands at this exact URL.
    """

    assert is_aeat_auth_gate_redirect("https://sede.agenciatributaria.gob.es/Sede/errores/erro4033.html")
    assert is_aeat_auth_gate_redirect(
        "https://sede.agenciatributaria.gob.es/Sede/errores/erro4033.html?from=ConsultaIntracomunitarios"
    )


def test_auth_gate_detector_rejects_non_4033_aeat_pages() -> None:
    """Other AEAT error pages and the form servlet itself are not auth-gates."""

    assert not is_aeat_auth_gate_redirect(
        "https://www1.agenciatributaria.gob.es/wlpl/IXVI-JDIT/ConsultaIntracomunitarios"
    )
    assert not is_aeat_auth_gate_redirect("https://sede.agenciatributaria.gob.es/Sede/errores/erro4032.html")
    assert not is_aeat_auth_gate_redirect("https://sede.agenciatributaria.gob.es/Sede/iva.html")


def test_auth_gate_detector_rejects_non_aeat_hosts() -> None:
    """The detector pins to AEAT subdomains; arbitrary URLs containing 'erro4033' do not match."""

    assert not is_aeat_auth_gate_redirect("https://example.com/erro4033.html")
    assert not is_aeat_auth_gate_redirect("")
