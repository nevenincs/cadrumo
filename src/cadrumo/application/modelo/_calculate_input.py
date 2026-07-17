"""Typed input bundle and validation for modelo work calculation.

This module converts CLI override tokens into a
:class:`WorkCalculateInputBundle`, resolves the active work unit's
:class:`~cadrumo.domain.calculations.registry.ModeloRevision`, and validates
canonical :class:`~cadrumo.domain.calculations.registry.CasillaId` values,
binding channels, relation ids, and shortcut-derived semantic-role casillas
before the calculate service persists a
:class:`~cadrumo.domain.modelos.CalculationRevision`.

The application result pairs that persisted revision with its parent
:class:`~cadrumo.domain.modelos.WorkUnit` and any non-blocking
:class:`~cadrumo.application.aggregation.CalculationSourceDiagnostic` rows
surfaced by bucket aggregation or post-calculation advisory collectors.

See Also:
    :func:`cadrumo.entrypoints.cli._modelo_work_calculate_cli.register_work_calculate_commands`:
        Parses the operator-facing ``modelo work calculate`` command and calls
        this module to build the input bundle.
    :func:`cadrumo.application.modelo.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`:
        Consumes the validated bundle and persists the draft calculation
        revision.
    :mod:`cadrumo.application.modelo._calculation_resolution`:
        Merges caller, backend, profile, relation, and borrador channels before
        registry-engine execution.
    :func:`cadrumo.application.modelo._semantic_role_resolution.casilla_id_for_unique_semantic_role`:
        Resolves shortcut inputs onto the unique casilla declared by a revision.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...core import (
    FETCH_GATED_M210_TIPO_RENTA_CODES,
    M210_TIPO_RENTA_CODE_PROJECTION,
    M347_THRESHOLD_EUR,
    M210GrossIncomeSourceMode,
    Modelo,
    RescateType,
)
from ...core.errors import CadrumoError
from ...core.resources import resources
from ...domain.calculations.registry import (
    BindingId,
    CasillaDefinition,
    CasillaId,
    DataBindingDefinition,
    ModeloRevision,
    RelationId,
    boolean_binding_encoded_values,
    casilla_noncanonical_reference_targets,
    casillas_by_id,
    declared_casilla_ids,
    enum_consumed_binding_ids,
    revision_date_binding_ids,
)
from ...domain.contribuyente import compute_deduccion_maternidad_0611
from ...domain.modelos import (
    CalculationRevision,
    Dt12WindowEligibility,
    Modelo184MemberRow,
    Modelo184ShareSumError,
    Modelo347ContraparteRow,
    Modelo347ThresholdError,
    ModeloDetailRow,
    ModeloError,
    WorkUnit,
    compute_dt12_reduccion_plan_pensiones,
    compute_sal_reserva_especial_dotacion,
    dt12_regime_window_eligibility,
    validate_m184_member_share_sum,
    validate_m347_threshold,
)
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
_DECLARANTE_SELECTOR_SEMANTIC_ROLE = "irpf_toma_datos_declarante_selector"
_DETAIL_CASILLA_OVERRIDE_PREFIXES = ("perc.", "perceptor.", "inmueble.")


class ModeloCalculateInputError(ModeloError, ValueError):
    """Raised when operator-supplied modelo calculation inputs are invalid."""


class ModeloCalculateDetailRowsError(ModeloCalculateInputError):
    """Raised when detail rows violate modelo calculation preconditions."""


class ModeloCalculateDecimalInputError(ModeloCalculateInputError):
    """Raised when a calculation override value is not decimal-shaped."""


class ModeloCalculateTextInputError(ModeloCalculateInputError):
    """Raised when a ``--casilla`` override targets a text casilla with an empty value."""


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
    """Application-facing input channels for one ``modelo work calculate`` run.

    The bundle is the handoff from CLI parsing to application calculation. It
    separates manual casilla inputs, text casilla inputs, decimal binding
    overrides, enum binding overrides, relation values, typed detail rows, and
    the optional borrador snapshot id so each downstream channel keeps its
    registry-declared type. ``text_casilla_inputs`` carries operator-supplied
    ``data_type = "text"`` casilla values (e.g. Modelo 210's ``tipo_renta``) on
    a channel parallel to ``casilla_inputs``: the registry engine's
    ``calculate_registry_snapshot(text_inputs=...)`` reads it for categorical
    formula dispatch, and it rides into the persisted
    :class:`~cadrumo.domain.modelos.CalculationRevision`
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
    m210_gross_income_source_mode: M210GrossIncomeSourceMode = M210GrossIncomeSourceMode.MANUAL
    shortcut_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()
    """Non-blocking advisories raised while resolving shortcut inputs.

    Carries the DT 12ª apartado-4 window diagnostics
    (:func:`apply_calculation_shortcut_inputs`) so the calculate service can fold
    them into its ``source_diagnostics`` / ``source_advisories`` channel. The
    shortcut path is the only site with the contingencia/rescate year facts, so
    the advisory originates here and rides the bundle to the operator surface.
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
        text_casilla_inputs: Mapping[CasillaId, str] | None = None,
        m210_official_tipo_renta_code: str | None = None,
        m210_gross_income_source_mode: M210GrossIncomeSourceMode = M210GrossIncomeSourceMode.MANUAL,
        shortcut_diagnostics: tuple[CalculationSourceDiagnostic, ...] = (),
    ) -> WorkCalculateInputBundle:
        """Freeze CLI-assembled mappings before crossing into calculation services.

        Returns:
            :class:`WorkCalculateInputBundle`: The frozen calculate input bundle.
        """
        return cls(
            casilla_inputs=dict(casilla_inputs),
            text_casilla_inputs=dict(text_casilla_inputs or {}),
            m210_official_tipo_renta_code=(
                m210_official_tipo_renta_code.strip() if m210_official_tipo_renta_code else None
            ),
            binding_values=dict(binding_values),
            enum_binding_values=dict(enum_binding_values),
            relation_values=dict(relation_values),
            detail_rows=detail_rows,
            borrador_snapshot_id=borrador_snapshot_id.strip() if borrador_snapshot_id else None,
            m210_gross_income_source_mode=m210_gross_income_source_mode,
            shortcut_diagnostics=shortcut_diagnostics,
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
class ModeloAuthorizationAdvisorySummary:
    """Application summary for an unauthorized-but-computable modelo.

    A modelo can have a local registry engine while still being marked as not
    authorised for filing. The calculate command keeps the computation path
    available and carries this advisory for the rendering layer.
    """

    state: str


@dataclass(frozen=True, slots=True)
class ModeloWorkCalculationServiceResult:
    """Application-owned result for one `modelo work calculate` command.

    ``revision`` is the persisted
    :class:`~cadrumo.domain.modelos.CalculationRevision`; ``work_unit`` is the
    parent :class:`~cadrumo.domain.modelos.WorkUnit` loaded after persistence so
    renderers do not have to repeat the lookup. The optional advisory summaries
    are presentation data derived from registry applicability and authorization
    metadata.

    ``source_diagnostics`` carries the NON-blocking
    :class:`~cadrumo.application.aggregation.CalculationSourceDiagnostic` rows the
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
    modality: Modelo202ModalitySummary | None = None
    authorization_advisory: ModeloAuthorizationAdvisorySummary | None = None
    source_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


def calculate_modelo_work_revision(
    *,
    work_unit_id: str,
    actor: str,
    inputs: WorkCalculateInputBundle,
) -> ModeloWorkCalculationServiceResult:
    """Persist a draft calculation revision as a :class:`ModeloWorkCalculationServiceResult`.

    The function forwards the already validated :class:`WorkCalculateInputBundle`
    into the bucket-aggregation calculation path, reloads the parent
    :class:`~cadrumo.domain.modelos.WorkUnit`, and attaches any Modelo 202
    modality, authorization, or non-blocking source diagnostics needed by the
    CLI payload.

    See Also:
        :func:`cadrumo.application.modelo.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`:
            Runs source aggregation and persists the calculation revision.
        :func:`cadrumo.entrypoints.cli._modelo_work_calculate_cli._run_work_calculate`:
            Calls this service and serialises the result for the operator.
    """
    from ._calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
    from ._work_lifecycle import get_work_unit

    calculation = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_id,
        actor=actor,
        casilla_inputs=inputs.casilla_inputs,
        text_casilla_inputs=inputs.optional_text_casilla_inputs(),
        m210_official_tipo_renta_code=inputs.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=inputs.m210_gross_income_source_mode,
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
        source_diagnostics=(*inputs.shortcut_diagnostics, *calculation.source_diagnostics),
    )


def build_work_calculate_input_bundle(
    *,
    work_unit_id: str,
    casilla_overrides: Mapping[str, str],
    binding_overrides: Mapping[BindingId, str],
    relation_overrides: Mapping[RelationId, str],
    detail_rows: tuple[ModeloDetailRow, ...],
    borrador_snapshot_id: str | None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode = M210GrossIncomeSourceMode.MANUAL,
    prestacion_inss_exenta: Decimal | None = None,
    meses_trabajo_con_hijo_menor_3: tuple[tuple[str, int], ...] = (),
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
) -> WorkCalculateInputBundle:
    """Build a :class:`WorkCalculateInputBundle` from operator-supplied tokens.

    The active work unit determines the
    :class:`~cadrumo.domain.calculations.registry.ModeloRevision` used for every
    validation step. ``--casilla`` values must be canonical casilla ids; printed
    numbers and ambiguous noncanonical references are refused. A ``--casilla``
    key whose registry :class:`~cadrumo.domain.calculations.registry.CasillaDefinition`
    declares ``data_type = "text"`` (e.g. Modelo 210's ``tipo_renta``) is routed
    onto the parallel text-casilla channel as a raw, non-empty string instead of
    being forced through the decimal parser; every other ``--casilla`` key keeps
    the existing decimal-only contract. ``--binding`` is routed by the
    registry-declared channel, so enum bindings stay as strings, decimal
    bindings are parsed as :class:`~decimal.Decimal`, and date-valued profile
    bindings are rejected with profile guidance. ``--relation`` values must
    match declared relation ids.

    Detail rows are checked before engine dispatch, and shortcut flags are
    translated into semantic-role casilla values or backend-owned bindings by
    :func:`cadrumo.application.modelo.apply_calculation_shortcut_inputs`.
    """
    _validate_detail_rows(detail_rows)
    revision = _revision_for_work_unit(work_unit_id)
    revision_casillas_by_id = casillas_by_id(revision)
    casilla_inputs: dict[CasillaId, Decimal] = {}
    text_casilla_inputs: dict[CasillaId, str] = {}
    m210_official_tipo_renta_code: str | None = None
    for raw_key, raw_value in casilla_overrides.items():
        _refuse_detail_casilla_override(raw_key)
        key = _validated_canonical_casilla_id(raw_key, revision)
        casilla_def = revision_casillas_by_id.get(key)
        if casilla_def is not None and casilla_def.data_type == "text":
            if casilla_def.semantic_role == "irnr_tipo_renta":
                m210_official_tipo_renta_code = _validated_m210_official_tipo_renta_code(raw_value, key=key)
                text_casilla_inputs[key] = M210_TIPO_RENTA_CODE_PROJECTION[m210_official_tipo_renta_code].value
            elif casilla_def.semantic_role == _DECLARANTE_SELECTOR_SEMANTIC_ROLE:
                text_casilla_inputs[key] = _validated_declarante_selector(raw_value, key=key, casilla_def=casilla_def)
            else:
                text_casilla_inputs[key] = _text_value(raw_value, key=key)
        else:
            casilla_inputs[key] = _decimal(raw_value, flag="--casilla", key=key)
    casilla_inputs = validate_casilla_input_ids(revision, casilla_inputs)

    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {}
    if binding_overrides:
        bindings_by_id = {binding.id: binding for binding in revision.bindings}
        known_binding_ids = set(bindings_by_id)
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
                binding_values[key] = _decimal_binding_value(raw_value, bindings_by_id[key])

    casilla_inputs, binding_values, shortcut_diagnostics = apply_calculation_shortcut_inputs(
        work_unit_id=work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values=binding_values,
        prestacion_inss_exenta=prestacion_inss_exenta,
        meses_trabajo_con_hijo_menor_3=meses_trabajo_con_hijo_menor_3,
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
    )

    known_relation_ids = {relation.id for relation in revision.relations}
    relation_values: dict[RelationId, Decimal] = {}
    for raw_key, raw_value in relation_overrides.items():
        key = _validated_relation_id(raw_key, known_relation_ids)
        relation_values[key] = _decimal(raw_value, flag="--relation", key=key)
    return WorkCalculateInputBundle.build(
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        detail_rows=detail_rows,
        borrador_snapshot_id=borrador_snapshot_id,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        shortcut_diagnostics=shortcut_diagnostics,
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


def _decimal_binding_value(raw_value: str, binding: DataBindingDefinition) -> Decimal:
    """Parse a ``--binding`` decimal value, teaching the accepted encoding on failure.

    For a boolean-typed decimal-channel binding (the Modelo 100 estimación-directa
    modality flag), a non-numeric value such as ``false`` otherwise produces the
    opaque "is not a decimal" error. This raises an instructive refusal that names
    the accepted ``0`` / ``1`` encoding and what each value means, derived from the
    binding's boolean selector rather than a per-form hardcoded table.
    """
    encoded_options = boolean_binding_encoded_values(binding)
    try:
        return Decimal(raw_value)
    except (InvalidOperation, ValueError) as exc:
        if encoded_options:
            mapping = ", ".join(
                f"{option.encoded_value} ({'true' if option.boolean_meaning else 'false'} = "
                f"registry value {option.registry_value!r})"
                for option in encoded_options
            )
            accepted = ", ".join(option.encoded_value for option in encoded_options)
            raise ModeloCalculateDecimalInputError(
                f"--binding value for {binding.id!r} is a decimal-encoded boolean flag and must "
                f"be one of: {accepted}. Received {raw_value!r}. Accepted encoding: {mapping}. "
                "Run `aeat app modelo bindings list <MODELO>` to see each binding's encoding.",
                context={
                    "flag": "--binding",
                    "key": binding.id,
                    "value": raw_value,
                    "accepted": accepted,
                    "mapping": mapping,
                },
                translated_message="application.modelo.errors.calculate_boolean_binding_encoding_invalid",
            ) from exc
        raise ModeloCalculateDecimalInputError(
            f"--binding value for {binding.id!r} is not a decimal: {raw_value!r}",
            context={"flag": "--binding", "key": binding.id, "value": raw_value},
            translated_message="application.modelo.errors.calculate_decimal_input_invalid",
        ) from exc


def _text_value(raw_value: str, *, key: str) -> str:
    """Validate a ``--casilla`` value routed to a ``data_type = "text"`` casilla.

    Mirrors the registry engine's own
    :func:`cadrumo.domain.calculations.registry.validated_text_input_casilla_ids`
    non-empty-string contract at the CLI boundary, so an empty text value
    refuses loudly here instead of surfacing a generic registry error deeper in
    the calculation pipeline.
    """
    value = raw_value.strip()
    if not value:
        raise ModeloCalculateTextInputError(
            f"--casilla value for {key!r} is a text casilla and must be a non-empty string; got {raw_value!r}",
            context={"key": key, "value": raw_value},
            translated_message="application.modelo.errors.calculate_text_input_empty",
        )
    return value


def _validated_m210_tipo_renta_code(raw_value: str, *, key: str) -> str:
    """Validate a Modelo 210 ``tipo_renta`` value against the declared official codes.

    The generic ``--casilla key=value`` surface cannot render a static Typer
    ``Choice`` for one casilla's value, so this is the sanctioned
    architecture-boundaries fallback: a registry-driven refusal that LISTS the
    accepted declared codes and names a fetch-gated code as fetch-gated rather
    than "invalid". The fetch-gated codes
    (:data:`~cadrumo.core.FETCH_GATED_M210_TIPO_RENTA_CODES`) are real AEAT
    HOJA-INFORMATIVA-210 codes whose rate is not yet grounded, so an operator
    entering code ``08`` is told it is not yet fileable, never that it is
    invalid. The accepted set is the declared code axis
    (:data:`~cadrumo.core.M210_TIPO_RENTA_CODE_PROJECTION`), kept in parity with the
    registry ``m210-tipo-renta-code-2025`` parameter by the registry-build gate.

    On acceptance the operator-entered official code is PROJECTED to its
    :class:`~cadrumo.core.TipoRentaIrnr` rate-concept token — the value the engine
    already keys the baseline rate table and treaty overrides on — so the
    operator declares the code the form asks for while the rate machinery keeps
    its conceptual key. (Codes that share a concept, e.g. arrendamiento ``01``
    and empresariales ``03`` both ``general``, collapse to that concept here;
    per-code form-fidelity display belongs to the fetch-gated full-casilla
    schema.)
    """
    return M210_TIPO_RENTA_CODE_PROJECTION[_validated_m210_official_tipo_renta_code(raw_value, key=key)].value


def _validated_m210_official_tipo_renta_code(raw_value: str, *, key: str) -> str:
    """Return the validated raw M210 code without collapsing its identity.

    The formula engine receives the conceptual rate token, while the ledger
    source resolver and persisted calculation revision retain this official
    code. Keeping both values prevents the many-to-one rate projection from
    turning distinct declarations such as codes ``01`` and ``03`` into the
    same ledger-selection key.
    """
    value = _text_value(raw_value, key=key)
    if value in M210_TIPO_RENTA_CODE_PROJECTION:
        return value
    accepted = ", ".join(sorted(M210_TIPO_RENTA_CODE_PROJECTION))
    if value in FETCH_GATED_M210_TIPO_RENTA_CODES:
        raise ModeloCalculateTextInputError(
            f"Modelo 210 tipo de renta code {value!r} is fetch-gated: its rate is not yet grounded "
            f"in the bundled corpus, so it cannot be filed yet. Accepted codes: {accepted}.",
            context={"key": key, "value": value, "accepted": accepted},
            translated_message="application.modelo.errors.calculate_m210_tipo_renta_fetch_gated",
        )
    fetch_gated = ", ".join(sorted(FETCH_GATED_M210_TIPO_RENTA_CODES))
    raise ModeloCalculateTextInputError(
        f"{value!r} is not a valid Modelo 210 tipo de renta code. Accepted codes: {accepted}. "
        f"Codes pending grounding (not yet fileable): {fetch_gated}.",
        context={"key": key, "value": value, "accepted": accepted, "fetch_gated": fetch_gated},
        translated_message="application.modelo.errors.calculate_m210_tipo_renta_unknown",
    )


def _validated_declarante_selector(raw_value: str, *, key: CasillaId, casilla_def: CasillaDefinition) -> str:
    """Refuse a purely-numeric value routed to a declarante-selector text casilla.

    A ``irpf_toma_datos_declarante_selector`` casilla (e.g. Modelo 100 ``0001``,
    "Contribuyente que obtiene los rendimientos") names the member who obtains the
    income — the contribuyente, the cónyuge, or a dependant — never a monetary
    amount. A bare number such as ``38000`` is a mis-routed income figure: routed
    onto the parallel text channel it would be stored silently in the text slot,
    ignored by the formula chain, and — combined with a subtraction-convention
    casilla — surface as a wrong (negative) base imponible. This guard fails the
    override early, naming the casilla, its label, its ``data_type``, and the
    numeric casilla channel the amount belongs on, mirroring the
    :func:`_validated_m210_tipo_renta_code` semantic-role fallback for the generic
    ``--casilla key=value`` surface that cannot render a per-casilla Typer choice.
    """
    value = _text_value(raw_value, key=key)
    try:
        Decimal(value)
    except (InvalidOperation, ValueError):
        return value
    raise ModeloCalculateTextInputError(
        f"--casilla value for {key!r} ({casilla_def.label}) is a non-numeric "
        f"data_type={casilla_def.data_type!r} declarante selector naming the "
        f"contribuyente who obtains the income, not an amount; got {raw_value!r}. "
        f"Enter the income figure in its own numeric casilla (e.g. `--casilla 0003=<amount>`) "
        f"and reserve this casilla for the member selector.",
        context={
            "key": key,
            "value": raw_value,
            "data_type": casilla_def.data_type,
            "label": casilla_def.label,
        },
        translated_message="application.modelo.errors.calculate_text_casilla_numeric_value",
    )


def _refuse_detail_casilla_override(key: str) -> None:
    """Reject detail-row aliases before the decimal-only casilla path parses values."""
    if not is_detail_casilla_override_key(key):
        return
    raise ModeloCalculateCasillaInputError(
        f"--casilla {key!r} names a Modelo 180 perceptor/property detail field, not a scalar decimal "
        "casilla input. The local work --casilla channel only accepts scalar decimal casillas; "
        "Modelo 180 perceptor/property detail rows are not supported on the public --row surface yet. "
        "Use `aeat app modelo aggregate --modelo 180 --retencion-observation ...` for the supported "
        "annual perceptor count/base/retenciones source, and do not supply string fields through --casilla.",
        context={"key": key},
        translated_message="application.modelo.errors.calculate_detail_casilla_unsupported",
    )


def is_detail_casilla_override_key(key: str) -> bool:
    """Return whether *key* names a reserved detail-row alias, not a scalar casilla."""
    return key.strip().lower().startswith(_DETAIL_CASILLA_OVERRIDE_PREFIXES)


def _revision_for_work_unit(work_unit_id: str) -> ModeloRevision:
    from ._action_errors import WorkUnitRevisionDivergenceError
    from ._work_lifecycle import get_work_unit

    unit = get_work_unit(work_unit_id)
    snapshot = resources().modelos.authority.snapshot(
        str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period.registry_token,
    )
    # Calc-time assertion (defense-in-depth): the
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
        f"--relation {key!r} does not match any relation id in this revision. Accepted relation ids: {accepted}.",
        context={"key": key, "accepted": accepted},
        translated_message="application.modelo.errors.calculate_relation_unknown",
    )


def _validated_canonical_casilla_id(key: str, revision: ModeloRevision) -> CasillaId:
    known_ids = declared_casilla_ids(revision)
    if key in known_ids:
        return key

    noncanonical_targets = casilla_noncanonical_reference_targets(revision, key)
    if noncanonical_targets:
        accepted = ", ".join(noncanonical_targets)
        if len(noncanonical_targets) > 1:
            raise ModeloCalculateCasillaInputError(
                f"--casilla {key!r} is not a canonical casilla.id and is ambiguous. "
                f"Candidate casilla.id values: {accepted}. "
                "Supply the exact canonical casilla.id.",
                context={"key": key, "accepted": accepted},
                translated_message="application.modelo.errors.calculate_casilla_noncanonical_ambiguous",
            )
        raise ModeloCalculateCasillaInputError(
            f"--casilla {key!r} is a printed casilla number or form number or export reference, "
            "not a canonical casilla.id. "
            f"Use the canonical casilla.id instead: {accepted}.",
            context={"key": key, "accepted": accepted},
            translated_message="application.modelo.errors.calculate_casilla_noncanonical_refused",
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
    """Return a :class:`Modelo202ModalitySummary` for ``work_unit`` when applicable.

    Non-Modelo-202 work units return ``None``. For Modelo 202, the active
    profile projection is passed to the registry applicability helper so the
    calculate payload can disclose whether Art. 40.2 or Art. 40.3 was selected.
    """
    if str(work_unit.modelo) != Modelo.M202:
        return None

    from ...domain.calculations.registry import derive_modelo_202_modality
    from ..user_profile import projection_for_taxpayer
    from ..workflow import workflow_state_repository

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    profile = projection_for_taxpayer(record or {}, tax_id_default="00000000T")
    verdict = derive_modelo_202_modality(profile)
    return Modelo202ModalitySummary(modality=verdict.modality.value, reason=verdict.reason)


def authorization_advisory_for_modelo(modelo: str) -> ModeloAuthorizationAdvisorySummary | None:
    """Return a :class:`ModeloAuthorizationAdvisorySummary` for an unauthorized-but-computable modelo.

    Authorized modelos and modelos without a local calculation engine return
    ``None``. Unauthorized modelos with an engine return the registry
    authorization state for non-blocking CLI disclosure.
    """
    from ...core.access_gate import AuthorizationState

    try:
        capability = resources().modelos.authority.authorization(modelo.strip())
    except CadrumoError:
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
    rescate_plan_pensiones_tipo: RescateType | None = None,
    rescate_plan_pensiones_contingencia_year: int | None = None,
    rescate_plan_pensiones_rescate_year: int | None = None,
    sal_beneficio_neto: Decimal | None = None,
    sal_reserva_dotada: Decimal | None = None,
    sal_capital_social: Decimal | None = None,
    autoconsumo_promotor_base: Decimal | None = None,
) -> tuple[dict[CasillaId, Decimal], dict[BindingId, Decimal], tuple[CalculationSourceDiagnostic, ...]]:
    """Apply backend-owned tax shortcut inputs for a calculation command.

    The CLI may parse option strings into typed values, but legal-rule
    computations, semantic casilla routing, and special binding injection
    belong to the application layer. INSS maternity/paternity, maternity
    deduction, DT 12 pension-rescue reduction, and SAL reserve inputs resolve to
    unique semantic-role casillas. The Modelo 303 autoconsumo-promotor shortcut
    writes the backend-owned binding consumed by the registry engine.

    The DT 12ª pension-rescate shortcut is fact-gated by the apartado-4 time
    window (LIRPF DT 12ª.4, added by Ley 26/2014). When the operator declares the
    contingencia year and the window predicate
    (:func:`~cadrumo.domain.modelos.dt12_regime_window_eligibility`) proves the
    window CLOSED, the 40% reducción injection is WITHHELD — the legally correct
    no-régimen result, since applying an out-of-window reducción would be a silent
    over-reduction (under-declaration of tax per ``no-silent-under-declaration``).
    When the window is open the reducción injects as usual; when the contingencia
    year is absent the reducción injects with an unverified-window advisory. Every
    branch surfaces a non-blocking
    :class:`~cadrumo.application.aggregation.CalculationSourceDiagnostic`; calculate
    never aborts on the window verdict.

    Returns:
        A triple: resolved casilla inputs, resolved decimal binding values, and
        the non-blocking DT 12ª window advisory diagnostics (empty when no
        pension rescate was supplied).

    See Also:
        :func:`cadrumo.application.modelo._semantic_role_resolution.casilla_id_for_unique_semantic_role`:
            Selects the unique semantic-role casilla for shortcut values.
    """
    resolved_casilla_values = dict(casilla_inputs)
    resolved_bindings = dict(binding_values)
    advisories: list[CalculationSourceDiagnostic] = []

    if prestacion_inss_exenta is not None:
        resolved_casilla_values[_semantic_role_casilla_id(work_unit_id, _INSS_EXENTA_SEMANTIC_ROLE)] = (
            prestacion_inss_exenta
        )

    if meses_trabajo_con_hijo_menor_3:
        deduccion = compute_deduccion_maternidad_0611(list(meses_trabajo_con_hijo_menor_3))
        resolved_casilla_values[_semantic_role_casilla_id(work_unit_id, _DEDUCCION_MATERNIDAD_SEMANTIC_ROLE)] = Decimal(
            deduccion
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
        reduccion = compute_dt12_reduccion_plan_pensiones(
            gross_rescate=rescate_plan_pensiones_capital,
            aportaciones_pre_2007=rescate_plan_pensiones_aportaciones_pre_2007,
            aportaciones_totales=rescate_plan_pensiones_aportaciones_totales,
        )
        reduccion_casilla_id = _semantic_role_casilla_id(work_unit_id, _REDUCCION_TRABAJO_SEMANTIC_ROLE)
        eligibility = _dt12_window_verdict(
            work_unit_id=work_unit_id,
            contingencia_year=rescate_plan_pensiones_contingencia_year,
            rescate_year=rescate_plan_pensiones_rescate_year,
        )
        inject, window_advisory = _dt12_window_decision(
            reduccion=reduccion,
            eligibility=eligibility,
            reduccion_casilla_id=reduccion_casilla_id,
        )
        if inject:
            resolved_casilla_values[reduccion_casilla_id] = reduccion
        if window_advisory is not None:
            advisories.append(window_advisory)
        if rescate_plan_pensiones_tipo is RescateType.PARCIAL:
            advisories.append(_dt12_parcial_guidance_advisory(reduccion_casilla_id))

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

    return resolved_casilla_values, resolved_bindings, tuple(advisories)


def _dt12_window_verdict(
    *,
    work_unit_id: str,
    contingencia_year: int | None,
    rescate_year: int | None,
) -> Dt12WindowEligibility | None:
    """Evaluate the DT 12ª apartado-4 window when the contingencia year is declared.

    The contingencia year is the load-bearing fact: without it the window cannot
    be evaluated and the caller emits the unverified-window advisory. The rescate
    (percepción) year defaults to the work unit's filing year, the common case
    (the prestación is percibida in the year being filed).
    """
    if contingencia_year is None:
        return None
    resolved_rescate_year = rescate_year if rescate_year is not None else _work_unit_filing_year(work_unit_id)
    return dt12_regime_window_eligibility(
        contingencia_year=contingencia_year,
        rescate_year=resolved_rescate_year,
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
                "DT 12ª: the 40% pension-rescate reducción was applied, but the apartado-4 time "
                "window (LIRPF DT 12ª.4, Ley 26/2014) was not verified because no contingencia year "
                "was declared. The régimen applies only to prestaciones percibidas within the window "
                "measured from the contingencia year (the contingencia year plus the two following, "
                "or through 2018 for contingencias in 2010 or earlier, or the eighth following "
                "ejercicio for 2011–2014). Re-run with --contingencia-year to confirm the window."
            ),
            casilla_id=reduccion_casilla_id,
        )
    if eligibility.eligible:
        return True, None
    return False, CalculationSourceDiagnostic(
        reason="dt12_regime_window_closed",
        source_kind="dt12_regime_window",
        message=(
            "DT 12ª: the 40% pension-rescate reducción was WITHHELD. The apartado-4 time window "
            "(LIRPF DT 12ª.4, Ley 26/2014) is CLOSED for this rescate: a contingencia in "
            f"{eligibility.contingencia_year} was eligible only for prestaciones percibidas through "
            f"{eligibility.eligible_through_year}, but the rescate is declared in "
            f"{eligibility.rescate_year}. Applying the reducción would over-reduce the return "
            "(under-declaration of tax); it is withheld as the legally correct result."
        ),
        casilla_id=reduccion_casilla_id,
    )


def _dt12_parcial_guidance_advisory(reduccion_casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    """Return the parcial-rescate guidance advisory (guidance signal, not a gate)."""
    return CalculationSourceDiagnostic(
        reason="dt12_parcial_rescate_guidance",
        source_kind="dt12_regime_window",
        message=(
            "DT 12ª parcial rescate: every partial cobro of the same contingency shares ONE "
            "apartado-4 time window, measured once from the contingencia year (it does not restart "
            "per withdrawal). Confirm each cobro falls inside that window, and note that a mixed "
            "capital/renta rescate may forfeit the transitional régimen (DGT criteria: the "
            "prestación must be received en forma de capital)."
        ),
        casilla_id=reduccion_casilla_id,
    )


def _work_unit_filing_year(work_unit_id: str) -> int:
    catalogue = WorkUnitCatalogueRepository().load()
    work_unit = catalogue.get(work_unit_id)
    if work_unit is None:
        raise LookupError(f"work unit {work_unit_id!r} not found")
    return work_unit.filing_year


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
    "ModeloCalculateTextInputError",
    "ModeloWorkCalculationServiceResult",
    "WorkCalculateInputBundle",
    "apply_calculation_shortcut_inputs",
    "authorization_advisory_for_modelo",
    "build_work_calculate_input_bundle",
    "calculate_modelo_work_revision",
    "is_detail_casilla_override_key",
    "modelo_202_modality_for_work_unit",
]
