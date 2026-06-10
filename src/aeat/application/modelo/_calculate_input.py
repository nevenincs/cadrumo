"""Typed input bundle for modelo work calculation.

Use of :class:`CalculationRevision` for compliance.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ...core import Modelo
from ...core.errors import AeatError
from ...core.external_constants import M347_THRESHOLD_EUR
from ...core.resources import resources
from ...domain.calculations.registry import ModeloRevision
from ...domain.contribuyente._deduccion_maternidad import compute_deduccion_maternidad_0611
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._dt12_reduccion import compute_dt12_reduccion_plan_pensiones
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

_AUTOCONSUMO_PROMOTOR_BINDING = "modelo-303-autoconsumo-promotor-base"
_INSS_EXENTA_SEMANTIC_ROLE = "irpf_rendimiento_trabajo_prestacion_inss_maternidad_paternidad_exenta"
_DEDUCCION_MATERNIDAD_SEMANTIC_ROLE = "irpf_deduccion_maternidad"
_REDUCCION_TRABAJO_SEMANTIC_ROLE = "irpf_rendimiento_trabajo_reduccion"
_SAL_RESERVA_ESPECIAL_SEMANTIC_ROLE = "is_sal_reserva_especial_dotacion"
_NUMERIC_CASILLA_DATA_TYPES: frozenset[str] = frozenset({"decimal", "money", "integer", "ratio"})
_BARE_NUMERIC_RE = re.compile(r"^\d+$")


@dataclass(frozen=True, slots=True)
class WorkCalculateInputBundle:
    """Application-facing inputs for one `modelo work calculate` run."""

    casilla_inputs: Mapping[str, Decimal]
    binding_values: Mapping[str, Decimal]
    enum_binding_values: Mapping[str, str]
    relation_values: Mapping[str, Decimal]
    detail_rows: tuple[ModeloDetailRow, ...]
    borrador_snapshot_id: str | None

    @classmethod
    def build(
        cls,
        *,
        casilla_inputs: Mapping[str, Decimal],
        binding_values: Mapping[str, Decimal],
        enum_binding_values: Mapping[str, str],
        relation_values: Mapping[str, Decimal],
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

    def optional_binding_values(self) -> Mapping[str, Decimal] | None:
        """Return binding values using the calculation-service optional contract."""
        return self.binding_values or None

    def optional_enum_binding_values(self) -> Mapping[str, str] | None:
        """Return enum binding values using the calculation-service optional contract."""
        return self.enum_binding_values or None

    def optional_relation_values(self) -> Mapping[str, Decimal] | None:
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
    casilla_overrides: Mapping[str, str],
    binding_overrides: Mapping[str, str],
    relation_overrides: Mapping[str, str],
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
    casilla_inputs: dict[str, Decimal] = {}
    for raw_key, raw_value in casilla_overrides.items():
        key = _normalise_casilla_key(raw_key, revision)
        _guard_casilla_data_type(key, revision)
        casilla_inputs[key] = _decimal(raw_value, flag="--casilla", key=key)

    binding_values: dict[str, Decimal] = {}
    enum_binding_values: dict[str, str] = {}
    for key, raw_value in binding_overrides.items():
        try:
            binding_values[key] = Decimal(raw_value)
        except (InvalidOperation, ValueError):
            enum_binding_values[key] = raw_value

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

    relation_values = {
        key: _decimal(raw_value, flag="--relation", key=key) for key, raw_value in relation_overrides.items()
    }
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
        raise ValueError(
            f"M184 miembro rows: share percentages must sum to exactly 100%; got {exc.total} across {exc.count} rows"
        ) from exc

    contraparte_rows = [row for row in rows if isinstance(row, Modelo347ContraparteRow)]
    try:
        validate_m347_threshold(contraparte_rows)
    except Modelo347ThresholdError as exc:
        raise ValueError(
            f"M347 contraparte row (nif={exc.nif!r}): importe total {exc.total} "
            f"does not exceed the EUR {M347_THRESHOLD_EUR} threshold required by RD 1065/2007 art. 31.1"
        ) from exc


def _decimal(raw_value: str, *, flag: str, key: str) -> Decimal:
    try:
        return Decimal(raw_value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{flag} value for {key!r} is not a decimal: {raw_value!r}") from exc


def _revision_for_work_unit(work_unit_id: str) -> ModeloRevision:
    from ._action_errors import WorkUnitRevisionDivergenceError
    from ._work_lifecycle import get_work_unit

    unit = get_work_unit(work_unit_id)
    snapshot = resources().modelos.authority.snapshot(
        str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period,
    )
    # D1 calc-time assertion (defense-in-depth, ruling 2 "both ends"): the
    # law-determined revision must equal the revision the work unit was created
    # against.  The work unit's revision_id is an identity claim, not a
    # resolution input — it is only compared against resolution's answer.
    if snapshot.revision.id != unit.revision_id:
        raise WorkUnitRevisionDivergenceError(
            f"work unit {unit.work_unit_id!r} was created against registry revision "
            f"{unit.revision_id!r}, but the law-determined revision for "
            f"modelo {unit.modelo!r} {unit.filing_year} {unit.period!r} "
            f"is now {snapshot.revision.id!r}. "
            f"The registry's law-mapping was corrected after this work unit was created. "
            f"Re-create the work unit (discard this one and run `aeat app modelo work ensure`) "
            f"to bind it to the current law-determined revision.",
        )
    return snapshot.revision


def _guard_casilla_data_type(casilla_id: str, revision: ModeloRevision) -> None:
    casilla_def = next((casilla for casilla in revision.casillas if str(casilla.id) == casilla_id), None)
    if casilla_def is None:
        return
    if casilla_def.data_type not in _NUMERIC_CASILLA_DATA_TYPES:
        raise ValueError(
            f"--casilla {casilla_id!r} targets non-numeric data_type={casilla_def.data_type!r} "
            f"({casilla_def.label}); use --binding or profile sources instead"
        )


def _normalise_casilla_key(key: str, revision: ModeloRevision) -> str:
    if not _BARE_NUMERIC_RE.fullmatch(key):
        return key
    key_numeric = int(key)

    def _as_int(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    matches = [casilla for casilla in revision.casillas if _as_int(casilla.number) == key_numeric]
    if len(matches) == 1:
        return str(matches[0].id)
    if len(matches) > 1:
        candidates = ", ".join(str(casilla.id) for casilla in sorted(matches, key=lambda casilla: str(casilla.id)))
        raise ValueError(
            f"--casilla {key!r} matches multiple casillas in this revision: {candidates}. "
            "Supply the qualified PREFIX:NNNNN form to disambiguate."
        )
    prefixes = sorted({str(casilla.id).split(":")[0] for casilla in revision.casillas if ":" in str(casilla.id)})
    prefix_hint = f" Available prefixes for this revision: {', '.join(prefixes)}." if prefixes else ""
    raise ValueError(
        f"--casilla {key!r} does not match any casilla number in this revision."
        f"{prefix_hint} Use `aeat app modelo casillas <MODELO>` to list valid casilla IDs."
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
    casilla_inputs: Mapping[str, Decimal],
    binding_values: Mapping[str, Decimal],
    prestacion_inss_exenta: Decimal | None = None,
    meses_trabajo_con_hijo_menor_3: tuple[tuple[str, int], ...] = (),
    rescate_plan_pensiones_capital: Decimal | None = None,
    rescate_plan_pensiones_aportaciones_pre_2007: Decimal | None = None,
    rescate_plan_pensiones_aportaciones_totales: Decimal | None = None,
    sal_beneficio_neto: Decimal | None = None,
    sal_reserva_dotada: Decimal | None = None,
    sal_capital_social: Decimal | None = None,
    autoconsumo_promotor_base: Decimal | None = None,
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """Apply backend-owned tax shortcut inputs for a calculation command.

    The CLI may parse option strings into typed values, but legal-rule
    computations, semantic casilla routing, and special binding injection
    belong to the application layer.
    """
    resolved_casillas = dict(casilla_inputs)
    resolved_bindings = dict(binding_values)

    if prestacion_inss_exenta is not None:
        resolved_casillas[_semantic_role_casilla_id(work_unit_id, _INSS_EXENTA_SEMANTIC_ROLE)] = prestacion_inss_exenta

    if meses_trabajo_con_hijo_menor_3:
        deduccion = compute_deduccion_maternidad_0611(list(meses_trabajo_con_hijo_menor_3))
        resolved_casillas[_semantic_role_casilla_id(work_unit_id, _DEDUCCION_MATERNIDAD_SEMANTIC_ROLE)] = Decimal(
            deduccion
        )

    pension_values = (
        rescate_plan_pensiones_capital,
        rescate_plan_pensiones_aportaciones_pre_2007,
        rescate_plan_pensiones_aportaciones_totales,
    )
    if any(value is not None for value in pension_values):
        if not all(value is not None for value in pension_values):
            raise ValueError(
                "--rescate-plan-pensiones-capital, --rescate-plan-pensiones-aportaciones-pre-2007, "
                "and --rescate-plan-pensiones-aportaciones-totales must all be supplied together."
            )
        assert rescate_plan_pensiones_capital is not None
        assert rescate_plan_pensiones_aportaciones_pre_2007 is not None
        assert rescate_plan_pensiones_aportaciones_totales is not None
        resolved_casillas[_semantic_role_casilla_id(work_unit_id, _REDUCCION_TRABAJO_SEMANTIC_ROLE)] = (
            compute_dt12_reduccion_plan_pensiones(
                gross_rescate=rescate_plan_pensiones_capital,
                aportaciones_pre_2007=rescate_plan_pensiones_aportaciones_pre_2007,
                aportaciones_totales=rescate_plan_pensiones_aportaciones_totales,
            )
        )

    sal_values = (sal_beneficio_neto, sal_reserva_dotada, sal_capital_social)
    if any(value is not None for value in sal_values):
        if not all(value is not None for value in sal_values):
            raise ValueError(
                "--sal-beneficio-neto, --sal-reserva-dotada, and --sal-capital-social must all be supplied together."
            )
        assert sal_beneficio_neto is not None
        assert sal_reserva_dotada is not None
        assert sal_capital_social is not None
        resolved_casillas[_semantic_role_casilla_id(work_unit_id, _SAL_RESERVA_ESPECIAL_SEMANTIC_ROLE)] = (
            compute_sal_reserva_especial_dotacion(
                beneficio_neto=sal_beneficio_neto,
                reserva_dotada=sal_reserva_dotada,
                capital_social=sal_capital_social,
            )
        )

    if autoconsumo_promotor_base is not None:
        resolved_bindings[_AUTOCONSUMO_PROMOTOR_BINDING] = autoconsumo_promotor_base

    return resolved_casillas, resolved_bindings


def _semantic_role_casilla_id(work_unit_id: str, semantic_role: str) -> str:
    catalogue = WorkUnitCatalogueRepository().load()
    work_unit = catalogue.get(work_unit_id)
    if work_unit is None:
        raise LookupError(f"work unit {work_unit_id!r} not found")
    snapshot = resources().modelos.authority.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )
    for casilla in snapshot.revision.casillas:
        if getattr(casilla, "semantic_role", None) == semantic_role:
            return str(casilla.id)
    raise ValueError(f"modelo revision has no casilla with semantic_role={semantic_role!r}")


__all__ = [
    "Modelo202ModalitySummary",
    "ModeloAuthorizationAdvisorySummary",
    "ModeloWorkCalculationServiceResult",
    "WorkCalculateInputBundle",
    "apply_calculation_shortcut_inputs",
    "authorization_advisory_for_modelo",
    "build_work_calculate_input_bundle",
    "calculate_modelo_work_revision",
    "modelo_202_modality_for_work_unit",
]
