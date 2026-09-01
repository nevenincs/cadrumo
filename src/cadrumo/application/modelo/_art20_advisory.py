"""Art. 20 LIRPF trabajo-reducción advisory helper for modelo verification.

The Art. 20 reduction remains a manual Modelo 100 casilla until the engine has
the cross-section ``otras rentas distintas del trabajo`` aggregate needed to
prove eligibility. This module emits a
non-blocking :class:`ModeloVerificationFinding` when the RNT band makes a
zero general reduction suspicious, but does not block a legitimate zero.

See Also:
    :func:`application.modelo._verification_actions._collect_revision_verification_findings`
        Verification collector that appends this advisory beside the DT 12ª
        advisory.
    :func:`application.modelo._dt12_advisory._dt12_reduccion_advisory_finding`
        Sibling registry-independent reduction advisory using the same helper
        mechanism.
    :func:`application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`
        Structural revision semantic-role lookup used to find the RNT and
        reduction casillas without hard-coding numbers.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.external_constants import MODELO_100_ART_20_TRABAJO_REDUCCION_RNT_CEILING_EUR
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_revision_semantic_role

_ART20_RNT_ROLE = "irpf_rendimiento_trabajo_rendimiento_neto"
_ART20_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion_gastos_generales"


def _art20_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
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

    The ``revision`` is a structural registry revision compatible with
    :func:`application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`.
    A matching case returns a :class:`ModeloVerificationFinding` with
    ``ley-35-2006:art-20`` grounding; absent roles or out-of-band values return
    ``None``.
    """
    try:
        rnt_id = casilla_id_for_unique_revision_semantic_role(revision, _ART20_RNT_ROLE)
        reduccion_id = casilla_id_for_unique_revision_semantic_role(revision, _ART20_REDUCCION_ROLE)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc

    if rnt_id is None or reduccion_id is None:
        return None

    rnt_value = casilla_values.get(rnt_id, Decimal(0))
    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))

    if Decimal(0) < rnt_value < MODELO_100_ART_20_TRABAJO_REDUCCION_RNT_CEILING_EUR and reduccion_value == Decimal(0):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=reduccion_id,
            message_locale_key="application.modelo.findings.art20_reduccion_possible",
            message_facts={
                "rnt_id": rnt_id,
                "rnt_value": rnt_value,
                "reduccion_id": reduccion_id,
            },
            legal_refs=("ley-35-2006:art-20",),
        )
    return None


__all__ = ["_art20_reduccion_advisory_finding"]
