"""DT 12ª LIRPF pension-plan reduction advisory for modelo verification.

The calculation input path can inject the DT 12ª reduction when the operator
supplies the three pension-plan shortcut amounts. This module covers the
opposite verification case: high trabajo income with a zero reduction casilla,
where the operator may have omitted pre-2007 pension-plan contribution data.

See Also:
    :func:`~cadrumo.application.modelo._calculate_input.apply_calculation_shortcut_inputs`
        Shortcut input path that computes and injects the reduction when the
        pension-plan amounts are supplied.
    :func:`~cadrumo.domain.modelos.compute_dt12_reduccion_plan_pensiones`
        Domain computation used by the shortcut path.
    :func:`~cadrumo.application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`
        Structural revision semantic-role lookup used by this advisory.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ...domain.modelos.errors import ModeloError
from ._semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_revision_semantic_role,
)

_DT12_TRABAJO_INGRESO_ROLE = "irpf_rendimiento_trabajo_importe_integro_dinerario"
_DT12_TRABAJO_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion"
_DT12_LARGE_TRABAJO_THRESHOLD = Decimal("20000")


def _dt12_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
) -> ModeloVerificationFinding | None:
    """Warn when large trabajo income is present but no DT 12ª reduction is declared.

    The ``revision`` is a structural registry revision compatible with
    :func:`~cadrumo.application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`.
    A matching case returns a warning-severity :class:`ModeloVerificationFinding`
    grounded in ``ley-35-2006:dt-12``; absent roles or a non-zero reduction return
    ``None``.
    """
    try:
        ingreso_id = casilla_id_for_unique_revision_semantic_role(revision, _DT12_TRABAJO_INGRESO_ROLE)
        reduccion_id = casilla_id_for_unique_revision_semantic_role(revision, _DT12_TRABAJO_REDUCCION_ROLE)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc

    if ingreso_id is None or reduccion_id is None:
        return None

    ingreso_value = casilla_values.get(ingreso_id, Decimal(0))
    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))

    if ingreso_value > _DT12_LARGE_TRABAJO_THRESHOLD and reduccion_value == Decimal(0):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=reduccion_id,
            message_locale_key="application.modelo.findings.dt12a_reduccion_possible",
            message_facts={
                "ingreso_id": ingreso_id,
                "ingreso_value": ingreso_value,
                "reduccion_id": reduccion_id,
            },
            legal_refs=("ley-35-2006:dt-12",),
        )
    return None


__all__ = ["_dt12_reduccion_advisory_finding"]
