"""Calculate-path advisory wiring for the annual prorrata-general regularización.

Exercises :func:`~application.modelo.prorrata_regularizacion_advisory.collect_prorrata_regularizacion_diagnostics`
against a REAL registry-loaded Modelo 303 revision and a REAL encrypted
:class:`~application.calculations.CalculationObservationRepository` inside a genuine bucket
runtime (``isolated_runtime_profile``) — no mocks, no stubs. The pure LIVA arts. 104-105 math
itself is proven in ``domain/iva/tests/test_prorrata_regularizacion.py`` and the pure advisory
projection in ``application/calculations/tests/test_prorrata_regularizacion.py``; this module
proves the collector's advisories are wired into the calculate-path fan-out and that it no
longer computes a regularisation of its own beside the source resolver.

See Also:
    :mod:`~application.modelo.prorrata_regularizacion_advisory`
        Collector under test for the calculate-path prorrata advisory fan-out.
    :func:`~application.calculations._prorrata_regularizacion.build_prorrata_missing_provisional_advisory`
        Pure missing-carry builder used by the mid-year unresolved-register
        regression.
    :func:`~application.calculations._prorrata_regularizacion.derive_prorrata_applicability`
        Fail-closed-to-visible projection that decides whether prorrata applies.
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`
        Bucket-persisted register input for active-prorrata coverage.
    :class:`~application.calculations.CalculationObservationRepository`
        Real encrypted observation store used for prior-year definitive carry
        lookup.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from .....application.modelo.prorrata_regularizacion_advisory import collect_prorrata_regularizacion_diagnostics
from .....core.aggregation import BindingSourceKind
from .....core.casilla_id import validated_casilla_id
from .....core.modelo import Modelo
from .....core.observed_header_fact import ObservedHeaderFact
from .....core.prorrata_register import ProrrataRegisterRegime
from .....domain.calculations.registry.authority import IndexedRegistryAuthority, bundled_indexed_authority
from .....domain.calculations.registry.binding_targets import casillas_by_binding
from .....domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_RESULTADO_CASILLA as M303_RESULTADO_CASILLA,
)
from .....domain.calculations.registry.prorrata_regularizacion_bindings import (
    ProrrataRegularizacionOutput,
    ProrrataRegularizacionProvider,
)
from .....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    revision_id_for_observation,
)
from .....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..bienes_inversion import BienesInversionIvaRegisterRepository
from ..calculation_observations import CalculationObservationRepository
from ..invoices import InvoiceCatalogueRepository
from ..prorrata_register import ProrrataRegisterRepository
from ..transactions import TransactionCatalogueRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "108e9631-8e8f-4a81-840f-39ba3e07a70b"
_YEAR = 2026
_PRIOR_YEAR = 2025
_SETTLEMENT_PERIOD_CODE = "4T"
_FIRST_PERIOD_CODE = "1T"

_VOLUMEN_TOTAL_ID = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_VOLUMEN_CON_DERECHO_ID = validated_casilla_id("iva.prorrata-volumen-con-derecho", surface="test casilla id")
_PORCENTAJE_ID = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")
_CUOTA_DEDUCIBLE_TOTAL_ID = validated_casilla_id("iva.cuota-deducible-total", surface="test casilla id")


def _revision(*, period: str = "4T"):
    snapshot = published_authority_operation().snapshot(Modelo("303").value, filing_year=_YEAR, period=period)
    return snapshot.revision


def _seed_prior_year_percentage(obs_repo: CalculationObservationRepository, *, percentage: Decimal) -> None:
    observation = registry_grounded_modelo_observation(
        modelo=Modelo("303").value,
        filing_year=_PRIOR_YEAR,
        period="4T",
        casilla_values={_PORCENTAJE_ID: percentage, M303_RESULTADO_CASILLA: Decimal("1")},
    )
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            observation,
            source_kind="aeat_sede_justificante",
            source_headers=(
                ObservedHeaderFact(
                    header_key="filing.result_disposition",
                    value="I",
                    source_artefact_kind="submitted_file",
                    source_locator="test:prorrata-prior-declaration-type",
                ),
            ),
            stamped_revision_id=revision_id_for_observation(observation),
        ),
    )


_SETTLEMENT_VALUES = {
    _VOLUMEN_TOTAL_ID: Decimal("100000"),
    _VOLUMEN_CON_DERECHO_ID: Decimal("80000"),
    _PORCENTAJE_ID: Decimal("80"),
    _CUOTA_DEDUCIBLE_TOTAL_ID: Decimal("20000.00"),
}


def _collect_settlement_diagnostics():
    """Collect the settlement-period diagnostics for an 80 percent definitive ratio over 100000 of volume."""
    return collect_prorrata_regularizacion_diagnostics(
        _revision(),
        _SETTLEMENT_VALUES,
        modelo=Modelo("303").value,
        period_token=_SETTLEMENT_PERIOD_CODE,
        filing_year=_YEAR,
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET),
        invoice_reader=InvoiceCatalogueRepository(bucket_id=_BUCKET),
        bienes_inversion_repository=BienesInversionIvaRegisterRepository(bucket_id=_BUCKET),
    )


def test_settlement_collector_does_not_recompute_the_regularisation(tmp_path: Path) -> None:
    """The regularisation box belongs to the source resolver; the collector adds no second figure.

    Volumen total 100.000, con derecho 80.000 (prorrata applies) and a prior
    definitive 90% against the current 80% once produced a casilla-44 advisory
    computed from the year's NET deducible total -- a second, divergent value.
    The resolver now owns the box and refuses visibly, so the collector stays
    silent here.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _seed_prior_year_percentage(
            CalculationObservationRepository(objects=profile.repository),
            percentage=Decimal("90"),
        )

        diagnostics = _collect_settlement_diagnostics()

    assert diagnostics == ()


def test_collector_uses_the_supplied_pinned_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A calculate-path collector does not lease a second authority generation."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET),
        bundled_indexed_authority().operation() as operation,
    ):
        revision = operation.snapshot(Modelo("303").value, filing_year=_YEAR, period="4T").revision

        def unexpected_authority(_authority: IndexedRegistryAuthority) -> None:
            raise AssertionError("prorrata advisory opened another registry authority")

        with monkeypatch.context() as patch:
            patch.setattr(IndexedRegistryAuthority, "operation", unexpected_authority)
            diagnostics = collect_prorrata_regularizacion_diagnostics(
                revision,
                _SETTLEMENT_VALUES,
                modelo="303",
                period_token=_SETTLEMENT_PERIOD_CODE,
                filing_year=_YEAR,
                prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET),
                transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET),
                invoice_reader=InvoiceCatalogueRepository(bucket_id=_BUCKET),
                bienes_inversion_repository=BienesInversionIvaRegisterRepository(bucket_id=_BUCKET),
                operation=operation,
            )

    assert diagnostics == ()


def test_no_advisory_when_no_sin_derecho_operations(tmp_path: Path) -> None:
    """Prorrata does not apply (100% con-derecho) -> no advisory noise."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        casilla_values = {
            _VOLUMEN_TOTAL_ID: Decimal("100000"),
            _VOLUMEN_CON_DERECHO_ID: Decimal("100000"),
            _PORCENTAJE_ID: Decimal("100"),
            _CUOTA_DEDUCIBLE_TOTAL_ID: Decimal("20000.00"),
        }
        diagnostics = collect_prorrata_regularizacion_diagnostics(
            _revision(),
            casilla_values,
            modelo=Modelo("303").value,
            period_token=_SETTLEMENT_PERIOD_CODE,
            filing_year=_YEAR,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET),
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET),
            invoice_reader=InvoiceCatalogueRepository(bucket_id=_BUCKET),
            bienes_inversion_repository=BienesInversionIvaRegisterRepository(bucket_id=_BUCKET),
        )

    assert diagnostics == ()


def test_no_advisory_on_mid_year_quarter(tmp_path: Path) -> None:
    """A mid-year quarter (1T) is never a regularisation event (LIVA art. 105.Cuatro)."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        casilla_values = {
            _VOLUMEN_TOTAL_ID: Decimal("100000"),
            _VOLUMEN_CON_DERECHO_ID: Decimal("80000"),
            _PORCENTAJE_ID: Decimal("80"),
            _CUOTA_DEDUCIBLE_TOTAL_ID: Decimal("20000.00"),
        }
        diagnostics = collect_prorrata_regularizacion_diagnostics(
            _revision(),
            casilla_values,
            modelo=Modelo("303").value,
            period_token=_FIRST_PERIOD_CODE,
            filing_year=_YEAR,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET),
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET),
            invoice_reader=InvoiceCatalogueRepository(bucket_id=_BUCKET),
            bienes_inversion_repository=BienesInversionIvaRegisterRepository(bucket_id=_BUCKET),
        )

    assert diagnostics == ()


def test_mid_year_active_prorrata_without_provisional_emits_missing_carry(tmp_path: Path) -> None:
    """An active general-prorrata register entry with no ladder value is visible in 1T."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        ProrrataRegisterRepository(bucket_id=_BUCKET, objects=profile.repository).save(
            ProrrataRegister(
                entries=(
                    ProrrataRegisterEntry(
                        ejercicio=_YEAR,
                        regime=ProrrataRegisterRegime.from_registry("general"),
                        especial_transition=None,
                        source_registry_snapshot_refs=(),
                    ),
                ),
            ),
        )

        diagnostics = collect_prorrata_regularizacion_diagnostics(
            _revision(period="1T"),
            {},
            modelo=Modelo("303").value,
            period_token=_FIRST_PERIOD_CODE,
            filing_year=_YEAR,
            bucket_id=_BUCKET,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET),
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET),
            invoice_reader=InvoiceCatalogueRepository(bucket_id=_BUCKET),
            bienes_inversion_repository=BienesInversionIvaRegisterRepository(bucket_id=_BUCKET),
        )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    revision = _revision(period="1T")
    prorrata_binding = next(
        binding
        for binding in revision.bindings
        if binding.source is BindingSourceKind.PRORRATA_REGULARIZACION
        and isinstance(binding.provider, ProrrataRegularizacionProvider)
        and binding.provider.regularizacion_output is ProrrataRegularizacionOutput.MODELO_303_CASILLA_44
    )
    assert diagnostic.casilla_id in casillas_by_binding(revision)[prorrata_binding.id]
    assert "definitiva del ejercicio anterior" in diagnostic.message
    assert "por defecto" in diagnostic.message


def test_no_advisory_for_non_m303_modelo(tmp_path: Path) -> None:
    """Only Modelo 303 declares the prorrata semantic roles; every other modelo is silent."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        diagnostics = collect_prorrata_regularizacion_diagnostics(
            _revision(),
            {},
            modelo=Modelo("130").value,
            period_token=_SETTLEMENT_PERIOD_CODE,
            filing_year=_YEAR,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET),
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET),
            invoice_reader=InvoiceCatalogueRepository(bucket_id=_BUCKET),
            bienes_inversion_repository=BienesInversionIvaRegisterRepository(bucket_id=_BUCKET),
        )

    assert diagnostics == ()
