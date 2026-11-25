"""What constitutes a well-formed request for an off-host evidence read.

The two halves — a named provider and an acknowledgement of THIS read — are
required together, and neither absorbs the other. The rule had one home, inside
a CLI helper, and no test anywhere in the tree; a second frontend offering the
same option would have re-decided it from scratch.

No case asserts refusal prose. The outcome member is the contract; the wording
is the surface's.
"""

from __future__ import annotations

import pytest

from .....core.config_support import LLMProvider
from ..consent import (
    OffHostEvidenceReadOutcome,
    classify_off_host_evidence_read,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _off_host_providers() -> list[LLMProvider]:
    """Every provider an operator may name for an off-host read, from the enum itself."""
    return list(LLMProvider)


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
