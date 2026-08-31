from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import validated_casilla_id
from .....core.resources.bundled_data import bundled_path
from ..formula_runtime import _evaluate_expression
from ..schema import CasillaId, DataBindingDefinition, ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from ..schema_formula import FormulaExpression, ParameterDefinition
from ..snapshot import build_snapshot


def _evaluate(
    expression: FormulaExpression,
    values: Mapping[CasillaId, Decimal] | None = None,
    *,
    parameters: Mapping[str, ParameterDefinition] | None = None,
    enum_bindings: Mapping[str, str] | None = None,
) -> Decimal:
    """Evaluate one formula expression in isolation, outside a full snapshot run.

    ``values`` (positional) supplies resolved casilla operands; ``parameters``
    and ``enum_bindings`` (keyword-only) supply the parameter table and enum
    dispatch a lookup-by-* op needs. All three default to empty, so a caller
    exercising only casilla arithmetic can omit the ones its op does not read.
    """
    operand_refs: list[str] = []
    operand_casilla_refs: list[CasillaId] = []
    operand_values: list[Decimal] = []
    return _evaluate_expression(
        expression,
        values=dict(values or {}),
        binding_values={},
        parameters=dict(parameters or {}),
        date_context={"filing_period": date(2025, 12, 31)},
        relation_values={},
        operand_refs=operand_refs,
        operand_casilla_refs=operand_casilla_refs,
        operand_values=operand_values,
        enum_binding_values=dict(enum_bindings or {}),
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
    )


_PREVIOUS_YEAR_NET_INCOME_BINDING = "irpf.previous_year_economic_activity_net_income"
_PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING = "modelo-130-resultados-negativos-anteriores"


_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02")
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id("04")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06")
_M130_DIFERENCIA_ACTIVIDADES_CASILLA: CasillaId = validated_casilla_id("07")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08")
_M130_DIFERENCIA_AGRARIA_CASILLA: CasillaId = validated_casilla_id("09")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10")
_M130_DIFERENCIA_TOTAL_CASILLA: CasillaId = validated_casilla_id("11")
_M130_RESULTADO_POSITIVO_CASILLA: CasillaId = validated_casilla_id("12")
_M130_MINORACION_CASILLA: CasillaId = validated_casilla_id("13")
_M130_RESULTADO_PREVIO_CASILLA: CasillaId = validated_casilla_id("14")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
_M130_DIFERENCIA_CASILLA: CasillaId = validated_casilla_id("17")
_M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = validated_casilla_id("18")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19")
_M130_SALDO_NEGATIVO_CASILLA: CasillaId = validated_casilla_id("saldo-negativo-fin-periodo")
_M115_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01")
_M115_BASE_CASILLA: CasillaId = validated_casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03")
_IVA_PRORRATA_PORCENTAJE_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-porcentaje")
_M100_RENDIMIENTO_NETO_ACTIVIDADES_CASILLA: CasillaId = validated_casilla_id("0224")
_M100_RETENCIONES_PAGOS_CUENTA_CASILLA: CasillaId = validated_casilla_id("1479")
_M100_PAGOS_FRACCIONADOS_CASILLA: CasillaId = validated_casilla_id("1553")
_M100_RESULTADO_AUTOLIQUIDACION_CASILLA: CasillaId = validated_casilla_id("1577")


def _committed_modelo_130_snapshot(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> RegistrySnapshot:
    """The formula-runtime engine's own calculation claim, never a filing one.

    Every consumer of this fixture asserts computed casilla arithmetic
    (dependency-order evaluation, constraint violations, signed intermediate
    results), so it must not fail on the revision-review, filing-capability or
    legal-review attestation gates that belong to a filing question.
    """
    return registry_snapshot("130", 2026, "1T", grade=RegistryAuthorityGrade.CALCULATION)


def _committed_modelo_180_snapshot(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> RegistrySnapshot:
    return registry_snapshot("180", 2026, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def _modelo_180_snapshot_with_inactive_relation_period(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> RegistrySnapshot:
    """A calculation-grade check of the runtime's relation-activity guard.

    Built from the compile-only registry tree, not ``registry_authority``:
    the authority validates every modelo in the tree before returning, so a
    filing-capability gap on an unrelated modelo would break this M180-only
    calculation claim for a reason that has nothing to do with it.
    """
    modelos, catalogues = registry_tree
    modelo = next(item for item in modelos if item.id == "180")
    revision = modelo.revisions["2023-y-siguientes"]
    selector = revision.period_selector.model_copy(update={"periods": ("0A", "1T")})
    widened_revision = revision.model_copy(update={"period_selector": selector})
    widened_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: widened_revision}})
    return build_snapshot(
        widened_modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
        grade=RegistryAuthorityGrade.CALCULATION,
    )


def _previous_year_net_income_binding(snapshot: RegistrySnapshot) -> DataBindingDefinition:
    return next(binding for binding in snapshot.revision.bindings if binding.id == _PREVIOUS_YEAR_NET_INCOME_BINDING)
