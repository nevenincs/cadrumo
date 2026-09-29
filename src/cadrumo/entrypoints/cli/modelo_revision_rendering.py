"""Pure rendering of prepared Modelo revision payloads and state labels."""

from __future__ import annotations

from ...core.i18n.render import tr
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ._modelo_payloads import CalculationRevisionPayload


def calculation_revision_state_label(state: str) -> str:
    """Return the established localized label for a calculation-revision state."""
    if state == CalculationRevisionState.BORRADOR.value:
        return tr("cli.app.modelo.work.state_label_borrador")
    if state == CalculationRevisionState.VERIFICADO_COMPLETO.value:
        return tr("cli.app.modelo.work.state_label_verificado_completo")
    if state == CalculationRevisionState.PRESENTADO.value:
        return tr("cli.app.modelo.work.state_label_presentado")
    if state == CalculationRevisionState.PRESENTADO_SUPERSEDIDO.value:
        return tr("cli.app.modelo.work.state_label_presentado_supersedido")
    if state == CalculationRevisionState.DESCARTADO.value:
        return tr("cli.app.modelo.work.state_label_descartado")
    return state


def calculation_observation_payload_lines(payload: CalculationRevisionPayload) -> list[str]:
    """Render the established text view from a prepared revision payload."""
    observations = sorted(payload.observations, key=lambda obs: obs.casilla_id)
    lines = [
        f"calculation_revision_id\t{payload.calculation_revision_id}",
        f"work_unit_id\t{payload.work_unit_id}",
        f"state\t{calculation_revision_state_label(payload.state)}",
        f"observation_count\t{len(observations)}",
        "casilla_id\tvalue\tformula_id\tlegal_refs\tsource_refs\toperand_refs\toperand_casilla_refs\toperand_values",
    ]
    lines.extend(
        "\t".join(
            (
                obs.casilla_id,
                obs.value,
                obs.formula_id or "",
                ";".join(obs.legal_refs),
                ";".join(obs.source_refs),
                ";".join(obs.operand_refs),
                ";".join(obs.operand_casilla_refs),
                ";".join(obs.operand_values),
            ),
        )
        for obs in observations
    )
    return lines


__all__ = ["calculation_observation_payload_lines", "calculation_revision_state_label"]
