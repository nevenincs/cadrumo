"""Every casilla number a modelo's registry revisions declare reads back from a summary.

The summary's casilla column is narrow, so long casilla identifiers wrap, and
the published registry is the inventory of what wraps. Each revision's casillas
-- number, label and section, in registry order -- are laid out as rows of one
synthetic report, rendered through the real writer and read back through the
real verifier, whose text-layer check requires every casilla number to be found
on the page, followed by its value.
"""

from __future__ import annotations

from typing import Final

import pytest

from .....application.modelo.calculation_report_verification import (
    CalculationSummaryVerificationOutcome,
    verify_calculation_summary,
)
from .....core.external_constants import OutputLanguage
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..summary_reading import read_calculation_summary_pdf
from .summary_report_support import render_summary, synthetic_keypair, synthetic_report, synthetic_report_rows

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_KEY = synthetic_keypair()
_MODELOS: Final[tuple[str, ...]] = ("100", "111", "115", "130", "180", "190", "303", "390")


@pytest.mark.parametrize("modelo", _MODELOS)
def test_every_declared_casilla_number_reads_back_from_the_summary(
    modelo: str,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    template = next(row for row in synthetic_report_rows() if row.casilla_id == "01")
    revision_ids = [revision_id for listed, revision_id in operation.revision_ids() if listed == modelo]

    assert revision_ids
    for revision_id in revision_ids:
        casillas = operation.revision(modelo, revision_id).casillas
        rows = tuple(
            template.model_copy(
                update={
                    "casilla_id": f"c{index}",
                    "number": str(casilla.number),
                    "label": casilla.label,
                    "section_path": tuple(casilla.section),
                },
            )
            for index, casilla in enumerate(casillas)
        )
        payload = render_summary(synthetic_report(OutputLanguage.ES, rows=rows), keypair=_KEY).payload

        verification = verify_calculation_summary(
            payload,
            reader=read_calculation_summary_pdf,
            trusted_public_key_hex=_KEY.public_key_hex,
        )

        assert verification.outcome is CalculationSummaryVerificationOutcome.VERIFIED, (
            revision_id,
            [check.detail for check in verification.checks if check.reason],
        )
