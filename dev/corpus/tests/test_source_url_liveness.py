"""The withdrawal census, and the reading that keeps it from inventing one.

Two properties are worth pinning about probing a publisher. The first is that
only a 404 or a 410 is the publisher saying nothing is served at an address;
every other refusal is it declining to answer, and reading those as retirements
would retire live documents on the strength of a bot wall. The second is that
one registered publisher -- BOE's consolidated-text API -- refuses any request
that does not negotiate ``application/xml``, so a probe that sends a default
``Accept`` header reports seven working endpoints as gone.

The offline tests below exercise both readings with an injected probe. The live
one is opt-in, and it compares the census with what the publishers answer today
rather than asserting universal reachability: an address that starts 404ing
fails until it is entered with a reason, and one that comes back fails until
its entry is removed.

Run the offline cases with::

    uv run --no-sync pytest dev/corpus/tests/test_source_url_liveness.py -q

and the live census with ``-m aeat_live``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ...registry.conformance.registry_schema_support import committed_registry_tree
from ..fetch_boe_normative import CONSOLIDATED_TEXT_API_HEADERS
from ..source_url_liveness import (
    WITHDRAWN_SOURCE_URLS,
    LivenessOutcome,
    UrlLiveness,
    classify_response,
    probe_source_url,
    probe_source_urls,
    request_headers_for,
)

pytestmark = [pytest.mark.hex_domain]

_CONSOLIDATED_TEXT_API = (
    "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2006-20764/texto/bloque/a95"
)


def _registered_sources() -> tuple[SourceReference, ...]:
    _modelos, catalogues = committed_registry_tree()
    return tuple(catalogues.sources.values())


def _registered_urls() -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(source.source_url) for source in _registered_sources()))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (200, UrlLiveness.REACHABLE),
        (301, UrlLiveness.REACHABLE),
        (404, UrlLiveness.WITHDRAWN),
        (410, UrlLiveness.WITHDRAWN),
        (400, UrlLiveness.REFUSED),
        (403, UrlLiveness.REFUSED),
        (429, UrlLiveness.REFUSED),
        (500, UrlLiveness.REFUSED),
        (None, UrlLiveness.UNREACHABLE),
    ),
)
def test_only_a_disclaimed_resource_reads_as_withdrawn(status: int | None, expected: UrlLiveness) -> None:
    """A bot wall, a rate limit and a server fault are refusals, not retirements."""
    assert classify_response(status) is expected


@pytest.mark.unit
def test_the_consolidated_text_api_is_addressed_the_way_its_acquirer_addresses_it() -> None:
    """Without the negotiated mime type this publisher answers 400 to everything."""
    headers = request_headers_for(_CONSOLIDATED_TEXT_API)

    assert CONSOLIDATED_TEXT_API_HEADERS.items() <= headers.items()


@pytest.mark.unit
def test_an_ordinary_publisher_is_not_given_the_api_mime_negotiation() -> None:
    """The header belongs to one API, not to every BOE address."""
    headers = request_headers_for("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764")

    assert "Accept" not in headers


@pytest.mark.unit
def test_each_address_is_asked_once_however_many_rows_cite_it() -> None:
    """Shared documents are ordinary here; probing one per row would multiply the traffic."""
    asked: list[str] = []

    def probe(url: str) -> LivenessOutcome:
        asked.append(url)
        return LivenessOutcome(url=url, liveness=UrlLiveness.REACHABLE, status=200)

    outcomes = probe_source_urls(("https://a.example/x", "https://b.example/y", "https://a.example/x"), probe=probe)

    assert asked == ["https://a.example/x", "https://b.example/y"]
    assert [outcome.url for outcome in outcomes] == ["https://a.example/x", "https://b.example/y"]


@pytest.mark.unit
def test_the_census_names_only_addresses_the_registry_actually_declares() -> None:
    """A census entry for an unregistered address would exempt nothing and read as though it did."""
    registered = set(_registered_urls())

    stray = sorted(set(WITHDRAWN_SOURCE_URLS) - registered)

    assert not stray, f"the withdrawal census names addresses no source row declares: {stray}"


@pytest.mark.unit
def test_every_withdrawn_address_still_has_its_bytes_in_the_corpus() -> None:
    """This is what makes a withdrawal recordable rather than a loss.

    A retired address whose payload was never bundled is an acquisition task:
    nothing in the repository can answer what the document said. Recording it
    beside evidence that is still hash-pinned is the opposite situation, and the
    census must not be able to drift from the first into the second.
    """
    base = bundled_path()
    missing = sorted(
        f"{source.id} -> {source.corpus_path}"
        for source in _registered_sources()
        if str(source.source_url) in WITHDRAWN_SOURCE_URLS and not Path(base / source.corpus_path).is_file()
    )

    assert not missing, f"withdrawn address(es) whose bytes are not bundled: {missing}"


@pytest.mark.unit
def test_the_census_is_not_vacuous() -> None:
    """A census emptied by accident would make the live comparison assert nothing."""
    assert WITHDRAWN_SOURCE_URLS, "the withdrawal census is empty; the live comparison has nothing to check"
    assert all(reason.strip() for reason in WITHDRAWN_SOURCE_URLS.values()), (
        "every census entry states why the address is gone"
    )


@pytest.mark.aeat_live
def test_the_publishers_still_agree_with_the_withdrawal_census() -> None:
    """Opt-in. Reads every registered publisher and compares with what is recorded."""
    outcomes = probe_source_urls(_registered_urls())
    withdrawn = {outcome.url for outcome in outcomes if outcome.liveness is UrlLiveness.WITHDRAWN}
    unanswered = sorted(
        f"{outcome.url} -> {outcome.liveness.value} {outcome.status} {outcome.detail}".rstrip()
        for outcome in outcomes
        if outcome.liveness in {UrlLiveness.REFUSED, UrlLiveness.UNREACHABLE}
    )

    newly_gone = sorted(withdrawn - set(WITHDRAWN_SOURCE_URLS))
    returned = sorted(set(WITHDRAWN_SOURCE_URLS) - withdrawn)

    assert not newly_gone and not returned, (
        "the withdrawal census no longer matches the publishers.\n"
        f"  newly withdrawn ({len(newly_gone)}): " + "\n    ".join(newly_gone) + "\n"
        f"  served again ({len(returned)}): " + "\n    ".join(returned) + "\n"
        f"  neither served nor disclaimed ({len(unanswered)}, not a census question): " + "\n    ".join(unanswered)
    )


@pytest.mark.aeat_live
def test_a_live_publisher_answers_the_probe_at_all() -> None:
    """Anti-vacuity for the live lane: a blanket network failure must not read as agreement."""
    outcome = probe_source_url("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764")

    assert outcome.liveness is UrlLiveness.REACHABLE, f"the live lane reached no publisher at all: {outcome}"
