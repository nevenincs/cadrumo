"""Modelo 210 annual grouped-renta calculation through the real persistence path."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core import M210PayerMode, Period
from ....core.resources import resources
from ....domain.modelos import Modelo210AgrupacionRentaRow, ModeloError
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...tests import register_wizard_catalogue
from .._calculation_actions import calculate_modelo_revision
from .._m303_regimen_simplificado_scope import active_taxpayer_profile
from .._work_lifecycle import create_work_unit
from .._work_plazo import calculated_m210_plazo_notice

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "0f629c46-1dc8-4cb1-8d02-aa0ee4f45a42"
_CLOCK = datetime(2026, 7, 10, 9, 0, 0, tzinfo=UTC)
_FILING_YEAR = 2025


__all__ = ["register_wizard_catalogue"]


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        _seed_minimal_profile(runtime.repository)
        yield


def _seed_minimal_profile(objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="activities.description", value="Spanish rental income"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        )
    )


def test_annual_grouped_rentas_persist_without_becoming_a_second_arithmetic_path(tmp_path: Path) -> None:
    """Real 0A calculation retains compatible rows but still uses manual casilla 5.

    The rows total EUR 300 while the declared ``rendimientos_integros`` is EUR
    900. A result that followed the rows rather than the registry formula's
    manual casilla input would therefore fail this integration proof.
    """
    rows = (
        Modelo210AgrupacionRentaRow(
            source_id="manual-renta-jan",
            tipo_renta_code="01",
            importe=Decimal("100.00"),
            tipo_gravamen=Decimal("0.24"),
            pagador_mode=M210PayerMode.SINGLE_PAYER,
            pagador_id="ES-PAGADOR-1",
            deriva_de_bien_derecho=True,
            bien_derecho_id="ES-INMUEBLE-1",
        ),
        Modelo210AgrupacionRentaRow(
            source_id="manual-renta-feb",
            tipo_renta_code="01",
            importe=Decimal("200.00"),
            tipo_gravamen=Decimal("0.24"),
            pagador_mode=M210PayerMode.SINGLE_PAYER,
            pagador_id="ES-PAGADOR-1",
            deriva_de_bien_derecho=True,
            bien_derecho_id="ES-INMUEBLE-1",
        ),
    )

    with _secure_backend(tmp_path):
        snapshot = resources().modelos.authority.snapshot("210", filing_year=_FILING_YEAR, period="0A")
        work_repo = WorkUnitCatalogueRepository()
        calculation_repo = CalculationRevisionCatalogueRepository()
        event_repo = BucketEventHistoryRepository()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="210",
            filing_year=_FILING_YEAR,
            period=Period.from_year_and_code(_FILING_YEAR, "0A"),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_CLOCK,
        )

        with pytest.raises(ModeloError):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={"rendimientos_integros": Decimal("900.00")},
                text_casilla_inputs={"tipo_renta": "general"},
                m210_official_tipo_renta_code="35",
                detail_rows=rows,
                work_unit_repository=work_repo,
                calculation_repository=calculation_repo,
                bucket_event_repository=event_repo,
                clock=_CLOCK,
            )

        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={"rendimientos_integros": Decimal("900.00")},
            text_casilla_inputs={"tipo_renta": "general"},
            m210_official_tipo_renta_code="01",
            detail_rows=rows,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            bucket_event_repository=event_repo,
            clock=_CLOCK,
        )
        plazo_notice = calculated_m210_plazo_notice(
            work_unit=work_unit,
            revision=revision,
            workflow_profile=active_taxpayer_profile(work_unit),
        )

    assert revision.detail_rows == rows
    assert revision.m210_official_tipo_renta_code == "01"
    assert revision.casilla_values["base_imponible"] == Decimal("900.00")
    assert plazo_notice is not None
    assert plazo_notice.code == "modelo.work.m210.plazo_resolved"
    assert plazo_notice.context == {
        "modelo": "210",
        "filing_year": "2025",
        "period": "0A",
        "resultado": "I",
        "tipo_renta_code": "01",
        "deadline_window_id": "modelo-210-2025-0a-arrendamiento-ingreso",
        "opens_on": "2026-04-01",
        "closes_on": "2026-04-20",
        "legal_refs": "orden-eha-3316-2010:art-5",
        "source_refs": "aeat-modelo-210-procedure, boe-modelo-210-base-order",
    }
