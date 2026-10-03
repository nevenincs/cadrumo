"""Resolve required manual casillas against exact scalar and scoped record values."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.casilla_membership import (
    row_field_template_records_by_casilla,
)
from ...domain.calculations.registry.ids import (
    BindingId,
)
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
)
from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.perceptor_clave_scope import (
    PERCEPTOR_CLAVE_SCOPE_MODELO,
    PerceptorClaveScope,
    resolve_perceptor_clave_scope,
    row_field_value_bindings,
    rows_missing_scoped_casilla,
)
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.work_unit import WorkUnit
from .preconditions import ModeloPreconditionFailure
from .verification_finding_contracts import M349_IMPORTE_RECTIFICACIONES_CASILLA, M349_NUMERO_RECTIFICACIONES_CASILLA
from .verification_preconditions import (
    build_verification_precondition_failure,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def perceptor_clave_scope(work_unit: WorkUnit, *, operation: PinnedAuthorityOperation) -> PerceptorClaveScope | None:
    """Return the registry clave scope for the work unit's ejercicio, if one is declared.

    The scope fact governs one modelo's perceptor records only. Any other
    modelo has nothing to scope, and its period may be a filing event or an
    instalment with no calendar span to place on the scope's date axis.
    """
    from ...domain.calculations.registry.errors import RegistryValidationError

    if str(work_unit.modelo) != PERCEPTOR_CLAVE_SCOPE_MODELO.value:
        return None
    try:
        return resolve_perceptor_clave_scope(period=work_unit.period, authority=operation)
    except RegistryValidationError:
        # An ejercicio no scope variant covers keeps every per-record casilla required.
        return None


def append_required_casilla_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    findings: list[ModeloVerificationFinding],
    resolved_casilla_ids: list[CasillaId],
    missing_required_casilla_ids: list[CasillaId],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
    clave_scope: PerceptorClaveScope | None = None,
) -> None:
    """Append required-value findings and exact preconditions in registry casilla order."""
    revision_keys = set(target.input_values_by_casilla_id)
    row_values = target.row_binding_values or {}
    # Where the registry scopes a modelo's per-record casillas by clave, each
    # record answers for the casillas its clave carries; a record outside a
    # casilla's scope owes it nothing.
    scoped = (
        clave_scope is not None
        and clave_scope.modelo_id == str(work_unit.modelo)
        and clave_scope.row_clave_binding in row_values
    )
    value_bindings = row_field_value_bindings(snapshot.revision) if scoped else {}
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind != InputKind.MANUAL or not casilla.required:
            continue
        value_binding = value_bindings.get(casilla.id)
        if required_manual_casilla_resolved(
            work_unit,
            target,
            snapshot,
            casilla,
            revision_keys,
            row_values,
            value_binding,
            scoped,
            clave_scope,
        ):
            resolved_casilla_ids.append(casilla.id)
            continue
        missing_required_casilla_ids.append(casilla.id)
        finding = missing_required_casilla_finding(casilla.id, casilla_def=casilla)
        findings.append(finding)
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=target.work_unit_id,
            condition_id="modelo.work.verify.required_casillas.complete",
            scenario_id="modelo.work.verify.required_casillas.missing",
            evidence_id="modelo.work.verify.required_casillas",
            evidence_values={
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
                "casilla_id": str(casilla.id),
            },
            provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        )


def detail_row_template_casilla_is_satisfied(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    casilla: CasillaDefinition,
    revision: ModeloRevision,
) -> bool:
    """Return whether a per-row template casilla is answered by its row source.

    A casilla an export record fills once per detail row is one field of each
    emitted row, not a scalar the operator types once; its completeness belongs
    to the row source. The same declared mapping decides which casillas
    calculate refuses as scalar inputs, so verify never demands one of them.
    Modelo 349 additionally proves its rows are present, since its operador and
    rectificacion records are the return's whole content.
    """
    if not casilla.section:
        return False
    section = str(casilla.section[0])
    if str(work_unit.modelo) != Modelo("349").value:
        return casilla.id in row_field_template_records_by_casilla(revision)
    if section == "operador":
        return any(getattr(row, "row_type", None) == "operador" for row in target.detail_rows)
    if section != "rectificacion":
        return False
    if any(getattr(row, "row_type", None) == "rectificacion" for row in target.detail_rows):
        return True
    # Only stated zero totals prove the return carries no rectificacion; an
    # unstated total leaves the casilla demanded rather than reading as zero.
    numero = target.casilla_values.get(M349_NUMERO_RECTIFICACIONES_CASILLA)
    importe = target.casilla_values.get(M349_IMPORTE_RECTIFICACIONES_CASILLA)
    return numero == Decimal("0") and importe == Decimal("0")


def missing_required_casilla_finding(
    casilla_id: CasillaId,
    *,
    casilla_def: CasillaDefinition | None = None,
) -> ModeloVerificationFinding:
    """Project the pinned casilla’s required-value refusal and declared provenance."""
    if casilla_def is None:
        raise ModeloValidationError(
            f"missing-required finding for casilla {casilla_id!r} requires registry casilla definition provenance",
        )
    legal_refs: tuple[str, ...] = tuple(str(r) for r in casilla_def.legal_refs)
    source_refs: tuple[str, ...] = tuple(str(r) for r in casilla_def.source_refs)
    if not legal_refs or not source_refs:
        raise ModeloValidationError(
            f"missing-required finding for casilla {casilla_id!r} requires legal_refs/source_refs provenance",
        )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.missing_required_casilla",
        message_facts={"casilla_id": str(casilla_id)},
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def required_manual_casilla_resolved(
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    casilla: CasillaDefinition,
    revision_keys: set[CasillaId],
    row_values: Mapping[BindingId, Mapping[str, str]],
    value_binding: BindingId | None,
    scoped: bool,
    clave_scope: PerceptorClaveScope | None,
) -> bool:
    """Resolve scoped rows exclusively, then ordinary template and scalar values."""
    if clave_scope is not None and scoped and (value_binding is not None):
        return not rows_missing_scoped_casilla(
            clave_scope, casilla_id=casilla.id, value_binding=value_binding, row_binding_values=row_values
        )
    return (
        detail_row_template_casilla_is_satisfied(
            work_unit=work_unit, target=target, casilla=casilla, revision=snapshot.revision
        )
        or casilla.id in revision_keys
    )
