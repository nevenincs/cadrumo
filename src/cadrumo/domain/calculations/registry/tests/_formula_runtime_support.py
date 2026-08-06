from __future__ import annotations

from collections.abc import Callable

from .....core.resources import bundled_path
from .._authority import ValidatedRegistryAuthority
from .._ids import validated_casilla_id
from .._schema import CasillaId, DataBindingDefinition, RegistrySnapshot
from .._snapshot import build_snapshot

_PREVIOUS_YEAR_NET_INCOME_BINDING = "irpf.previous_year_economic_activity_net_income"
_PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING = "modelo-130-resultados-negativos-anteriores"


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"formula runtime fixture casilla key {value!r} is not a CasillaId") from exc


_M130_INGRESOS_CASILLA: CasillaId = _casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = _casilla_id("02")
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = _casilla_id("04")
_M130_RETENCIONES_CASILLA: CasillaId = _casilla_id("06")
_M130_DIFERENCIA_ACTIVIDADES_CASILLA: CasillaId = _casilla_id("07")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = _casilla_id("08")
_M130_DIFERENCIA_AGRARIA_CASILLA: CasillaId = _casilla_id("09")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = _casilla_id("10")
_M130_DIFERENCIA_TOTAL_CASILLA: CasillaId = _casilla_id("11")
_M130_RESULTADO_POSITIVO_CASILLA: CasillaId = _casilla_id("12")
_M130_MINORACION_CASILLA: CasillaId = _casilla_id("13")
_M130_RESULTADO_PREVIO_CASILLA: CasillaId = _casilla_id("14")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = _casilla_id("16")
_M130_DIFERENCIA_CASILLA: CasillaId = _casilla_id("17")
_M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = _casilla_id("18")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = _casilla_id("19")
_M130_SALDO_NEGATIVO_CASILLA: CasillaId = _casilla_id("saldo-negativo-fin-periodo")
_M115_PERCEPTORES_CASILLA: CasillaId = _casilla_id("01")
_M115_BASE_CASILLA: CasillaId = _casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = _casilla_id("03")
_IVA_PRORRATA_PORCENTAJE_CASILLA: CasillaId = _casilla_id("iva.prorrata-porcentaje")
_M100_RENDIMIENTO_NETO_ACTIVIDADES_CASILLA: CasillaId = _casilla_id("0224")
_M100_RETENCIONES_PAGOS_CUENTA_CASILLA: CasillaId = _casilla_id("1479")
_M100_PAGOS_FRACCIONADOS_CASILLA: CasillaId = _casilla_id("1553")
_M100_RESULTADO_AUTOLIQUIDACION_CASILLA: CasillaId = _casilla_id("1577")


def _committed_modelo_130_snapshot(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> RegistrySnapshot:
    return registry_snapshot("130", 2026, "1T")


def _committed_modelo_180_snapshot(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> RegistrySnapshot:
    return registry_snapshot("180", 2026, "0A")


def _modelo_180_snapshot_with_inactive_relation_period(
    registry_authority: ValidatedRegistryAuthority,
) -> RegistrySnapshot:
    modelo = registry_authority.modelo("180")
    revision = modelo.revisions["2023-y-siguientes"]
    selector = revision.period_selector.model_copy(update={"periods": ("0A", "1T")})
    widened_revision = revision.model_copy(update={"period_selector": selector})
    widened_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: widened_revision}})
    return build_snapshot(
        widened_modelo,
        registry_authority.catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )


def _previous_year_net_income_binding(snapshot: RegistrySnapshot) -> DataBindingDefinition:
    return next(binding for binding in snapshot.revision.bindings if binding.id == _PREVIOUS_YEAR_NET_INCOME_BINDING)
