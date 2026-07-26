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

import pytest

from ......core.config import Settings
from .._declarations import (
    _SEDE_BASE,
    _cotejo_document_url,
    _cotejo_view_url,
    _listing_url_for,
    _origin_of,
)

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
            _origin_of(f"{origin}{Settings.external_constants().aeat.sede_paths.declarations_listing}?MODELO=303")
            == origin
        )

    @pytest.mark.parametrize("landed", ["", None, "not-a-url", "/relative/only"])
    def test_an_unusable_landing_falls_back_to_the_navigated_origin(self, landed: str | None) -> None:
        """With no usable landing, the origin the navigation used is the best true answer.

        This is a truthfulness fallback rather than a preference: the read
        was issued against that origin, so naming it is accurate even when
        the landing cannot be read.
        """
        assert _origin_of(landed) == _SEDE_BASE


class TestRecordedUrlsUseTheLandedOrigin:
    """Every recorded-URL builder must honour the origin it is given."""

    @pytest.mark.parametrize("origin", _DISPATCH_ORIGINS)
    def test_listing_url_uses_the_given_origin(self, origin: str) -> None:
        """The listing URL recorded on an observation names the landed host."""
        built = _listing_url_for(origin, modelo="303", ejercicio=2024)
        assert built.startswith(origin)
        assert "MODELO=303" in built
        assert "EJERCICIO=2024" in built

    @pytest.mark.parametrize("origin", _DISPATCH_ORIGINS)
    def test_cotejo_urls_use_the_given_origin(self, origin: str) -> None:
        """Both cotejo URLs recorded on a justificante reference name the landed host."""
        assert _cotejo_view_url(origin, "FIXTURECSV1234X7").startswith(origin)
        assert _cotejo_document_url(origin, "FIXTURECSV1234X7").startswith(origin)

    def test_the_builders_would_fail_if_they_ignored_their_origin(self) -> None:
        """Prove the assertions above discriminate rather than pass on any input.

        A builder that ignored its argument and used the module's pinned
        host would satisfy nothing here, because the origin under test is
        deliberately not that host. This is the check that the parametrised
        cases are measuring the argument and not a coincidence.
        """
        foreign = _DOMAINS.www12
        assert foreign != _SEDE_BASE, "the discriminating origin must differ from the pinned one"
        for built in (
            _listing_url_for(foreign, modelo="130", ejercicio=2025),
            _cotejo_view_url(foreign, "FIXTURECSV1234X7"),
            _cotejo_document_url(foreign, "FIXTURECSV1234X7"),
        ):
            assert not built.startswith(_SEDE_BASE)
