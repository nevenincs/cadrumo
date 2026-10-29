"""Typed input bundle and validation for modelo work calculation.

This module converts CLI override tokens into a
:class:`WorkCalculateInputBundle`, resolves the active work unit's
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`, and validates
canonical :class:`~cadrumo.core.casilla_id.CasillaId` values,
binding channels, relation ids, and shortcut-derived semantic-role casillas
before the calculate service persists a
:class:`~CalculationRevision`.

The application result pairs that persisted revision with its parent
:class:`~WorkUnit` and any non-blocking
:class:`~cadrumo.application.aggregation.source_mesh.CalculationSourceDiagnostic` rows
surfaced by bucket aggregation or post-calculation advisory collectors.

See Also:
    :mod:`cadrumo.entrypoints.cli._modelo_work_calculate_cli`:
        Parses the operator-facing ``modelo work calculate`` command and calls
        this module to build the input bundle.
    :func:`cadrumo.application.modelo.calculation_bucket_actions.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`:
        Consumes the validated bundle and persists the draft calculation
        revision.
    :mod:`cadrumo.application.modelo.calculation_resolution`:
        Merges caller, backend, profile, relation, and borrador channels before
        registry-engine execution.
    :func:`cadrumo.application.modelo.semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`:
        Resolves shortcut inputs onto the unique casilla declared by a revision.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.modelo import Modelo
from ...core.rescate_type import RescateType
from ...core.time.clock import today_madrid
from ...domain.calculations.registry.binding_targets import revision_bindings_by_id
from ...domain.calculations.registry.casilla_membership import (
    casillas_by_id,
    row_field_template_records_by_casilla,
)
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ...domain.calculations.registry.runtime_graph import (
    enum_consumed_binding_ids,
    revision_date_binding_ids,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.calculations.registry.schema_scalars import (
    registry_scalar_value_type,
)
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from ...domain.modelos.dt12_reduccion import (
    Dt12WindowEligibility,
    compute_dt12_reduccion_plan_pensiones,
    dt12_regime_window_eligibility,
)
from ...domain.modelos.modelo_fact_context import ModeloFactResolutionContext
from ...domain.modelos.row_models import (
    ModeloDetailRow,
)
from ...domain.modelos.sal_reserva_especial import compute_sal_reserva_especial_dotacion
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ._registry_helpers import validate_casilla_input_ids
from .calculate_input_validation import (
    ModeloCalculateBindingInputError,
    ModeloCalculateCasillaInputError,
    ModeloCalculateDecimalInputError,
    ModeloCalculateDetailRowsError,
    ModeloCalculateInputError,
    ModeloCalculateRelationInputError,
    ModeloCalculateSemanticRoleError,
    ModeloCalculateShortcutInputError,
    ModeloCalculateTextInputError,
    decimal,
    decimal_binding_value,
    projected_m210_tipo_renta_code,
    refuse_row_field_casilla_override,
    text_value,
    typed_text_value,
    validate_detail_rows,
    validated_binding_input_channel,
    validated_canonical_casilla_id,
    validated_m210_official_tipo_renta_code,
    validated_relation_id,
)
from .calculate_maternidad_advisory import (
    ambiguous_relacion_hijo_ids,
    maternidad_ambiguous_relacion_advisory,
    maternidad_ceilings_unresolved_advisory,
    maternidad_cotizaciones_ceiling_advisory,
    maternidad_meses_withheld_advisory,
)
from .calculation_action_ports import CalculationActionPorts

# Intra-package reuse of a sibling module's cap, permitted by the architecture
# rule; only cross-package private reaches are barred, and that gate is separate.
from .profile_derived_facts import MaternidadMesesResolution
from .semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_revision_semantic_role
from .work_plazo import M210PlazoResolution
from .work_profile import ModeloWorkProfile
from .work_selection import (
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    resolve_modelo_work_bucket,
    select_modelo_work_resolution,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.user_profile.values import UserProfileRecord


# Registry authority: selected calculate-input declarations are consumed through
# the pinned operation and the dated mapping fact.
def _registry_calculate_input_declarations(
    work_unit: WorkUnit | None = None,
    *,
    operation: PinnedAuthorityOperation,
) -> ResolvedMappingFact:
    """Resolve calculate-input declarations from the selected registry mapping."""
    effective_date = date(work_unit.filing_year, 12, 31) if work_unit is not None else today_madrid()
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-calculate-input-declarations-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("calculate-input declarations must resolve as a mapping fact")
    return resolved


def _registry_calculate_input_declaration(
    key: str,
    *,
    work_unit: WorkUnit | None = None,
    operation: PinnedAuthorityOperation,
) -> str:
    """Return one nonblank calculate-input declaration from exact authority."""
    resolved = _registry_calculate_input_declarations(work_unit, operation=operation)
    values = tuple(str(entry.value).strip() for entry in resolved.payload.entries if str(entry.key) == key)
    if len(values) != 1 or not values[0]:
        raise TypeError(f"calculate-input declarations must define exactly one nonblank {key!r}")
    return values[0]


@dataclass(frozen=True, slots=True)
class WorkCalculateInputBundle:
    """Application-facing input channels for one ``modelo work calculate`` run.

    The bundle is the handoff from CLI parsing to application calculation. It
    separates manual casilla inputs, text casilla inputs, decimal binding
    overrides, enum binding overrides, relation values, typed detail rows, and
    the optional borrador snapshot id so each downstream channel keeps its
    registry-declared type. ``text_casilla_inputs`` carries operator-supplied
    text-scalar casilla values — every family whose
    :func:`~cadrumo.domain.calculations.registry.schema_scalars.registry_scalar_value_type` is
    ``"str"``, such as Modelo 210's ``tipo_renta`` (``text``) and Modelo 303's
    ``decl.periodo`` (``period_code``) — on
    a channel parallel to ``casilla_inputs``: the registry engine's
    ``calculate_registry_snapshot(text_inputs=...)`` reads it for categorical
    formula dispatch, and it rides into the persisted
    :class:`~CalculationRevision`
    ``input_values_by_casilla_id`` field so the verification layer's
    required-casilla and
    ``casilla_equals_implies_nonzero`` predicate checks can see it. It is never
    folded into the Decimal ``casilla_values`` projection.
    """

    casilla_inputs: Mapping[CasillaId, Decimal]
    text_casilla_inputs: Mapping[CasillaId, str]
    m210_official_tipo_renta_code: str | None
    binding_values: Mapping[BindingId, Decimal]
    enum_binding_values: Mapping[BindingId, str]
    relation_values: Mapping[RelationId, Decimal]
    detail_rows: tuple[ModeloDetailRow, ...]
    borrador_snapshot_id: str | None
    filing_instance_evidence: FilingInstanceEvidence | None = None
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = M210GrossIncomeSourceMode.MANUAL
    shortcut_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()
    """Non-blocking advisories raised while resolving shortcut inputs.

    Carries the DT 12ª apartado-3 window diagnostics
    (:func:`apply_calculation_shortcut_inputs`) so the calculate service can fold
    them into its ``source_diagnostics`` / ``source_advisories`` channel. The
    shortcut path is the only site with the contingencia/rescate year facts, so
    the advisory originates here and rides the bundle to the operator surface.
    """
    cleared_casilla_ids: tuple[CasillaId, ...] = ()
    """Casillas the operator explicitly cleared, replayed from the calculation head."""
    record_operator_layer: bool = False
    """Whether the revision records these inputs as the operator's own layer.

    Only a replay of a head whose layer is known sets it, so explicit
    full-specification inputs are never mistaken for the operator's typed values.
    """

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
        filing_instance_evidence: FilingInstanceEvidence | None = None,
        text_casilla_inputs: Mapping[CasillaId, str] | None = None,
        m210_official_tipo_renta_code: str | None = None,
        m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = M210GrossIncomeSourceMode.MANUAL,
        shortcut_diagnostics: tuple[CalculationSourceDiagnostic, ...] = (),
        cleared_casilla_ids: tuple[CasillaId, ...] = (),
        record_operator_layer: bool = False,
    ) -> WorkCalculateInputBundle:
        """Freeze CLI-assembled mappings before crossing into calculation services.

        Returns:
            :class:`WorkCalculateInputBundle`: The frozen calculate input bundle.
        """
        return cls(
            casilla_inputs=dict(casilla_inputs),
            text_casilla_inputs=dict(text_casilla_inputs or {}),
            m210_official_tipo_renta_code=(
                m210_official_tipo_renta_code.strip()
                if (m210_official_tipo_renta_code is not None and m210_official_tipo_renta_code)
                else None
            ),
            binding_values=dict(binding_values),
            enum_binding_values=dict(enum_binding_values),
            relation_values=dict(relation_values),
            detail_rows=detail_rows,
            borrador_snapshot_id=borrador_snapshot_id.strip()
            if (borrador_snapshot_id is not None and borrador_snapshot_id)
            else None,
            filing_instance_evidence=filing_instance_evidence,
            m210_gross_income_source_mode=m210_gross_income_source_mode,
            shortcut_diagnostics=shortcut_diagnostics,
            cleared_casilla_ids=cleared_casilla_ids,
            record_operator_layer=record_operator_layer,
        )

    def optional_binding_values(self) -> Mapping[BindingId, Decimal] | None:
        """Return decimal binding values using the calculation-service optional contract."""
        return self.binding_values or None

    def optional_enum_binding_values(self) -> Mapping[BindingId, str] | None:
        """Return enum binding values using the calculation-service optional contract."""
        return self.enum_binding_values or None

    def optional_relation_values(self) -> Mapping[RelationId, Decimal] | None:
        """Return relation values using the calculation-service optional contract."""
        return self.relation_values or None

    def optional_text_casilla_inputs(self) -> Mapping[CasillaId, str] | None:
        """Return text casilla inputs using the calculation-service optional contract."""
        return self.text_casilla_inputs or None


@dataclass(frozen=True, slots=True)
class Modelo202ModalitySummary:
    """Application summary of the Modelo 202 Art. 40.2 / 40.3 modality.

    The calculate CLI includes this advisory when the work unit is a Modelo 202
    calculation so the operator can see which registry modality the profile
    selected and why.
    """

    modality: str
    reason: str


@dataclass(frozen=True, slots=True)
class ModeloWorkCalculationServiceResult:
    """Application-owned result for one `modelo work calculate` command.

    ``revision`` is the persisted
    :class:`~CalculationRevision`; ``work_unit`` is the
    parent :class:`~WorkUnit` returned by the writer so
    renderers do not have to repeat the lookup. The optional advisory summaries
    are presentation data derived from registry applicability and authorization
    metadata.

    ``source_diagnostics`` carries the NON-blocking
    :class:`~cadrumo.application.aggregation.source_mesh.CalculationSourceDiagnostic` rows the
    source mesh and post-calculation advisory collectors raised. They include
    unresolved or deferred binding sources, unrouted ledger observations, and
    calculate-grade official-box / prior-payment / settlement advisories. The
    calculate verb succeeded and persisted the revision regardless; surfacing
    these rows keeps omitted or degraded source evidence operator-visible
    (no-silent-under-declaration). Each diagnostic's ``message`` carries the
    evidence needed by the CLI renderer.
    """

    revision: CalculationRevision
    work_unit: WorkUnit
    revision_published: bool
    modality: Modelo202ModalitySummary | None = None
    source_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()
    plazo_resolutions: tuple[M210PlazoResolution, ...] = ()


def calculate_modelo_work_revision(
    *,
    work_unit_id: str,
    actor: str,
    inputs: WorkCalculateInputBundle,
    ports: CalculationActionPorts,
    profile: ModeloWorkProfile | None = None,
) -> ModeloWorkCalculationServiceResult:
    """Persist a draft calculation revision as a :class:`ModeloWorkCalculationServiceResult`.

    The function forwards the already validated :class:`WorkCalculateInputBundle`
    into the bucket-aggregation calculation path, retains the writer-returned parent
    :class:`~WorkUnit`, and attaches any Modelo 202
    modality, authorization, or non-blocking source diagnostics needed by the
    CLI payload. ``profile`` is the work profile the command already loaded;
    when omitted, the calculation loads it once. Every profile read below
    uses the profile the calculation checked.

    See Also:
        :func:`cadrumo.application.modelo.calculation_bucket_actions.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`:
            Runs source aggregation and persists the calculation revision.
        :func:`cadrumo.entrypoints.cli._modelo_work_calculate_cli._run_work_calculate`:
            Calls this service and serialises the result for the operator.
    """
    from .calculation_bucket_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics

    calculation = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_id,
        ports=ports,
        actor=actor,
        casilla_inputs=inputs.casilla_inputs,
        text_casilla_inputs=inputs.optional_text_casilla_inputs(),
        cleared_casilla_ids=inputs.cleared_casilla_ids,
        record_operator_layer=inputs.record_operator_layer,
        m210_official_tipo_renta_code=inputs.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=inputs.m210_gross_income_source_mode,
        binding_values=inputs.optional_binding_values(),
        enum_binding_values=inputs.optional_enum_binding_values(),
        borrador_snapshot_id=inputs.borrador_snapshot_id,
        relation_values=inputs.optional_relation_values(),
        detail_rows=inputs.detail_rows,
        filing_instance_evidence=inputs.filing_instance_evidence,
        profile=profile,
    )
    revision = calculation.revision
    work_unit = calculation.publication.work_unit
    plazo_resolutions: tuple[M210PlazoResolution, ...] = ()
    if work_unit.modelo == Modelo("210"):
        from .m303_regimen_simplificado_scope import taxpayer_profile_for_work
        from .work_plazo import calculated_m210_plazo_resolution

        resolution = calculated_m210_plazo_resolution(
            work_unit=work_unit,
            revision=revision,
            workflow_profile=taxpayer_profile_for_work(calculation.profile),
            operation=ports.operation,
        )
        if resolution is not None:
            plazo_resolutions = (resolution,)
    return ModeloWorkCalculationServiceResult(
        revision=revision,
        work_unit=work_unit,
        revision_published=calculation.publication.published,
        modality=modelo_202_modality_for_record(work_unit, calculation.profile.record, operation=ports.operation),
        source_diagnostics=(*inputs.shortcut_diagnostics, *calculation.source_diagnostics),
        plazo_resolutions=plazo_resolutions,
    )


def _validated_string_casilla_override(
    raw_value: str,
    *,
    key: CasillaId,
    casilla_def: CasillaDefinition,
    operation: PinnedAuthorityOperation,
) -> tuple[str, str | None]:
    """Validate one registry-declared string casilla and return its projection."""
    if casilla_def.semantic_role == "irnr_tipo_renta":
        official_code = validated_m210_official_tipo_renta_code(raw_value, key=key)
        return projected_m210_tipo_renta_code(official_code), official_code
    declarante_selector_role = _registry_calculate_input_declaration(
        "modelo.role.declarante_selector",
        operation=operation,
    )
    if casilla_def.semantic_role == declarante_selector_role:
        return _validated_declarante_selector(raw_value, key=key, casilla_def=casilla_def), None
    return typed_text_value(raw_value, key=key, casilla_def=casilla_def), None


def _validated_declarante_selector(raw_value: str, *, key: CasillaId, casilla_def: CasillaDefinition) -> str:
    """Refuse a purely numeric value routed to a declarante-selector text casilla.

    The selector names the member who obtains the income, never an amount. A
    bare number is a mis-routed income figure: on the text channel it would be
    stored silently and ignored by the formula chain, understating the base.
    """
    value = text_value(raw_value, key=key)
    try:
        Decimal(value)
    except (InvalidOperation, ValueError):
        return typed_text_value(value, key=key, casilla_def=casilla_def)
    raise ModeloCalculateTextInputError(
        context={"key": key, "label": casilla_def.label, "data_type": casilla_def.data_type},
        translated_message="application.modelo.errors.calculate_text_casilla_numeric_value",
    )


def _resolve_casilla_overrides(
    casilla_overrides: Mapping[str, str],
    revision: ModeloRevision,
    *,
    operation: PinnedAuthorityOperation,
    work_unit: WorkUnit,
) -> tuple[dict[CasillaId, Decimal], dict[CasillaId, str], str | None]:
    """Resolve canonical casilla overrides onto their registry-declared channels."""
    revision_casillas_by_id = casillas_by_id(revision)
    row_field_records = row_field_template_records_by_casilla(revision)
    casilla_inputs: dict[CasillaId, Decimal] = {}
    text_casilla_inputs: dict[CasillaId, str] = {}
    m210_official_tipo_renta_code: str | None = None
    for raw_key, raw_value in casilla_overrides.items():
        key = validated_canonical_casilla_id(raw_key, revision, work_unit=work_unit)
        # Before any value parsing: a row field is refused for being one, not
        # for a value its scalar channel could not have held anyway.
        if key in row_field_records:
            refuse_row_field_casilla_override(key, records=row_field_records[key], work_unit=work_unit)
        casilla_def = revision_casillas_by_id.get(key)
        if casilla_def is not None and registry_scalar_value_type(casilla_def.data_type) == "str":
            text_value, official_code = _validated_string_casilla_override(
                raw_value,
                key=key,
                casilla_def=casilla_def,
                operation=operation,
            )
            text_casilla_inputs[key] = text_value
            if official_code is not None:
                m210_official_tipo_renta_code = official_code
            continue
        casilla_inputs[key] = decimal(raw_value, flag="--casilla", key=key)
    return (
        validate_casilla_input_ids(revision, casilla_inputs),
        text_casilla_inputs,
        m210_official_tipo_renta_code,
    )


def resolve_binding_overrides(
    binding_overrides: Mapping[BindingId, str],
    revision: ModeloRevision,
    *,
    work_unit: WorkUnit | None = None,
) -> tuple[dict[BindingId, Decimal], dict[BindingId, str]]:
    """Resolve binding overrides using the revision's declared input channels.

    ``work_unit`` is the calculate target; when supplied, a refused override
    carries its declared ``modelo.work.calculate`` precondition failure.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {}
    if not binding_overrides:
        return binding_values, enum_binding_values

    bindings_by_id = revision_bindings_by_id(revision)
    known_binding_ids = set(bindings_by_id)
    enum_channel_ids = enum_consumed_binding_ids(revision)
    date_channel_ids = revision_date_binding_ids(revision)
    for raw_key, raw_value in binding_overrides.items():
        if raw_key in date_channel_ids:
            raise ModeloCalculateBindingInputError(
                context={"key": raw_key},
                translated_message="application.modelo.errors.calculate_binding_is_date_sourced",
            )
        key, channel = validated_binding_input_channel(
            raw_key,
            revision,
            known_binding_ids,
            enum_channel_ids,
            work_unit=work_unit,
        )
        if channel == "enum":
            enum_binding_values[key] = raw_value
            continue
        binding_values[key] = decimal_binding_value(raw_value, bindings_by_id[key], work_unit=work_unit)
    return binding_values, enum_binding_values


def _resolve_relation_overrides(
    relation_overrides: Mapping[RelationId, str],
    revision: ModeloRevision,
) -> dict[RelationId, Decimal]:
    """Resolve relation overrides against the active revision and decimal grammar."""
    known_relation_ids = {binding.id for binding, _ in relation_prefill_bindings_for_period(revision)}
    relation_values: dict[RelationId, Decimal] = {}
    for raw_key, raw_value in relation_overrides.items():
        key = validated_relation_id(raw_key, known_relation_ids)
        relation_values[key] = decimal(raw_value, flag="--relation", key=key)
    return relation_values


def build_work_calculate_input_bundle(
    *,
    work_unit_id: str,
    ports: CalculationActionPorts,
    casilla_overrides: Mapping[str, str],
    binding_overrides: Mapping[BindingId, str],
    relation_overrides: Mapping[RelationId, str],
    detail_rows: tuple[ModeloDetailRow, ...],
    borrador_snapshot_id: str | None,
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode = M210GrossIncomeSourceMode.MANUAL,
    prestacion_inss_exenta: Decimal | None = None,
    rescate_plan_pensiones_capital: Decimal | None = None,
    rescate_plan_pensiones_aportaciones_pre_2007: Decimal | None = None,
    rescate_plan_pensiones_aportaciones_totales: Decimal | None = None,
    rescate_plan_pensiones_tipo: RescateType | None = None,
    rescate_plan_pensiones_contingencia_year: int | None = None,
    rescate_plan_pensiones_rescate_year: int | None = None,
    sal_beneficio_neto: Decimal | None = None,
    sal_reserva_dotada: Decimal | None = None,
    sal_capital_social: Decimal | None = None,
    autoconsumo_promotor_base: Decimal | None = None,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> WorkCalculateInputBundle:
    """Build a :class:`WorkCalculateInputBundle` from operator-supplied tokens.

    The active work unit determines the
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision` used for every
    validation step. ``--casilla`` values must be canonical casilla ids; printed
    numbers and ambiguous noncanonical references are refused. A ``--casilla``
    key whose registry :class:`~cadrumo.domain.calculations.registry.schema_surfaces.CasillaDefinition`
    declares a text-scalar ``data_type`` — every family whose
    :func:`~cadrumo.domain.calculations.registry.schema_scalars.registry_scalar_value_type` is
    ``"str"``, so ``text`` (Modelo 210's ``tipo_renta``) alongside
    ``period_code``, ``nif``, ``iban`` and the rest — is routed onto the
    parallel text-casilla channel, canonicalised by that family's own declared
    validator instead of being forced through the decimal parser; every other
    ``--casilla`` key keeps the existing decimal-only contract. Membership is
    derived from the type family rather than keyed on one literal member, so a
    string-family override can never be silently routed to the Decimal channel.
    ``--binding`` is routed by the
    registry-declared channel, so enum bindings stay as strings, decimal
    bindings are parsed as :class:`~decimal.Decimal`, and date-valued profile
    bindings are rejected with profile guidance. ``--relation`` values must
    match declared relation ids.

    Detail rows are checked before engine dispatch, and shortcut flags are
    translated into semantic-role casilla values or backend-owned bindings by
    :func:`cadrumo.application.modelo.calculate_input.apply_calculation_shortcut_inputs`.
    ``profile`` is the work profile the command already loaded; when omitted,
    it is loaded where a profile-backed shortcut first needs it.
    """
    catalogue, bucket_id = _capture_work_catalogue(work_unit_id, repository=ports.work_unit_repository)
    work_unit = _selected_work_unit(work_unit_id=work_unit_id, catalogue=catalogue, bucket_id=bucket_id)
    validate_detail_rows(detail_rows, work_unit=work_unit, operation=operation)
    revision = _revision_for_work_unit(work_unit, operation=operation)
    casilla_inputs, text_casilla_inputs, m210_official_tipo_renta_code = _resolve_casilla_overrides(
        casilla_overrides,
        revision,
        operation=operation,
        work_unit=work_unit,
    )
    binding_values, enum_binding_values = resolve_binding_overrides(
        binding_overrides,
        revision,
        work_unit=work_unit,
    )

    casilla_inputs, binding_values, shortcut_diagnostics = apply_calculation_shortcut_inputs(
        work_unit=work_unit,
        casilla_inputs=casilla_inputs,
        binding_values=binding_values,
        fact_context=_modelo_fact_context(work_unit, operation=operation),
        operation=operation,
        prestacion_inss_exenta=prestacion_inss_exenta,
        rescate_plan_pensiones_capital=rescate_plan_pensiones_capital,
        rescate_plan_pensiones_aportaciones_pre_2007=rescate_plan_pensiones_aportaciones_pre_2007,
        rescate_plan_pensiones_aportaciones_totales=rescate_plan_pensiones_aportaciones_totales,
        rescate_plan_pensiones_tipo=rescate_plan_pensiones_tipo,
        rescate_plan_pensiones_contingencia_year=rescate_plan_pensiones_contingencia_year,
        rescate_plan_pensiones_rescate_year=rescate_plan_pensiones_rescate_year,
        sal_beneficio_neto=sal_beneficio_neto,
        sal_reserva_dotada=sal_reserva_dotada,
        sal_capital_social=sal_capital_social,
        autoconsumo_promotor_base=autoconsumo_promotor_base,
        profile=profile,
    )

    relation_values = _resolve_relation_overrides(relation_overrides, revision)
    return WorkCalculateInputBundle.build(
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        detail_rows=detail_rows,
        borrador_snapshot_id=borrador_snapshot_id,
        filing_instance_evidence=filing_instance_evidence,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        shortcut_diagnostics=shortcut_diagnostics,
        # This builder validates the explicit caller tier. Retain its ownership
        # before aggregation merges source values into the saved replay maps.
        record_operator_layer=True,
    )


def _capture_work_catalogue(
    work_unit_id: str,
    *,
    repository: WorkUnitCatalogueRepositoryProtocol,
) -> tuple[WorkUnitCatalogue, str]:
    """Capture the active work catalogue before a caller invokes the pure selector."""
    request = ModeloWorkSelectorRequest(work_unit_id=work_unit_id)
    bucket_id = resolve_modelo_work_bucket(request)
    return repository.load(), bucket_id


def _selected_work_unit(*, work_unit_id: str, catalogue: WorkUnitCatalogue, bucket_id: str) -> WorkUnit:
    """Translate canonical exact-selection absence for calculation input callers."""
    request = ModeloWorkSelectorRequest(work_unit_id=work_unit_id)
    resolution = select_modelo_work_resolution(request, catalogue=catalogue, bucket_id=bucket_id)
    if resolution.state is not ModeloWorkSelectorState.RESOLVED or resolution.work_unit is None:
        raise LookupError(f"work unit {work_unit_id!r} not found")
    return resolution.work_unit


def _revision_for_work_unit(work_unit: WorkUnit, *, operation: PinnedAuthorityOperation) -> ModeloRevision:
    from ._calculation_helpers import resolve_registry_snapshot_for_work_unit

    # The calculate path needs the rung that computes amounts, not the
    # filing rung: a revision that honestly declares calculation must not be
    # refused for work this application does entirely in memory.
    return resolve_registry_snapshot_for_work_unit(
        work_unit,
        grade=RegistryAuthorityGrade.CALCULATION,
        operation=operation,
    ).revision


def _resolved_maternidad_meses(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile,
) -> MaternidadMesesResolution:
    """Resolve the Art. 81.1 maternidad months the work profile contributes."""
    from ._calculation_helpers import resolve_registry_snapshot_for_work_unit
    from .profile_derived_facts import resolve_maternidad_meses

    snapshot = resolve_registry_snapshot_for_work_unit(
        work_unit,
        grade=RegistryAuthorityGrade.CALCULATION,
        operation=operation,
    )
    return resolve_maternidad_meses(profile.record, snapshot, operation=operation)


def _maternidad_casilla_id(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> CasillaId | None:
    """The Art. 81.1 deducción casilla for this work unit, or ``None`` when the modelo has none.

    The gate on the whole derived-maternidad block. Resolving the role rather
    than testing the modelo id keeps the derivation registry-driven: a revision
    that declares the role gets the derived months with no code edit, and every
    modelo that does not is left untouched — including its profile read, which
    would otherwise run on every calculation of every modelo.
    """
    from .semantic_role_resolution import casilla_id_for_unambiguous_revision_semantic_role

    return casilla_id_for_unambiguous_revision_semantic_role(
        _revision_for_work_unit(work_unit, operation=operation),
        _registry_calculate_input_declaration(
            "modelo.role.deduccion_maternidad",
            work_unit=work_unit,
            operation=operation,
        ),
        modelo_id=str(work_unit.modelo),
    )


def modelo_202_modality_for_record(
    work_unit: WorkUnit,
    record: UserProfileRecord | None,
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> Modelo202ModalitySummary | None:
    """Return the Modelo 202 modality summary for an already-loaded profile record.

    Core types:
    :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
    """
    if str(work_unit.modelo) != Modelo("202"):
        return None

    from ...domain.calculations.registry.applicability_modelo202 import derive_modelo_202_modality
    from ...domain.calculations.registry.authority import bundled_indexed_authority
    from ..user_profile.projections import projection_for_taxpayer

    with nullcontext(operation) if operation is not None else bundled_indexed_authority().operation() as authority:
        profile = projection_for_taxpayer(record or {}, schema=authority.profile_schema())
        verdict = derive_modelo_202_modality(
            profile, effective_date=date(work_unit.filing_year, 12, 31), authority=authority
        )
    return Modelo202ModalitySummary(modality=verdict.modality.value, reason=verdict.reason)


def _supplied_option_group(
    values: tuple[Decimal | None, ...],
    *,
    message: str,
    translated_message: str,
) -> tuple[Decimal, ...] | None:
    """Return an all-or-nothing option group, or ``None`` when none was supplied.

    Presence is tested against ``None`` and never against truthiness, because a
    declared zero is a supplied value: a zero aportación is a fact the operator
    stated, not an omission.

    Raises:
        ModeloCalculateShortcutInputError: When the group is partially supplied.
    """
    supplied = tuple(value for value in values if value is not None)
    if not supplied:
        return None
    if len(supplied) != len(values):
        raise ModeloCalculateShortcutInputError(message, translated_message=translated_message)
    return supplied


def _maternidad_advisories(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None,
) -> list[CalculationSourceDiagnostic]:
    """Raise the non-blocking advisories for the maternidad-deduction casilla.

    Returns nothing when the bucket has no profile yet, mirroring the
    silent-absent handling profile-sourced bindings already apply.
    """
    maternidad_casilla_id = _maternidad_casilla_id(work_unit, operation=operation)
    if maternidad_casilla_id is None:
        return []
    if profile is None:
        from .profile_readiness_gate import load_modelo_work_profile

        profile = load_modelo_work_profile(
            bucket_id=work_unit.bucket_id,
            profile_decode_context=operation.profile_decode_context(),
        )
    if profile is None:
        return []
    maternidad = _resolved_maternidad_meses(work_unit, operation=operation, profile=profile)
    # The active profile's descendiente records are the SOLE authority for
    # casilla 0611: the calculate-time `--meses-trabajo-con-hijo-menor-3`
    # shortcut this block once reconciled against (a free-form hijo id no
    # descendant record answered to, itself never eligibility-checked) is
    # retired. One channel means no two-authorities refusal is possible any
    # more, and both advisories below always evaluate against the one
    # source rather than being gated on a second channel's absence.
    candidates = (
        maternidad_ceilings_unresolved_advisory(
            maternidad.declares_meses and not maternidad.ceilings_resolved,
            maternidad_casilla_id,
        ),
        maternidad_meses_withheld_advisory(maternidad.withheld_indices, maternidad_casilla_id),
        maternidad_cotizaciones_ceiling_advisory(
            maternidad.declares_meses and maternidad.cotizaciones_ceiling_inexpressible,
            maternidad_casilla_id,
        ),
        maternidad_ambiguous_relacion_advisory(
            ambiguous_relacion_hijo_ids(
                frozenset(hijo_id for hijo_id, _ in maternidad.pairs),
                profile=profile,
            ),
            maternidad_casilla_id,
        ),
    )
    return [advisory for advisory in candidates if advisory is not None]


def _pension_rescate_contributions(
    *,
    work_unit: WorkUnit,
    capital: Decimal | None,
    aportaciones_pre_2007: Decimal | None,
    aportaciones_totales: Decimal | None,
    tipo: RescateType | None,
    contingencia_year: int | None,
    rescate_year: int | None,
    fact_context: ModeloFactResolutionContext,
    operation: PinnedAuthorityOperation,
) -> tuple[dict[CasillaId, Decimal], list[CalculationSourceDiagnostic]]:
    """Resolve the DT 12ª pension-rescate reducción and its window advisories.

    A window proven CLOSED withholds the reducción rather than injecting it, so
    the returned mapping is empty in that case while the advisory still names
    the refusal.
    """
    supplied = _supplied_option_group(
        (capital, aportaciones_pre_2007, aportaciones_totales),
        message=(
            "--rescate-plan-pensiones-capital, --rescate-plan-pensiones-aportaciones-pre-2007, "
            "and --rescate-plan-pensiones-aportaciones-totales must all be supplied together."
        ),
        translated_message="application.modelo.errors.calculate_pension_inputs_incomplete",
    )
    if supplied is None:
        return {}, []
    gross_rescate, resolved_pre_2007, resolved_totales = supplied
    reduccion = compute_dt12_reduccion_plan_pensiones(
        gross_rescate=gross_rescate,
        aportaciones_pre_2007=resolved_pre_2007,
        aportaciones_totales=resolved_totales,
        context=fact_context,
    )
    reduccion_casilla_id = _semantic_role_casilla_id(
        work_unit,
        _registry_calculate_input_declaration(
            "modelo.role.reduccion_trabajo",
            work_unit=work_unit,
            operation=operation,
        ),
        operation=operation,
    )
    inject, window_advisory = _dt12_window_decision(
        reduccion=reduccion,
        eligibility=_dt12_window_verdict(
            work_unit=work_unit,
            contingencia_year=contingencia_year,
            rescate_year=rescate_year,
            fact_context=fact_context,
        ),
        reduccion_casilla_id=reduccion_casilla_id,
    )
    advisories: list[CalculationSourceDiagnostic] = []
    if window_advisory is not None:
        advisories.append(window_advisory)
    if tipo is RescateType.PARCIAL:
        advisories.append(_dt12_parcial_guidance_advisory(reduccion_casilla_id))
    casilla_values: dict[CasillaId, Decimal] = {}
    if inject:
        casilla_values[reduccion_casilla_id] = reduccion
    return casilla_values, advisories


def _sal_reserva_especial_contribution(
    *,
    work_unit: WorkUnit,
    beneficio_neto: Decimal | None,
    reserva_dotada: Decimal | None,
    capital_social: Decimal | None,
    fact_context: ModeloFactResolutionContext,
    operation: PinnedAuthorityOperation,
) -> dict[CasillaId, Decimal]:
    """Resolve the SAL reserva-especial dotación into its semantic-role casilla."""
    supplied = _supplied_option_group(
        (beneficio_neto, reserva_dotada, capital_social),
        message="--sal-beneficio-neto, --sal-reserva-dotada, and --sal-capital-social must all be supplied together.",
        translated_message="application.modelo.errors.calculate_sal_inputs_incomplete",
    )
    if supplied is None:
        return {}
    resolved_neto, resolved_dotada, resolved_capital = supplied
    return {
        _semantic_role_casilla_id(
            work_unit,
            _registry_calculate_input_declaration(
                "modelo.role.sal_reserva_especial",
                work_unit=work_unit,
                operation=operation,
            ),
            operation=operation,
        ): compute_sal_reserva_especial_dotacion(
            beneficio_neto=resolved_neto,
            reserva_dotada=resolved_dotada,
            capital_social=resolved_capital,
            context=fact_context,
        )
    }


def apply_calculation_shortcut_inputs(
    *,
    work_unit: WorkUnit,
    casilla_inputs: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
    fact_context: ModeloFactResolutionContext,
    prestacion_inss_exenta: Decimal | None = None,
    rescate_plan_pensiones_capital: Decimal | None = None,
    rescate_plan_pensiones_aportaciones_pre_2007: Decimal | None = None,
    rescate_plan_pensiones_aportaciones_totales: Decimal | None = None,
    rescate_plan_pensiones_tipo: RescateType | None = None,
    rescate_plan_pensiones_contingencia_year: int | None = None,
    rescate_plan_pensiones_rescate_year: int | None = None,
    sal_beneficio_neto: Decimal | None = None,
    sal_reserva_dotada: Decimal | None = None,
    sal_capital_social: Decimal | None = None,
    autoconsumo_promotor_base: Decimal | None = None,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> tuple[dict[CasillaId, Decimal], dict[BindingId, Decimal], tuple[CalculationSourceDiagnostic, ...]]:
    """Apply backend-owned tax shortcut inputs for a calculation command.

    The CLI may parse option strings into typed values, but legal-rule
    computations, semantic casilla routing, and special binding injection
    belong to the application layer. INSS maternity/paternity, maternity
    deduction, DT 12 pension-rescue reduction, and SAL reserve inputs resolve to
    unique semantic-role casillas. The Modelo 303 autoconsumo-promotor shortcut
    writes the backend-owned binding consumed by the registry engine.

    The DT 12ª pension-rescate shortcut is fact-gated by the apartado-3 time
    window (LIRPF DT 12ª.4, added by Ley 26/2014). When the operator declares the
    contingencia year and the window predicate
    (:func:`~cadrumo.domain.modelos.dt12_reduccion.dt12_regime_window_eligibility`) proves the
    window CLOSED, the 40% reducción injection is WITHHELD — the legally correct
    no-régimen result, since applying an out-of-window reducción would be a silent
    over-reduction (under-declaration of tax per ``no-silent-under-declaration``).
    When the window is open the reducción injects as usual; when the contingencia
    year is absent the reducción injects with an unverified-window advisory. Every
    branch surfaces a non-blocking
    :class:`~cadrumo.application.aggregation.source_mesh.CalculationSourceDiagnostic`; calculate
    never aborts on the window verdict.

    Returns:
        A triple: resolved casilla inputs, resolved decimal binding values, and
        the non-blocking DT 12ª window advisory diagnostics (empty when no
        pension rescate was supplied).

    See Also:
        :func:`cadrumo.application.modelo.semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`:
            Selects the unique semantic-role casilla for shortcut values.
    """
    resolved_casilla_values = dict(casilla_inputs)
    resolved_bindings = dict(binding_values)
    advisories: list[CalculationSourceDiagnostic] = []

    if prestacion_inss_exenta is not None:
        resolved_casilla_values[
            _semantic_role_casilla_id(
                work_unit,
                _registry_calculate_input_declaration(
                    "modelo.role.inss_exenta",
                    work_unit=work_unit,
                    operation=operation,
                ),
                operation=operation,
            )
        ] = prestacion_inss_exenta

    advisories.extend(_maternidad_advisories(work_unit, operation=operation, profile=profile))

    pension_casilla_values, pension_advisories = _pension_rescate_contributions(
        work_unit=work_unit,
        capital=rescate_plan_pensiones_capital,
        aportaciones_pre_2007=rescate_plan_pensiones_aportaciones_pre_2007,
        aportaciones_totales=rescate_plan_pensiones_aportaciones_totales,
        tipo=rescate_plan_pensiones_tipo,
        contingencia_year=rescate_plan_pensiones_contingencia_year,
        rescate_year=rescate_plan_pensiones_rescate_year,
        fact_context=fact_context,
        operation=operation,
    )
    resolved_casilla_values.update(pension_casilla_values)
    advisories.extend(pension_advisories)

    resolved_casilla_values.update(
        _sal_reserva_especial_contribution(
            work_unit=work_unit,
            beneficio_neto=sal_beneficio_neto,
            reserva_dotada=sal_reserva_dotada,
            capital_social=sal_capital_social,
            fact_context=fact_context,
            operation=operation,
        ),
    )

    if autoconsumo_promotor_base is not None:
        binding_id = _registry_calculate_input_declaration(
            "modelo.binding.autoconsumo_promotor",
            work_unit=work_unit,
            operation=operation,
        )
        resolved_bindings[binding_id] = autoconsumo_promotor_base

    return resolved_casilla_values, resolved_bindings, tuple(advisories)


def _dt12_window_verdict(
    *,
    work_unit: WorkUnit,
    contingencia_year: int | None,
    rescate_year: int | None,
    fact_context: ModeloFactResolutionContext,
) -> Dt12WindowEligibility | None:
    """Evaluate the DT 12ª apartado-3 window when the contingencia year is declared.

    The contingencia year is the load-bearing fact: without it the window cannot
    be evaluated and the caller emits the unverified-window advisory. The rescate
    (percepción) year defaults to the work unit's filing year, the common case
    (the prestación is percibida in the year being filed).
    """
    if contingencia_year is None:
        return None
    resolved_rescate_year = rescate_year if rescate_year is not None else work_unit.filing_year
    return dt12_regime_window_eligibility(
        contingencia_year=contingencia_year,
        rescate_year=resolved_rescate_year,
        context=fact_context,
    )


def _modelo_fact_context(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> ModeloFactResolutionContext:
    """Compose the explicit filing/devengo coordinate for modelo scalar facts."""
    coordinate = date(work_unit.filing_year, 12, 31)
    return ModeloFactResolutionContext(
        authority=operation,
        filing_period=coordinate,
        devengo_date=coordinate,
    )


def _dt12_window_decision(
    *,
    reduccion: Decimal,
    eligibility: Dt12WindowEligibility | None,
    reduccion_casilla_id: CasillaId,
) -> tuple[bool, CalculationSourceDiagnostic | None]:
    """Decide whether to inject the DT 12ª reducción and which advisory to raise.

    Returns ``(inject, advisory)``. A proven-closed window WITHHOLDS the injection
    (``inject = False``) and raises a ``dt12_regime_window_closed`` advisory naming
    the closed window and eligible range; an open window injects with no advisory;
    an absent contingencia year injects with a ``dt12_regime_window_unverified``
    advisory.
    """
    if eligibility is None:
        return True, CalculationSourceDiagnostic(
            reason="dt12_regime_window_unverified",
            source_kind="dt12_regime_window",
            message=(
                "DT 12ª: the 40% pension-rescate reducción was applied, but the apartado-3 time "
                "window (LIRPF DT 12ª.4, Ley 26/2014) was not verified because no contingencia year "
                "was declared. The régimen applies only to prestaciones percibidas within the window "
                "measured from the contingencia year (the contingencia year plus the two following, "
                "or through 2018 for contingencias in 2010 or earlier, or the eighth following "
                "ejercicio for 2011–2014). Re-run with --contingencia-year to confirm the window."
            ),
            casilla_id=reduccion_casilla_id,
            # No casilla carries DT 12ª's own grounding (the reducción casilla's
            # legal_refs describe the reducción itself, not the transitional
            # time-window rule this advisory is about), so the provision is
            # declared rather than read off a registry object.
            asserted_legal_refs=("ley-35-2006:dt-12",),
        )
    if eligibility.eligible:
        return True, None
    return False, CalculationSourceDiagnostic(
        reason="dt12_regime_window_closed",
        source_kind="dt12_regime_window",
        message=(
            "DT 12ª: the 40% pension-rescate reducción was WITHHELD. The apartado-3 time window "
            "(LIRPF DT 12ª.4, Ley 26/2014) is CLOSED for this rescate: a contingencia in "
            f"{eligibility.contingencia_year} was eligible only for prestaciones percibidas through "
            f"{eligibility.eligible_through_year}, but the rescate is declared in "
            f"{eligibility.rescate_year}. Applying the reducción would over-reduce the return "
            "(under-declaration of tax); it is withheld as the legally correct result."
        ),
        casilla_id=reduccion_casilla_id,
        asserted_legal_refs=("ley-35-2006:dt-12",),
    )


def _dt12_parcial_guidance_advisory(reduccion_casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    """Return the parcial-rescate guidance advisory (guidance signal, not a gate)."""
    return CalculationSourceDiagnostic(
        reason="dt12_parcial_rescate_guidance",
        source_kind="dt12_regime_window",
        message=(
            "DT 12ª parcial rescate: every partial cobro of the same contingency shares ONE "
            "apartado-3 time window, measured once from the contingencia year (it does not restart "
            "per withdrawal). Confirm each cobro falls inside that window, and note that a mixed "
            "capital/renta rescate may forfeit the transitional régimen (DGT criteria: the "
            "prestación must be received en forma de capital)."
        ),
        casilla_id=reduccion_casilla_id,
        asserted_legal_refs=("ley-35-2006:dt-12",),
    )


def _semantic_role_casilla_id(
    work_unit: WorkUnit,
    semantic_role: str,
    *,
    operation: PinnedAuthorityOperation,
) -> CasillaId:
    """Resolve one semantic role from the already captured parent work unit."""
    modelo_id = str(work_unit.modelo)
    revision = operation.revision_for_context(
        modelo_id,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    try:
        casilla_id = casilla_id_for_unique_revision_semantic_role(revision, semantic_role, modelo_id=modelo_id)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloCalculateSemanticRoleError(
            str(exc),
            context=exc.ambiguity.context(),
            translated_message="application.modelo.errors.calculate_semantic_role_ambiguous",
        ) from exc
    if casilla_id is not None:
        return casilla_id
    raise ModeloCalculateSemanticRoleError(
        context={
            "modelo": modelo_id,
            "revision": revision.id,
            "semantic_role": semantic_role,
        },
        translated_message="application.modelo.errors.calculate_semantic_role_missing",
    )


__all__ = [
    "Modelo202ModalitySummary",
    "ModeloCalculateCasillaInputError",
    "ModeloCalculateDecimalInputError",
    "ModeloCalculateDetailRowsError",
    "ModeloCalculateInputError",
    "ModeloCalculateRelationInputError",
    "ModeloCalculateSemanticRoleError",
    "ModeloCalculateShortcutInputError",
    "ModeloCalculateTextInputError",
    "ModeloWorkCalculationServiceResult",
    "WorkCalculateInputBundle",
    "apply_calculation_shortcut_inputs",
    "build_work_calculate_input_bundle",
    "calculate_modelo_work_revision",
    "resolve_binding_overrides",
]
