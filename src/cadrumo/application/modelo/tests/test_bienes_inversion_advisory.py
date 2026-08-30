"""Calculate-path advisory wiring for the capital-goods IVA regularización register.

Exercises :func:`~cadrumo.application.modelo._bienes_inversion_advisory.collect_bienes_inversion_regularizacion_diagnostics`
against a REAL encrypted register persisted through
:class:`~cadrumo.adapters.persistence.profile.bienes_inversion.BienesInversionIvaRegisterRepository`
inside a genuine bucket runtime (``isolated_runtime_profile``) — no mocks, no
stubs. The pure art-109 math itself is proven in
``domain/bienes_inversion/tests/test_regularizacion.py`` and the pure advisory
projection in
``application/calculations/tests/test_bienes_inversion_regularizacion.py``; this
module proves the register is actually READ on the live calculate path, which
is the integration point between the persisted register and
``_calculation_diagnostics``.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from ....core.aggregation import BindingSourceKind
from ....domain.bienes_inversion import (
    BienInversionDisposal,
    BienInversionDisposalRegime,
    BienInversionIvaRecord,
    BienInversionKind,
)
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import ModeloRevision
from ....tests.secure_sql import isolated_runtime_profile
from .._bienes_inversion_advisory import collect_bienes_inversion_regularizacion_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "34d42853-3d81-4c00-b0b9-ad6c27290c49"  # was 'bi-advisory-bucket'


def _revision(modelo: str, *, filing_year: int, period_token: str) -> ModeloRevision:
    return bundled_authority().snapshot(modelo, filing_year=filing_year, period=period_token).revision


def _record(identifier: str = "bi-2022-maquina") -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier=identifier,
        description="Máquina afecta a la actividad",
        acquisition_year=2022,
        cuota_soportada=Decimal("5000.00"),
        prorrata_inicial_pct=Decimal("80"),
        kind=BienInversionKind.MUEBLE,
        acquisition_ledger_id="ledger-bi-2022-maquina",
    )


def _disposed_record(identifier: str = "bi-2022-furgoneta", disposal_year: int = 2024) -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier=identifier,
        description="Furgoneta transmitida",
        acquisition_year=2022,
        cuota_soportada=Decimal("10000.00"),
        prorrata_inicial_pct=Decimal("60"),
        kind=BienInversionKind.MUEBLE,
        acquisition_ledger_id="ledger-bi-2022-furgoneta",
        disposal=BienInversionDisposal(year=disposal_year, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
    )


def test_advisory_fires_on_m303_settlement_period_with_in_window_good(tmp_path: Path) -> None:
    """A registered in-window good raises the advisory on the 4T settlement period.

    The good is acquired in 2022 (mueble, 4-year window: 2023-2026), so 2024 is
    in-window. This collector supplies no current-year definitive percentage, so
    the good is reported pending it and the advisory still fires
    (no-silent-under-declaration).
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        BienesInversionIvaRegisterRepository(objects=profile.repository).add(_record())

        diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
            _revision("303", filing_year=2024, period_token="4T"),
            modelo="303",
            period_token="4T",
            filing_year=2024,
            bucket_id=_BUCKET,
        )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.binding_source is BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    assert "43" in diagnostic.message
    assert "pendiente" in diagnostic.message
    assert diagnostic.legal_refs, "casilla 43's own registry grounding must reach the advisory"


def test_advisory_fires_on_m303_annual_period(tmp_path: Path) -> None:
    """The annual period token (``0A``) is also a valid settlement period."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        BienesInversionIvaRegisterRepository(objects=profile.repository).add(_record())

        diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
            # 0A resolves no registered M303 revision on its own (a real
            # quarterly-filer revision, selected on any of its valid quarterly
            # tokens); the collector's own period-token handling is a pure
            # calendar check independent of which revision variant is loaded.
            _revision("303", filing_year=2024, period_token="4T"),
            modelo="303",
            period_token="0A",
            filing_year=2024,
            bucket_id=_BUCKET,
        )

    assert len(diagnostics) == 1


def test_no_advisory_on_mid_year_quarter(tmp_path: Path) -> None:
    """A mid-year quarter (1T) is never a regularisation event (LIVA art. 107.Siete)."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        BienesInversionIvaRegisterRepository(objects=profile.repository).add(_record())

        diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
            _revision("303", filing_year=2024, period_token="1T"),
            modelo="303",
            period_token="1T",
            filing_year=2024,
            bucket_id=_BUCKET,
        )

    assert diagnostics == ()


def test_no_advisory_for_non_m303_modelo(tmp_path: Path) -> None:
    """Only Modelo 303 declares casilla 43; every other modelo is out of scope."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        BienesInversionIvaRegisterRepository(objects=profile.repository).add(_record())

        diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
            _revision("390", filing_year=2024, period_token="0A"),
            modelo="390",
            period_token="0A",
            filing_year=2024,
            bucket_id=_BUCKET,
        )

    assert diagnostics == ()


def test_no_advisory_when_register_empty(tmp_path: Path) -> None:
    """An untouched register (no bienes declared) raises no advisory (no noise)."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
            _revision("303", filing_year=2024, period_token="4T"),
            modelo="303",
            period_token="4T",
            filing_year=2024,
            bucket_id=_BUCKET,
        )

    assert diagnostics == ()


def test_no_advisory_when_good_is_out_of_window(tmp_path: Path) -> None:
    """A good acquired in 2022 (mueble, 4yr window through 2026) is out of window by 2030."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        BienesInversionIvaRegisterRepository(objects=profile.repository).add(_record())

        diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
            _revision("303", filing_year=2030, period_token="4T"),
            modelo="303",
            period_token="4T",
            filing_year=2030,
            bucket_id=_BUCKET,
        )

    assert diagnostics == ()


def test_disposal_advisory_fires_on_m303_settlement_period(tmp_path: Path) -> None:
    """A good disposed of during the filing year raises the art-110 disposal advisory.

    Unlike the annual advisory, the disposal advisory always names a concrete
    figure (no pending state): mueble acquired 2022, disposed 2024 under regla
    1.ª, 3 remaining years, cuota 10.000, prorrata inicial 60% → −2.400,00.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        BienesInversionIvaRegisterRepository(objects=profile.repository).add(_disposed_record())

        diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
            _revision("303", filing_year=2024, period_token="4T"),
            modelo="303",
            period_token="4T",
            filing_year=2024,
            bucket_id=_BUCKET,
        )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.source_kind == "bienes_inversion_regularizacion_transmision"
    assert "43" in diagnostic.message
    assert "-2400.00" in diagnostic.message
    assert diagnostic.legal_refs, "casilla 43's own registry grounding must reach the disposal advisory"


def test_both_advisories_fire_when_the_register_holds_both_kinds(tmp_path: Path) -> None:
    """A register with a non-disposed in-window good AND a disposed good fires both advisories."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        repo = BienesInversionIvaRegisterRepository(objects=profile.repository)
        repo.add(_record())
        repo.add(_disposed_record())

        diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
            _revision("303", filing_year=2024, period_token="4T"),
            modelo="303",
            period_token="4T",
            filing_year=2024,
            bucket_id=_BUCKET,
        )

    assert len(diagnostics) == 2
    source_kinds = {diagnostic.source_kind for diagnostic in diagnostics}
    assert BindingSourceKind.BIENES_INVERSION_REGULARIZACION.value in source_kinds
    assert "bienes_inversion_regularizacion_transmision" in source_kinds


def test_no_disposal_advisory_when_disposal_year_differs_from_filing_year(tmp_path: Path) -> None:
    """A disposal recorded for a different year does not fire the disposal advisory."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        BienesInversionIvaRegisterRepository(objects=profile.repository).add(_disposed_record(disposal_year=2023))

        diagnostics = collect_bienes_inversion_regularizacion_diagnostics(
            _revision("303", filing_year=2024, period_token="4T"),
            modelo="303",
            period_token="4T",
            filing_year=2024,
            bucket_id=_BUCKET,
        )

    # 2024 is in-window for the (now excluded-from-annual) disposed good's original
    # window, but the good is disposed of in 2023 (before 2024), so in_window_records
    # excludes it from the annual path too — nothing fires.
    assert diagnostics == ()
