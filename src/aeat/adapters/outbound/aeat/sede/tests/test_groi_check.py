"""Offline contract tests for the GROI Spanish-ROI sede driver.

Covers the parts of the driver that are testable without live browser
access: the planned-operations enumeration, empty-input rejection, the
Pydantic observation/result models, and the verdict parser exercised
against text fragments captured live from real AEAT responses on
2026-05-07.

Live navigation tests run under ``@pytest.mark.aeat_live`` and require
``AEAT_LIVE_TESTS_ENABLED=1`` plus a working cl@ve-movil session; they
live in a separate live test module to keep the unit suite fast.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest
from pydantic import ValidationError

from ......core.config import Settings
from ......domain.calculations.registry import GROI_ORACLE_ID, RegistryValidationError
from .._groi_check import (
    DEFAULT_GROI_TIMEOUT_MS,
    GroiNifVerdict,
    GroiResult,
    GroiSedeDriver,
    _assert_query_browser_action,
    extract_verdict_from_response_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_driver_mode_is_live() -> None:
    assert GroiSedeDriver().mode == "live"


def test_oracle_id_matches_registry_namespace() -> None:
    """The oracle id is kebab-case and identifies the GROI Spanish-ROI surface."""

    assert GROI_ORACLE_ID == "aeat-groi-spanish-roi-checker"


def test_url_pins_to_aeat_www2_groi_servlet() -> None:
    """URL captured live; pinned so a future drift forces re-verification."""

    constants = Settings.external_constants().aeat
    configured = urlsplit(constants.oracles.groi_check)
    assert configured.scheme == "https"
    assert configured.netloc == urlsplit(constants.domains.www2).netloc
    assert configured.path


def test_default_timeout_is_thirty_seconds() -> None:
    assert DEFAULT_GROI_TIMEOUT_MS == 30_000


def test_planned_operations_lists_form_open_per_nif_discard() -> None:
    driver = GroiSedeDriver()

    operations = driver.planned_operations(
        b"",
        expected={"A28015865": "valid", "B12345678": "invalid"},
    )

    # Four steps: form GET, open-form, two per-NIF checks (sorted), discard.
    assert len(operations) == 5
    assert operations[0].kind == "http"
    assert operations[0].method == "GET"
    assert str(operations[0].url) == Settings.external_constants().aeat.oracles.groi_check
    assert operations[1].kind == "browser_action"
    assert operations[1].action == "open-groi-form"
    assert operations[2].kind == "browser_action"
    assert operations[2].action == "check-nif-A28015865"
    assert operations[3].kind == "browser_action"
    assert operations[3].action == "check-nif-B12345678"
    assert operations[4].kind == "browser_action"
    assert operations[4].action == "discard-session"


def test_planned_operations_rejects_empty_expected() -> None:
    driver = GroiSedeDriver()

    with pytest.raises(RegistryValidationError, match="at least one expected NIF"):
        driver.planned_operations(b"", expected={})


def test_direct_driver_query_guard_rejects_unclassified_browser_action() -> None:
    _assert_query_browser_action("open-groi-form")
    _assert_query_browser_action("check-nif-A28015865")
    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        _assert_query_browser_action("new-unreviewed-groi-action")


def test_observation_model_round_trips_through_strict_frozen_pydantic() -> None:
    observation = GroiNifVerdict(
        nif="A28015865",
        verdict="valid",
        raw_evidence_locator=Settings.external_constants().aeat.oracles.groi_check,
    )
    rebuilt = GroiNifVerdict.model_validate(observation.model_dump())
    assert rebuilt == observation


def test_observation_model_rejects_unknown_verdict() -> None:
    with pytest.raises(ValidationError, match=r"verdict|Input should be"):
        GroiNifVerdict.model_validate({"nif": "A28015865", "verdict": "registered"})


def test_observation_model_rejects_empty_nif() -> None:
    with pytest.raises(ValidationError, match=r"nif|at least 1 character"):
        GroiNifVerdict(nif="", verdict="valid")


def test_observation_model_is_frozen() -> None:
    observation = GroiNifVerdict(nif="A28015865", verdict="valid")
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        observation.nif = "B12345678"


def test_result_model_defaults_to_empty_observations() -> None:
    assert GroiResult().observations == ()


# ---------------------------------------------------------------------------
# Verdict parser fixtures derived from live AEAT response samples captured
# 2026-05-07 (.tmp/nif_iva_capture/groi_response_A28015865.html and
# groi_response_B00000001.html). The marker text is what AEAT produced live;
# the parser is the unit under test, the response text is the authority.
# ---------------------------------------------------------------------------


def test_verdict_parser_recognises_valid_response_for_registered_operator() -> None:
    """Real AEAT response for A28015865 (Telefónica, ROI-registered)."""

    body_text = (
        "La Agencia Tributaria certifica que: "
        "A FECHA 07-05-2026 13:10:51 CONSTA UN OPERADOR INTRACOMUNITARIO EN ESPAÑA "
        "CON EL NÚMERO DE IVA ESA28015865"
    )
    assert extract_verdict_from_response_text(body_text) == "valid"


def test_verdict_parser_recognises_invalid_response_for_malformed_input() -> None:
    """Real AEAT response for B00000001 (syntactically invalid Spanish NIF)."""

    body_text = "Consulta Operadores IVA intracomunitarios españoles El campo Nif no es un NIF válido. (Ir a error)"
    assert extract_verdict_from_response_text(body_text) == "invalid"


def test_verdict_parser_recognises_no_consta_response() -> None:
    """AEAT phrasing for valid-format but unregistered NIF: 'NO CONSTA'."""

    body_text = "A FECHA 07-05-2026 NO CONSTA OPERADOR INTRACOMUNITARIO CON EL NÚMERO DE IVA ESB99999999"
    assert extract_verdict_from_response_text(body_text) == "invalid"


def test_verdict_parser_returns_unknown_for_empty_body() -> None:
    assert extract_verdict_from_response_text("") == "unknown"


def test_verdict_parser_returns_unknown_for_unrecognised_content() -> None:
    """Body without any verdict marker yields 'unknown' rather than guessing."""

    assert extract_verdict_from_response_text("Página de ayuda") == "unknown"


def test_verdict_parser_negative_marker_wins_over_positive_token() -> None:
    """``no consta`` must NOT collapse to ``valid`` because of a generic ``operador`` token."""

    body_text = "A FECHA 07-05-2026 NO CONSTA OPERADOR INTRACOMUNITARIO con esos datos"
    assert extract_verdict_from_response_text(body_text) == "invalid"


# ---------------------------------------------------------------------------
# Parametrised regression suite over committed live-AEAT response samples.
# Each fixture file under corpus/aeat_official/groi_response_samples/ encodes
# the expected verdict in its filename prefix (`valid_`, `invalid_`, or
# `unknown_`). The fixture text is verbatim-captured from real AEAT — when
# AEAT changes the response phrasing, this suite breaks loudly.
# ---------------------------------------------------------------------------

from ......core.resources import bundled_path

_GROI_RESPONSE_SAMPLES_DIR = bundled_path("corpus", "aeat_official", "groi_response_samples")


def _discover_groi_response_samples() -> list[tuple[str, str]]:
    """Yield (expected_verdict, fixture_path_str) for every .txt sample on disk."""

    samples: list[tuple[str, str]] = []
    if not _GROI_RESPONSE_SAMPLES_DIR.is_dir():
        return samples
    for path in sorted(_GROI_RESPONSE_SAMPLES_DIR.glob("*.txt")):
        prefix = path.stem.split("_", 1)[0]
        if prefix not in {"valid", "invalid", "unknown"}:
            continue
        samples.append((prefix, str(path)))
    return samples


@pytest.mark.parametrize(("expected_verdict", "fixture_path"), _discover_groi_response_samples())
def test_groi_response_samples_parse_to_expected_verdict(expected_verdict: str, fixture_path: str) -> None:
    """Verbatim live-AEAT responses parse to the verdict their filename declares."""

    from pathlib import Path

    body_text = Path(fixture_path).read_text(encoding="utf-8")
    assert extract_verdict_from_response_text(body_text) == expected_verdict
