"""Calculate-path advisory wiring for the capital-goods IVA register port.

These tests exercise the application collector through its inward-owned
register capability. Persistence roundtrips and encrypted-storage behavior
belong to the adapter-profile test package; this module keeps the advisory
behavior independent of that implementation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind
from ....domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    BienInversionDisposal,
    BienInversionIvaRecord,
)
from ....domain.bienes_inversion.vocabulary import BienInversionDisposalRegime, BienInversionKind
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.authored_editions import filing_grade_exercises, filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ..bienes_inversion_advisory import collect_bienes_inversion_regularizacion_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "34d42853-3d81-4c00-b0b9-ad6c27290c49"  # was 'bi-advisory-bucket'
_FILING_YEAR = filing_year_envelope().horizon
_ACQUISITION_YEAR = _FILING_YEAR - 2
"""A mueble acquired two years before the filing year: inside its four-year regularisation window."""


class _InMemoryRegisterRepository:
    """Minimal inward fake for the collector's required read capability."""

    def __init__(self, register: BienesInversionIvaRegister) -> None:
        self._register = register

    def load(self) -> BienesInversionIvaRegister:
        return self._register

    def add(self, record: BienInversionIvaRecord) -> BienesInversionIvaRegister:
        self._register = BienesInversionIvaRegister(records=(*self._register.records, record))
        return self._register


def _revision(modelo: str, *, filing_year: int, period_token: str) -> ModeloRevision:
    return published_snapshot(modelo, filing_year=filing_year, period=period_token).revision


def _record(identifier: str = "bi-maquina", acquisition_year: int = _ACQUISITION_YEAR) -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier=identifier,
        description="Máquina afecta a la actividad",
        acquisition_year=acquisition_year,
        cuota_soportada=Decimal("5000.00"),
        prorrata_inicial_pct=Decimal("80"),
        kind=BienInversionKind.from_registry("mueble"),
        acquisition_ledger_id="ledger-bi-maquina",
    )


def _disposed_record(identifier: str = "bi-furgoneta", disposal_year: int = _FILING_YEAR) -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier=identifier,
        description="Furgoneta transmitida",
        acquisition_year=_ACQUISITION_YEAR,
        cuota_soportada=Decimal("10000.00"),
        prorrata_inicial_pct=Decimal("60"),
        kind=BienInversionKind.from_registry("mueble"),
        acquisition_ledger_id="ledger-bi-furgoneta",
        disposal=BienInversionDisposal(
            year=disposal_year, regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta")
        ),
    )


def test_advisory_fires_on_m303_settlement_period_with_in_window_good() -> None:
    """A registered in-window good raises the advisory on the 4T settlement period.

    The good is acquired two years before the filing year (mueble, 4-year window
    starting the year after acquisition), so the filing year is in-window. This collector supplies no current-year definitive percentage, so
    the good is reported pending it and the advisory still fires
    (no-silent-under-declaration).
    """
    diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
        _revision("303", filing_year=_FILING_YEAR, period_token="4T"),
        modelo="303",
        period_token="4T",
        filing_year=_FILING_YEAR,
        bucket_id=_BUCKET,
        register_repository=_InMemoryRegisterRepository(BienesInversionIvaRegister(records=(_record(),))),
    )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.binding_source is BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    assert "43" in diagnostic.message
    assert "pendiente" in diagnostic.message
    assert diagnostic.legal_refs, "casilla 43's own registry grounding must reach the advisory"


def test_annual_token_is_refused_as_a_modelo_303_settlement_period() -> None:
    """Modelo 303 liquidates quarterly or monthly; ``0A`` belongs to Modelo 390 and is refused."""
    with pytest.raises(RegistryValidationError, match="quarterly or monthly liquidation period"):
        collect_bienes_inversion_regularizacion_diagnostics(
            _revision("303", filing_year=_FILING_YEAR, period_token="4T"),
            modelo="303",
            period_token="0A",
            filing_year=_FILING_YEAR,
            bucket_id=_BUCKET,
            register_repository=_InMemoryRegisterRepository(BienesInversionIvaRegister(records=(_record(),))),
        )


def test_no_advisory_on_mid_year_quarter() -> None:
    """A mid-year quarter (1T) is never a regularisation event (LIVA art. 107.Siete)."""
    diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
        _revision("303", filing_year=_FILING_YEAR, period_token="1T"),
        modelo="303",
        period_token="1T",
        filing_year=_FILING_YEAR,
        bucket_id=_BUCKET,
        register_repository=_InMemoryRegisterRepository(BienesInversionIvaRegister(records=(_record(),))),
    )

    assert diagnostics == ()


def test_no_advisory_for_non_m303_modelo() -> None:
    """Only Modelo 303 declares casilla 43; every other modelo is out of scope."""
    diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
        _revision("390", filing_year=filing_grade_exercises("390")[-1], period_token="0A"),
        modelo="390",
        period_token="0A",
        filing_year=_FILING_YEAR,
        bucket_id=_BUCKET,
        register_repository=_InMemoryRegisterRepository(BienesInversionIvaRegister(records=(_record(),))),
    )

    assert diagnostics == ()


def test_no_advisory_when_register_empty() -> None:
    """An untouched register (no bienes declared) raises no advisory (no noise)."""
    diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
        _revision("303", filing_year=_FILING_YEAR, period_token="4T"),
        modelo="303",
        period_token="4T",
        filing_year=_FILING_YEAR,
        bucket_id=_BUCKET,
        register_repository=_InMemoryRegisterRepository(BienesInversionIvaRegister()),
    )

    assert diagnostics == ()


def test_no_advisory_when_good_is_out_of_window() -> None:
    """A good acquired five years before the filing year (mueble, 4yr window) is out of window."""
    diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
        _revision("303", filing_year=_FILING_YEAR, period_token="4T"),
        modelo="303",
        period_token="4T",
        filing_year=_FILING_YEAR,
        bucket_id=_BUCKET,
        register_repository=_InMemoryRegisterRepository(
            BienesInversionIvaRegister(records=(_record(acquisition_year=_FILING_YEAR - 5),))
        ),
    )

    assert diagnostics == ()


def test_disposal_advisory_fires_on_m303_settlement_period() -> None:
    """A good disposed of during the filing year raises the art-110 disposal advisory.

    Unlike the annual advisory, the disposal advisory always names a concrete
    figure (no pending state): mueble acquired two years earlier, disposed under regla
    1.ª, 3 remaining years, cuota 10.000, prorrata inicial 60% → −2.400,00.
    """
    diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
        _revision("303", filing_year=_FILING_YEAR, period_token="4T"),
        modelo="303",
        period_token="4T",
        filing_year=_FILING_YEAR,
        bucket_id=_BUCKET,
        register_repository=_InMemoryRegisterRepository(BienesInversionIvaRegister(records=(_disposed_record(),))),
    )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.source_kind == "bienes_inversion_regularizacion_transmision"
    assert "43" in diagnostic.message
    assert "-2400.00" in diagnostic.message
    assert diagnostic.legal_refs, "casilla 43's own registry grounding must reach the disposal advisory"


def test_both_advisories_fire_when_the_register_holds_both_kinds() -> None:
    """A register with a non-disposed in-window good AND a disposed good fires both advisories."""
    diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
        _revision("303", filing_year=_FILING_YEAR, period_token="4T"),
        modelo="303",
        period_token="4T",
        filing_year=_FILING_YEAR,
        bucket_id=_BUCKET,
        register_repository=_InMemoryRegisterRepository(
            BienesInversionIvaRegister(records=(_record(), _disposed_record())),
        ),
    )

    assert len(diagnostics) == 2
    source_kinds = {diagnostic.source_kind for diagnostic in diagnostics}
    assert BindingSourceKind.BIENES_INVERSION_REGULARIZACION.value in source_kinds
    assert "bienes_inversion_regularizacion_transmision" in source_kinds


def test_no_disposal_advisory_when_disposal_year_differs_from_filing_year() -> None:
    """A disposal recorded for a different year does not fire the disposal advisory."""
    diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
        _revision("303", filing_year=_FILING_YEAR, period_token="4T"),
        modelo="303",
        period_token="4T",
        filing_year=_FILING_YEAR,
        bucket_id=_BUCKET,
        register_repository=_InMemoryRegisterRepository(
            BienesInversionIvaRegister(records=(_disposed_record(disposal_year=_FILING_YEAR - 1),)),
        ),
    )

    # The filing year is in-window for the (now excluded-from-annual) disposed good's original
    # window, but the good is disposed of the year before, so in_window_records
    # excludes it from the annual path too — nothing fires.
    assert diagnostics == ()
