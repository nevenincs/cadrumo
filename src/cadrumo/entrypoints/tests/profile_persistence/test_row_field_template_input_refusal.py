"""Calculate refuses a scalar input for a casilla that an export record fills once per detail row.

The calculation drops a row-field template casilla's scalar value and
observation, so accepting a scalar input for one would persist an operator
input with no registry-grounded observation, which the evidence capture at
verify and amend then refuses. Calculate refuses it first, before the engine
runs or anything is written. Exercised through the real calculation action,
the published registry and the encrypted profile repositories.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.tests.calculation_catalogue_tamper_support import (
    plant_calculation_revision_unchecked,
)
from cadrumo.application.modelo.action_errors import StoredRowFieldScalarInputError
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.stored_row_field_input_gate import refuse_stored_row_field_scalar_inputs
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.casilla_membership import row_field_template_records_by_casilla
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    derive_calculation_revision_id_from_revision,
)
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import (
    DEFAULT_180_BINDING_VALUES,
    DEFAULT_180_RELATION_VALUES,
    T1,
    T2,
    Repos,
    calculation_ports_for_test,
    registry_required_manual_casillas,
    seed_modelo_180_work_unit,
    seed_modelo_193_work_unit,
    seed_work_unit,
    verify_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REFUSAL_KEY = "errors.calc.row_field_template_supplied_as_input"
_M180_PERCEPTOR_RECORD = "modelo-180-perceptor"
_M180_RETENCIONES: CasillaId = validated_casilla_id("perc.retenciones")
_M180_PERCEPTOR_NIF: CasillaId = validated_casilla_id("perc.nif")
_M349_OPERADOR_BASE: CasillaId = validated_casilla_id("op.base-imponible")
_M349_COUNTRY: CasillaId = validated_casilla_id("op.codigo-pais")
_M349_DECLARANTE_BINDING_VALUES = {
    "iva-349-declarante-numero-operadores": Decimal("1"),
    "iva-349-declarante-importe-operaciones": Decimal("100"),
    "iva-349-declarante-numero-rectificaciones": Decimal("0"),
    "iva-349-declarante-importe-rectificaciones": Decimal("0"),
}


def _row_field_records(work_unit: WorkUnit, casilla_id: CasillaId) -> tuple[str, ...]:
    revision = resolved_revision(
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    return row_field_template_records_by_casilla(revision)[casilla_id]


def _assert_nothing_persisted(repos: Repos, work_unit: WorkUnit) -> None:
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    assert not any(revision.work_unit_id == work_unit.work_unit_id for revision in cr_repo.load().revisions.values())
    assert wu_repo.load().work_units[work_unit.work_unit_id].current_calculation_revision_id is None
    assert not bv_repo.load().for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_CALCULATION_CREATED,),
    )


def test_m180_scalar_retenciones_input_is_refused_before_anything_is_persisted(repos: Repos) -> None:
    """``perc.retenciones`` belongs to each perceptor row, so a scalar value for it is refused."""
    wu_repo, *_ = repos
    work_unit = seed_modelo_180_work_unit(wu_repo)
    assert _row_field_records(work_unit, _M180_RETENCIONES) == (_M180_PERCEPTOR_RECORD,)

    with (
        pytest.raises(RegistryValidationError) as refusal,
        calculation_ports_for_test(bucket_id=work_unit.bucket_id) as ports,
    ):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            ports=ports,
            actor="operator-A",
            casilla_inputs={_M180_RETENCIONES: Decimal("150")},
            binding_values=DEFAULT_180_BINDING_VALUES,
            relation_values=DEFAULT_180_RELATION_VALUES,
            clock=T1,
        )

    assert refusal.value.translated_message == _REFUSAL_KEY
    assert refusal.value.context == {"casilla_ids": _M180_RETENCIONES, "record_ids": _M180_PERCEPTOR_RECORD}
    _assert_nothing_persisted(repos, work_unit)


def test_m180_scalar_text_input_for_a_perceptor_field_is_refused(repos: Repos) -> None:
    """The text channel is a scalar channel too; a perceptor NIF typed once names no row."""
    wu_repo, *_ = repos
    work_unit = seed_modelo_180_work_unit(wu_repo)

    with (
        pytest.raises(RegistryValidationError) as refusal,
        calculation_ports_for_test(bucket_id=work_unit.bucket_id) as ports,
    ):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            ports=ports,
            actor="operator-A",
            casilla_inputs={},
            text_casilla_inputs={_M180_PERCEPTOR_NIF: "00098765Z"},
            binding_values=DEFAULT_180_BINDING_VALUES,
            relation_values=DEFAULT_180_RELATION_VALUES,
            clock=T1,
        )

    assert refusal.value.translated_message == _REFUSAL_KEY
    assert refusal.value.context == {"casilla_ids": _M180_PERCEPTOR_NIF, "record_ids": _M180_PERCEPTOR_RECORD}
    _assert_nothing_persisted(repos, work_unit)


def test_m349_scalar_operador_inputs_are_refused_naming_every_record_that_carries_them(repos: Repos) -> None:
    """Modelo 349 operador fields are refused the same way, on both scalar channels.

    The country code is a field of the operador and the rectificacion records
    alike, so the refusal names both records alongside the operador-only base.
    """
    wu_repo, *_ = repos
    work_unit = seed_work_unit(
        wu_repo,
        modelo="349",
        filing_year=2026,
        period="1T",
        revision_id="2020-y-siguientes",
    )
    records = sorted(
        {*_row_field_records(work_unit, _M349_OPERADOR_BASE), *_row_field_records(work_unit, _M349_COUNTRY)}
    )
    assert len(records) == 2

    with (
        pytest.raises(RegistryValidationError) as refusal,
        calculation_ports_for_test(bucket_id=work_unit.bucket_id) as ports,
    ):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            ports=ports,
            actor="operator-A",
            casilla_inputs={_M349_OPERADOR_BASE: Decimal("100")},
            text_casilla_inputs={_M349_COUNTRY: "FR"},
            binding_values=_M349_DECLARANTE_BINDING_VALUES,
            clock=T1,
        )

    assert refusal.value.translated_message == _REFUSAL_KEY
    assert refusal.value.context == {
        "casilla_ids": ",".join(sorted((_M349_OPERADOR_BASE, _M349_COUNTRY))),
        "record_ids": ",".join(records),
    }
    _assert_nothing_persisted(repos, work_unit)


def test_a_scalar_input_outside_every_row_field_template_still_calculates(repos: Repos) -> None:
    """Modelo 193's declared-expenses total is a scalar of the return, beside its perceptor rows.

    The refusal is keyed on the export layout's row mapping, not on the modelo
    having detail records at all, so the declarant scalar is accepted and its
    observation carries the registry's references.
    """
    wu_repo, *_ = repos
    work_unit = seed_modelo_193_work_unit(wu_repo)
    revision_casillas = resolved_revision(
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    assert row_field_template_records_by_casilla(revision_casillas)
    (declarant_casilla,) = registry_required_manual_casillas(
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )

    with calculation_ports_for_test(bucket_id=work_unit.bucket_id) as ports:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            ports=ports,
            actor="operator-A",
            casilla_inputs={declarant_casilla: Decimal("250")},
            clock=T1,
        )

    assert declarant_casilla in revision.input_values_by_casilla_id
    observation = next(obs for obs in revision.observations if obs.casilla_id == declarant_casilla)
    assert observation.legal_refs
    assert observation.source_refs
    _wu_repo, cr_repo, *_ = repos
    assert revision.calculation_revision_id in cr_repo.load().revisions


def _saved_before_the_refusal(
    revision: CalculationRevision, *, casilla_id: CasillaId, value: str
) -> CalculationRevision:
    """Return ``revision`` as calculate stored it before row fields were refused as scalars.

    It carries the scalar input with no observation, which is what those
    revisions hold, under the content address such a payload derives, so the
    storage integrity check accepts it exactly as it accepted them.
    """
    stored = revision.model_copy(
        update={"input_values_by_casilla_id": {**revision.input_values_by_casilla_id, casilla_id: value}},
    )
    return stored.model_copy(update={"calculation_revision_id": derive_calculation_revision_id_from_revision(stored)})


def _calculate_clean_180(repos: Repos) -> tuple[WorkUnit, CalculationRevision]:
    wu_repo, *_ = repos
    work_unit = seed_modelo_180_work_unit(wu_repo)
    with calculation_ports_for_test(bucket_id=work_unit.bucket_id) as ports:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            ports=ports,
            actor="operator-A",
            casilla_inputs={},
            binding_values=DEFAULT_180_BINDING_VALUES,
            relation_values=DEFAULT_180_RELATION_VALUES,
            clock=T1,
        )
    return work_unit, revision


def test_verify_refuses_a_revision_saved_with_a_scalar_row_field_input(repos: Repos) -> None:
    """A revision stored before calculate refused row-field scalars cannot be verified; it must be recalculated."""
    wu_repo, cr_repo, _fr_repo, vr_repo, bv_repo = repos
    work_unit, clean = _calculate_clean_180(repos)
    stored = _saved_before_the_refusal(clean, casilla_id=_M180_RETENCIONES, value="150")
    plant_calculation_revision_unchecked(cr_repo.load(), stored)

    with pytest.raises(StoredRowFieldScalarInputError) as refusal:
        verify_revision(
            stored.calculation_revision_id,
            revision=stored,
            work_unit=work_unit,
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=T2,
        )

    assert refusal.value.translated_message == "errors.refused.refused_modelo_stored_row_field_input"
    assert refusal.value.context == {
        "casilla_ids": _M180_RETENCIONES,
        "calculation_revision_id": stored.calculation_revision_id,
        "work_unit_id": work_unit.work_unit_id,
    }


def test_the_stored_input_guard_passes_a_revision_calculated_under_the_refusal(repos: Repos) -> None:
    """Detector teeth: the guard that verify and amend share keys on the stored row-field input alone."""
    work_unit, clean = _calculate_clean_180(repos)

    with bundled_indexed_authority().operation() as operation:
        refuse_stored_row_field_scalar_inputs(clean, work_unit=work_unit, operation=operation)
        with pytest.raises(StoredRowFieldScalarInputError):
            refuse_stored_row_field_scalar_inputs(
                _saved_before_the_refusal(clean, casilla_id=_M180_PERCEPTOR_NIF, value="00098765Z"),
                work_unit=work_unit,
                operation=operation,
            )
