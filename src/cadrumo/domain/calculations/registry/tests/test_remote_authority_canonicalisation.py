"""Tests for the single canonical remote-authority decision.

Two defects motivated this module and are pinned here.

The first: every remote safety check parsed a URL's authority its own way.
The Cl@ve landing predicates compared ``urlsplit(url).netloc``, so a
credentialed authority whose string still ended in the AEAT suffix passed;
the guard read ``pydantic.AnyUrl.host``, which reports the host with
user-info and port already stripped, so the same URL and an off-port
redirect both read as a plain AEAT host.

The second: :func:`_evaluate_http` constrained method, path and host but
never the SCHEME, so an ``http://`` or even ``ftp://`` URL under an allowed
AEAT host was admitted on an authenticated policy.

:func:`canonical_remote_hostname` is now the one authority for both
questions, and the guard consumes it.
"""

from __future__ import annotations

import inspect
from importlib.util import find_spec

import pytest
from pydantic import AnyUrl

import cadrumo.core as core
import cadrumo.domain.calculations.registry as registry
from cadrumo.core.external_constants import load_external_constants
from cadrumo.core.remote_authority import (
    REMOTE_READ_SCHEME,
    aeat_host_suffixes,
    canonical_remote_hostname,
    first_aeat_host,
    is_aeat_host,
    is_sanctioned_gov_idp_host,
    sanctioned_gov_idp_host_suffixes,
)

from .....tests.aeat_literal_fixtures import aeat_host, aeat_url, configured_path
from ..remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    RemoteStateGuardResult,
    evaluate_remote_operation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_WWW6_HOST = aeat_host("www6")
_SEDE_HOST = aeat_host("sede")
_READ_PATH = configured_path("sede_paths", "declarations_listing")
_ALLOWED_URL = aeat_url("www6", _READ_PATH)


def _authenticated_policy() -> RemoteStateGuardPolicy:
    """Return an authenticated-read policy admitting exactly one AEAT host."""
    return RemoteStateGuardPolicy(
        id="authority-canonicalisation-probe",
        evidence_tier="official_source_guidance",
        classification="authenticated_read_surface",
        allowed_hosts=(_WWW6_HOST,),
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=False,
    )


#: Fragment unique to the authority refusal, so a test can tell "the
#: canonicalisation rejected this" from "the host allow-list rejected this".
#: The two refusals reach the same ``blocked`` decision by different grounds,
#: and only one of them is what these tests add.
_AUTHORITY_REFUSAL_GROUND = "is not a bare"
_ALLOW_LIST_REFUSAL_GROUND = "not in allowed read-only hosts"


def _evaluate(url: str) -> RemoteStateGuardResult:
    """Return the full guard result for a read of ``url`` under the probe policy."""
    return evaluate_remote_operation(
        _authenticated_policy(),
        RemoteOperation(kind="http", method="GET", url=AnyUrl(url)),
    )


def _decide(url: str) -> str:
    """Return only the guard decision for a read of ``url``."""
    return _evaluate(url).decision


# --------------------------------------------------------------------------
# Layer controls: prove these tests measure OUR check, not pydantic's parser
# --------------------------------------------------------------------------
#
# A URL that never reaches the canonicalisation would also produce a blocked
# decision, and the two are indistinguishable from the outcome alone. These
# controls pin WHICH layer sees the hostile authority. If pydantic ever starts
# sanitising or rejecting these shapes itself, these tests fail and say so —
# rather than the guard tests below silently going vacuous while still passing.


def test_pydantic_preserves_the_user_info_the_guard_must_reject() -> None:
    """``AnyUrl`` carries user-info through, so the guard is what refuses it.

    Control, not a proof of the fix: it asserts the *precondition* that makes
    :func:`test_guard_blocks_user_info_on_an_otherwise_allowed_host` meaningful.
    """
    parsed = AnyUrl(f"https://evil:secret@{_WWW6_HOST}{_READ_PATH}")

    assert parsed.username == "evil"
    # Suppression rationale: not a credential. This reads back the synthetic
    # user-info from the URL literal three lines above, as the positive control
    # proving pydantic does not sanitise it -- which is the precondition that
    # makes the sibling guard test measure the guard rather than pass vacuously.
    assert parsed.password == "secret"  # noqa: S105
    assert "evil" in str(parsed), "pydantic sanitised the user-info; the guard test no longer measures the guard"


def test_pydantic_accepts_the_non_https_schemes_the_guard_must_reject() -> None:
    """``AnyUrl`` admits ``http`` and ``ftp``, so the guard is what refuses them.

    Control, not a proof of the fix: without it, a passing scheme test could be
    pinning pydantic's URL validation rather than the scheme check F59 adds.
    """
    for scheme in ("http", "ftp"):
        parsed = AnyUrl(f"{scheme}://{_WWW6_HOST}{_READ_PATH}")

        assert parsed.scheme == scheme, f"pydantic rewrote the {scheme!r} scheme before the guard could refuse it"


def test_pydantic_preserves_a_non_default_port_the_guard_must_reject() -> None:
    """``AnyUrl`` keeps ``:8443`` in its serialised form.

    Control, not a proof of the fix. Note the deliberate asymmetry documented in
    :func:`_evaluate_http`: pydantic DOES normalise an explicit *default* port
    (``:443``) away, so that one shape cannot be refused at the guard and is
    admitted as the equivalent portless URL it denotes.
    """
    assert ":8443" in str(AnyUrl(f"https://{_WWW6_HOST}:8443{_READ_PATH}"))
    assert ":443" not in str(AnyUrl(f"https://{_WWW6_HOST}:443{_READ_PATH}"))


# --------------------------------------------------------------------------
# canonical_remote_hostname: the one authority
# --------------------------------------------------------------------------


def test_plain_https_authority_canonicalises_to_its_hostname() -> None:
    """A bare https authority yields the lower-cased hostname."""
    assert canonical_remote_hostname(_ALLOWED_URL) == _WWW6_HOST


def test_uppercase_authority_canonicalises_to_lower_case() -> None:
    """Host comparison is case-insensitive, so the canonical form is lower-cased."""
    upper = f"https://{_WWW6_HOST.upper()}{_READ_PATH}"

    assert canonical_remote_hostname(upper) == _WWW6_HOST


def test_sibling_aeat_host_canonicalises_to_itself_not_the_allowed_host() -> None:
    """Canonicalisation reports the real host; allow-listing stays the caller's job."""
    assert canonical_remote_hostname(aeat_url("sede", _READ_PATH)) == _SEDE_HOST
    assert canonical_remote_hostname(aeat_url("sede", _READ_PATH)) != _WWW6_HOST


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(f"https://evil@{_WWW6_HOST}{_READ_PATH}", id="username-only"),
        pytest.param(f"https://evil:secret@{_WWW6_HOST}{_READ_PATH}", id="username-and-password"),
        pytest.param(f"https://:secret@{_WWW6_HOST}{_READ_PATH}", id="password-only"),
    ],
)
def test_user_info_authority_is_refused(url: str) -> None:
    """A credentialed authority is refused, never stripped down to its host."""
    assert canonical_remote_hostname(url) is None


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(f"https://{_WWW6_HOST}:443{_READ_PATH}", id="explicit-default-port"),
        pytest.param(f"https://{_WWW6_HOST}:8443{_READ_PATH}", id="explicit-alternate-port"),
        pytest.param(f"https://{_WWW6_HOST}:80{_READ_PATH}", id="explicit-cleartext-port"),
    ],
)
def test_explicit_port_authority_is_refused(url: str) -> None:
    """An explicitly pinned port is refused; a read surface is addressed by host."""
    assert canonical_remote_hostname(url) is None


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(f"http://{_WWW6_HOST}{_READ_PATH}", id="cleartext-http"),
        pytest.param(f"ftp://{_WWW6_HOST}{_READ_PATH}", id="ftp"),
        pytest.param(f"file://{_WWW6_HOST}{_READ_PATH}", id="file"),
        pytest.param(f"//{_WWW6_HOST}{_READ_PATH}", id="scheme-relative"),
        pytest.param(_READ_PATH, id="scheme-and-authority-absent"),
    ],
)
def test_non_https_scheme_is_refused(url: str) -> None:
    """Only the TLS scheme AEAT publishes its read surfaces on is accepted."""
    assert canonical_remote_hostname(url) is None


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(f"https://{_WWW6_HOST}:notaport{_READ_PATH}", id="non-numeric-port"),
        pytest.param(f"https://{_WWW6_HOST}:99999{_READ_PATH}", id="out-of-range-port"),
        pytest.param(f"https://[{_WWW6_HOST}{_READ_PATH}", id="unclosed-ipv6-bracket"),
        pytest.param("https://", id="empty-authority"),
        pytest.param(f"https:///{_READ_PATH.lstrip('/')}", id="missing-authority"),
    ],
)
def test_malformed_authority_is_refused(url: str) -> None:
    """A malformed authority fails closed rather than raising into the caller."""
    assert canonical_remote_hostname(url) is None


def test_canonical_scheme_is_tls() -> None:
    """The accepted scheme constant names TLS, not cleartext."""
    assert REMOTE_READ_SCHEME == "https"


def test_aeat_suffixes_preserve_configured_and_legacy_authority() -> None:
    """The typed registry supplies both AEAT suffixes without a runtime-settings facade."""
    domains = load_external_constants().aeat.domains

    assert aeat_host_suffixes() == (domains.host_suffix, domains.legacy_host_suffix)
    assert is_aeat_host(domains.host_suffix)
    assert is_aeat_host(f"www9.{domains.host_suffix}")
    assert is_aeat_host(domains.legacy_host_suffix)
    assert is_aeat_host(f"sede.{domains.legacy_host_suffix}")
    assert first_aeat_host(("example.invalid", f"sede.{domains.legacy_host_suffix}")) == (
        f"sede.{domains.legacy_host_suffix}"
    )
    source = inspect.getsource(aeat_host_suffixes)
    assert "load_external_constants()" in source
    assert "Settings" not in source


def test_sanctioned_idp_is_separate_from_aeat_authority() -> None:
    """Cl@ve stays an explicit opt-in IdP surface, never an AEAT host suffix."""
    domains = load_external_constants().aeat.domains
    (idp_suffix,) = sanctioned_gov_idp_host_suffixes()

    assert idp_suffix == domains.clave.removeprefix("https://")
    assert is_sanctioned_gov_idp_host(f"se-pasarela.{idp_suffix}")
    assert not is_aeat_host(idp_suffix)


def test_registry_remote_authority_surface_has_no_facade_or_retired_module() -> None:
    """Consumers reach the direct core owner; packages expose no compatibility surface."""
    retired_module = ".".join(("cadrumo", "domain", "calculations", "registry", "aeat_hosts"))

    assert find_spec(retired_module) is None
    assert registry.__all__ == []
    assert not hasattr(registry, "aeat_hosts")
    assert not any(
        hasattr(core, name)
        for name in (
            "REMOTE_READ_SCHEME",
            "canonical_remote_hostname",
            "aeat_host_suffixes",
            "is_aeat_host",
            "first_aeat_host",
            "sanctioned_gov_idp_host_suffixes",
            "is_sanctioned_gov_idp_host",
        )
    )


# --------------------------------------------------------------------------
# The guard consumes that one authority
# --------------------------------------------------------------------------


def test_guard_allows_a_plain_https_read_on_an_allowed_host() -> None:
    """The ordinary authenticated read the tightening must not break."""
    assert _decide(_ALLOWED_URL) == "allowed"


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(f"https://evil@{_WWW6_HOST}{_READ_PATH}", id="username-only"),
        pytest.param(f"https://evil:secret@{_WWW6_HOST}{_READ_PATH}", id="username-and-password"),
        pytest.param(f"https://{_WWW6_HOST}:8443{_READ_PATH}", id="explicit-non-default-port"),
        pytest.param(f"http://{_WWW6_HOST}{_READ_PATH}", id="cleartext-http"),
        pytest.param(f"ftp://{_WWW6_HOST}{_READ_PATH}", id="ftp"),
    ],
)
def test_guard_refuses_a_hostile_authority_on_the_authority_ground(url: str) -> None:
    """The AUTHORITY check refuses these, not the host allow-list.

    The host these URLs name IS allow-listed, so a blocked decision alone
    proves nothing about which check fired — the refusal ground is asserted
    instead. Before the fix ``AnyUrl.host`` reported a plain allow-listed host
    for every one of them and the guard returned ``allowed``.
    """
    result = _evaluate(url)

    assert result.decision == "blocked"
    assert _AUTHORITY_REFUSAL_GROUND in result.reason, f"expected an authority refusal, got: {result.reason}"
    assert _ALLOW_LIST_REFUSAL_GROUND not in result.reason


def test_guard_still_blocks_a_sibling_host_on_the_allow_list_ground() -> None:
    """A well-formed but unlisted host is refused by the allow-list, not the authority check.

    The negative half of the ground assertion above: canonicalisation must not
    widen host admission, and must not swallow the allow-list's own refusal.
    """
    result = _evaluate(aeat_url("sede", _READ_PATH))

    assert result.decision == "blocked"
    assert _ALLOW_LIST_REFUSAL_GROUND in result.reason
    assert _AUTHORITY_REFUSAL_GROUND not in result.reason


def test_guard_refusal_reason_names_the_scheme_and_the_policy() -> None:
    """A refusal is instructive: it names the required scheme and its policy."""
    policy = _authenticated_policy()
    result = evaluate_remote_operation(
        policy,
        RemoteOperation(kind="http", method="GET", url=AnyUrl(f"http://{_WWW6_HOST}{_READ_PATH}")),
    )

    assert result.decision == "blocked"
    assert REMOTE_READ_SCHEME in result.reason
    assert result.policy_id == policy.id
