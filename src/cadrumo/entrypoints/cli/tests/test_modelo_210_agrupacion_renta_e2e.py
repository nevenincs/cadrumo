"""Modelo 210 annual grouped-renta calculation through the real persistence path."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts,
    seed_test_profile_record,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.file_flow_test_support import calculation_ports_for_test
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.calculate_input import WorkCalculateInputBundle, calculate_modelo_work_revision
from ....application.modelo.calculation_actions import calculate_modelo_revision
from ....application.modelo.m303_regimen_simplificado_scope import active_taxpayer_profile
from ....application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....application.modelo.work_plazo import calculated_m210_plazo_resolution
from ....application.tests.wizard_catalogue_fixtures import register_wizard_catalogue
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.modelos.errors import ModeloError
from ....domain.modelos.row_models import Modelo210AgrupacionRentaRow
from ....domain.transactions.m210_income_classification import resolve_m210_payer_mode
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ....tests.cli_envelope import unwrap_envelope_notices
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "0f629c46-1dc8-4cb1-8d02-aa0ee4f45a42"


def _authored_m210_annual_filing_year() -> int:
    """Return the newest supported year whose annual Modelo 210 revision covers that year."""
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no supported filing years"
    for year in sorted(support.years, reverse=True):
        valid_to = published_snapshot("210", filing_year=year, period="0A").revision.valid_to
        if valid_to is None or valid_to.year >= year:
            return year
    raise AssertionError("no supported filing year has an authored annual Modelo 210 revision")


_FILING_YEAR = _authored_m210_annual_filing_year()
# Records are stamped inside the income year the declaration covers.
_CLOCK = datetime(_FILING_YEAR, 7, 10, 9, 0, 0, tzinfo=UTC)


def _declared_window_context(kind: str) -> dict[str, str]:
    """Return the notice fields of the annual window the registry declares for the filing year.

    The dates and their grounding change with the governing order, so the
    expectation is the declaration itself: the notice must carry exactly the
    window that applies to the keyed filing year.
    """
    window_id = f"modelo-210-{_FILING_YEAR}-0a-{kind}"
    window = published_snapshot("210", filing_year=_FILING_YEAR, period="0A").deadline_windows[window_id]
    return {
        "deadline_window_id": window_id,
        "opens_on": window.opens_on.isoformat(),
        "closes_on": window.closes_on.isoformat(),
        "legal_refs": ", ".join(window.legal_refs),
        "source_refs": ", ".join(window.source_refs),
    }


# Modelo 210 is the IRNR self-assessment of a taxpayer without a permanent
# establishment, so only a non-resident profile may open its work.
_NON_RESIDENT_FACTS = {
    "taxpayer_type.fiscal_residency": "non_resident_irnr",
    "taxpayer_type.country_of_fiscal_residence": "GB",
    "taxpayer_type.representante_fiscal_nif": "12345678Z",
    "taxpayer_type.representante_fiscal_nombre": "Test Representative",
}


__all__ = ["register_wizard_catalogue"]


@contextmanager
def _secure_backend(tmp_path: Path) -> Generator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        _seed_minimal_profile(runtime.repository)
        yield


def _seed_minimal_profile(objects: SecureObjectRepository) -> None:
    """Seed the modelo readiness baseline through the canonical seeder.

    The fact tuple this used to restate lived here in four identical
    copies. It is declared once in the storage profile-capsule test support
    now, because
    the readiness gate decides what modelo work may run at all and every
    copy was another place for that answer to drift.
    """
    del objects
    create_context, _decode_context = profile_authority_contexts()
    facts = (
        *(fact for fact in MODELO_READY_PROFILE_FACTS if fact.path not in _NON_RESIDENT_FACTS),
        *(UserProfileFact(path=path, value=value) for path, value in _NON_RESIDENT_FACTS.items()),
    )
    seed_test_profile_record(
        create_user_profile_record(
            context=create_context,
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=str(_BUCKET_ID),
            facts=facts,
            created_at=_CLOCK,
            updated_at=_CLOCK,
        )
    )


def _verify_plazo_notices(calculation_revision_id: str) -> tuple[dict[str, object], ...]:
    result = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "verify", calculation_revision_id],
    )
    assert result.exit_code in {0, 1}, result.output
    notices: list[dict[str, object]] = []
    for notice in unwrap_envelope_notices(result.output):
        if notice["code"] == "modelo.work.m210.plazo_resolved":
            notices.append(dict(notice))
    return tuple(notices)


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
            pagador_mode=resolve_m210_payer_mode("single_payer", effective_date=_CLOCK.date()),
            pagador_id="ES-PAGADOR-1",
            deriva_de_bien_derecho=True,
            bien_derecho_id="ES-INMUEBLE-1",
        ),
        Modelo210AgrupacionRentaRow(
            source_id="manual-renta-feb",
            tipo_renta_code="01",
            importe=Decimal("200.00"),
            tipo_gravamen=Decimal("0.24"),
            pagador_mode=resolve_m210_payer_mode("single_payer", effective_date=_CLOCK.date()),
            pagador_id="ES-PAGADOR-1",
            deriva_de_bien_derecho=True,
            bien_derecho_id="ES-INMUEBLE-1",
        ),
    )

    with _secure_backend(tmp_path):
        snapshot = published_snapshot("210", filing_year=_FILING_YEAR, period="0A")
        work_repo = WorkUnitCatalogueRepository()
        calculation_repo = CalculationRevisionCatalogueRepository()
        event_repo = BucketEventHistoryRepository()
        with bundled_indexed_authority().operation() as operation:
            work_unit = create_work_unit(
                bucket_id=_BUCKET_ID,
                modelo="210",
                filing_year=_FILING_YEAR,
                period=Period.from_year_and_code(_FILING_YEAR, "0A"),
                revision_id=snapshot.revision.id,
                ports=WorkLifecyclePorts(work_unit_repository=work_repo, bucket_event_repository=event_repo),
                operation=operation,
                clock=_CLOCK,
            )

        with (
            pytest.raises(ModeloError),
            calculation_ports_for_test(
                bucket_id=_BUCKET_ID,
                work_unit_repository=work_repo,
                calculation_repository=calculation_repo,
                bucket_event_repository=event_repo,
            ) as _calculation_ports_131,
        ):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={"rendimientos_integros": Decimal("900.00")},
                text_casilla_inputs={"tipo_renta": "general"},
                m210_official_tipo_renta_code="35",
                detail_rows=rows,
                ports=_calculation_ports_131,
                clock=_CLOCK,
            )
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            bucket_event_repository=event_repo,
        ) as _calculation_ports_147:
            revision = calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={"rendimientos_integros": Decimal("900.00")},
                text_casilla_inputs={"tipo_renta": "general"},
                m210_official_tipo_renta_code="01",
                detail_rows=rows,
                ports=_calculation_ports_147,
                clock=_CLOCK,
            )
        plazo_resolution = calculated_m210_plazo_resolution(
            work_unit=work_unit,
            revision=revision,
            workflow_profile=active_taxpayer_profile(work_unit),
        )

    assert revision.detail_rows == rows
    assert revision.m210_official_tipo_renta_code == "01"
    assert revision.casilla_values["base_imponible"] == Decimal("900.00")
    assert plazo_resolution is not None
    assert plazo_resolution.closes_on
    assert plazo_resolution.context == {
        "modelo": "210",
        "filing_year": str(_FILING_YEAR),
        "period": "0A",
        "resultado": "I",
        "tipo_renta_code": "01",
        **_declared_window_context("arrendamiento-ingreso"),
    }


@pytest.mark.parametrize(
    ("tipo_renta_code", "casilla_inputs", "text_tipo_renta", "expected_resultado", "expected_window"),
    [
        pytest.param(
            "01",
            {"rendimientos_integros": Decimal("900.00")},
            "general",
            "I",
            "arrendamiento-ingreso",
            id="arrendamiento-01-ingreso",
        ),
        pytest.param(
            "35",
            {"rendimientos_integros": Decimal("900.00")},
            "general",
            "I",
            "arrendamiento-ingreso",
            id="arrendamiento-35-ingreso",
        ),
        pytest.param(
            "01",
            {"rendimientos_integros": Decimal("0.00")},
            "general",
            "N",
            "cuota-cero",
            id="cuota-cero",
        ),
        pytest.param(
            "01",
            {
                "rendimientos_integros": Decimal("100.00"),
                "retencion_practicada": Decimal("100.00"),
            },
            "general",
            "D",
            "devolucion",
            id="devolver",
        ),
    ],
)
def test_calculate_and_verify_project_exactly_one_grounded_qualified_plazo_notice(
    tmp_path: Path,
    tipo_renta_code: str,
    casilla_inputs: dict[str, Decimal],
    text_tipo_renta: str,
    expected_resultado: str,
    expected_window: str,
) -> None:
    """Real calculation and verification retain one identical grounded notice."""
    with _secure_backend(tmp_path):
        snapshot = published_snapshot("210", filing_year=_FILING_YEAR, period="0A")
        work_repo = WorkUnitCatalogueRepository()
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=work_repo,
        ) as _calculation_ports_210:
            work_unit = create_work_unit(
                bucket_id=_BUCKET_ID,
                modelo="210",
                filing_year=_FILING_YEAR,
                period=Period.from_year_and_code(_FILING_YEAR, "0A"),
                revision_id=snapshot.revision.id,
                ports=_calculation_ports_210.work_lifecycle_ports,
                operation=_calculation_ports_210.operation,
                clock=_CLOCK,
            )
            calculation_result = calculate_modelo_work_revision(
                work_unit_id=work_unit.work_unit_id,
                actor="operator",
                inputs=WorkCalculateInputBundle.build(
                    casilla_inputs=casilla_inputs,
                    text_casilla_inputs={"tipo_renta": text_tipo_renta},
                    m210_official_tipo_renta_code=tipo_renta_code,
                    binding_values={},
                    enum_binding_values={},
                    relation_values={},
                    detail_rows=(
                        Modelo210AgrupacionRentaRow(
                            source_id=f"plazo-{tipo_renta_code}",
                            tipo_renta_code=tipo_renta_code,
                            importe=casilla_inputs["rendimientos_integros"],
                            tipo_gravamen=Decimal("0.24"),
                            pagador_mode=resolve_m210_payer_mode(
                                "multiple_payers_code_35" if tipo_renta_code == "35" else "single_payer",
                                effective_date=_CLOCK.date(),
                            ),
                            pagador_id=None if tipo_renta_code == "35" else "ES-PAGADOR-1",
                            deriva_de_bien_derecho=True,
                            bien_derecho_id="ES-INMUEBLE-1",
                        ),
                    ),
                    borrador_snapshot_id=None,
                ),
                ports=_calculation_ports_210,
            )
            calculate_notices = tuple(resolution for resolution in calculation_result.plazo_resolutions)
            verify_notices = _verify_plazo_notices(calculation_result.revision.calculation_revision_id)

    assert len(calculate_notices) == len(verify_notices) == 1
    context = calculate_notices[0].context
    assert context is not None
    assert context == {
        "modelo": "210",
        "filing_year": str(_FILING_YEAR),
        "period": "0A",
        "resultado": expected_resultado,
        "tipo_renta_code": tipo_renta_code,
        **_declared_window_context(expected_window),
    }
    assert verify_notices[0]["context"] == dict(context)


def test_calculate_and_verify_never_project_an_ungrounded_tipo_28_offset(tmp_path: Path) -> None:
    """Tipo 28 remains event-shaped and silent at both lifecycle boundaries."""
    with _secure_backend(tmp_path):
        snapshot = published_snapshot("210", filing_year=_FILING_YEAR, period="EVENT-1")
        work_repo = WorkUnitCatalogueRepository()
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=work_repo,
        ) as _calculation_ports_28:
            work_unit = create_work_unit(
                bucket_id=_BUCKET_ID,
                modelo="210",
                filing_year=_FILING_YEAR,
                period=Period.from_year_and_code(_FILING_YEAR, "EVENT-1"),
                revision_id=snapshot.revision.id,
                ports=_calculation_ports_28.work_lifecycle_ports,
                operation=_calculation_ports_28.operation,
                clock=_CLOCK,
            )
            calculation_result = calculate_modelo_work_revision(
                work_unit_id=work_unit.work_unit_id,
                actor="operator",
                inputs=WorkCalculateInputBundle.build(
                    casilla_inputs={"rendimientos_integros": Decimal("900.00")},
                    text_casilla_inputs={"tipo_renta": "ganancia_patrimonial"},
                    m210_official_tipo_renta_code="28",
                    binding_values={},
                    enum_binding_values={},
                    relation_values={},
                    detail_rows=(),
                    borrador_snapshot_id=None,
                ),
                ports=_calculation_ports_28,
            )
            calculate_notices = tuple(resolution for resolution in calculation_result.plazo_resolutions)
            verify_notices = _verify_plazo_notices(calculation_result.revision.calculation_revision_id)

    assert calculate_notices == ()
    assert verify_notices == ()


def test_imputadas_02_event_work_with_an_unresolved_treaty_rate_projects_no_plazo_notice(
    tmp_path: Path,
) -> None:
    """An imputed-income quota that rests on an unresolved treaty rate is not a zero quota.

    The registry bundles no treaty override for imputed income, so a declared
    residence state leaves the rate unresolved. The result-qualified plazo is
    then unknown, and neither lifecycle boundary may project the zero-quota
    window in its place.
    """
    with _secure_backend(tmp_path):
        snapshot = published_snapshot("210", filing_year=_FILING_YEAR, period="EVENT-1")
        work_repo = WorkUnitCatalogueRepository()
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=work_repo,
        ) as _calculation_ports_02:
            work_unit = create_work_unit(
                bucket_id=_BUCKET_ID,
                modelo="210",
                filing_year=_FILING_YEAR,
                period=Period.from_year_and_code(_FILING_YEAR, "EVENT-1"),
                revision_id=snapshot.revision.id,
                ports=_calculation_ports_02.work_lifecycle_ports,
                operation=_calculation_ports_02.operation,
                clock=_CLOCK,
            )
            calculation_result = calculate_modelo_work_revision(
                work_unit_id=work_unit.work_unit_id,
                actor="operator",
                inputs=WorkCalculateInputBundle.build(
                    casilla_inputs={
                        "valor_catastral": Decimal("100000.00"),
                        "coeficiente_imputacion_inmobiliaria": Decimal("0.011"),
                        "dias_imputacion": Decimal("365"),
                    },
                    text_casilla_inputs={"tipo_renta": "inmobiliaria"},
                    m210_official_tipo_renta_code="02",
                    binding_values={},
                    enum_binding_values={},
                    relation_values={},
                    detail_rows=(),
                    borrador_snapshot_id=None,
                ),
                ports=_calculation_ports_02,
            )
            calculate_notices = tuple(resolution for resolution in calculation_result.plazo_resolutions)
            unresolved_outcomes = calculation_result.revision.unresolved_outcomes
            verify_notices = _verify_plazo_notices(calculation_result.revision.calculation_revision_id)

    assert tuple(outcome.casilla_id for outcome in unresolved_outcomes) == ("tipo_gravamen",)
    assert calculate_notices == ()
    assert verify_notices == ()
