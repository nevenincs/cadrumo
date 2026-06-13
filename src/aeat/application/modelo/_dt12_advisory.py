"""DT12 advisory helper for modelo verification."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.i18n import tr
from ...domain.modelos._verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)

_DT12_TRABAJO_INGRESO_ROLE = "irpf_rendimiento_trabajo_importe_integro_dinerario"
_DT12_TRABAJO_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion"
_DT12_LARGE_TRABAJO_THRESHOLD = Decimal("20000")


def _dt12_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[str, Decimal],
) -> ModeloVerificationFinding | None:
    """Warn when large trabajo income is present but no DT12 reduction is declared."""
    ingreso_id: str | None = None
    reduccion_id: str | None = None
    for casilla in getattr(revision, "casillas", ()):
        role = getattr(casilla, "semantic_role", None)
        if role == _DT12_TRABAJO_INGRESO_ROLE:
            ingreso_id = str(casilla.id)
        elif role == _DT12_TRABAJO_REDUCCION_ROLE:
            reduccion_id = str(casilla.id)

    if ingreso_id is None or reduccion_id is None:
        return None

    ingreso_value = casilla_values.get(ingreso_id, Decimal(0))
    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))

    if ingreso_value > _DT12_LARGE_TRABAJO_THRESHOLD and reduccion_value == Decimal(0):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=reduccion_id,
            message=tr(
                "application.modelo.findings.dt12a_reduccion_possible",
                ingreso_id=ingreso_id,
                ingreso_value=str(ingreso_value),
                reduccion_id=reduccion_id,
            ),
            next_action=tr("application.modelo.findings.dt12a_reduccion_next_action"),
            legal_refs=("ley-35-2006:dt-12",),
        )
    return None


__all__ = ["_dt12_reduccion_advisory_finding"]
