"""The transport boundary that folds justificante evidence advisories into the envelope.

The application layer already raises one typed WARNING per stored artefact that
yielded no evidence, each naming its own reason. That only reaches an operator if
the CLI forwards it, and the forwarding is a single ``extend`` at the boundary
where three advisory sources converge on one channel.

These assertions drive that builder directly. Reading ``evidence_notices`` back
off a run the test just constructed proves only that pydantic stores a tuple: it
cannot fail if the forwarding is deleted, because the field is populated by the
test rather than by the code under test. The distinction matters here more than
usual, because the reasons exist precisely to undo a uniform silence -- a capture
that extracted casillas while enrolling nothing used to report an unexplained
zero, indistinguishable from a period with no receipt to enrol.
"""

from __future__ import annotations

import pytest

from ....application.live import (
    FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE,
    FiledHistoryOnboardingRun,
    FiledHistoryPairOutcome,
    FiledJustificanteUnreachedReason,
)
from ....core import FiledHistoryDiscoverySignal
from ....core.json_contract import Notice, NoticeSeverity
from .._app_live import _filed_pull_all_notices

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _answered_pair() -> FiledHistoryPairOutcome:
    """A pair that answered with filings, so it raises no advisory of its own."""
    return FiledHistoryPairOutcome(
        modelo="303",
        ejercicio=2025,
        signals=(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,),
        row_count=1,
    )


def _unreached_notice(reason: FiledJustificanteUnreachedReason) -> Notice:
    return Notice(
        severity=NoticeSeverity.WARNING,
        code=FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE,
        message=f"artefact produced no evidence ({reason.value})",
        context={"reason": reason.value, "modelo": "130", "expediente_id": "202613000000199Z"},
    )


def _run(
    *notices: Notice,
    pairs: tuple[FiledHistoryPairOutcome, ...] | None = None,
) -> FiledHistoryOnboardingRun:
    """A run whose only advisories are the ones passed in.

    ``carries_a_taxpayer_specific_denominator`` is set so the builder's own
    denominator warning stays out of the way; the default pair answers, so no
    expected-but-not-found notice fires either.
    """
    return FiledHistoryOnboardingRun(
        pairs=pairs if pairs is not None else (_answered_pair(),),
        carries_a_taxpayer_specific_denominator=True,
        evidence_notices=notices,
    )


def test_the_transport_forwards_every_unreached_reason_as_its_own_notice() -> None:
    """Every member of the reason taxonomy survives the fold onto the envelope.

    Driving the FULL enum rather than a hand-listed sample is what makes a newly
    added reason fail here instead of going unrelayed: the expected set is derived
    from the enum, so it cannot drift behind it.
    """
    reasons = tuple(FiledJustificanteUnreachedReason)
    assert reasons, "the reason taxonomy is empty, so this test would pass vacuously"

    notices = _filed_pull_all_notices(_run(*(_unreached_notice(reason) for reason in reasons)))

    relayed = [notice for notice in notices if notice.code == FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE]
    assert {notice.context["reason"] for notice in relayed if notice.context} == {reason.value for reason in reasons}
    # One per reason. A builder that merged two dead ends into a single
    # "evidence not enrolled" notice would rebuild the uniform silence one layer
    # up, while still emitting something and still looking like a relay.
    assert len(relayed) == len(reasons)


def test_the_transport_preserves_each_forwarded_notice_verbatim() -> None:
    """The advisory arrives unrewritten, context included.

    Severity, code, message and context all have to survive: an operator triaging
    an unusable receipt needs the reason and the expediente, and a boundary that
    rebuilt the notice from its code alone would drop exactly those.
    """
    original = _unreached_notice(FiledJustificanteUnreachedReason.CSV_MISMATCH)

    notices = _filed_pull_all_notices(_run(original))

    assert original in notices


def test_the_transport_keeps_run_advisories_and_evidence_advisories_distinct() -> None:
    """Two authorities, one channel, still two readable facts.

    A refused pair and an unusable receipt are different events: the first says
    the read did not happen, the second says it happened and produced nothing
    enrollable. Sharing the notices channel must not merge their identities.
    """
    refused = FiledHistoryPairOutcome(
        modelo="303",
        ejercicio=2024,
        signals=(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,),
        row_count=0,
        refused=True,
    )
    run = _run(
        _unreached_notice(FiledJustificanteUnreachedReason.UNPARSABLE_PDF),
        pairs=(_answered_pair(), refused),
    )

    codes = [notice.code for notice in _filed_pull_all_notices(run)]

    assert FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE in codes
    assert "live.filed.pull_all.pairs_refused" in codes


def test_a_run_that_reached_all_its_evidence_forwards_no_unreached_notice() -> None:
    """The channel stays clean on the success path.

    Without this, a builder appending the advisory unconditionally would satisfy
    every assertion above while telling an operator that a wholly successful pull
    reached no evidence.
    """
    codes = [notice.code for notice in _filed_pull_all_notices(_run())]

    assert FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE not in codes
