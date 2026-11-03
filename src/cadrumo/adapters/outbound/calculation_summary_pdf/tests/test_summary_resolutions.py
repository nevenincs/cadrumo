"""A summary PDF shows the acceptances its report lists, and verifies as a document.

The report attests to the acceptances applied when it was produced. Verification
checks the document: it reads the same whatever the profile's resolutions say
afterwards, and the page text must show every listed acceptance.
"""

from __future__ import annotations

import pytest

from .....application.modelo.calculation_report_verification import (
    CalculationSummaryVerificationOutcome,
    verify_calculation_summary,
)
from .....application.modelo.calculation_summary_presentation import build_calculation_summary_presentation
from .....core.external_constants import OutputLanguage
from .....core.product_identity import PRODUCT_IDENTITY
from ..summary_reading import read_calculation_summary_pdf
from .summary_report_support import render_summary, synthetic_keypair, synthetic_report, synthetic_resolution

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_KEY = synthetic_keypair()


def _page_text(payload: bytes) -> str:
    return "".join(read_calculation_summary_pdf(payload).page_text.split())


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_an_acceptance_is_shown_on_the_page_in_the_reports_language_and_the_document_verifies(
    language: OutputLanguage,
) -> None:
    resolution = synthetic_resolution()
    report = synthetic_report(language, credit_resolutions=(resolution,))
    payload = render_summary(report, keypair=_KEY).payload
    presentation = build_calculation_summary_presentation(
        report, csv_sha256="c" * 64, signing_key_fingerprint="d" * 64, brand=PRODUCT_IDENTITY.display_name
    )

    (fact,) = presentation.resolutions
    page = _page_text(payload)

    assert presentation.resolutions_heading
    for text in (presentation.resolutions_heading, fact.label, fact.value):
        assert "".join(text.split()) in page
    assert resolution.finding_id in page
    verification = verify_calculation_summary(
        payload, reader=read_calculation_summary_pdf, trusted_public_key_hex=_KEY.public_key_hex
    )
    assert verification.outcome is CalculationSummaryVerificationOutcome.VERIFIED


def test_a_summary_without_an_acceptance_has_no_such_section() -> None:
    report = synthetic_report(OutputLanguage.EN)
    presentation = build_calculation_summary_presentation(
        report, csv_sha256="c" * 64, signing_key_fingerprint="d" * 64, brand=PRODUCT_IDENTITY.display_name
    )

    assert presentation.resolutions == () and presentation.resolutions_heading == ""
    assert (
        "Accepted source disagreements"
        not in read_calculation_summary_pdf(render_summary(report, keypair=_KEY).payload).page_text
    )
