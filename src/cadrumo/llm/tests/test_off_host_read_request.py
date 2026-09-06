"""What constitutes a well-formed request for an off-host evidence read.

The two halves — a named provider and an acknowledgement of THIS read — are
required together, and neither absorbs the other. The rule had one home, inside
a CLI helper, and no test anywhere in the tree; a second frontend offering the
same option would have re-decided it from scratch.

The on-host refusal is the case worth stating plainly. The dispatch-point gate
inspects a consent token only when the provider actually leaves the host, so a
token minted against the local provider is never looked at: the acknowledgement
is taken, bound to a surface, and covers a read that was always going to run
here. Nothing is disclosed, which is exactly why it goes unnoticed — the harm
is that the operator learns the prompt means nothing.

No case asserts refusal prose. The outcome member is the contract; the wording
is the surface's.
"""

from __future__ import annotations

import pytest

from ...core.config import LLMProvider
from ..consent import (
    OffHostEvidenceReadOutcome,
    classify_off_host_evidence_read,
    provider_reads_off_host,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _off_host_providers() -> list[LLMProvider]:
    """Every provider that actually leaves this host, from the enum itself."""
    return [provider for provider in LLMProvider if provider_reads_off_host(provider)]


def test_neither_half_is_the_on_host_default() -> None:
    """The overwhelmingly common call, and it must ask the operator nothing."""
    outcome = classify_off_host_evidence_read(provider=None, acknowledged=False)

    assert outcome is OffHostEvidenceReadOutcome.ON_HOST_DEFAULT


@pytest.mark.parametrize("provider", _off_host_providers())
def test_both_halves_against_an_off_host_provider_proceed(provider: LLMProvider) -> None:
    """The supported path, checked at every off-host provider.

    Parametrised over the enum rather than one representative, so a provider
    added later is covered without anyone remembering to add a case.
    """
    outcome = classify_off_host_evidence_read(provider=provider, acknowledged=True)

    assert outcome is OffHostEvidenceReadOutcome.OFF_HOST_CONSENTED


@pytest.mark.parametrize("provider", _off_host_providers())
def test_a_provider_without_an_acknowledgement_is_refused(provider: LLMProvider) -> None:
    """A document would leave the host on an input that never said so."""
    outcome = classify_off_host_evidence_read(provider=provider, acknowledged=False)

    assert outcome is OffHostEvidenceReadOutcome.PROVIDER_WITHOUT_ACKNOWLEDGEMENT


def test_an_acknowledgement_without_a_provider_is_refused() -> None:
    """A consent that changes nothing is worse than not asking for one."""
    outcome = classify_off_host_evidence_read(provider=None, acknowledged=True)

    assert outcome is OffHostEvidenceReadOutcome.ACKNOWLEDGEMENT_WITHOUT_PROVIDER


@pytest.mark.parametrize("acknowledged", [True, False])
def test_an_on_host_provider_is_refused_however_it_is_acknowledged(acknowledged: bool) -> None:
    """Acknowledging harder does not make a local read an off-host one.

    Both values are checked because the refusal must not depend on the
    acknowledgement: a caller reading the acknowledged case as permitted would
    mint the token the dispatch gate then ignores.
    """
    outcome = classify_off_host_evidence_read(provider=LLMProvider.LOCAL, acknowledged=acknowledged)

    assert outcome is OffHostEvidenceReadOutcome.PROVIDER_READS_ON_HOST


def test_exactly_one_provider_reads_on_host() -> None:
    """Pinned so a second local transport has to state which side it is on.

    The refusal above asks :func:`provider_reads_off_host` rather than naming
    ``LOCAL``, so a new on-host provider is refused by construction — but only
    if that predicate is what classifies it, which this holds together.
    """
    on_host = [provider for provider in LLMProvider if not provider_reads_off_host(provider)]

    assert on_host == [LLMProvider.LOCAL]


def test_every_outcome_is_reachable() -> None:
    """No member is unreachable, and none is missing a case above.

    A refusal the classifier can never return reads as a rule being enforced
    when nothing enforces it.
    """
    reachable = {
        classify_off_host_evidence_read(provider=provider, acknowledged=acknowledged)
        for provider in [None, *LLMProvider]
        for acknowledged in (True, False)
    }

    assert reachable == set(OffHostEvidenceReadOutcome)
