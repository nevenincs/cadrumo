"""The bulk register CAPTURE continues past a failed pair, not just the listing.

The sibling sweep test proves cross-pair continuation for
:func:`~application.live.list_filed_data_bulk`. That is a different guarantee
from the one asserted here. ``capture_filed_data_bulk`` resolves an active
bucket id before its loop and then, for every walked row, drives the per-row
observation capture and persists through the accumulator -- so what the listing
test proves about ITS loop says nothing about whether THIS one survives a
refused pair. Until now the capture function's register seam was known only to
compile, type-check and leave every caller unchanged.

The deferred cost was the real encrypted-storage setup rather than the browser,
so that is what this test pays: a genuine active-profile bucket runtime, the
same one production resolves through, alongside the real headless page the
listing test already proved reachable offline.

Reaching the loop needs the register-injection seam rather than route
interception alone. Interception makes the browser reachable with no production
change, but the function first resolves a verified session, which runs the
live-read access gate and then the central live-session writer; satisfying that
would ARM real AEAT access. Injecting an already-open register is what lets this
test never request live access in the first place. ``CADRUMO_LIVE_TESTS_ENABLED``
is never set here and the live-read gate is never satisfied.

Everything else is real: a real :class:`AeatSession`, a real headless Chromium
page, a real ``DeclaracionesRegisterSession``, a real bucket, the real form
drive, the real parse and the real capture loop. Only the network is
intercepted, and only with synthetic fixtures -- nothing here contacts AEAT.

WHY THE REACHED PAIR YIELDS NO PERSISTED OBSERVATION, and why chasing one would
be wrong. Per-row capture opens the justificante popup and then fetches the
cotejo PDF through ``context.request``, an API request context. Route
interception cannot reach it: a ``**/*`` handler registered on the page OR on
the browser context is never consulted for ``context.request`` traffic, which
leaves the browser for the real origin. Measured directly rather than assumed --
an intercepted ``context.request.get`` against the sede host returned a real 404
from the real host with the handler never invoked. So driving this far enough to
persist an observation offline would either need production changes or would
make genuine AEAT contact, which is precisely what this test exists to avoid.

The reached pair therefore stops at the popup wait and records per-ROW outcomes.
That is enough, because continuation is read off the SHAPE of the failures: a
walk-level refusal carries no expediente (no row was ever parsed), while
anything the second pair produces carries one. The assertion stays written as
"an observation OR a per-row outcome" so it keeps holding, rather than inverting
into a false alarm, if the PDF leg ever does become reachable offline.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ....adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ....tests.offline_aeat_register import (
    aeat_sede_fixture,
    declared_register_total,
    open_routed_declarations_register,
    rendered_register_rows,
)
from ....tests.secure_sql import isolated_runtime_profile
from ..filed_data_capture import capture_filed_data_bulk
from ..remote_state_models import BulkFiledDataCaptureReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "100"
# Both years carry a registry revision for this modelo, so both survive the
# pre-flight query plan and actually reach the register walk.
_YEAR_FROM = 2024
_YEAR_TO = 2025
_BUCKET_ID = "7c7c7c7c-7c7c-47c7-87c7-7c7c7c7c7c7c"


def _capture(output_root: Path) -> BulkFiledDataCaptureReport:
    """Run the real bulk capture over two queued pages, one truncated, one complete."""
    documents = (
        aeat_sede_fixture("declaraciones-register-form-paginated-synthetic"),
        aeat_sede_fixture("declaraciones-register-form-complete-synthetic"),
    )

    async def _run() -> BulkFiledDataCaptureReport:
        async with open_routed_declarations_register(documents, ver_click_timeout_ms=1500) as (register, routed):
            report = await capture_filed_data_bulk(
                year_from=_YEAR_FROM,
                year_to=_YEAR_TO,
                output_root=output_root,
                modelos=(_MODELO,),
                register=register,
                sync_run_repository=SyncRunRecordRepository(),
            )
            assert not routed.pending
            return report

    return asyncio.run(_run())


def test_a_truncated_pair_is_reported_while_the_other_pair_is_still_captured(tmp_path: Path) -> None:
    """One pair refused at the walk, the other pair walked and its rows processed.

    The assertions are deliberately order-independent. The route handler cannot
    see which ``(modelo, ejercicio)`` a navigation belongs to -- the pair is
    chosen after the document loads, by driving the comboboxes -- so the pages
    are served in walk order and the property is asserted without naming which
    year got which page.

    Nothing here asserts a pair count. A count would pass just as well if the
    capture walked one pair twice, and would need rewriting the moment the
    fixture pool changed.

    Continuation is read off the SHAPE of the failures rather than off a tally.
    A walk-level truncation refusal carries no expediente, because no row was
    ever parsed; anything the second pair produces is per-ROW and therefore
    carries one. A capture that stopped at the refused pair could only ever
    report the first kind.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        report = _capture(tmp_path / "captures")

    truncation_failures = [failure for failure in report.failures if failure.error_type == "SedeParseError"]
    assert truncation_failures, f"no truncation refusal was absorbed into a failure row: {report.failures}"

    # Both numbers are read straight out of the fixture's own markup rather than
    # from anything the parser computed, so the row is cross-checked against the
    # page it came from and neither number is hardcoded here.
    truncated_page = aeat_sede_fixture("declaraciones-register-form-paginated-synthetic")
    declared_total = declared_register_total(truncated_page)
    assert declared_total is not None
    rendered_rows = rendered_register_rows(truncated_page)
    assert rendered_rows < declared_total, "fixture no longer renders fewer rows than its pager declares"
    for failure in truncation_failures:
        assert str(rendered_rows) in failure.message and str(declared_total) in failure.message, (
            f"the failure row lost the rendered-versus-declared cause: {failure.message!r}"
        )

    walk_refusals = [failure for failure in report.failures if failure.expediente_id is None]
    per_row_outcomes = [failure for failure in report.failures if failure.expediente_id is not None]
    assert walk_refusals, "no walk-level refusal was recorded, so the truncated pair never reached the absorber"
    assert report.observation_paths or per_row_outcomes, (
        "the complete pair produced neither an observation nor a per-row outcome, "
        "so the capture never got past the refused pair"
    )

    refused_years = {failure.year for failure in walk_refusals}
    reached_years = {failure.year for failure in per_row_outcomes}
    assert not (refused_years & reached_years), (
        f"a pair both refused at the walk and reached its rows: refused={refused_years} reached={reached_years}"
    )
