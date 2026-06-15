"""Art. 20 LIRPF trabajo-reducción advisory helper for modelo verification."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.external_constants import MODELO_100_ART_20_TRABAJO_REDUCCION_RNT_CEILING_EUR
from ...core.i18n import tr
from ...domain.modelos._verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)

_ART20_RNT_ROLE = "irpf_rendimiento_trabajo_rendimiento_neto"
_ART20_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion_gastos_generales"


def _art20_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[str, Decimal],
) -> ModeloVerificationFinding | None:
    """Warn when RNT is within the art. 20 band but no general reduction is declared.

    The art. 20 LIRPF reducción por obtención de rendimientos del trabajo decays to
    zero at :data:`MODELO_100_ART_20_TRABAJO_REDUCCION_RNT_CEILING_EUR`. When the
    rendimiento neto del trabajo (casilla role
    ``irpf_rendimiento_trabajo_rendimiento_neto``) is strictly positive and below that
    ceiling but the general-reducción casilla
    (role ``irpf_rendimiento_trabajo_reduccion_gastos_generales``) is zero, the operator
    may have left a determinable reduction unapplied. The finding is ADVISORY because
    the art. 20 eligibility gate ("otras rentas distintas del trabajo" ≤ 6.500 €) is a
    cross-section aggregate the engine cannot yet evaluate, so a legitimately-zero
    reduction (otras rentas above the gate) must remain permissible
    (``no-silent-under-declaration``).
    """
    rnt_id: str | None = None
    reduccion_id: str | None = None
    for casilla in getattr(revision, "casillas", ()):
        role = getattr(casilla, "semantic_role", None)
        if role == _ART20_RNT_ROLE:
            rnt_id = str(casilla.id)
        elif role == _ART20_REDUCCION_ROLE:
            reduccion_id = str(casilla.id)

    if rnt_id is None or reduccion_id is None:
        return None

    rnt_value = casilla_values.get(rnt_id, Decimal(0))
    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))

    if (
        Decimal(0) < rnt_value < MODELO_100_ART_20_TRABAJO_REDUCCION_RNT_CEILING_EUR
        and reduccion_value == Decimal(0)
    ):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=reduccion_id,
            message=tr(
                "application.modelo.findings.art20_reduccion_possible",
                rnt_id=rnt_id,
                rnt_value=str(rnt_value),
                reduccion_id=reduccion_id,
            ),
            next_action=tr("application.modelo.findings.art20_reduccion_next_action"),
            legal_refs=("ley-35-2006:art-20",),
        )
    return None


__all__ = ["_art20_reduccion_advisory_finding"]
