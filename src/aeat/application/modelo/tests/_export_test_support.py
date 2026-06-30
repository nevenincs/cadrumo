"""Shared real-behavior support for modelo export tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.identity import nif_check_letter
from ....core.resources import resources
from ....domain.calculations.registry import BindingId, CasillaId, RegistrySnapshotRef, validated_casilla_id
from ....domain.deadlines import TaxpayerProfile
from ....domain.deadlines._models import IVARegime
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository

_ACTIVE_STORAGE_STACK: ExitStack | None = None
_PROFILE_SPAN_OPEN = False
_M130_INPUT_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INPUT_CASILLA")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("03", surface="_M130_RENDIMIENTO_NETO_CASILLA")
_M130_RESULT_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULT_CASILLA")
_M303_RESULT_CASILLA: CasillaId = validated_casilla_id("71", surface="_M303_RESULT_CASILLA")
_SPANISH_IBAN = "ES9121000418450200051332"
_M200_REFUND_RESULT_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:00599",
    surface="_M200_REFUND_RESULT_CASILLA",
)


def _casilla_id_from_payload(value: object) -> CasillaId:
    return validated_casilla_id(value, surface="test casilla id")


def _snapshot_ref(*, modelo: str, period: Period, revision_id: str) -> RegistrySnapshotRef:
    return RegistrySnapshotRef(
        modelo=modelo,
        revision_id=revision_id,
        modelo_year=period.year,
        period=period.registry_token,
    )


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="taxpayerdefault",
        iva_regime=IVARegime.GENERAL,
    )


@contextmanager
def isolated_backend_context(tmp_path: Path) -> Iterator[None]:
    global _ACTIVE_STORAGE_STACK, _PROFILE_SPAN_OPEN

    with ExitStack() as stack:
        stack.enter_context(isolated_profile_storage_root(tmp_path=tmp_path))
        _ACTIVE_STORAGE_STACK = stack
        _PROFILE_SPAN_OPEN = False
        try:
            yield
        finally:
            _PROFILE_SPAN_OPEN = False
            _ACTIVE_STORAGE_STACK = None


@pytest.fixture
def isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_backend_context(tmp_path):
        yield


def _ensure_operator_storage_span() -> None:
    global _PROFILE_SPAN_OPEN

    if _PROFILE_SPAN_OPEN:
        return
    if _ACTIVE_STORAGE_STACK is None:
        raise RuntimeError("modelo export test storage span is not active")
    _ACTIVE_STORAGE_STACK.enter_context(profile_create_storage_span("11111111-1111-4111-8111-111111111111"))
    _PROFILE_SPAN_OPEN = True


def _seed_profile(*, tax_id: str | None = None, profile_overrides: dict[str, str] | None = None) -> str:
    _ensure_operator_storage_span()
    overrides = {
        "identity.name": "Test",
        "identity.surnames": "Operator",
        **dict(profile_overrides or {}),
    }
    if tax_id is not None:
        overrides["identity.tax_id"] = tax_id
    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state, profile_id="11111111-1111-4111-8111-111111111111", overrides=overrides or None
        ),
    )
    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _seed_revision(
    *,
    bucket_id: str,
    state: CalculationRevisionState,
    modelo: str = "130",
    filing_year: int = 2026,
    period: str = "1T",
    input_values_by_casilla_id: dict[CasillaId, str] | None = None,
    binding_overrides: dict[BindingId, str] | None = None,
    casilla_values: dict[CasillaId, Decimal] | None = None,
) -> tuple[str, str]:
    input_values_by_casilla_id = dict(input_values_by_casilla_id or {})
    binding_overrides = dict(binding_overrides or {})
    casilla_values = dict(casilla_values or {})
    typed_period = Period.from_year_and_code(filing_year, period)
    snapshot = resources().modelos.authority.snapshot(
        modelo,
        filing_year=filing_year,
        period=typed_period.registry_token,
    )
    revision_id = snapshot.revision.id
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
    )
    now = datetime.now(UTC)
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{typed_period.registry_token}",
        created_at=now,
        updated_at=now,
    )
    WorkUnitCatalogueRepository().save(
        upsert_work_unit(WorkUnitCatalogueRepository().load(), work_unit),
    )
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=state,
        created_at=now,
        updated_at=now,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            casilla_values=casilla_values,
        )
        if casilla_values
        else (),
        verified_at=now if state is not CalculationRevisionState.BORRADOR else None,
        verified_by="operator" if state is not CalculationRevisionState.BORRADOR else None,
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return work_unit_id, calculation_revision_id


def _load_seeded_work_unit_and_revision(
    work_unit_id: str,
    calculation_revision_id: str,
) -> tuple[WorkUnit, CalculationRevision]:
    work_unit = WorkUnitCatalogueRepository().load().get(work_unit_id)
    revision = CalculationRevisionCatalogueRepository().load().get(calculation_revision_id)
    assert work_unit is not None
    assert revision is not None
    return work_unit, revision


def _synthetic_valid_nif(number: int) -> str:
    return f"{number:08d}{nif_check_letter(number)}"
