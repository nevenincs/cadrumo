"""A return slot a resolver filled is imported, not assumed: the form reads the revision's own source trace.

The detail rows of Modelo 369 are ``manual_input`` slots of the official record
(DR369 T36904 and its siblings): the filer may state a row, and the OSS/IOSS
ledger fold states the rows the issued invoices declare (LIVA arts. 163
noniesdecies and following). The fold records that in the revision's source
trace, one value-free primary node per slot it filled, and the form reads it:
the slot is imported from the filer's records and the assumed-value gate does
not hold the declaration back on it.

The node alone does not release the hold. The form claims a derived value only
where the trace names a resolver AND the operator's own entries are recorded,
so a revision whose operator record is unknown keeps the same slot assumed and
verification refuses it. Absence of a node is never read as a source: a held
slot no resolver claims stays assumed, which is what keeps a staged default
from reaching a declaration as a figure the filer never saw.

Real encrypted store, bucket-aggregation calculation, work-form service,
verification stage and the registered assumed-value gate over the published
authority; the invoice arithmetic is the sibling Modelo 369 scenario's own.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.modelo.assumed_value_gate import unconfirmed_assumed_fields
from cadrumo.application.modelo.calculation_bucket_actions import BucketAggregationCalculationResult
from cadrumo.application.modelo.source_policy import SourceFamily
from cadrumo.application.modelo.work_form_assumed import assumed_fields
from cadrumo.application.modelo.work_form_field_vocabulary import ModeloFormBindingAddressV1, ModeloFormOrigin
from cadrumo.application.modelo.work_form_models import ModeloFormField
from cadrumo.application.modelo.work_form_next_step import applicable_fields
from cadrumo.application.modelo.work_form_service import load_modelo_work_form
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision_sources import bound_binding_source_refs
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.adapter_composition_work_ports import build_verification_repository_bundle

from .test_m369_destination_rows_live import (
    _EXTERIOR,
    _calculate,
    _invoice,
    _verify,
    objects,
    seeded_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

__all__ = ["objects", "seeded_profile"]

#: The first destination row of the exterior scheme's services table: the country the fold states.
_SLOT = "modelo-369-exterior-fichero.3-prestaciones-de-servicios-codigo-de-pais-em-de-consumo-1"

#: The same row's taxable base, so the proof is not read from one text slot alone.
_BASE_SLOT = "modelo-369-exterior-fichero.3-prestaciones-de-servicios-base-imponible-1"


def _slot_field(work_unit: WorkUnit, operation: PinnedAuthorityOperation) -> ModeloFormField:
    """Read the slot's field from the form the work-form service builds, as every stage reads it."""
    repositories = build_verification_repository_bundle(work_unit.bucket_id, operation=operation)
    loaded = load_modelo_work_form(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        operation=operation,
        work_unit_repository=repositories.work_unit,
        calculation_repository=repositories.calculation,
        verification_repository=repositories.verification,
        admission=None,
        language=OutputLanguage.EN,
        credit_resolutions=repositories.credit_resolution,
    )
    (field,) = (
        item
        for item in applicable_fields(loaded.form)
        if isinstance(item.address, ModeloFormBindingAddressV1) and item.address.binding_id == _SLOT
    )
    return field


def _held_slots(work_unit: WorkUnit, operation: PinnedAuthorityOperation) -> tuple[str, ...]:
    """The bindings the registered gate holds the declaration back on, as it selects them."""
    repositories = build_verification_repository_bundle(work_unit.bucket_id, operation=operation)
    fields = unconfirmed_assumed_fields(
        work_unit,
        work_unit_repository=repositories.work_unit,
        calculation_repository=repositories.calculation,
        verification_repository=repositories.verification,
        credit_resolutions=repositories.credit_resolution,
        operation=operation,
    )
    return tuple(field.address.binding_id for field in fields if isinstance(field.address, ModeloFormBindingAddressV1))


def _oss_quarter(
    objects: SecureObjectRepository,
    operation: PinnedAuthorityOperation,
    *,
    record_operator_layer: bool,
) -> tuple[BucketAggregationCalculationResult, WorkUnit]:
    """One exterior-scheme quarter whose single French service line the OSS fold states."""
    return _calculate(
        objects,
        _EXTERIOR,
        (_invoice(_EXTERIOR, "OSS-SUPPLIED", "FR", "general", "100.00", "20.00"),),
        operation,
        record_operator_layer=record_operator_layer,
    )


def test_a_slot_the_oss_fold_filled_is_imported_and_the_gate_passes(objects: SecureObjectRepository) -> None:
    with bundled_indexed_authority().operation() as operation:
        result, work_unit = _oss_quarter(objects, operation, record_operator_layer=True)

        # The revision names the fold as the source of the slot, and records no figure beside it.
        supplied = bound_binding_source_refs(result.revision.source_provenance)[_SLOT]
        assert supplied.resolver_id == "ledger_oss_aggregation"
        assert supplied.resolved_binding_source is BindingSourceKind.LEDGER_OSS_AGGREGATION
        assert result.revision.binding_overrides[_SLOT] == "FR"

        field = _slot_field(work_unit, operation)
        assert field.origin is ModeloFormOrigin.IMPORTED
        assert field.unattributed is False
        assert field.source is not None
        assert field.source.source_kind is BindingSourceKind.LEDGER_OSS_AGGREGATION
        assert field.source.family is SourceFamily.RECORDS
        assert _SLOT not in _held_slots(work_unit, operation)

    assert _verify(result).granted_verificado_completo is True


def test_the_same_slot_stays_assumed_and_refused_where_the_operator_record_is_unknown(
    objects: SecureObjectRepository,
) -> None:
    """A derived value is claimed only against a known operator record, so an unknown one keeps the hold."""
    with bundled_indexed_authority().operation() as operation:
        result, work_unit = _oss_quarter(objects, operation, record_operator_layer=False)

        # The fold's node stands; only the operator record is unknown, so that alone decides the two cases.
        assert _SLOT in bound_binding_source_refs(result.revision.source_provenance)
        assert result.revision.operator_layer is None

        field = _slot_field(work_unit, operation)
        assert field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
        assert field.unattributed is True
        assert _SLOT in _held_slots(work_unit, operation)

    report = _verify(result)
    assert report.granted_verificado_completo is False
    assert "application.modelo.findings.assumed_value_unconfirmed" in {
        finding.message_locale_key for finding in report.findings
    }


def test_the_form_and_the_gate_hold_the_same_slots(objects: SecureObjectRepository) -> None:
    """One selection serves both: the form's own assumed fields are the bindings the gate names."""
    with bundled_indexed_authority().operation() as operation:
        result, work_unit = _oss_quarter(objects, operation, record_operator_layer=False)
        repositories = build_verification_repository_bundle(work_unit.bucket_id, operation=operation)
        loaded = load_modelo_work_form(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=repositories.work_unit,
            calculation_repository=repositories.calculation,
            verification_repository=repositories.verification,
            admission=None,
            language=OutputLanguage.EN,
            credit_resolutions=repositories.credit_resolution,
        )
        from_form = tuple(
            field.address.binding_id
            for field in assumed_fields(loaded.form)
            if isinstance(field.address, ModeloFormBindingAddressV1)
        )
        assert from_form == _held_slots(work_unit, operation)
        # The whole row waits, not only its country: its base is held on the same footing.
        assert _BASE_SLOT in from_form
        assert Decimal(result.revision.binding_overrides[_BASE_SLOT]) == Decimal("100")
