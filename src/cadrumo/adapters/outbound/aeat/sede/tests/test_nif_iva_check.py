"""Offline contract tests for the AEAT NIF-IVA sede driver.

Exercises the parts of the driver that are implementable without live
browser access: the ``planned_operations`` enumeration, empty-input
rejection, the ``Pydantic`` observation/result models, and the
the canonical ``extract_marker_verdict`` parser with NIF-IVA markers.

Live navigation tests live behind ``@pytest.mark.aeat_live`` and require
``CADRUMO_LIVE_TESTS_ENABLED=1`` plus a working AEAT browser session.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest
from pydantic import AnyUrl, ValidationError

from ......core.config import Settings
from ......domain.calculations.registry.errors import RegistryValidationError
from ......domain.calculations.registry.remote_state_guard import RemoteOperation, assert_remote_operation_allowed
from ......tests.aeat_literal_fixtures import (
    AEAT_NON_HOST_AUTHORITY_CANARIES,
    CENSAL_WRITE_SURFACE_PATH_CANARIES,
    PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE,
    aeat_url,
)
from .._adapter_utils import extract_marker_verdict, is_aeat_auth_gate_redirect
from ..errors import SedeNavigationError
from ..nif_iva_check import (
    _POSITIVE_MARKERS,
    DEFAULT_NIF_IVA_TIMEOUT_MS,
    READ_GUARD_POLICY,
    NifIvaCheckResult,
    NifIvaCheckSedeDriver,
    SedeNifIvaCheckObservation,
    _assert_query_browser_action,
    assert_nif_iva_read_landing,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_AEAT = Settings.external_constants().aeat
_NIF_IVA_ENTRY_URL = f"{_AEAT.domains.sede}{_AEAT.help_pages.nif_iva_landing}"
_AUTH_GATE_4033_URL = f"{_AEAT.domains.sede}{_AEAT.sede_paths.auth_gate_4033}"


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
    observation = SedeNifIvaCheckObservation(
        nif="DE111222333",
        verdict="valid",
        raw_evidence_locator=_AEAT.oracles.nif_iva_verification,
    )
    rebuilt = SedeNifIvaCheckObservation.model_validate(observation.model_dump())
    assert rebuilt == observation


def test_observation_model_rejects_unknown_verdict() -> None:
    with pytest.raises(ValidationError, match=r"verdict|Input should be"):
        SedeNifIvaCheckObservation.model_validate({"nif": "DE111", "verdict": "maybe"})


def test_observation_model_rejects_empty_nif() -> None:
    with pytest.raises(ValidationError, match=r"nif|at least 1 character"):
        SedeNifIvaCheckObservation(nif="", verdict="valid")


def test_observation_model_is_frozen() -> None:
    observation = SedeNifIvaCheckObservation(nif="DE111", verdict="valid")
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        observation.nif = "FR222"


def test_result_model_defaults_to_empty_observations() -> None:
    result = NifIvaCheckResult()
    assert result.observations == ()


def test_marker_verdict_parses_valid_response_text() -> None:
    assert (
        extract_marker_verdict("Sí. Operador intracomunitario identificado", positive_markers=_POSITIVE_MARKERS)
        == "valid"
    )
    assert extract_marker_verdict("NIF-IVA válido", positive_markers=_POSITIVE_MARKERS) == "valid"


def test_marker_verdict_parses_invalid_response_text_before_positive_tokens() -> None:
    assert extract_marker_verdict("No. Operador no identificado", positive_markers=_POSITIVE_MARKERS) == "invalid"
    assert extract_marker_verdict("NIF-IVA no válido", positive_markers=_POSITIVE_MARKERS) == "invalid"


def test_marker_verdict_returns_unknown_for_unrecognized_response_text() -> None:
    assert extract_marker_verdict("", positive_markers=_POSITIVE_MARKERS) == "unknown"


def test_auth_gate_detector_matches_aeat_4033_redirect() -> None:
    """The detector recognises AEAT's 4033 / 403 error landing URL exactly.

    Verified end-to-end via .tmp/probe_nif_iva_driver.py against live
    AEAT: navigating to the configured NIF-IVA verification servlet without authentication
    lands at this exact URL.
    """

    assert is_aeat_auth_gate_redirect(_AUTH_GATE_4033_URL)
    assert is_aeat_auth_gate_redirect(
        f"{_AUTH_GATE_4033_URL}?from={_AEAT.oracles.nif_iva_auth_locked_descriptor.rsplit(maxsplit=1)[-1]}",
    )


def test_auth_gate_detector_rejects_non_4033_aeat_pages() -> None:
    """Other AEAT error pages and the form servlet itself are not auth-gates."""

    assert not is_aeat_auth_gate_redirect(_AEAT.oracles.nif_iva_verification)
    assert not is_aeat_auth_gate_redirect(
        f"{_AEAT.domains.sede}{_AEAT.sede_paths.auth_gate_4033.replace('4033', '4032')}",
    )
    assert not is_aeat_auth_gate_redirect(_NIF_IVA_ENTRY_URL)


def test_auth_gate_detector_rejects_non_aeat_hosts() -> None:
    """The detector pins to AEAT subdomains; arbitrary URLs containing 'erro4033' do not match."""

    assert not is_aeat_auth_gate_redirect("https://example.com/erro4033.html")
    assert not is_aeat_auth_gate_redirect("")


@pytest.mark.parametrize("authority", AEAT_NON_HOST_AUTHORITY_CANARIES)
def test_auth_gate_detector_rejects_non_host_authorities(authority: str) -> None:
    """A credential or port-shaped authority cannot impersonate the AEAT host."""
    assert not is_aeat_auth_gate_redirect(f"https://{authority}{_AEAT.sede_paths.auth_gate_4033}")


def test_nif_iva_read_guard_admits_sibling_load_balancer_host() -> None:
    """A NIF-IVA verification dispatched to a sibling www{n} host under the AEAT apex is allowed."""
    drifted = f"{_AEAT.domains.www12}{urlsplit(_AEAT.oracles.nif_iva_verification).path}"
    result = assert_remote_operation_allowed(
        READ_GUARD_POLICY,
        RemoteOperation(kind="http", method="GET", url=AnyUrl(drifted)),
    )
    assert result.decision == "allowed"


def test_nif_iva_read_guard_refuses_non_aeat_host() -> None:
    """Widening to the AEAT apex suffix must not admit an off-AEAT host."""
    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        assert_remote_operation_allowed(
            READ_GUARD_POLICY,
            RemoteOperation(kind="http", method="GET", url=AnyUrl("https://attacker.example/read/path")),
        )


class TestNifIvaLandingRefusal:
    """Where AEAT actually served the read, checked after every query.

    The auth-gate detector names ONE known landing and keeps precedence
    for its far better diagnostic. This rule is the complement: it refuses
    every landing nobody enumerated, which is the set an auth-gate
    detector structurally cannot cover. The tests drive the driver's own
    exported rule, not a copy of it.
    """

    def test_the_sede_entry_page_is_admitted(self) -> None:
        assert_nif_iva_read_landing(_NIF_IVA_ENTRY_URL)

    def test_the_form_servlet_is_admitted(self) -> None:
        assert_nif_iva_read_landing(_AEAT.oracles.nif_iva_verification)

    def test_a_sibling_load_balancer_host_serving_the_servlet_is_admitted(self) -> None:
        """Host drift across AEAT's www{n} pool is dispatch, not a write."""
        assert_nif_iva_read_landing(f"{_AEAT.domains.www12}{urlsplit(_AEAT.oracles.nif_iva_verification).path}")

    @pytest.mark.parametrize("write_path", CENSAL_WRITE_SURFACE_PATH_CANARIES)
    def test_a_real_aeat_write_surface_is_refused(self, write_path: str) -> None:
        """None of these carries a write verb; the path allow-list is what refuses them."""
        with pytest.raises(SedeNavigationError):
            assert_nif_iva_read_landing(aeat_url("www1", write_path))

    def test_the_procedure_launcher_family_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_nif_iva_read_landing(aeat_url("www1", f"{PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE}G322.shtml"))

    def test_the_auth_gate_landing_is_refused_when_the_detector_is_bypassed(self) -> None:
        """The 4033 gate is the observed landing for this surface.

        The dedicated detector runs first on the navigation path and wins
        on diagnostic quality; this proves the generic rule refuses it
        too, so a query that lands there after a submit -- where the
        detector is not consulted -- is still refused.
        """
        with pytest.raises(SedeNavigationError):
            assert_nif_iva_read_landing(_AUTH_GATE_4033_URL)

    def test_an_unreadable_landing_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_nif_iva_read_landing("")
