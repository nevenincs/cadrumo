"""The bulk register sweep reports one failed pair and keeps walking the rest.

Cross-pair continuation had no coverage of any kind. Per-pair absorption is
covered -- a refusal raised by one walk becomes a
:class:`~application.live.FiledDataCaptureFailureRow` -- but that proves only
that the failure was turned into a row, not that the loop around it went on to
the next pair. A sweep that stopped at the first failure would report exactly
the same row for that pair and simply omit every later one, which reads as "the
taxpayer filed nothing after this" rather than as an aborted run.

Reaching that loop offline needs the register-injection seam rather than route
interception alone. Interception makes the browser reachable with no production
change, but both bulk functions first resolve a verified session, which runs the
live-read access gate and then the central live-session writer; satisfying that
would ARM real AEAT access. Injecting an already-open register is what lets this
test never request live access in the first place.

Everything else is real: a real :class:`AeatSession`, a real headless Chromium
page, a real ``DeclaracionesRegisterSession``, the real form drive, the real
parse and the real sweep. Only the network is intercepted, and only with
synthetic fixtures -- nothing here contacts AEAT.
"""

from __future__ import annotations

import asyncio
import pytest
from ....tests.offline_aeat_register import (
    aeat_sede_fixture,
    declared_register_total,
    open_routed_declarations_register,
    rendered_register_rows,
)
from .._filed_data import BulkFiledDataListingReport
from .._filed_data_capture import list_filed_data_bulk

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "100"
# Both years carry a registry revision for this modelo, so both survive the
# pre-flight query plan and actually reach the register walk.
_YEAR_FROM = 2024
_YEAR_TO = 2025


def test_a_truncated_pair_is_reported_while_the_other_pair_still_yields_rows() -> None:
    """One pair refused, another pair's rows returned, every queued page consumed.

    The assertions are deliberately order-independent. The route handler cannot
    see which ``(modelo, ejercicio)`` a navigation belongs to -- the pair is
    chosen after the document loads, by driving the comboboxes -- so the pages
    are served in walk order and the property is asserted without naming which
    year got which page: some pair is refused for truncation, some OTHER pair
    returns rows, and no pair does both.

    Nothing here asserts a pair count. A count would pass just as well if the
    sweep walked one pair twice, and would need rewriting the moment the fixture
    pool changed.
    """
    documents = (
        aeat_sede_fixture("declaraciones-register-form-paginated-synthetic"),
        aeat_sede_fixture("declaraciones-register-form-complete-synthetic"),
    )

    async def _sweep() -> BulkFiledDataListingReport:
        async with open_routed_declarations_register(documents) as (register, routed):
            report = await list_filed_data_bulk(
                year_from=_YEAR_FROM,
                year_to=_YEAR_TO,
                modelos=(_MODELO,),
                register=register,
            )
            assert not routed.pending
            return report

    report = asyncio.run(_sweep())

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

    assert report.rows, "the untruncated pair returned no rows, so the sweep did not survive the refusal"
    refused_years = {failure.year for failure in truncation_failures}
    returned_years = {row.year for row in report.rows}
    assert not (refused_years & returned_years), (
        f"a pair both refused and returned rows: refused={refused_years} returned={returned_years}"
    )
