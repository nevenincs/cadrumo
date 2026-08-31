"""A category citation must resolve to an official AEAT or BOE origin.

A citation is the operator's route back to the authority behind a deduction
rule, so an arbitrary host is not a weaker citation -- it is an unverifiable
one. ``AnyHttpUrl`` alone accepts any host on either scheme, which is the gap
these tests close.

Scope is deliberately the *origin* only. The companion weakness -- that
``reference`` and ``locator`` are free-form prose rather than resolved
registry identities -- is NOT addressed here: every one of the 162 shipped
citations carries prose references, so constraining them is a legal-grounding
exercise against the bundled corpus, not a shape change. That half is
recorded as its own finding.

Each test states whether it is DISCRIMINATING (fails when the constraint is
removed or weakened) or SUPPORTING. No mocks: the real external-constants
registry supplies the origins and the real shipped profiles are loaded.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....core.external_constants import load_external_constants
from ....core.i18n import Translatable as tr
from ....tests.aeat_literal_fixtures import (
    AEAT_HOST_SUFFIX_EXPECTED,
    CITATION_APEX_URL_FIXTURE,
    CITATION_SEDE_AYUDA_URL_FIXTURE,
    CITATION_SEDE_BARE_HOST_FIXTURE,
    CITATION_SEDE_HTTP_DOWNGRADE_URL_CANARY,
    CITATION_SEDE_LOOKALIKE_HOST_URL_CANARY,
)
from .._proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    _authoritative_citation_origins,
)
from .._registry import load_category_profiles

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _citation(url: str) -> CategoryCitation:
    return CategoryCitation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30",
        url=url,
        quote=tr("texto autoritativo"),
        legal_ref="ley-35-2006:art-30",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )


def test_shipped_profiles_still_load_under_the_constraint() -> None:
    """Every shipped citation satisfies the origin rule.

    SUPPORTING by construction -- it cannot fail while the shipped data is
    conformant -- but it is the regression that makes the constraint safe to
    keep: it fails the moment a future citation cites a non-official origin,
    which is exactly when an author needs to be told.
    """
    profiles = load_category_profiles()
    citations = [c for p in profiles.values() for c in p.proportionality.citations]

    # Gated on the property, never on a tally. A citation count encodes the
    # moment it was written and then detects nothing, and it is the assertion
    # that breaks every time a profile legitimately gains evidence.
    assert citations, "the shipped corpus carries no citations at all; this gate would pass vacuously"
    assert {str(c.url).split("/")[2] for c in citations} <= {
        CITATION_SEDE_BARE_HOST_FIXTURE,
        "www.boe.es",
    }


def test_a_non_authoritative_host_is_refused() -> None:
    """The audit's own probe URL is refused.

    DISCRIMINATING. Fails if the origin constraint is dropped, because
    ``AnyHttpUrl`` accepts this host unchanged.
    """
    with pytest.raises(ValidationError) as excinfo:
        _citation("https://example.invalid/not-authoritative")

    assert "not an official authority" in str(excinfo.value)


def test_a_lookalike_host_cannot_pass_by_suffix() -> None:
    """A host merely *ending* in the official domain is refused.

    DISCRIMINATING, and the reason suffix matching is anchored on a dot:
    an unanchored ``endswith`` would admit this host, so the test fails if
    the boundary anchor is removed while every other test still passes.
    """
    with pytest.raises(ValidationError):
        _citation(CITATION_SEDE_LOOKALIKE_HOST_URL_CANARY)


def test_an_http_origin_is_refused_as_a_downgrade() -> None:
    """A real AEAT host over plain http is still refused.

    DISCRIMINATING. Fails if the scheme check is dropped, and it is
    independent of the host check because the host here is genuine.
    """
    with pytest.raises(ValidationError):
        _citation(CITATION_SEDE_HTTP_DOWNGRADE_URL_CANARY)


@pytest.mark.parametrize(
    "url",
    [
        CITATION_SEDE_AYUDA_URL_FIXTURE,
        "https://www.boe.es/buscar/act.php",
        CITATION_APEX_URL_FIXTURE,
    ],
)
def test_official_origins_are_accepted(url: str) -> None:
    """Real AEAT and BOE origins, including the bare apex, still validate.

    DISCRIMINATING against over-tightening: a constraint that admitted
    nothing would pass every refusal test above, so the accepting direction
    has to be pinned too.
    """
    citation = _citation(url)

    assert str(citation.url).startswith(url)


def test_accepted_origins_agree_with_the_canonical_domain_registry() -> None:
    """The origin set matches the registry's declared hostnames.

    SUPPORTING, and labelled so after being caught by mutation. This
    assertion was originally claimed as proof that the origins are
    *derived* rather than restated -- it is not. Replacing the derivation
    with hardcoded literals left this test green, because today's literals
    equal today's registry values. It pins agreement at the current values,
    which is worth having, but the derivation is asserted by
    :func:`test_origin_set_is_read_from_the_registry_at_call_time`.
    """
    domains = load_external_constants().aeat.domains
    accepted = _authoritative_citation_origins()

    assert domains.host_suffix.lower() in accepted
    assert domains.boe.lower().endswith(next(o for o in accepted if "boe" in o))


def test_origin_set_is_read_from_the_registry_at_call_time() -> None:
    """The origins are read from the canonical registry, not restated here.

    DISCRIMINATING, and the only test that catches restated literals.
    Verified by mutation: replacing the derivation with a hardcoded
    hostname set left all seven other tests green -- behaviour is identical
    while today's literals match today's registry, so the duplication is
    invisible until a domain rotates. The read itself is therefore
    asserted, exactly as the LLM retention selector asserts its wiring.
    """
    import inspect

    source = inspect.getsource(_authoritative_citation_origins)

    assert "load_external_constants()" in source, source
    for literal in (AEAT_HOST_SUFFIX_EXPECTED, "boe.es"):
        assert literal not in source, f"hostname literal {literal!r} restated instead of derived:\n{source}"
