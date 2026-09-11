"""Offline contract tests for the GROI Spanish-ROI sede driver.

Covers the parts of the driver that are testable without live browser
access: the planned-operations enumeration, empty-input rejection, the
Pydantic observation/result models, and the verdict parser exercised
against text fragments captured live from real AEAT responses on
2026-05-07.

Live navigation tests run under ``@pytest.mark.aeat_live`` and require
``CADRUMO_LIVE_TESTS_ENABLED=1`` plus a working cl@ve-movil session; they
live in a separate live test module to keep the unit suite fast.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import pytest
from pydantic import AnyUrl, ValidationError

from ......core.config import Settings
from ......domain.calculations.registry.errors import RegistryValidationError
from ......domain.calculations.registry.remote_state_guard import RemoteOperation, assert_remote_operation_allowed
from ......tests.aeat_literal_fixtures import (
    CENSAL_WRITE_SURFACE_PATH_CANARIES,
    PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE,
    aeat_url,
    configured_path,
)
from .._adapter_utils import extract_marker_verdict
from ..errors import SedeNavigationError
from ..groi_check import (
    _POSITIVE_MARKERS,
    DEFAULT_GROI_TIMEOUT_MS,
    READ_GUARD_POLICY,
    GroiNifVerdict,
    GroiResult,
    GroiSedeDriver,
    _assert_query_browser_action,
    assert_groi_read_landing,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_driver_mode_is_live() -> None:
    assert GroiSedeDriver().mode == "live"


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
    assert extract_marker_verdict(body_text, positive_markers=_POSITIVE_MARKERS) == "valid"


def test_verdict_parser_recognises_invalid_response_for_malformed_input() -> None:
    """Real AEAT response for B00000001 (syntactically invalid Spanish NIF)."""

    body_text = "Consulta Operadores IVA intracomunitarios españoles El campo Nif no es un NIF válido. (Ir a error)"
    assert extract_marker_verdict(body_text, positive_markers=_POSITIVE_MARKERS) == "invalid"


def test_verdict_parser_recognises_no_consta_response() -> None:
    """AEAT phrasing for valid-format but unregistered NIF: 'NO CONSTA'.

    NOT captured evidence. This body text is RECONSTRUCTED from the
    ``valid`` capture's sentence frame, not observed live -- no committed
    sample exercises the unregistered case. It is a declared coverage gap
    (see PROVENANCE.md 'Known coverage gaps'); closing it needs an
    authenticated re-probe. Treat this as a parser smoke test, not as
    grounding for AEAT's actual unregistered-NIF phrasing.
    """

    body_text = "A FECHA 07-05-2026 NO CONSTA OPERADOR INTRACOMUNITARIO CON EL NÚMERO DE IVA ESB99999999"
    assert extract_marker_verdict(body_text, positive_markers=_POSITIVE_MARKERS) == "invalid"


def test_verdict_parser_returns_unknown_for_empty_body() -> None:
    assert extract_marker_verdict("", positive_markers=_POSITIVE_MARKERS) == "unknown"


def test_verdict_parser_returns_unknown_for_unrecognised_content() -> None:
    """Body without any verdict marker yields 'unknown' rather than guessing."""

    assert extract_marker_verdict("Página de ayuda", positive_markers=_POSITIVE_MARKERS) == "unknown"


def test_verdict_parser_negative_marker_wins_over_positive_token() -> None:
    """``no consta`` must NOT collapse to ``valid`` because of a generic ``operador`` token."""

    body_text = "A FECHA 07-05-2026 NO CONSTA OPERADOR INTRACOMUNITARIO con esos datos"
    assert extract_marker_verdict(body_text, positive_markers=_POSITIVE_MARKERS) == "invalid"


# ---------------------------------------------------------------------------
# Parametrised regression suite over committed live-AEAT response samples.
# Each fixture file under corpus/aeat_official/groi_response_samples/ encodes
# the expected verdict in its filename prefix (`valid_`, `invalid_`, or
# `unknown_`). The fixture text is verbatim-captured from real AEAT — when
# AEAT changes the response phrasing, this suite breaks loudly.
# ---------------------------------------------------------------------------

from ......core.directory_scan import scan_directory
from ......core.resources.bundled_data import bundled_path

_GROI_RESPONSE_SAMPLES_DIR = bundled_path("corpus", "aeat_official", "groi_response_samples")


_GROI_SAMPLE_VERDICT_PREFIXES = frozenset({"valid", "invalid", "unknown"})


def _discover_groi_response_samples() -> list[tuple[str, str]]:
    """Yield (expected_verdict, fixture_path_str) for every .txt sample on disk.

    Raises rather than returning an empty or filtered list. Collection-time
    silence is the failure mode this corpus exists to prevent: a missing
    directory or a misnamed file would otherwise parametrise to zero cases,
    and the suite would report green while asserting nothing about the
    parser that gates live modelo 349 ROI checks.
    """

    if not _GROI_RESPONSE_SAMPLES_DIR.is_dir():
        raise AssertionError(
            f"GROI response-sample corpus missing at {_GROI_RESPONSE_SAMPLES_DIR}; "
            "the verdict parser has no external authority without it",
        )

    samples: list[tuple[str, str]] = []
    misnamed: list[str] = []
    for path in scan_directory(_GROI_RESPONSE_SAMPLES_DIR, pattern="*.txt"):
        prefix = path.stem.split("_", 1)[0]
        if prefix not in _GROI_SAMPLE_VERDICT_PREFIXES:
            misnamed.append(path.name)
            continue
        samples.append((prefix, str(path)))

    if misnamed:
        raise AssertionError(
            f"GROI response samples violate the '{{verdict}}_{{descriptor}}.txt' naming contract: "
            f"{sorted(misnamed)!r}; expected a prefix in {sorted(_GROI_SAMPLE_VERDICT_PREFIXES)!r}. "
            "A misnamed sample is never asserted against -- rename it or remove it.",
        )
    if not samples:
        raise AssertionError(
            f"no GROI response samples discovered under {_GROI_RESPONSE_SAMPLES_DIR}; "
            "the parametrised parser regression would silently assert nothing",
        )
    return samples


@pytest.mark.parametrize(("expected_verdict", "fixture_path"), _discover_groi_response_samples())
def test_groi_response_samples_parse_to_expected_verdict(expected_verdict: str, fixture_path: str) -> None:
    """Verbatim live-AEAT responses parse to the verdict their filename declares."""

    body_text = Path(fixture_path).read_text(encoding="utf-8")
    assert extract_marker_verdict(body_text, positive_markers=_POSITIVE_MARKERS) == expected_verdict


def test_groi_response_samples_carry_provenance_entries() -> None:
    """Every committed sample MUST be documented in PROVENANCE.md.

    A sample added without a provenance row loses its capture date, source
    endpoint, and hash -- the audit trail that makes it evidence rather than
    an anonymous fixture. Mirrors the corpus-wide provenance gate at
    ``src/cadrumo/_data/corpus/tests/test_corpus_provenance.py``, which is
    scoped to the instructions corpus and does not reach this directory.
    """

    provenance = _GROI_RESPONSE_SAMPLES_DIR / "PROVENANCE.md"
    assert provenance.is_file(), f"PROVENANCE.md missing at {provenance}"

    body = provenance.read_text(encoding="utf-8")
    assert "## Source" in body, "PROVENANCE.md missing '## Source' section"
    assert "## Corpus capture date" in body, "PROVENANCE.md missing corpus capture date"
    assert "## Known coverage gaps" in body, (
        "PROVENANCE.md missing the coverage-gap declaration; uncaptured verdict "
        "classes must stay visible rather than reading as complete coverage"
    )

    undocumented = [
        name for _, path_str in _discover_groi_response_samples() if (name := Path(path_str).name) not in body
    ]
    assert not undocumented, (
        f"GROI samples not listed in PROVENANCE.md: {sorted(undocumented)!r}; "
        "add a row to the Documents table before landing"
    )


def test_groi_read_guard_admits_sibling_load_balancer_host() -> None:
    """A GROI check dispatched to a sibling www{n} host under the AEAT apex is allowed."""
    aeat = Settings.external_constants().aeat
    drifted = f"{aeat.domains.www12}{urlsplit(aeat.oracles.groi_check).path}"
    result = assert_remote_operation_allowed(
        READ_GUARD_POLICY,
        RemoteOperation(kind="http", method="GET", url=AnyUrl(drifted)),
    )
    assert result.decision == "allowed"


def test_groi_read_guard_refuses_non_aeat_host() -> None:
    """Widening to the AEAT apex suffix must not admit an off-AEAT host."""
    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        assert_remote_operation_allowed(
            READ_GUARD_POLICY,
            RemoteOperation(kind="http", method="GET", url=AnyUrl("https://attacker.example/read/path")),
        )


class TestGroiLandingRefusal:
    """Where AEAT actually served the read, checked after every submit.

    The GROI driver fills a NIF and clicks a submit control. That click
    issues a browser form POST which reaches neither the first-party HTTP
    guard nor the package's forbidden-verb source scan, so this landing
    rule is the only wall between the click and whatever AEAT served. The
    tests drive the driver's own exported rule, not a copy of it.
    """

    def test_the_consult_servlet_is_admitted(self) -> None:
        assert_groi_read_landing(Settings.external_constants().aeat.oracles.groi_check)

    def test_a_sibling_load_balancer_host_serving_the_servlet_is_admitted(self) -> None:
        """Host drift across AEAT's www{n} pool is dispatch, not a write."""
        aeat = Settings.external_constants().aeat
        assert_groi_read_landing(f"{aeat.domains.www12}{urlsplit(aeat.oracles.groi_check).path}")

    @pytest.mark.parametrize("write_path", CENSAL_WRITE_SURFACE_PATH_CANARIES)
    def test_a_real_aeat_write_surface_is_refused(self, write_path: str) -> None:
        """None of these carries a write verb; the path allow-list is what refuses them."""
        with pytest.raises(SedeNavigationError):
            assert_groi_read_landing(aeat_url("www2", write_path))

    def test_the_procedure_launcher_family_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_groi_read_landing(aeat_url("www2", f"{PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE}G322.shtml"))

    def test_the_auth_gate_landing_is_refused(self) -> None:
        """The observed failure mode for this surface: AEAT answers with its 4033 gate.

        Before this rule the driver scraped that page and classified its
        text, so an auth refusal could only ever surface as a verdict.
        """
        with pytest.raises(SedeNavigationError):
            assert_groi_read_landing(aeat_url("www2", configured_path("sede_paths", "auth_gate_4033")))

    def test_an_unreadable_landing_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_groi_read_landing("")
