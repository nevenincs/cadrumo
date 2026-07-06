"""Deferred-source advisory projection for capital-goods IVA regularización."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import BindingSourceKind, Period
from ....core.resources import resources
from ....domain.bienes_inversion import (
    BienesInversionIvaRegister,
    BienInversionDisposal,
    BienInversionDisposalRegime,
    BienInversionIvaRecord,
    BienInversionKind,
)
from ....tests.application_adapter_exports import BienesInversionIvaRegisterRepository
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceContext
from .._bienes_inversion_regularizacion import (
    CASILLA_REGULARIZACION_BIENES_INVERSION,
    BienesInversionRegularizacionSourceResolver,
    build_bienes_inversion_regularizacion_advisory,
    build_bienes_inversion_transmision_advisory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BINDING_ID = "modelo-303-bienes-inversion-regularizacion-casilla-43"
_CURRENT_YEAR_PRORRATA_ID = "iva.prorrata-porcentaje"
_FILING_YEAR = 2024
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "4T")
_BUCKET_ID = "bienes-inversion-regularizacion-source-resolver"


def _context() -> CalculationSourceContext:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=_FILING_YEAR, period="4T")
    return CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        revision=snapshot.revision,
    )


def _register() -> BienesInversionIvaRegister:
    return BienesInversionIvaRegister(
        records=(
            BienInversionIvaRecord(
                identifier="bi-2022-maquina",
                description="Máquina afecta",
                acquisition_year=2022,
                cuota_soportada=Decimal("5000.00"),
                prorrata_inicial_pct=Decimal("80"),
                kind=BienInversionKind.MUEBLE,
            ),
        )
    )


def test_advisory_surfaces_proposed_casilla_43_for_in_window_goods() -> None:
    """An in-window good produces a non-blocking advisory naming the proposed value.

    cuota 5.000, 80→60 (20-point drop), efectuada 4.000 − procedente 3.000 = 1.000,
    ÷5 = 200,00 → proposed casilla 43.
    """
    projection, diagnostic = build_bienes_inversion_regularizacion_advisory(
        _register(),
        regularizacion_year=2024,
        prorrata_definitiva_by_identifier={"bi-2022-maquina": Decimal("60")},
    )
    assert projection.proposed_casilla_43 == Decimal("200.00")
    assert diagnostic is not None
    assert diagnostic.source_kind == BindingSourceKind.BIENES_INVERSION_REGULARIZACION.value
    assert diagnostic.binding_source is BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    assert CASILLA_REGULARIZACION_BIENES_INVERSION in diagnostic.message
    assert "200.00" in diagnostic.message


def test_advisory_fires_even_when_percentage_pending() -> None:
    """No-silent-under-declaration: in-window goods alert even without the percentage.

    The current-year definitive percentage is the deferred input; when it is absent
    the advisory still fires (the operator is told casilla 43 may be due), and the
    good is reported as pending rather than silently dropped.
    """
    projection, diagnostic = build_bienes_inversion_regularizacion_advisory(
        _register(),
        regularizacion_year=2024,
        prorrata_definitiva_by_identifier={},
    )
    assert projection.pending_percentage_count == 1
    assert projection.proposed_casilla_43 == Decimal("0.00")
    assert diagnostic is not None
    assert "pendiente" in diagnostic.message


def test_no_advisory_when_no_in_window_goods() -> None:
    """A register with no in-window goods produces no diagnostic (no noise)."""
    projection, diagnostic = build_bienes_inversion_regularizacion_advisory(
        _register(),
        regularizacion_year=2030,  # outside the 2023-2026 mueble window
        prorrata_definitiva_by_identifier={},
    )
    assert projection.rows == ()
    assert diagnostic is None


def test_source_resolver_projects_repository_register_to_binding_and_bound_casilla(tmp_path: Path) -> None:
    """The live resolver fills the declared M303 binding and casilla 43 from the real register."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = BienesInversionIvaRegisterRepository(objects=profile.repository)
        repository.add(_register().records[0])

        resolution = BienesInversionRegularizacionSourceResolver(
            current_year_values={_CURRENT_YEAR_PRORRATA_ID: Decimal("60")},
            register_repository=repository,
        ).resolve(_context())

    assert resolution.binding_values[_BINDING_ID] == Decimal("200.00")
    assert resolution.bound_inputs_by_casilla_id[CASILLA_REGULARIZACION_BIENES_INVERSION] == Decimal("200.00")
    assert _BINDING_ID not in resolution.unresolved_binding_ids
    assert resolution.diagnostics == ()
    assert BindingSourceKind.BIENES_INVERSION_REGULARIZACION in resolution.owned_sources
    assert resolution.provenance
    assert resolution.provenance[0].binding_source is BindingSourceKind.BIENES_INVERSION_REGULARIZACION


def test_source_resolver_leaves_binding_unresolved_without_current_year_prorrata(tmp_path: Path) -> None:
    """A current-year definitive prorrata gap keeps the M303 binding unresolved."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = BienesInversionIvaRegisterRepository(objects=profile.repository)
        repository.add(_register().records[0])

        resolution = BienesInversionRegularizacionSourceResolver(
            register_repository=repository,
        ).resolve(_context())

    assert _BINDING_ID in resolution.unresolved_binding_ids
    assert _BINDING_ID not in resolution.binding_values
    assert CASILLA_REGULARIZACION_BIENES_INVERSION not in resolution.bound_inputs_by_casilla_id
    assert resolution.diagnostics
    assert resolution.diagnostics[0].binding_source is BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    assert "iva.prorrata-porcentaje" in resolution.diagnostics[0].message


def test_source_resolver_adds_disposal_year_art_110_amount(tmp_path: Path) -> None:
    """A disposal-year record contributes the art. 110 single regularisation amount."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = BienesInversionIvaRegisterRepository(objects=profile.repository)
        repository.add(_disposed_register().records[0])

        resolution = BienesInversionRegularizacionSourceResolver(
            register_repository=repository,
        ).resolve(_context())

    assert resolution.binding_values[_BINDING_ID] == Decimal("-2400.00")
    assert resolution.bound_inputs_by_casilla_id[CASILLA_REGULARIZACION_BIENES_INVERSION] == Decimal("-2400.00")
    assert _BINDING_ID not in resolution.unresolved_binding_ids
    assert resolution.diagnostics == ()


def test_source_resolver_resolves_empty_register_to_explicit_zero(tmp_path: Path) -> None:
    """An empty real register produces an explicit zero for the declared M303 binding."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = BienesInversionIvaRegisterRepository(objects=profile.repository)

        resolution = BienesInversionRegularizacionSourceResolver(
            register_repository=repository,
        ).resolve(_context())

    assert resolution.binding_values[_BINDING_ID] == Decimal("0.00")
    assert resolution.bound_inputs_by_casilla_id[CASILLA_REGULARIZACION_BIENES_INVERSION] == Decimal("0.00")
    assert resolution.unresolved_binding_ids == ()
    assert resolution.diagnostics == ()


def _disposed_register() -> BienesInversionIvaRegister:
    return BienesInversionIvaRegister(
        records=(
            BienInversionIvaRecord(
                identifier="bi-2022-furgoneta",
                description="Furgoneta de reparto afecta",
                acquisition_year=2022,
                cuota_soportada=Decimal("10000.00"),
                prorrata_inicial_pct=Decimal("60"),
                kind=BienInversionKind.MUEBLE,
                disposal=BienInversionDisposal(year=2024, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
            ),
        )
    )


def test_transmision_advisory_surfaces_proposed_casilla_43_for_disposed_good() -> None:
    """A disposed good always produces a concrete advisory, never a pending state.

    Mueble acquired 2022 (window 2023-2026), disposed 2024 under regla 1.ª: 3
    remaining years, cuota 10.000, prorrata inicial 60% → efectuada 6.000,00 −
    imputada (100%) 10.000,00 = −4.000,00 × 3 ÷ 5 = −2.400,00.
    """
    projection, diagnostic = build_bienes_inversion_transmision_advisory(
        _disposed_register(),
        disposal_year=2024,
    )
    assert projection.proposed_casilla_43 == Decimal("-2400.00")
    assert diagnostic is not None
    assert diagnostic.source_kind == "bienes_inversion_regularizacion_transmision"
    assert CASILLA_REGULARIZACION_BIENES_INVERSION in diagnostic.message
    assert "-2400.00" in diagnostic.message


def test_transmision_advisory_applies_supplied_cap() -> None:
    """The regla-1.ª cap is passed through when the caller supplies the cuota devengada."""
    projection, diagnostic = build_bienes_inversion_transmision_advisory(
        _disposed_register(),
        disposal_year=2024,
        cuota_devengada_entrega_by_identifier={"bi-2022-furgoneta": Decimal("1500.00")},
    )
    assert projection.proposed_casilla_43 == Decimal("-1500.00")
    assert diagnostic is not None
    assert "-1500.00" in diagnostic.message


def test_no_transmision_advisory_when_no_disposal_in_year() -> None:
    """A register with no disposal recorded for the year produces no diagnostic."""
    projection, diagnostic = build_bienes_inversion_transmision_advisory(
        _disposed_register(),
        disposal_year=2023,  # the recorded disposal is 2024
    )
    assert projection.rows == ()
    assert diagnostic is None
