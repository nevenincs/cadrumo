"""Convenio doble imposición limitation-of-benefits (LOB) advisory tests.

Covers the ``m210_convenio_lob_advisory`` non-blocking
:class:`~domain.modelos.ModeloVerificationFinding` this module surfaces
whenever a Modelo 210 rate actually applies a matched treaty override row (per
the treaty-eligibility policy: residence-certificate and
limitation-of-benefits checks surface as non-blocking advisory notices rather
than being silently trusted).

The advisory must fire for every treaty-country persona with a matched
override row (GB/general FLAT, MA/interest CEILING, DE/interest EXEMPT,
AR/pension ALLOCATION_DOMESTIC_TARIFF) and must not fire for a domestic
resident with no ``country_of_fiscal_residence``, nor for a treaty country
whose declared ``tipo_renta`` has no matching override row (the missing-row
BLOCKING branch is a separate concern owned by
:func:`~application.modelo._m210_rate.resolve_m210_rate`).

See Also:
    :func:`~application.modelo._m210_convenio_lob_advisory._m210_convenio_lob_advisory_finding`
        Advisory builder under test.
    :func:`~application.modelo._m210_rate.resolve_m210_rate`
        Rate resolver that owns the blocking missing-row branch.
    :class:`~domain.calculations.registry.ConvenioAuthority`
        Cross-cutting treaty authority consumed by the advisory and resolver.
"""

from __future__ import annotations

import pytest

from ._m210_snapshot_fixture import m210_snapshot

__all__ = ["m210_snapshot"]

from ....core import validated_casilla_id
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from ....domain.deadlines import FiscalResidency, IVARegime, TaxpayerProfile
from ....domain.modelos import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from .._m210_convenio_lob_advisory import _m210_convenio_lob_advisory_finding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TIPO_RENTA = validated_casilla_id("tipo_renta", surface="test_m210_convenio_lob_advisory")


def _irnr_profile(country_code: str) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
        country_of_fiscal_residence=country_code,
        representante_fiscal_nif="12345678Z",
        representante_fiscal_nombre="Test Representative",
    )


def _resident_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.RESIDENT_IRPF,
    )


@pytest.mark.parametrize(
    ("country_code", "tipo_renta", "expected_legal_refs"),
    [
        pytest.param(
            "GB",
            "general",
            ("convenio-es-gb-2013:art-6", "trlirnr-rdleg-5-2004:art-25.1.a"),
            id="olivia-gb-general-flat",
        ),
        pytest.param(
            "MA",
            "interest",
            ("convenio-es-ma-1978:art-11",),
            id="khadija-ma-interest-ceiling",
        ),
        pytest.param(
            "DE",
            "interest",
            ("convenio-es-de-2011:art-11",),
            id="german-interest-exempt",
        ),
        pytest.param(
            "AR",
            "pension",
            ("convenio-es-ar-1992:art-19", "trlirnr-rdleg-5-2004:art-25.1.b"),
            id="felipe-ar-pension-allocation-domestic-tariff",
        ),
    ],
)
def test_lob_advisory_fires_for_every_matched_treaty_override(
    m210_snapshot: RegistrySnapshot,
    country_code: str,
    tipo_renta: str,
    expected_legal_refs: tuple[str, ...],
) -> None:
    """Every treaty-country persona with a matched override row triggers the LOB advisory.

    The expected ``legal_refs`` are read from the real committed treaty rows
    (cross-checked in ``test_committed_convenio_rows_resolve_corrected_legal_anchors``),
    not hand-computed, so a regression that stops resolving the override (or
    resolves the wrong row) fails this test rather than passing tautologically.
    """
    profile = _irnr_profile(country_code)
    input_values = {_TIPO_RENTA: tipo_renta}

    finding = _m210_convenio_lob_advisory_finding(m210_snapshot, profile, input_values)

    assert finding is not None
    assert finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert finding.casilla_id == _TIPO_RENTA
    assert finding.legal_refs == expected_legal_refs
    assert finding.message_locale_key == "application.modelo.findings.m210_convenio_lob_advisory"
    assert finding.message_facts["country_code"] == country_code
    assert "next_action" not in finding.model_dump(mode="json")


def test_lob_advisory_silent_for_domestic_resident_with_no_treaty_country(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """A resident profile with no ``country_of_fiscal_residence`` never claims treaty relief."""
    profile = _resident_profile()
    input_values = {_TIPO_RENTA: "dividend"}

    finding = _m210_convenio_lob_advisory_finding(m210_snapshot, profile, input_values)

    assert finding is None


def test_lob_advisory_silent_when_treaty_country_has_no_matching_override_row(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """A treaty country with no override row for the declared income type does not fire the LOB advisory.

    Zimbabwe (ZW) is not a seeded treaty country at all, and GB has no
    ``interest`` override row (only ``general``). Both are missing-row cases
    owned by the BLOCKING ``m210-convenio-rate-missing`` finding
    (:func:`~application.modelo._m210_rate.resolve_m210_rate`), not the LOB
    advisory: there is no matched treaty benefit to scrutinise.
    """
    zw_profile = _irnr_profile("ZW")
    assert _m210_convenio_lob_advisory_finding(m210_snapshot, zw_profile, {_TIPO_RENTA: "general"}) is None

    gb_profile = _irnr_profile("GB")
    assert _m210_convenio_lob_advisory_finding(m210_snapshot, gb_profile, {_TIPO_RENTA: "interest"}) is None


def test_lob_advisory_silent_when_tipo_renta_is_absent_or_unrecognised(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """An absent or unrecognised ``tipo_renta`` value cannot resolve a treaty override."""
    profile = _irnr_profile("GB")

    assert _m210_convenio_lob_advisory_finding(m210_snapshot, profile, {}) is None
    assert _m210_convenio_lob_advisory_finding(m210_snapshot, profile, {_TIPO_RENTA: "royalty"}) is None
