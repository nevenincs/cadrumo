"""The Cl@ve authenticated-landing predicates refuse a hostile authority.

Both providers decided "is this a protected AEAT page?" by comparing
``urlsplit(landing_url).netloc`` against the AEAT host suffix. That string
still ends in the AEAT suffix when a credential prefix rides in front of it,
so ``https://evil@www6.agenciatributaria.gob.es/<target>`` was accepted as an
authenticated AEAT landing — a URL the browser will navigate WITH those
credentials, and one the guard's own allow-list would refuse.

Both predicates now route the authority through the one canonical helper,
which refuses user-info, explicit ports and non-``https`` schemes.

These cases drive the real providers against the real external-constants
surface. Nothing is stubbed: no browser is reached by the decision under test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pytest

from ......core.config import Settings
from ......core.remote_authority import canonical_remote_hostname
from ..clave_movil import ClaveMovilAuthProvider
from ..clave_permanente import ClavePermanenteAuthProvider
from ._clave_movil_support import _DOMAINS, _aeat_url
from ._clave_movil_support import _settings_for as _movil_settings_for
from ._clave_permanente_support import _settings_for as _permanente_settings_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

EXTERNAL = Settings.external_constants()
_TARGET_PATH = EXTERNAL.aeat.sede_paths.expedientes_resumen
_HOST_SUFFIX = EXTERNAL.aeat.domains.host_suffix
_HONEST_LANDING = _aeat_url(_DOMAINS.www6, _TARGET_PATH)
_WWW6_HOST = _DOMAINS.www6.removeprefix("https://")


def _movil(tmp_path: Path) -> ClaveMovilAuthProvider:
    """Build the real Móvil provider; the predicate under test reaches no browser."""
    return ClaveMovilAuthProvider(_movil_settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z"))


def _permanente(tmp_path: Path) -> ClavePermanenteAuthProvider:
    """Build the real Permanente provider; the predicate under test reaches no browser."""
    return ClavePermanenteAuthProvider(
        _permanente_settings_for(
            tmp_path,
            CADRUMO_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            CADRUMO_CLAVE_PERMANENTE_PASSWORD="unused-by-this-predicate",
        ),
    )


class _AuthenticatedLandingProvider(Protocol):
    """Provider surface whose landing predicate this contract exercises."""

    def _is_authenticated_aeat_landing(self, *, landing_url: str, target_path: str) -> bool: ...


def _is_landing(provider: _AuthenticatedLandingProvider, landing_url: str) -> bool:
    """Ask a provider's authenticated-landing predicate about ``landing_url``."""
    return provider._is_authenticated_aeat_landing(landing_url=landing_url, target_path=_TARGET_PATH)


#: Authorities the PRE-FIX ``parsed.netloc`` comparison ACCEPTED, because the
#: whole authority string still ends in the AEAT host suffix. These are the
#: discriminating fixtures: the defect is exactly that they got through.
_PREVIOUSLY_ACCEPTED_HOSTILE: tuple[str, ...] = (
    f"https://evil@{_WWW6_HOST}{_TARGET_PATH}",
    f"https://evil:secret@{_WWW6_HOST}{_TARGET_PATH}",
    f"http://{_WWW6_HOST}{_TARGET_PATH}",
)

#: Authorities the pre-fix comparison ALREADY refused, because appending a port
#: stops the string ending in the suffix. Refusing them is a regression guard,
#: NOT evidence for this change — a distinction the layer control below
#: enforces mechanically so the two sets cannot be quietly merged.
_ALREADY_REFUSED_HOSTILE: tuple[str, ...] = (f"https://{_WWW6_HOST}:8443{_TARGET_PATH}",)


# --------------------------------------------------------------------------
# DISCRIMINATING — these fail if either predicate stops canonicalising
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "landing_url", _PREVIOUSLY_ACCEPTED_HOSTILE, ids=("username-only", "username-and-password", "cleartext-http")
)
def test_movil_refuses_a_hostile_authority_that_ends_in_the_aeat_suffix(
    tmp_path: Path,
    landing_url: str,
) -> None:
    """DISCRIMINATING. Reverting to ``parsed.netloc`` makes these observably ACCEPTED.

    Each URL's authority still ends in the AEAT host suffix, so the pre-fix
    string comparison passed and the predicate returned True.
    """
    assert _is_landing(_movil(tmp_path), landing_url) is False


@pytest.mark.parametrize(
    "landing_url", _PREVIOUSLY_ACCEPTED_HOSTILE, ids=("username-only", "username-and-password", "cleartext-http")
)
def test_permanente_refuses_a_hostile_authority_that_ends_in_the_aeat_suffix(
    tmp_path: Path,
    landing_url: str,
) -> None:
    """DISCRIMINATING. Reverting to ``parsed.netloc`` makes these observably ACCEPTED."""
    assert _is_landing(_permanente(tmp_path), landing_url) is False


def test_both_providers_agree_on_every_hostile_authority(tmp_path: Path) -> None:
    """DISCRIMINATING. One provider conformed and the other not is the mixed population.

    Fails if either predicate is fixed alone, which is the state this change
    exists to leave the codebase out of.
    """
    movil = _movil(tmp_path)
    permanente = _permanente(tmp_path)

    for landing_url in (*_PREVIOUSLY_ACCEPTED_HOSTILE, *_ALREADY_REFUSED_HOSTILE):
        assert _is_landing(movil, landing_url) == _is_landing(permanente, landing_url) is False, (
            f"providers disagree on {landing_url!r}"
        )


@pytest.mark.parametrize("landing_url", _ALREADY_REFUSED_HOSTILE, ids=("explicit-non-default-port",))
def test_an_explicit_port_landing_stays_refused(tmp_path: Path, landing_url: str) -> None:
    """SUPPORTING (regression guard). Passes under mutation.

    A ported authority was already refused before this change, by the suffix
    comparison rather than by the canonicalisation. Kept so the tightening
    cannot silently start ADMITTING it, but it is not evidence for the fix.
    """
    assert _is_landing(_movil(tmp_path), landing_url) is False
    assert _is_landing(_permanente(tmp_path), landing_url) is False


# --------------------------------------------------------------------------
# SUPPORTING — anti-tautology and layer controls
# --------------------------------------------------------------------------


def test_movil_still_accepts_the_honest_authenticated_landing(tmp_path: Path) -> None:
    """SUPPORTING (anti-tautology). Passes under mutation; proves no constant refusal.

    Without this, a predicate hard-wired to ``return False`` would satisfy
    every discriminating case above.
    """
    assert _is_landing(_movil(tmp_path), _HONEST_LANDING) is True


def test_permanente_still_accepts_the_honest_authenticated_landing(tmp_path: Path) -> None:
    """SUPPORTING (anti-tautology). Passes under mutation; proves no constant refusal."""
    assert _is_landing(_permanente(tmp_path), _HONEST_LANDING) is True


def test_the_discriminating_fixtures_pass_the_old_suffix_test() -> None:
    """SUPPORTING (layer control). Passes under mutation.

    Pins what makes the discriminating cases discriminating: each of those
    authorities genuinely satisfies the pre-fix suffix comparison, so its
    refusal can only come from the canonicalisation. A fixture that fails the
    suffix test would have been refused anyway and would prove nothing — this
    assertion is what keeps such a fixture out of the discriminating set.
    """
    from urllib.parse import urlsplit

    for landing_url in _PREVIOUSLY_ACCEPTED_HOSTILE:
        netloc = urlsplit(landing_url).netloc.casefold()

        assert netloc.endswith(f".{_HOST_SUFFIX.casefold()}") or netloc == _HOST_SUFFIX.casefold(), (
            f"fixture {netloc!r} would be refused by the suffix check anyway; it proves nothing"
        )


def test_the_already_refused_fixtures_fail_the_old_suffix_test() -> None:
    """SUPPORTING (layer control). Passes under mutation.

    The complement of the assertion above: it proves the ported authority is in
    the supporting set for a reason, and fails if someone moves it into the
    discriminating set where it would inflate the proof count.
    """
    from urllib.parse import urlsplit

    for landing_url in _ALREADY_REFUSED_HOSTILE:
        netloc = urlsplit(landing_url).netloc.casefold()

        assert not (netloc.endswith(f".{_HOST_SUFFIX.casefold()}") or netloc == _HOST_SUFFIX.casefold())


def test_the_canonical_helper_is_what_refuses_these_authorities() -> None:
    """SUPPORTING (layer control). Passes under mutation.

    Names the mechanism the predicates delegate to, so a later reader can see
    the refusal ground rather than inferring it from a boolean.
    """
    for landing_url in (*_PREVIOUSLY_ACCEPTED_HOSTILE, *_ALREADY_REFUSED_HOSTILE):
        assert canonical_remote_hostname(landing_url) is None
