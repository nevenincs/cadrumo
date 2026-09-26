"""The two-character period span every AEAT filing envelope prints.

The envelope grammar spends exactly two characters on the period, in the prefix
and again in the relative closer (``<T{modelo}0{AAAA}{PP}0000>``). A registry
filing period token is not always two characters, so the envelope has its own
representation of a period; these tests pin it to the record designs.
"""

from __future__ import annotations

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.schema_exports import FilingEnvelopePrefixRole
from ....domain.filing.errors import FilingExportValidationError
from ....domain.filing.software_identity import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity
from ..export_envelope import envelope_closer_bytes, envelope_period_token, render_envelope_prefix_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

#: Modelo 308's ad-hoc settlement, the period the envelope cannot print verbatim.
_AD_HOC = Period.from_year_and_code(2022, "AD-HOC")


def _software_identity() -> AeatProductSoftwareIdentity:
    return AeatProductSoftwareIdentity(
        program_identifier="C308",
        developer_tax_id="Y0000001S",
        evidence=(AeatProductSoftwareEvidence(reference="aeat-software-registration:c308", digest="a" * 64),),
    )


@pytest.mark.parametrize("code", ["1T", "4T", "0A", "01", "12", "1P"])
def test_a_two_character_filing_period_prints_itself(code: str) -> None:
    assert envelope_period_token(Period.from_year_and_code(2025, code)) == code


def test_an_ad_hoc_settlement_prints_the_only_token_its_record_design_admits() -> None:
    """``aeat-dr-308-2019`` M30800 row 5 admits ``1T``-``4T`` or ``0A``; ad-hoc is in no quarter."""
    assert envelope_period_token(_AD_HOC) == "0A"


@pytest.mark.parametrize("code", ["EXT-1T", "EXT-4T", "EVENT-3"])
def test_a_period_with_no_two_character_representation_is_refused(code: str) -> None:
    period = Period.from_year_and_code(2025, code)

    with pytest.raises(FilingExportValidationError, match="envelope representation"):
        envelope_period_token(period)


def test_the_declared_period_prefix_field_renders_the_ad_hoc_token_to_its_declared_extent() -> None:
    rendered = render_envelope_prefix_field(
        FilingEnvelopePrefixRole.PERIOD,
        length=2,
        modelo=Modelo("308"),
        period=_AD_HOC,
        product_software_identity=_software_identity(),
    )

    assert rendered == b"0A"


def test_the_relative_closer_spends_two_characters_on_an_ad_hoc_period() -> None:
    """``aeat-dr-308-2019`` M30800 row 15 declares ``</T3080AAAAPP0000>`` at eighteen bytes."""
    assert envelope_closer_bytes(modelo=Modelo("308"), period=_AD_HOC) == b"</T308020220A0000>"


def test_the_closer_refuses_a_period_the_envelope_cannot_print() -> None:
    period = Period.from_year_and_code(2025, "EXT-1T")

    with pytest.raises(FilingExportValidationError, match="envelope representation"):
        envelope_closer_bytes(modelo=Modelo("369"), period=period)
