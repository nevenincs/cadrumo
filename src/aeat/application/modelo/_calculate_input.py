"""Typed input bundle for modelo work calculation.

Use of :class:`CalculationRevision` for compliance. Resolves the work unit's
:class:`ModeloRevision` to guard each casilla key and data type against the
revision's registry-declared casilla set.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from ...core import Modelo
from ...core.errors import AeatError
from ...core.external_constants import M347_THRESHOLD_EUR
from ...core.resources import resources
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    ModeloRevision,
    RelationId,
    casilla_metadata_alias_targets,
    declared_casilla_ids,
    enum_consumed_binding_ids,
    revision_date_binding_ids,
)
from ...domain.contribuyente._deduccion_maternidad import compute_deduccion_maternidad_0611
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._dt12_reduccion import compute_dt12_reduccion_plan_pensiones
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.modelos._row_models import (
    Modelo184MemberRow,
    Modelo184ShareSumError,
    Modelo347ContraparteRow,
    Modelo347ThresholdError,
    ModeloDetailRow,
    validate_m184_member_share_sum,
    validate_m347_threshold,
)
from ...domain.modelos._sal_reserva_especial import compute_sal_reserva_especial_dotacion
from ...domain.modelos._work_unit import WorkUnit
from ..aggregation import CalculationSourceDiagnostic
from ._registry_helpers import validate_casilla_input_ids
from ._semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_semantic_role,
)

_AUTOCONSUMO_PROMOTOR_BINDING: BindingId = "modelo-303-autoconsumo-promotor-base"
_INSS_EXENTA_SEMANTIC_ROLE = "irpf_rendimiento_trabajo_prestacion_inss_maternidad_paternidad_exenta"
_DEDUCCION_MATERNIDAD_SEMANTIC_ROLE = "irpf_deduccion_maternidad"
_REDUCCION_TRABAJO_SEMANTIC_ROLE = "irpf_rendimiento_trabajo_reduccion"
_SAL_RESERVA_ESPECIAL_SEMANTIC_ROLE = "is_sal_reserva_especial_dotacion"


class ModeloCalculateInputError(ModeloError, ValueError):
    """Raised when operator-supplied modelo calculation inputs are invalid."""


class ModeloCalculateDetailRowsError(ModeloCalculateInputError):
    """Raised when detail rows violate modelo calculation preconditions."""


class ModeloCalculateDecimalInputError(ModeloCalculateInputError):
    """Raised when a calculation override value is not decimal-shaped."""


class ModeloCalculateCasillaInputError(ModeloCalculateInputError):
    """Raised when a casilla override cannot be resolved for the active revision."""


class ModeloCalculateBindingInputError(ModeloCalculateInputError):
    """Raised when a ``--binding`` override cannot be resolved for the active revision."""


class ModeloCalculateRelationInputError(ModeloCalculateInputError):
    """Raised when a ``--relation`` override cannot be resolved for the active revision."""


class ModeloCalculateShortcutInputError(ModeloCalculateInputError):
    """Raised when grouped calculation shortcut inputs are incomplete."""


class ModeloCalculateSemanticRoleError(ModeloCalculateInputError):
    """Raised when a registry revision lacks a semantic-role target required by a shortcut."""


@dataclass(frozen=True, slots=True)
class WorkCalculateInputBundle:
    """Application-facing inputs for one `modelo work calculate` run."""

    casilla_inputs: Mapping[CasillaId, Decimal]
    binding_values: Mapping[BindingId, Decimal]
    enum_binding_values: Mapping[BindingId, str]
    relation_values: Mapping[RelationId, Decimal]
    detail_rows: tuple[ModeloDetailRow, ...]
    borrador_snapshot_id: str | None

    @classmethod
    def build(
        cls,
        *,
        casilla_inputs: Mapping[CasillaId, Decimal],
        binding_values: Mapping[BindingId, Decimal],
        enum_binding_values: Mapping[BindingId, str],
        relation_values: Mapping[RelationId, Decimal],
        detail_rows: tuple[ModeloDetailRow, ...],
        borrador_snapshot_id: str | None,
    ) -> WorkCalculateInputBundle:
        """Freeze CLI-assembled mappings before crossing into calculation services.

        Returns:
            :class:`WorkCalculateInputBundle`: The frozen calculate input bundle.
        """
        return cls(
            casilla_inputs=dict(casilla_inputs),
            binding_values=dict(binding_values),
            enum_binding_values=dict(enum_binding_values),
            relation_values=dict(relation_values),
            detail_rows=detail_rows,
            borrador_snapshot_id=borrador_snapshot_id.strip() if borrador_snapshot_id else None,
        )

    def optional_binding_values(self) -> Mapping[BindingId, Decimal] | None:
        """Return binding values using the calculation-service optional contract."""
        return self.binding_values or None

    def optional_enum_binding_values(self) -> Mapping[BindingId, str] | None:
        """Return enum binding values using the calculation-service optional contract."""
        return self.enum_binding_values or None

    def optional_relation_values(self) -> Mapping[RelationId, Decimal] | None:
        """Return relation values using the calculation-service optional contract."""
        return self.relation_values or None


@dataclass(frozen=True, slots=True)
class Modelo202ModalitySummary:
    """Application summary of the Modelo 202 Art. 40.2 / 40.3 modality."""

    modality: str
    reason: str


@dataclass(frozen=True, slots=True)
class ModeloAuthorizationAdvisorySummary:
    """Application summary for an unauthorized-but-computable modelo."""

    state: str


@dataclass(frozen=True, slots=True)
class ModeloWorkCalculationServiceResult:
    """Application-owned result for one `modelo work calculate` command.

    ``source_diagnostics`` carries the NON-blocking
    :class:`CalculationSourceDiagnostic` rows the source mesh raised while
    resolving the bucket ledger — notably the unconsumed-declarable-IVA
    advisories (a declarable IVA observation no ``ledger_iva_aggregation``
    binding selects). The calculate verb succeeded regardless; surfacing them
    keeps an unrouted observation from being silently under-declared
    (no-silent-under-declaration). Each diagnostic's ``message`` carries the
    observation's category / rate / flow provenance.
    """

    revision: CalculationRevision
    work_unit: WorkUnit
    modality: Modelo202ModalitySummary | None = None
    authorization_advisory: ModeloAuthorizationAdvisorySummary | None = None
    source_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


def calculate_modelo_work_revision(
    *,
    work_unit_id: str,
    actor: str,
    inputs: WorkCalculateInputBundle,
) -> ModeloWorkCalculationServiceResult:
    """Persist a draft revision and return a :class:`ModeloWorkCalculationServiceResult`."""
    from ._calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
    from ._work_lifecycle import get_work_unit

    calculation = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_id,
        actor=actor,
        casilla_inputs=inputs.casilla_inputs,
        binding_values=inputs.optional_binding_values(),
        enum_binding_values=inputs.optional_enum_binding_values(),
        borrador_snapshot_id=inputs.borrador_snapshot_id,
        relation_values=inputs.optional_relation_values(),
        detail_rows=inputs.detail_rows,
    )
    revision = calculation.revision
    work_unit = get_work_unit(revision.work_unit_id)
    return ModeloWorkCalculationServiceResult(
        revision=revision,
        work_unit=work_unit,
        modality=modelo_202_modality_for_work_unit(work_unit),
        authorization_advisory=authorization_advisory_for_modelo(str(work_unit.modelo)),
        source_diagnostics=calculation.source_diagnostics,
    )


def build_work_calculate_input_bundle(
    *,
    work_unit_id: str,
    casilla_overrides: Mapping[CasillaId, str],
    binding_overrides: Mapping[BindingId, str],
    relation_overrides: Mapping[RelationId, str],
    detail_rows: tuple[ModeloDetailRow, ...],
    borrador_snapshot_id: str | None,
    prestacion_inss_exenta: Decimal | None = None,
    meses_trabajo_con_hijo_menor_3: tuple[tuple[str, int], ...] = (),
    rescate_plan_pensiones_capital: Decimal | None = None,
    rescate_plan_pensiones_aportaciones_pre_2007: Decimal | None = None,
    rescate_plan_pensiones_aportaciones_totales: Decimal | None = None,
    sal_beneficio_neto: Decimal | None = None,
    sal_reserva_dotada: Decimal | None = None,
    sal_capital_social: Decimal | None = None,
    autoconsumo_promotor_base: Decimal | None = None,
) -> WorkCalculateInputBundle:
    """Build a :class:`WorkCalculateInputBundle` from operator-supplied override tokens."""
    _validate_detail_rows(detail_rows)
    revision = _revision_for_work_unit(work_unit_id)
    casilla_inputs: dict[CasillaId, Decimal] = {}
    for raw_key, raw_value in casilla_overrides.items():
        key = _validated_canonical_casilla_id(raw_key, revision)
        casilla_inputs[key] = _decimal(raw_value, flag="--casilla", key=key)
    casilla_inputs = validate_casilla_input_ids(revision, casilla_inputs)

    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {}
    if binding_overrides:
        known_binding_ids = {binding.id for binding in revision.bindings}
        enum_channel_ids = enum_consumed_binding_ids(revision)
        date_channel_ids = revision_date_binding_ids(revision)
        for raw_key, raw_value in binding_overrides.items():
            if raw_key in date_channel_ids:
                raise ModeloCalculateBindingInputError(
                    f"--binding {raw_key!r} is a date-valued binding sourced from the active "
                    "profile (a taxpayer date fact such as the birth date); it cannot be "
                    "supplied through --binding, which carries only decimal and enum "
                    "values. Set it as a profile fact (e.g. `aeat config profile create "
                    "... --taxpayer-birth-date YYYY-MM-DD`) and recalculate.",
                    context={"key": raw_key},
                    translated_message="application.modelo.errors.calculate_binding_is_date_sourced",
                )
            key, channel = _validated_binding_input_channel(raw_key, revision, known_binding_ids, enum_channel_ids)
            if channel == "enum":
                enum_binding_values[key] = raw_value
            else:
                binding_values[key] = _decimal(raw_value, flag="--binding", key=key)

    casilla_inputs, binding_values = apply_calculation_shortcut_inputs(
        work_unit_id=work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values=binding_values,
        prestacion_inss_exenta=prestacion_inss_exenta,
        meses_trabajo_con_hijo_menor_3=meses_trabajo_con_hijo_menor_3,
        rescate_plan_pensiones_capital=rescate_plan_pensiones_capital,
        rescate_plan_pensiones_aportaciones_pre_2007=rescate_plan_pensiones_aportaciones_pre_2007,
        rescate_plan_pensiones_aportaciones_totales=rescate_plan_pensiones_aportaciones_totales,
        sal_beneficio_neto=sal_beneficio_neto,
        sal_reserva_dotada=sal_reserva_dotada,
        sal_capital_social=sal_capital_social,
        autoconsumo_promotor_base=autoconsumo_promotor_base,
    )

    known_relation_ids = {relation.id for relation in revision.relations}
    relation_values: dict[RelationId, Decimal] = {}
    for raw_key, raw_value in relation_overrides.items():
        key = _validated_relation_id(raw_key, known_relation_ids)
        relation_values[key] = _decimal(raw_value, flag="--relation", key=key)
    return WorkCalculateInputBundle.build(
        casilla_inputs=casilla_inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        detail_rows=detail_rows,
        borrador_snapshot_id=borrador_snapshot_id,
    )


def _validate_detail_rows(rows: tuple[ModeloDetailRow, ...]) -> None:
    member_rows = [row for row in rows if isinstance(row, Modelo184MemberRow)]
    try:
        validate_m184_member_share_sum(member_rows)
    except Modelo184ShareSumError as exc:
        raise ModeloCalculateDetailRowsError(
            f"M184 miembro rows: share percentages must sum to exactly 100%; got {exc.total} across {exc.count} rows",
            context={"total": str(exc.total), "count": str(exc.count)},
            translated_message="application.modelo.errors.calculate_m184_share_sum_invalid",
        ) from exc

    contraparte_rows = [row for row in rows if isinstance(row, Modelo347ContraparteRow)]
    try:
        validate_m347_threshold(contraparte_rows)
    except Modelo347ThresholdError as exc:
        raise ModeloCalculateDetailRowsError(
            f"M347 contraparte row (nif={exc.nif!r}): importe total {exc.total} "
            f"does not exceed the EUR {M347_THRESHOLD_EUR} threshold required by RD 1065/2007 art. 33.1",
            context={"nif": exc.nif, "total": str(exc.total), "threshold": str(M347_THRESHOLD_EUR)},
            translated_message="application.modelo.errors.calculate_m347_threshold_not_met",
        ) from exc


def _decimal(raw_value: str, *, flag: str, key: str) -> Decimal:
    try:
        return Decimal(raw_value)
    except (InvalidOperation, ValueError) as exc:
        raise ModeloCalculateDecimalInputError(
            f"{flag} value for {key!r} is not a decimal: {raw_value!r}",
            context={"flag": flag, "key": key, "value": raw_value},
            translated_message="application.modelo.errors.calculate_decimal_input_invalid",
        ) from exc


def _revision_for_work_unit(work_unit_id: str) -> ModeloRevision:
    from ._action_errors import WorkUnitRevisionDivergenceError
    from ._work_lifecycle import get_work_unit

    unit = get_work_unit(work_unit_id)
    snapshot = resources().modelos.authority.snapshot(
        str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period.registry_token,
    )
    # D1 calc-time assertion (defense-in-depth, ruling 2 "both ends"): the
    # law-determined revision must equal the revision the work unit was created
    # against.  The work unit's revision_id is an identity claim, not a
    # resolution input — it is only compared against resolution's answer.
    if snapshot.revision.id != unit.revision_id:
        raise WorkUnitRevisionDivergenceError(
            f"work unit {unit.work_unit_id!r} was created against registry revision "
            f"{unit.revision_id!r}, but the law-determined revision for "
            f"modelo {unit.modelo!r} {unit.filing_year} {unit.period.registry_token!r} "
            f"is now {snapshot.revision.id!r}. "
            f"The registry's law-mapping was corrected after this work unit was created. "
            f"Re-create the work unit (discard this one and run `aeat app modelo work create`) "
            f"to bind it to the current law-determined revision.",
        )
    return snapshot.revision


def _validated_binding_input_channel(
    key: str,
    revision: ModeloRevision,
    known_binding_ids: set[BindingId],
    enum_channel_ids: frozenset[BindingId],
) -> tuple[BindingId, Literal["decimal", "enum"]]:
    """Return the registry-declared engine channel for a ``--binding`` override.

    Routes the override by the binding's *declared* input channel, not by
    parse success: a binding the revision's formulas consume as a string
    enum key (``enum_consumed_binding_ids``) is an ``"enum"`` channel and
    its override is carried verbatim; every other declared binding is a
    ``"decimal"`` channel whose override the caller coerces with
    :func:`_decimal` (so a malformed numeric value REFUSES instead of
    silently reclassifying as an enum string). An unknown binding id
    refuses with the accepted set, per ``no-silent-under-declaration``
    and the CLI-Choice-hint mandate.
    """
    if key not in known_binding_ids:
        accepted = ", ".join(sorted(known_binding_ids))
        raise ModeloCalculateBindingInputError(
            f"--binding {key!r} does not match any binding id in this revision. "
            f"Accepted binding ids: {accepted}. "
            "Use `aeat app modelo bindings list <MODELO>` to list valid binding ids.",
            context={"key": key, "accepted": accepted},
            translated_message="application.modelo.errors.calculate_binding_unknown",
        )
    return key, "enum" if key in enum_channel_ids else "decimal"


def _validated_relation_id(key: str, known_relation_ids: set[RelationId]) -> RelationId:
    if key in known_relation_ids:
        return key
    accepted = ", ".join(sorted(known_relation_ids))
    raise ModeloCalculateRelationInputError(
        f"--relation {key!r} does not match any relation id in this revision. "
        f"Accepted relation ids: {accepted}.",
        context={"key": key, "accepted": accepted},
        translated_message="application.modelo.errors.calculate_relation_unknown",
    )


def _validated_canonical_casilla_id(key: str, revision: ModeloRevision) -> CasillaId:
    known_ids = declared_casilla_ids(revision)
    if key in known_ids:
        return key

    metadata_alias_matches = casilla_metadata_alias_targets(revision, key)
    if metadata_alias_matches:
        accepted = ", ".join(metadata_alias_matches)
        raise ModeloCalculateCasillaInputError(
            f"--casilla {key!r} is a printed casilla number or form number or export reference, "
            "not a canonical casilla.id. "
            f"Use the canonical casilla.id instead: {accepted}.",
            context={"key": key, "accepted": accepted},
            translated_message="application.modelo.errors.calculate_casilla_alias_refused",
        )

    accepted_hint = ", ".join(sorted(known_ids)[:20])
    if len(known_ids) > 20:
        accepted_hint += ", ..."
    raise ModeloCalculateCasillaInputError(
        f"--casilla {key!r} is not a canonical casilla.id in this revision. "
        f"Accepted casilla.id values include: {accepted_hint}. "
        "Use `aeat app modelo casillas <MODELO>` to list valid casilla IDs.",
        context={"key": key, "accepted": accepted_hint},
        translated_message="application.modelo.errors.calculate_casilla_unknown",
    )


def modelo_202_modality_for_work_unit(work_unit: WorkUnit) -> Modelo202ModalitySummary | None:
    """Return a :class:`Modelo202ModalitySummary` for a work unit, or ``None`` when not applicable."""
    if str(work_unit.modelo) != Modelo.M202:
        return None

    from ...application.user_profile import projection_for_taxpayer
    from ...application.workflow import workflow_state_repository
    from ...domain.calculations.registry.applicability import derive_modelo_202_modality

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    profile = projection_for_taxpayer(record or {}, tax_id_default="00000000T")
    verdict = derive_modelo_202_modality(profile)
    return Modelo202ModalitySummary(modality=verdict.modality.value, reason=verdict.reason)


def authorization_advisory_for_modelo(modelo: str) -> ModeloAuthorizationAdvisorySummary | None:
    """Return a :class:`ModeloAuthorizationAdvisorySummary` for an unauthorized-but-computable modelo."""
    from ...core.access_gate import AuthorizationState

    try:
        capability = resources().modelos.authority.authorization(modelo.strip())
    except AeatError:
        return None
    if capability.state is AuthorizationState.AUTHORIZED:
        return None
    if not capability.has_engine:
        return None
    return ModeloAuthorizationAdvisorySummary(state=capability.state.value)


def apply_calculation_shortcut_inputs(
    *,
    work_unit_id: str,
    casilla_inputs: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
    prestacion_inss_exenta: Decimal | None = None,
    meses_trabajo_con_hijo_menor_3: tuple[tuple[str, int], ...] = (),
    rescate_plan_pensiones_capital: Decimal | None = None,
    rescate_plan_pensiones_aportaciones_pre_2007: Decimal | None = None,
    rescate_plan_pensiones_aportaciones_totales: Decimal | None = None,
    sal_beneficio_neto: Decimal | None = None,
    sal_reserva_dotada: Decimal | None = None,
    sal_capital_social: Decimal | None = None,
    autoconsumo_promotor_base: Decimal | None = None,
) -> tuple[dict[CasillaId, Decimal], dict[BindingId, Decimal]]:
    """Apply backend-owned tax shortcut inputs for a calculation command.

    The CLI may parse option strings into typed values, but legal-rule
    computations, semantic casilla routing, and special binding injection
    belong to the application layer.
    """
    resolved_casilla_values = dict(casilla_inputs)
    resolved_bindings = dict(binding_values)

    if prestacion_inss_exenta is not None:
        resolved_casilla_values[_semantic_role_casilla_id(work_unit_id, _INSS_EXENTA_SEMANTIC_ROLE)] = (
            prestacion_inss_exenta
        )

    if meses_trabajo_con_hijo_menor_3:
        deduccion = compute_deduccion_maternidad_0611(list(meses_trabajo_con_hijo_menor_3))
        resolved_casilla_values[_semantic_role_casilla_id(work_unit_id, _DEDUCCION_MATERNIDAD_SEMANTIC_ROLE)] = (
            Decimal(deduccion)
        )

    pension_values = (
        rescate_plan_pensiones_capital,
        rescate_plan_pensiones_aportaciones_pre_2007,
        rescate_plan_pensiones_aportaciones_totales,
    )
    if any(value is not None for value in pension_values):
        if not all(value is not None for value in pension_values):
            raise ModeloCalculateShortcutInputError(
                "--rescate-plan-pensiones-capital, --rescate-plan-pensiones-aportaciones-pre-2007, "
                "and --rescate-plan-pensiones-aportaciones-totales must all be supplied together.",
                translated_message="application.modelo.errors.calculate_pension_inputs_incomplete",
            )
        assert rescate_plan_pensiones_capital is not None
        assert rescate_plan_pensiones_aportaciones_pre_2007 is not None
        assert rescate_plan_pensiones_aportaciones_totales is not None
        resolved_casilla_values[_semantic_role_casilla_id(work_unit_id, _REDUCCION_TRABAJO_SEMANTIC_ROLE)] = (
            compute_dt12_reduccion_plan_pensiones(
                gross_rescate=rescate_plan_pensiones_capital,
                aportaciones_pre_2007=rescate_plan_pensiones_aportaciones_pre_2007,
                aportaciones_totales=rescate_plan_pensiones_aportaciones_totales,
            )
        )

    sal_values = (sal_beneficio_neto, sal_reserva_dotada, sal_capital_social)
    if any(value is not None for value in sal_values):
        if not all(value is not None for value in sal_values):
            raise ModeloCalculateShortcutInputError(
                "--sal-beneficio-neto, --sal-reserva-dotada, and --sal-capital-social must all be supplied together.",
                translated_message="application.modelo.errors.calculate_sal_inputs_incomplete",
            )
        assert sal_beneficio_neto is not None
        assert sal_reserva_dotada is not None
        assert sal_capital_social is not None
        resolved_casilla_values[_semantic_role_casilla_id(work_unit_id, _SAL_RESERVA_ESPECIAL_SEMANTIC_ROLE)] = (
            compute_sal_reserva_especial_dotacion(
                beneficio_neto=sal_beneficio_neto,
                reserva_dotada=sal_reserva_dotada,
                capital_social=sal_capital_social,
            )
        )

    if autoconsumo_promotor_base is not None:
        resolved_bindings[_AUTOCONSUMO_PROMOTOR_BINDING] = autoconsumo_promotor_base

    return resolved_casilla_values, resolved_bindings


def _semantic_role_casilla_id(work_unit_id: str, semantic_role: str) -> CasillaId:
    catalogue = WorkUnitCatalogueRepository().load()
    work_unit = catalogue.get(work_unit_id)
    if work_unit is None:
        raise LookupError(f"work unit {work_unit_id!r} not found")
    snapshot = resources().modelos.authority.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    try:
        casilla_id = casilla_id_for_unique_semantic_role(snapshot, semantic_role)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloCalculateSemanticRoleError(
            str(exc),
            context=exc.ambiguity.context(),
            translated_message="application.modelo.errors.calculate_semantic_role_ambiguous",
        ) from exc
    if casilla_id is not None:
        return casilla_id
    raise ModeloCalculateSemanticRoleError(
        f"modelo revision has no casilla with semantic_role={semantic_role!r}",
        context={
            "modelo": snapshot.modelo.id,
            "revision": snapshot.revision.id,
            "semantic_role": semantic_role,
        },
        translated_message="application.modelo.errors.calculate_semantic_role_missing",
    )


__all__ = [
    "Modelo202ModalitySummary",
    "ModeloAuthorizationAdvisorySummary",
    "ModeloCalculateCasillaInputError",
    "ModeloCalculateDecimalInputError",
    "ModeloCalculateDetailRowsError",
    "ModeloCalculateInputError",
    "ModeloCalculateRelationInputError",
    "ModeloCalculateSemanticRoleError",
    "ModeloCalculateShortcutInputError",
    "ModeloWorkCalculationServiceResult",
    "WorkCalculateInputBundle",
    "apply_calculation_shortcut_inputs",
    "authorization_advisory_for_modelo",
    "build_work_calculate_input_bundle",
    "calculate_modelo_work_revision",
    "modelo_202_modality_for_work_unit",
]
