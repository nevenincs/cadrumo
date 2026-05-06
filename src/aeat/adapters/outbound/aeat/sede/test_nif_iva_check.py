"""Offline contract tests for the AEAT NIF-IVA sede driver.

Exercises the parts of the driver that are implementable without live
browser access: the ``planned_operations`` enumeration, empty-input
rejection, the ``Pydantic`` observation/result models, and the
``extract_verdict_from_response_text`` fail-safe.

Live navigation tests live behind ``@pytest.mark.live_read`` and require
``AEAT_LIVE_TESTS_ENABLED=1`` plus a working AEAT browser session; they
will fail loudly until the form-specific Playwright selectors are
captured (the ``_open_nif_iva_form`` and ``_check_single_nif`` stubs in
the driver raise ``NotImplementedError``).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aeat.adapters.outbound.aeat.sede._nif_iva_check import (
    AEAT_NIF_IVA_ENTRY_URL,
    AEAT_NIF_IVA_VERIFICATION_URL,
    DEFAULT_NIF_IVA_TIMEOUT_MS,
    NifIvaCheckObservation,
    NifIvaCheckResult,
    NifIvaCheckSedeDriver,
    extract_verdict_from_response_text,
)
from aeat.domain.calculations.registry._errors import RegistryValidationError

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
    assert operations[0].kind == "http"
    assert operations[0].method == "GET"
    assert operations[0].url == AEAT_NIF_IVA_ENTRY_URL
    assert operations[1].kind == "http"
    assert operations[1].method == "GET"
    assert operations[1].url == AEAT_NIF_IVA_VERIFICATION_URL
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
    with pytest.raises(ValidationError):
        NifIvaCheckObservation.model_validate({"nif": "DE111", "verdict": "maybe"})


def test_observation_model_rejects_empty_nif() -> None:
    with pytest.raises(ValidationError):
        NifIvaCheckObservation(nif="", verdict="valid")


def test_observation_model_is_frozen() -> None:
    observation = NifIvaCheckObservation(nif="DE111", verdict="valid")
    with pytest.raises(ValidationError):
        observation.nif = "FR222"  # type: ignore[misc]


def test_result_model_defaults_to_empty_observations() -> None:
    result = NifIvaCheckResult()
    assert result.observations == ()


def test_extract_verdict_returns_unknown_until_response_shape_captured() -> None:
    """The fail-safe stub returns 'unknown' for every input until live response samples land."""

    assert extract_verdict_from_response_text("Sí. Operador identificado") == "unknown"
    assert extract_verdict_from_response_text("No. Operador no identificado") == "unknown"
    assert extract_verdict_from_response_text("") == "unknown"
