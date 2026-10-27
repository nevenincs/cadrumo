"""The context request guard's union and the operator-view policy, through the real guard."""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from ......core.config import Settings
from ......core.remote_authority import aeat_origin_hosts
from ...auth.clave_movil_support import auth_browser_action_policy
from ..request_guard import (
    OPERATOR_VIEW_POLICY_ID,
    ContextRequestGuard,
    RequestGuardVerdict,
    log_safe_host,
    offerable_url,
    operator_view_policy,
    operator_view_request_guard,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_DOMAINS = Settings.external_constants().aeat.domains
_SEDE = _DOMAINS.sede
_IDP_HOST = f"se-pasarela.{urlsplit(_DOMAINS.clave).netloc}"
_UNLISTED_AEAT_HOST = f"www7.{_DOMAINS.host_suffix}"


def _view_verdict(method: str, url: str) -> RequestGuardVerdict:
    return ContextRequestGuard((operator_view_policy(),)).evaluate(method, url)


def test_empty_policy_set_refuses_every_request() -> None:
    guard = ContextRequestGuard(())

    assert guard.evaluate("GET", f"{_SEDE}/").allowed is False
    assert guard.evaluate("HEAD", f"{_SEDE}/Sede/inicio.html").allowed is False
    assert guard.policy_ids == ()


@pytest.mark.parametrize("method", ["GET", "HEAD", "get"])
@pytest.mark.parametrize("origin", [_DOMAINS.sede, _DOMAINS.www1, _DOMAINS.www6, _DOMAINS.www12, _DOMAINS.aeat_gob])
def test_operator_view_admits_reads_on_any_path_of_declared_aeat_origins(origin: str, method: str) -> None:
    verdict = _view_verdict(method, f"{origin}/wlpl/ANY-PATH/Consulta?ejercicio=2025")

    assert verdict == RequestGuardVerdict(allowed=True, policy_id=OPERATOR_VIEW_POLICY_ID)


def test_operator_view_admits_the_clave_identity_provider() -> None:
    assert _view_verdict("GET", f"https://{_IDP_HOST}/Proxy2/ServiceProvider").allowed is True


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_operator_view_refuses_every_undeclared_write_method(method: str) -> None:
    assert _view_verdict(method, f"{_SEDE}/wlpl/BUGC-JDIT/Consulta").allowed is False


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(f"{_SEDE}/wlpl/PRES-MODE/PresentarDeclaracion", id="path-token"),
        pytest.param(f"{_SEDE}/wlpl/CONS-ULTA/Inicio?accion=firmar", id="query-token"),
        pytest.param(f"{_DOMAINS.www6}/wlpl/OVCT-CXEW/DialogoRepresentacion", id="representacion-collision"),
    ],
)
def test_operator_view_refuses_a_get_carrying_a_forbidden_token(url: str) -> None:
    assert _view_verdict("GET", url).allowed is False


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("https://www.example.com/pixel.png", id="off-host"),
        pytest.param(f"https://{_UNLISTED_AEAT_HOST}/Sede/inicio.html", id="unlisted-aeat-host"),
        pytest.param(f"{_DOMAINS.legacy_www}/", id="legacy-www"),
        pytest.param(f"http://{urlsplit(_SEDE).netloc}/", id="cleartext"),
        pytest.param(f"https://{urlsplit(_SEDE).netloc}:8443/", id="explicit-port"),
        pytest.param("data:text/html,<p>inline</p>", id="data-url"),
        pytest.param("not a url", id="unrepresentable"),
    ],
)
def test_operator_view_refuses_what_it_does_not_declare(url: str) -> None:
    assert _view_verdict("GET", url).allowed is False


def test_union_admits_what_any_member_admits_and_names_it() -> None:
    provider = auth_browser_action_policy(Settings())
    url = f"https://{_UNLISTED_AEAT_HOST}/wlpl/MOVI-P24H/Estado"

    assert _view_verdict("GET", url).allowed is False
    verdict = operator_view_request_guard(provider).evaluate("GET", url)

    assert verdict == RequestGuardVerdict(allowed=True, policy_id=provider.id)
    assert operator_view_request_guard(provider).policy_ids == (OPERATOR_VIEW_POLICY_ID, provider.id)


def test_union_never_admits_what_every_member_refuses() -> None:
    guard = operator_view_request_guard(auth_browser_action_policy(Settings()))

    assert guard.evaluate("POST", f"{_SEDE}/wlpl/BUGC-JDIT/Consulta").allowed is False
    assert guard.evaluate("GET", f"{_SEDE}/wlpl/PRES-MODE/PresentarDeclaracion").allowed is False
    assert guard.evaluate("GET", "https://www.example.com/").allowed is False


def test_view_guard_without_a_provider_policy_is_the_operator_view_alone() -> None:
    assert operator_view_request_guard(None).policy_ids == (OPERATOR_VIEW_POLICY_ID,)


def test_operator_view_policy_declares_no_read_post_and_the_declared_origins() -> None:
    policy = operator_view_policy()

    assert policy.classification == "authenticated_read_surface"
    assert policy.allows_gov_idp_hosts is True
    assert policy.allowed_read_post_paths == ()
    assert policy.allowed_read_paths == ()
    assert policy.allowed_hosts == aeat_origin_hosts()
    assert policy.allowed_host_suffixes == (urlsplit(_DOMAINS.clave).netloc,)


def test_refusal_log_host_carries_no_path_or_query() -> None:
    assert log_safe_host(f"{_SEDE}/wlpl/X/Y?nif=00000000T") == urlsplit(_SEDE).netloc
    assert log_safe_host("about:blank") == "-"


@pytest.mark.parametrize(
    ("url", "offered"),
    [
        (f"{_SEDE}/Sede/inicio.html", True),
        ("http://www.example.com/", True),
        ("about:blank", False),
        ("chrome-error://chromewebdata/", False),
        ("javascript:alert(1)", False),
        ("https:///no-host", False),
    ],
)
def test_only_absolute_web_urls_are_offered_externally(url: str, offered: bool) -> None:
    assert (offerable_url(url) == url) is offered
    assert (offerable_url(url) is None) is not offered
