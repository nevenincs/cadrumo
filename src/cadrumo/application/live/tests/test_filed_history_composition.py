"""The filed-history composition, executed: sequencing, propagation, notices.

:func:`pull_filed_history` was executed by nothing. Two live runtime breaks survived
on that -- a helper called with one argument where it has always required two, and a
report read for a field it did not carry -- and neither is subtle; either surfaces on
first run. There was no first run.

It was unreachable because its FIRST stage, :func:`discover_filed_history`, brings up
an authenticated session. What is untested here is the COMPOSITION, though: the order
the stages run in, how a stage failure propagates into the run rather than collapsing
it, and how the capture's evidence notices reach the returned report. None of that
needs AEAT. So discovery is injected at a port and everything downstream is the real
thing -- the real :func:`capture_filed_data_bulk`, the real pair/failure join, the
real report construction.

**No test double stands in for any of that.** The injected discovery is a real async
function returning a real, strict-model :class:`FiledHistoryDiscoveryReport`; it is an
implementation of the port, not a patch of the composition's internals. Everything the
assertions below are about runs for real.

The scenario nominates a filing year the bundled registry serves no revision for, so
the bulk capture classifies every pair as unsupported and returns through its own
no-live-contact door -- the same door
:mod:`~application.live.tests.test_filed_bulk_capture` already uses. That is what
keeps a composition test off the network without anyone's certificate deciding whether
it is safe.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import pytest

from ....domain.deadlines import TaxpayerProfile
from .._filed_data_capture import (
    FiledHistoryDiscoveryPair,
    FiledHistoryDiscoveryPort,
    FiledHistoryDiscoveryReport,
    FiledHistoryDiscoverySignal,
    pull_filed_history,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A filing year inside the model's accepted range that the bundled registry serves no
#: revision for, which is what makes the pair unsupported and keeps the walk local.
_UNSERVED_YEAR = 2000
_TODAY = date(2026, 3, 15)


def _discovery_returning(*pairs: FiledHistoryDiscoveryPair) -> FiledHistoryDiscoveryPort:
    """A real implementation of the discovery port that reaches no session."""

    async def discover(
        *,
        profile: TaxpayerProfile | None = None,
        today: date | None = None,
    ) -> FiledHistoryDiscoveryReport:
        # register_options_read=True and no profile span: the register nominated
        # these pairs, so the report carries no taxpayer-specific denominator -- a
        # derived property here rather than a field, which is why it is not set.
        return FiledHistoryDiscoveryReport(
            pairs=pairs,
            register_options_read=True,
            profile_year_span_determined=False,
        )

    return discover


def _pair(modelo: str = "100", *, ejercicio: int = _UNSERVED_YEAR) -> FiledHistoryDiscoveryPair:
    return FiledHistoryDiscoveryPair(
        modelo=modelo,
        ejercicio=ejercicio,
        signals=(FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,),
    )


def _run(*pairs: FiledHistoryDiscoveryPair, tmp_path: Path, dry_run: bool = False):
    return asyncio.run(
        pull_filed_history(
            output_root=tmp_path,
            today=_TODAY,
            dry_run=dry_run,
            discover=_discovery_returning(*pairs),
        ),
    )


def test_the_composition_runs_end_to_end_and_returns_a_run(tmp_path: Path) -> None:
    """The whole sequence executes and produces a run for the discovered pair.

    This is the assertion that did not exist. It reaches the final construction --
    the one that read ``capture.evidence_notices`` off a report that did not carry
    it -- so the ``AttributeError`` that shipped could not survive this test.
    """
    run = _run(_pair(), tmp_path=tmp_path)

    assert len(run.pairs) == 1
    assert run.pairs[0].modelo == "100"
    assert run.pairs[0].ejercicio == _UNSERVED_YEAR
    assert run.evidence_notices == ()


def test_an_unserviceable_pair_is_reported_as_refused_rather_than_lost(tmp_path: Path) -> None:
    """A capture failure propagates onto its own pair instead of collapsing the run.

    The composition joins the bulk report's failure rows back onto the discovered
    pairs. If that join broke, the run would still be returned and still look
    healthy -- the pair would simply carry no refusal -- which is the silent shape
    worth pinning rather than the loud one.
    """
    run = _run(_pair(), tmp_path=tmp_path)

    assert run.pairs[0].refused is True
    assert run.pairs[0].failure_type == "LiveApplicationInputError"
    assert run.pairs[0].failure_message
    assert run.pairs[0].captured_count == 0


def test_every_discovered_pair_survives_the_join(tmp_path: Path) -> None:
    """Two pairs in, two pairs out, in discovery order.

    Pins the composition against a join that drops or reorders pairs -- a single-pair
    scenario cannot distinguish "joined correctly" from "returned the only thing it
    had".
    """
    run = _run(_pair("100"), _pair("303"), tmp_path=tmp_path)

    assert [(pair.modelo, pair.ejercicio) for pair in run.pairs] == [
        ("100", _UNSERVED_YEAR),
        ("303", _UNSERVED_YEAR),
    ]


def test_dry_run_preserves_the_composed_discovery_scope_without_provenance(tmp_path: Path) -> None:
    """Preview walks the same discovered pairs and retains no sync-run identity."""
    pairs = (_pair("100"), _pair("303"))

    normal = _run(*pairs, tmp_path=tmp_path)
    preview = _run(*pairs, tmp_path=tmp_path, dry_run=True)

    assert [(pair.modelo, pair.ejercicio) for pair in preview.pairs] == [
        (pair.modelo, pair.ejercicio) for pair in normal.pairs
    ]
    assert preview.dry_run is True
    assert preview.sync_run_ref is None
    assert preview.iva_wallet_status == "not_attempted"
    assert preview.notificaciones_status == "not_attempted"


def test_no_discovered_pair_short_circuits_before_the_capture(tmp_path: Path) -> None:
    """An empty grid returns early and says so, rather than walking nothing.

    The early return is a different exit from the one above, and it carries the
    stage-failure note that tells an operator why the run is empty.
    """
    run = _run(tmp_path=tmp_path)

    assert run.pairs == ()
    assert run.stage_failures == ("discovery: no modelo/ejercicio pair to walk",)
