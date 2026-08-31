"""The two populations the sync-run writer once paired can genuinely diverge.

This is the behavioural half of the sync-run coverage guarantee. The structural
half -- deriving both counts from one source, and an AST floor requiring every
production writer to do so -- proves that the invalid pair is no longer
expressible. It does not prove the pair was ever reachable, and a guarantee
against an unreachable state is theatre.

So this drives real production code to the state the old pairing produced: more
divergences than units. A recapture advisory is raised once per observation
ABSORBED, while the count it used to be paired against was the number of
observations successfully ENROLLED, and enrolment narrows twice against
absorption -- the finalizer keeps only the latest observation per (modelo,
ejercicio, period), and a best-effort enrolment failure diverts its observation
into failures instead of keys. Either narrowing is enough.

WHY THIS IS REACHABLE OFFLINE AT ALL, given the sibling capture test records
that a full sweep is not. That test cannot persist an observation because
per-row capture fetches the cotejo PDF through ``context.request``, which route
interception cannot reach. The blocked leg is CAPTURE FROM AEAT. What this
needs is a PERSISTED OBSERVATION, and those are separable: the observation can
be seeded straight through the production persistence function, which is what
happens here. Nothing below contacts AEAT, opens a browser, or reads a PDF.

Everything here is production code: the real encrypted profile bucket, the real
observation persistence, the real divergence comparator and the real finalizer.
The only thing authored locally is the observation content itself.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...storage.sync_runs.records import SyncRunCoverage
from ..filed_capture_finalizer import FiledCaptureFailurePolicy, finalize_filed_capture
from ..filed_data_capture import recapture_divergence_notices
from ..filed_observation_persistence import persist_filed_calculation_observation
from ._filed_capture_history_support import (
    _M303_DECLARATION_TYPE_C,
    _prior_303_observation,
    _secure_backend,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The filed result the first capture recorded, and the corrected one a later
#: sweep reads back. AEAT legitimately permits a complementaria, so a value
#: changing between captures is ordinary rather than exceptional -- which is
#: exactly why the advisory exists and why the count it feeds has to be right.
#:
#: BOTH ARE NEGATIVE, and the declaration-type header below is chosen to match.
#: The M303 carry ingress screens the declared disposition against the SIGN of
#: the filed resultado and refuses a contradiction at persist time -- before the
#: divergence read this file exists to exercise. So a mismatched pair does not
#: fail an assertion, it kills the test upstream of every assertion it has.
#:
#: The mapping is resolved rather than inferred from the letter, because the
#: letter is not the disposition and guessing it wrong is how this fixture was
#: broken twice. Measured against the screen's own frozensets:
#:
#:     N -> NEGATIVA        accepted ONLY with resultado == 0
#:     C -> COMPENSACION    negative        D -> DEVOLUCION      negative
#:     V -> CUENTA_CORRIENTE_DEVOLUCION     negative
#:     X -> DEVOLUCION_TRANSFERENCIA_EXTRANJERO  negative
#:     I -> INGRESO         positive        U -> DOMICILIACION   positive
#:     G -> CUENTA_CORRIENTE_INGRESO        positive
#:
#: The support fixture defaults to "N", which admits a ZERO resultado only --
#: neither the negative nor the positive class. A non-zero seed of either sign
#: is refused under it, which is why inverting the sign alone did not help.
_ORIGINAL_RESULT = Decimal("-50.00")
_CORRECTED_RESULT = Decimal("-999.00")


def _observation(*, result: Decimal):
    """One M303 filed observation for a fixed period, carrying a given result.

    The declaration-type header is passed explicitly rather than defaulted. The
    support fixture defaults to "N", which the carry screen accepts only with a
    zero resultado, and these observations carry a non-zero one so the recapture
    comparison has a value to disagree about. "C" is COMPENSACION, a negative
    disposition, which is what the negative results above require.
    """
    return _prior_303_observation(
        pending_compensation=Decimal("0.00"),
        result=result,
        headers=(_M303_DECLARATION_TYPE_C,),
    )


def test_a_recapture_divergence_is_producible_without_contacting_aeat(tmp_path: Path) -> None:
    """The advisory fires against a genuinely persisted prior observation.

    The positive control for the test below. If this ever stopped producing a
    divergence, the population comparison that follows would compare two empty
    sets and pass while proving nothing.
    """
    with _secure_backend(tmp_path):
        persist_filed_calculation_observation(_observation(result=_ORIGINAL_RESULT))
        notices = recapture_divergence_notices((_observation(result=_CORRECTED_RESULT),))

    assert len(notices) == 1, "a corrected filing must raise exactly one recapture advisory"
    assert notices[0].code == "live.filed.pull_all.recapture_divergence"


def test_enrolment_reaches_fewer_units_than_absorption_raises_divergences(tmp_path: Path) -> None:
    """The defect state, reproduced: more divergences than enrolled units.

    Two observations for ONE period are absorbed and both diverge, so two
    advisories are raised. The finalizer then narrows that population -- by the
    latest-per-period collapse, by a best-effort enrolment failure, or by both.
    The assertion is written against the NARROWING rather than against a
    specific surviving count, because either cause produces the defect and
    pinning the number would make this test brittle about which one did.

    The old pairing is then shown to be refused outright and the current one
    accepted. That contrast is the whole point: it is the difference between a
    record that could not be written at the end of a real sweep and one that
    can.
    """
    with _secure_backend(tmp_path):
        persist_filed_calculation_observation(_observation(result=_ORIGINAL_RESULT))
        corrected = _observation(result=_CORRECTED_RESULT)

        # One absorb per observation, so a two-observation sweep raises two
        # advisories against the same stored prior.
        divergences = recapture_divergence_notices((corrected, corrected))
        reached = 2

        enrolled = finalize_filed_capture(
            (corrected, corrected),
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
        ).calculation_observation_keys

    assert len(divergences) == reached, "each absorbed observation must contribute one advisory"
    # Assert the population is REAL before asserting a relation over it. Without
    # this, enrolment collapsing to zero for an unrelated reason would satisfy
    # the narrowing below -- 0 < N passes happily -- and this test would go on
    # reporting a defect it was no longer reproducing.
    assert len(enrolled) >= 1, "no observation enrolled at all, so the narrowing below would pass vacuously"
    assert len(enrolled) < len(divergences), (
        "enrolment no longer narrows against absorption, so the two populations this test "
        f"exists to separate have converged: enrolled={len(enrolled)} divergences={len(divergences)}"
    )

    # The pairing the filed sweep used before 2b10626f59: advisories counted per
    # observation absorbed, against units counted per observation enrolled. This
    # raised at the END of a real run, after everything was already persisted.
    with pytest.raises(ValidationError, match="cannot have diverged"):
        SyncRunCoverage(unit_count=len(enrolled), divergence_count=len(divergences))

    # The pairing it uses now, both counts drawn from the one population the
    # advisories were raised over.
    coverage = SyncRunCoverage(unit_count=reached, divergence_count=len(divergences))
    assert coverage.divergence_count == len(divergences)
