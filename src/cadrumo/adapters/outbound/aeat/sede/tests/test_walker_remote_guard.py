"""The expedientes walker must refuse an off-AEAT read before it happens.

The walker navigates to URLs it did not construct. ``Expediente.detail_url``
is read off an ``href`` on the resumen page and the parser deliberately
preserves a supplied external netloc, so the page decides the host. The
session is authenticated, so following such a URL sends AEAT session
cookies wherever the page names.

Every adjacent authenticated sede reader preflights each GET against a
:class:`RemoteStateGuardPolicy`. The walker did not, which made it the one
authenticated reader that would follow an arbitrary absolute URL.

Proof discipline for this module, because the correct and incorrect
implementations can reach the same visible end state (no capture returned):

* **DISCRIMINATING** assertions observe the MECHANISM -- that the guard was
  consulted and refused, and that nothing crossed the wire. Each fails when
  the guard is removed. They are marked ``DISCRIMINATING`` in their
  docstrings.
* **SUPPORTING** assertions cover the admit path and policy shape. They pass
  with the guard removed and are context, not proof. They are marked
  ``SUPPORTING``.

An assertion of the form "no capture was returned" would be SUPPORTING at
best: a capture can fail to happen for many reasons that have nothing to do
with the guard.
"""

from __future__ import annotations

import pytest

from ......core.config import Settings
from ......domain.calculations.registry.errors import RegistryValidationError
from ......tests.aeat_literal_fixtures import (
    AEAT_APEX_EVIL_SUFFIX_URL_CANARY,
    AEAT_APEX_NOT_PREFIX_URL_CANARY,
)
from .. import _declarations_fetch, _walker
from .._parse import parse_resumen_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_DOMAINS = Settings.external_constants().aeat.domains

# Read from the registry rather than spelled out, so the gate cannot pass by
# privileging one number while the code hardcodes it.
_DISPATCH_ORIGINS: tuple[str, ...] = (
    _DOMAINS.www1,
    _DOMAINS.www2,
    _DOMAINS.www6,
    _DOMAINS.www12,
)

# Hosts a page could name that are NOT AEAT. Hardcoded here on purpose: an
# expectation derived from the production allow-list would only prove
# self-consistency.
_OFF_AEAT_URLS: tuple[str, ...] = (
    "https://evil.example.test/steal?e=1",
    "http://127.0.0.1:8080/collect",
    AEAT_APEX_EVIL_SUFFIX_URL_CANARY,
    AEAT_APEX_NOT_PREFIX_URL_CANARY,
)


def _host_of(url: str) -> str:
    """Return the hostname a refusal message is expected to name."""
    from urllib.parse import urlsplit

    host = urlsplit(url).hostname
    assert host is not None, f"test fixture URL {url!r} has no hostname"
    return host


class _NavigationRecorder:
    """Records what would cross the wire.

    This is an observation point at the network boundary, not a stand-in for
    the logic under test: the code under test is the guard in ``_walker``, and
    this records whether a request escaped it. It implements only the two
    attributes of a Playwright ``Page`` that ``_goto_guarded`` touches.
    """

    def __init__(self, *, landing: str | None = None) -> None:
        self.attempted: list[str] = []
        self.url: str = ""
        self._landing = landing

    async def goto(self, url: str, wait_until: str | None = None) -> None:
        self.attempted.append(url)
        self.url = url if self._landing is None else self._landing


class TestOffHostNavigationIsRefusedBeforeItHappens:
    """The requested URL is guarded, and the refusal precedes the request."""

    @pytest.mark.parametrize("url", _OFF_AEAT_URLS)
    @pytest.mark.asyncio
    async def test_the_guard_refuses_and_nothing_crosses_the_wire(self, url: str) -> None:
        """DISCRIMINATING: guard consulted, refused, and zero navigation attempts.

        Two observations, both required. The raise proves the guard was
        consulted; the empty ``attempted`` list proves the refusal happened
        BEFORE the request rather than being reported after it.

        With the guard removed, ``attempted`` contains the off-AEAT URL --
        that is the positive control, and it is what makes this assertion
        discriminate rather than merely pass.
        """
        recorder = _NavigationRecorder()
        refusal: RegistryValidationError | None = None
        try:
            await _walker._goto_guarded(recorder, url)
        except RegistryValidationError as exc:
            refusal = exc

        # PRIMARY observation, deliberately checked before the refusal itself:
        # did anything cross the wire? Asserting `pytest.raises` first would
        # make the mutation fail on "DID NOT RAISE", which proves the guard was
        # not consulted but NOT that the request actually went out. This
        # ordering makes the mutation report the navigation itself.
        assert recorder.attempted == [], (
            f"AUTHENTICATED SESSION NAVIGATED OFF-AEAT to {recorder.attempted!r}; the guard did not stop the request"
        )
        # Then: it was the guard that stopped it, and it named what it rejected.
        # Which check fires varies by URL shape -- a non-https or ported
        # authority is refused earlier than a well-formed off-AEAT host -- so
        # this pins the host rather than one branch's wording.
        assert refusal is not None, "nothing crossed the wire, but no guard refusal was raised"
        assert _host_of(url) in str(refusal)

    @pytest.mark.parametrize("url", _OFF_AEAT_URLS)
    def test_the_pdf_fetch_guard_refuses_an_off_host_url(self, url: str) -> None:
        """DISCRIMINATING: ``JustificanteRef.pdf_url`` is guarded too.

        ``pdf_url`` is an absolute ``AnyHttpUrl`` on a public schema, so it is
        guarded rather than trusted to have been built by this module.
        """
        with pytest.raises(RegistryValidationError):
            _walker._assert_read_http("GET", url)

    @pytest.mark.parametrize("url", _OFF_AEAT_URLS)
    def test_the_walker_refuses_with_the_declarations_readers_shape(self, url: str) -> None:
        """DISCRIMINATING: same refusal shape as the adjacent guarded reader.

        Asserted absolutely on BOTH sides rather than only as an equality
        between them: two relaxed predicates would agree with each other while
        admitting everything. Each reader is separately required to raise and
        to name the rejected URL; only then is the shared shape compared.
        """
        with pytest.raises(RegistryValidationError) as walker_exc:
            _walker._assert_read_http("GET", url)
        with pytest.raises(RegistryValidationError) as declarations_exc:
            _declarations_fetch._assert_read_http("GET", url)

        # Absolute, per reader.
        assert _host_of(url) in str(walker_exc.value)
        assert _host_of(url) in str(declarations_exc.value)
        # Relative, only meaningful because each side was pinned above.
        assert type(walker_exc.value) is type(declarations_exc.value)
        assert str(walker_exc.value) == str(declarations_exc.value)


class TestTheLandedUrlIsReAsserted:
    """A redirect is a second chance to leave the allowed host set."""

    @pytest.mark.parametrize("landing", _OFF_AEAT_URLS)
    @pytest.mark.asyncio
    async def test_an_off_host_redirect_is_refused_after_navigation(self, landing: str) -> None:
        """DISCRIMINATING: guarding only the request would miss this entirely.

        The requested URL is a legitimate AEAT URL that the guard admits, so
        the navigation proceeds. The response lands off-AEAT. Checking only
        the request would guard the intent and not the outcome.
        """
        recorder = _NavigationRecorder(landing=landing)
        with pytest.raises(RegistryValidationError):
            await _walker._goto_guarded(recorder, _walker._RESUMEN_URL)
        assert recorder.attempted == [_walker._RESUMEN_URL]


class TestTheOffHostUrlReachesTheGuardFromARealParse:
    """End-to-end: a resumen page names the host, and the guard still refuses."""

    @pytest.mark.asyncio
    async def test_a_page_supplied_off_host_href_is_refused(self) -> None:
        """DISCRIMINATING: the audit's reproduction, now closed.

        Drives the real parser over a resumen page carrying an off-AEAT
        ``href``, confirms the parser really does hand back that host (so the
        test is not passing because the URL was rejected upstream), then
        confirms the walker's guard refuses to navigate to it.
        """
        html = (
            "<html><body><h1>Mis Expedientes</h1>"
            '<ul><li><a onclick="javascript:desplegar(1)">Modelo 100 - IRPF</a>'
            '<ul><li><a onclick="lanzarTewvForm()" '
            'href="https://evil.example.test/steal?e=1">2024EXP00000001</a></li></ul>'
            "</li></ul></body></html>"
        )
        expedientes = parse_resumen_tree(html, base_url=_walker._SEDE_BASE)

        assert len(expedientes) == 1, "the fixture must actually parse, or the guard is never reached"
        detail_url = str(expedientes[0].detail_url)
        assert detail_url == "https://evil.example.test/steal?e=1", (
            "the parser must preserve the off-AEAT netloc, or this test proves nothing about the guard"
        )

        recorder = _NavigationRecorder()
        refusal: RegistryValidationError | None = None
        try:
            await _walker._goto_guarded(recorder, detail_url)
        except RegistryValidationError as exc:
            refusal = exc

        # Wire observation first, for the same reason as the unit case: this
        # is what proves the guard is consulted at a point where the hostile
        # netloc is still present, rather than after something normalised it
        # away. Under mutation this reports the actual off-AEAT navigation.
        assert recorder.attempted == [], (
            f"AUTHENTICATED SESSION NAVIGATED OFF-AEAT to {recorder.attempted!r} "
            "from a page-supplied href; the guard did not stop the request"
        )
        assert refusal is not None, "nothing crossed the wire, but no guard refusal was raised"


class TestLegitimateAeatReadsStillPass:
    """The guard must not refuse the reads the walker exists to perform."""

    @pytest.mark.parametrize("origin", _DISPATCH_ORIGINS)
    def test_every_dispatch_host_in_the_pool_is_admitted(self, origin: str) -> None:
        """SUPPORTING: passes with the guard removed; guards against over-refusal.

        AEAT load-balances the authenticated surface across its numbered pool,
        so pinning one host would refuse a legitimate dispatch.
        """
        _walker._assert_read_http("GET", f"{origin}{Settings.external_constants().aeat.sede_paths.expedientes_resumen}")

    @pytest.mark.asyncio
    async def test_an_allowed_url_navigates(self) -> None:
        """SUPPORTING: passes with the guard removed; confirms the admit path."""
        recorder = _NavigationRecorder()
        await _walker._goto_guarded(recorder, _walker._RESUMEN_URL)
        assert recorder.attempted == [_walker._RESUMEN_URL]


class TestThePolicyShape:
    """The policy declares what this reader is, and declares no controls."""

    def test_the_policy_is_an_authenticated_read_surface(self) -> None:
        """SUPPORTING: passes with the navigation guard removed."""
        policy = _walker._READ_GUARD_POLICY
        assert policy.classification == "authenticated_read_surface"
        assert policy.requires_authentication is True
        assert policy.synthetic_data_allowed is False

    def test_the_policy_declares_no_browser_actions(self) -> None:
        """SUPPORTING: the walker drives no controls, so any action must refuse.

        An empty allow-list means a browser action added here later fails the
        guard until it is declared, rather than passing unnoticed.
        """
        assert _walker._READ_GUARD_POLICY.allowed_browser_action_patterns == ()


class TestNoUnguardedWireCrossingRemains:
    """No wire-crossing call in the walker may bypass the guard."""

    def test_every_navigation_goes_through_the_guarded_helper(self) -> None:
        """DISCRIMINATING: a re-grown bare ``page.goto`` reintroduces the hole.

        The instrument is exercised rather than trusted: the helper's own
        definition contains the only sanctioned bare ``page.goto``, so the
        scan below is confirmed to be capable of finding that shape before
        its zero result is believed.
        """
        source = _read_walker_source()
        sanctioned = source.count("await page.goto(")
        assert sanctioned == 1, (
            "expected exactly one bare page.goto -- the one inside _goto_guarded; "
            f"found {sanctioned}, so either the helper changed or a caller bypassed it"
        )

    def test_the_pdf_fetch_is_preceded_by_a_guard_assertion(self) -> None:
        """DISCRIMINATING: the PDF GET must be preflighted, not just typed."""
        import inspect

        source = inspect.getsource(_walker.capture_justificante)
        guard_at = source.find('_assert_read_http("GET", str(ref.pdf_url))')
        fetch_at = source.find("context.request.get(str(ref.pdf_url))")
        assert guard_at != -1, "the PDF fetch is not guarded"
        assert fetch_at != -1, "the PDF fetch call was not found; this test is stale"
        assert guard_at < fetch_at, "the guard must run BEFORE the fetch, not after"


def _read_walker_source() -> str:
    from pathlib import Path

    return Path(_walker.__file__).read_text(encoding="utf-8")
