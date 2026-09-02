"""Recorded URLs on declarations evidence must name the host that answered.

AEAT load-balances an authenticated session across its numbered sede
hosts. The host that answers is assigned, not chosen, and a session
minted on one may be refused by another. So a URL written onto stored
evidence is a claim about where a read actually happened, and
reconstructing it from a fixed host makes that claim false for every
capture that landed anywhere else.

This gate covers the RECORDING half of the module: the origin used to
build a ``source_url``, ``detail_url``, ``cotejo_url`` or ``pdf_url``.

The module's initial NAVIGATION host is still pinned, and that is now a
measured decision rather than an open question. Requesting the
declarations listing on the unnumbered sede origin with a valid session
returns a genuine 404, landing on the requested host rather than
bouncing, so the obvious de-pin would break a working reader. The readers
that name no host reach their surface through the Cl@ve access selector
and let AEAT dispatch; this module has no selector entry, so giving it
one is new navigation behaviour rather than removing a pin, and is
tracked separately.

A source-wide "no numbered host" scan therefore still cannot pass, and is
still not attempted - a gate that cannot pass teaches nobody anything.
What changed is that the reason is evidence rather than an assumption.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

from ......core.config import Settings
from .. import _declarations_fetch
from ..declarations import (
    SEDE_BASE,
    cotejo_document_url,
    cotejo_view_url,
    listing_url_for,
    origin_of,
)
from ..errors import SedeNavigationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_DOMAINS = Settings.external_constants().aeat.domains

# The declared numbered pool, read from the registry rather than spelled
# out here. Naming a host in this file would be the same defect the gate
# is about, one layer up.
_DISPATCH_ORIGINS: tuple[str, ...] = (
    _DOMAINS.www1,
    _DOMAINS.www2,
    _DOMAINS.www6,
    _DOMAINS.www12,
)


class TestOriginOf:
    """The recorded origin is read off the landing, not assumed."""

    @pytest.mark.parametrize("origin", _DISPATCH_ORIGINS)
    def test_every_dispatch_host_is_carried_through(self, origin: str) -> None:
        """A read that landed on any numbered host records that host.

        Parametrised across the pool rather than asserting one value,
        because privileging a number is the defect this gate exists to
        prevent: a check that only ever sees one host would pass while
        the code hardcoded it.
        """
        assert (
            origin_of(f"{origin}{Settings.external_constants().aeat.sede_paths.declarations_listing}?MODELO=303")
            == origin
        )

    @pytest.mark.parametrize("landed", ["", None, "not-a-url", "/relative/only", "about:blank"])
    def test_an_unusable_landing_is_refused(self, landed: str | None) -> None:
        """DISCRIMINATING: an origin that cannot be established must not be invented.

        This assertion previously read the other way, requiring a fallback to
        the navigated origin and defending it as "the best true answer
        available". That defence does not survive inspection: AEAT
        load-balances the authenticated session across its numbered pool, so
        precisely when the landing cannot be read is when there is no evidence
        the read stayed on the requested host. The fallback's truth was
        guaranteed only in the case where it was never needed.

        The recorded value feeds an evidence ``source_url``, so a guess there
        is indistinguishable from a measurement to every later reader. Missing
        evidence must read as missing.

        Reverting the refusal makes this fail by observably producing the
        fabricated origin -- see the paired production check below.
        """
        with pytest.raises(SedeNavigationError) as exc_info:
            origin_of(landed)
        assert repr(landed) in str(exc_info.value)

    @pytest.mark.parametrize("landed", ["", None, "not-a-url", "/relative/only", "about:blank"])
    def test_no_fabricated_origin_is_produced_for_an_unusable_landing(self, landed: str | None) -> None:
        """DISCRIMINATING positive control: name what the old code produced.

        Asserting only "it raises" would pass against a function that raised
        for an unrelated reason. This pins the specific wrong value the
        retired fallback returned, so a revert reports the fabrication itself
        rather than a bare missing exception.
        """
        produced: str | None = None
        try:
            produced = origin_of(landed)
        except SedeNavigationError:
            produced = None
        assert produced != SEDE_BASE, (
            f"FABRICATED ORIGIN {produced!r} recorded for an unusable landing {landed!r}; "
            "this is a guess written into an evidence source_url"
        )
        assert produced is None


class TestRecordedUrlsUseTheLandedOrigin:
    """Every recorded-URL builder must honour the origin it is given."""

    @pytest.mark.parametrize("origin", _DISPATCH_ORIGINS)
    def test_listing_url_uses_the_given_origin(self, origin: str) -> None:
        """The listing URL recorded on an observation names the landed host."""
        built = listing_url_for(origin, modelo="303", ejercicio=2024)
        assert built.startswith(origin)
        assert "MODELO=303" in built
        assert "EJERCICIO=2024" in built

    @pytest.mark.parametrize("origin", _DISPATCH_ORIGINS)
    def test_cotejo_urls_use_the_given_origin(self, origin: str) -> None:
        """Both cotejo URLs recorded on a justificante reference name the landed host."""
        assert cotejo_view_url(origin, "FIXTURECSV1234X7").startswith(origin)
        assert cotejo_document_url(origin, "FIXTURECSV1234X7").startswith(origin)

    def test_the_builders_would_fail_if_they_ignored_their_origin(self) -> None:
        """Prove the assertions above discriminate rather than pass on any input.

        A builder that ignored its argument and used the module's pinned
        host would satisfy nothing here, because the origin under test is
        deliberately not that host. This is the check that the parametrised
        cases are measuring the argument and not a coincidence.
        """
        foreign = _DOMAINS.www12
        assert foreign != SEDE_BASE, "the discriminating origin must differ from the pinned one"
        for built in (
            listing_url_for(foreign, modelo="130", ejercicio=2025),
            cotejo_view_url(foreign, "FIXTURECSV1234X7"),
            cotejo_document_url(foreign, "FIXTURECSV1234X7"),
        ):
            assert not built.startswith(SEDE_BASE)


class TestDeclarationsUrlPrimitiveAuthority:
    """The fetch adapter owns each Sede URL primitive exactly once."""

    def test_url_primitives_have_one_module_level_definition(self) -> None:
        """Prevent a second assignment from silently shadowing the URL authority."""
        source = Path(_declarations_fetch.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        assignments = Counter(
            target.id
            for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
            if isinstance(target, ast.Name)
        )

        assert {
            name: assignments[name]
            for name in (
                "SEDE_BASE",
                "_SEDE_HOST",
                "_LISTING_URL",
                "_LISTING_PATH",
                "_COTEJO_QUERY_PATH",
                "_COTEJO_DOCUMENT_PATH",
                "COTEJO_PATH_PREFIX",
            )
        } == {
            "SEDE_BASE": 1,
            "_SEDE_HOST": 1,
            "_LISTING_URL": 1,
            "_LISTING_PATH": 1,
            "_COTEJO_QUERY_PATH": 1,
            "_COTEJO_DOCUMENT_PATH": 1,
            "COTEJO_PATH_PREFIX": 1,
        }
