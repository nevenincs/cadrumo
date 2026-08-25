"""A salvaged Cl@ve session records only a landing a later probe can reuse.

Salvaging an authenticated context out of a failed post-authentication
navigation is only worth anything if the resulting session survives the
reuse probe. The probe target is the session's own recorded landing URL,
so what the salvage writes there decides whether the saved session has a
route back in at all.

A fresh login that fails is still somewhere in the Cl@ve flow, and the
provider's authenticated-landing predicate refuses every Cl@ve marker.
Recording the failing page would therefore persist a session whose probe
target is refused before the navigation runs, however live its cookies
are.

These cases drive the real provider against the real external-constants
surface. Nothing is stubbed: the URLs are assembled from the shipped
AEAT domain and marker constants, so a marker rename moves the fixtures
and the assertions together.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ......core.config import Settings
from ..clave_movil import ClaveMovilAuthProvider
from ._clave_movil_support import _CLAVE_SURFACE, _DOMAINS, _aeat_url, _settings_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SEDE_PATHS = Settings.external_constants().aeat.sede_paths
_TARGET_PATH = _SEDE_PATHS.expedientes_resumen
_COMPLETED_LANDING = _aeat_url(_DOMAINS.www6, _TARGET_PATH)


def _provider(tmp_path: Path) -> ClaveMovilAuthProvider:
    """Build the real provider; no browser is reached by the decision under test."""
    return ClaveMovilAuthProvider(_settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z"))


def test_a_completed_authenticated_landing_is_recorded(tmp_path: Path) -> None:
    """Anti-tautology proof: the decision is not a constant refusal.

    Every other case below asserts a refusal, so a helper that returned
    ``None`` unconditionally would satisfy all of them while destroying
    the one landing worth keeping.
    """

    recorded = _provider(tmp_path)._salvageable_landing_url(_COMPLETED_LANDING, target_path=_TARGET_PATH)

    assert recorded == _COMPLETED_LANDING


@pytest.mark.parametrize(
    "clave_flow_url",
    [
        _CLAVE_SURFACE.selector_access_url_template.format(target=_TARGET_PATH),
        _aeat_url(_DOMAINS.www6, _CLAVE_SURFACE.dialogo_representacion_path),
        _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.obtener_clave_movil_non_qr_path),
        _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.obtener_clave_movil_qr_path),
        _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.cancelar_clave_movil_path),
    ],
)
def test_every_clave_flow_page_is_refused_as_a_landing(tmp_path: Path, clave_flow_url: str) -> None:
    """These are the pages a failing fresh login is actually left on.

    Each is refused by the authenticated-landing predicate, so recording
    one would persist a session that cannot pass its own reuse probe.
    """

    assert _provider(tmp_path)._salvageable_landing_url(clave_flow_url, target_path=_TARGET_PATH) is None


def test_the_refused_selector_page_is_the_one_that_re_enters_the_clave_dispatch(tmp_path: Path) -> None:
    """States why the selector page in particular must not be recorded.

    The provider's on-landing hook keys on the selector marker, and the
    selector URL carries it, so a probe sent to that URL runs the Cl@ve
    dispatch rather than reading an authenticated page. Asserting the
    marker match alongside the refusal keeps the reason attached to the
    rule: a later reader relaxing the refusal can see what it re-opens.
    """

    selector_url = _CLAVE_SURFACE.selector_access_url_template.format(target=_TARGET_PATH)

    assert _CLAVE_SURFACE.selector_access_path_marker in selector_url
    assert _provider(tmp_path)._salvageable_landing_url(selector_url, target_path=_TARGET_PATH) is None


def test_the_auth_gate_error_page_is_refused(tmp_path: Path) -> None:
    """The 4033 gate is AEAT reporting the session did not authorise."""

    gate_url = _aeat_url(_DOMAINS.sede, _SEDE_PATHS.auth_gate_4033)

    assert _provider(tmp_path)._salvageable_landing_url(gate_url, target_path=_TARGET_PATH) is None


def test_a_non_aeat_host_is_refused(tmp_path: Path) -> None:
    """A landing off the AEAT apex is never a session this provider owns."""

    assert (
        _provider(tmp_path)._salvageable_landing_url(
            f"https://example.invalid{_TARGET_PATH}",
            target_path=_TARGET_PATH,
        )
        is None
    )


@pytest.mark.parametrize("observed", [None, ""])
def test_no_observed_url_records_nothing(tmp_path: Path, observed: str | None) -> None:
    """A page that never reported a URL leaves the landing unset, not empty-stringed."""

    assert _provider(tmp_path)._salvageable_landing_url(observed, target_path=_TARGET_PATH) is None
