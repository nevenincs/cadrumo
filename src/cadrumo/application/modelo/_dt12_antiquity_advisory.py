"""DT 12ª LIRPF pension-rescate antiquity-condition advisory for modelo verification.

DT 12ª LIRPF (régimen transitorio de planes de pensiones) imports the pre-2007
TRLIRPF art. 17.2.a) 1ª/2ª eligibility condition for the 40% reducción on a capital
rescate: the rescate must be percibida "cuando hayan transcurrido más de dos años
desde la primera aportación" (more than two years since the first contribution),
EXCEPT for prestaciones por invalidez, which are exempt from the two-year antiquity
requirement. The calculate-shortcut path
(:func:`~application.modelo._calculate_input.apply_calculation_shortcut_inputs`)
already gates the DT 12ª apartado-3 TIME WINDOW (the post-2014 contingencia-year
window in :mod:`~domain.modelos.dt12_reduccion`), but the engine does not model
the antiquity condition: no casilla captures "years since the first aportación" or
an invalidez flag, so a rescate whose contributions were made within two years of the
rescate could still receive the 40% reducción with no operator signal.

This module implements the non-blocking counterpart: when a DT 12ª-eligible
reducción has been applied (the reducción casilla is strictly positive), emit an
ADVISORY prompting the operator to confirm the antiquity condition. The finding
stays advisory because a genuine invalidez-exempt rescate, or a rescate whose
antiquity the operator has already confirmed, must remain permissible
(``no-silent-under-declaration``).

See Also:
    :func:`~application.modelo._dt12_advisory._dt12_reduccion_advisory_finding`
        Sibling advisory for the OPPOSITE case: large trabajo income with a zero
        reducción, warning the reducción may be unapplied.
    :func:`~domain.modelos.dt12_regime_window_eligibility`
        The apartado-3 time-window predicate this advisory does not duplicate; it
        covers the DISTINCT pre-2007 antiquity-since-first-aportación condition.
    :func:`~application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`
        Structural revision semantic-role lookup used to find the reducción
        casilla without hard-coding numbers.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ._semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_revision_semantic_role,
)

_DT12_TRABAJO_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion"


def _dt12_antiquity_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
) -> ModeloVerificationFinding | None:
    """Warn to confirm the DT 12ª antiquity condition when a reducción is applied.

    The ``revision`` is a structural registry revision compatible with
    :func:`~application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`.
    When the trabajo reducción casilla (role ``irpf_rendimiento_trabajo_reduccion``)
    is strictly positive, this returns a warning-severity
    :class:`ModeloVerificationFinding` grounded in ``ley-35-2006:dt-12`` prompting
    the operator to confirm the pre-2007 TRLIRPF art. 17.2.a) antiquity condition
    (more than two years since the first aportación, waived for invalidez). A zero
    or absent reducción, or an absent semantic role, returns ``None``.
    """
    try:
        reduccion_id = casilla_id_for_unique_revision_semantic_role(revision, _DT12_TRABAJO_REDUCCION_ROLE)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc

    if reduccion_id is None:
        return None

    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))

    if reduccion_value > Decimal(0):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=reduccion_id,
            message_locale_key="application.modelo.findings.dt12a_reduccion_antiquity_possible",
            message_facts={
                "reduccion_id": reduccion_id,
                "reduccion_value": reduccion_value,
            },
            legal_refs=("ley-35-2006:dt-12",),
        )
    return None


__all__ = ["_dt12_antiquity_advisory_finding"]
