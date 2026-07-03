"""Art. 52 LIRPF previsión-social individual sub-limit advisory for modelo verification.

The Modelo 100 previsión-social reducción (casilla 0468) already enforces the joint
EUR 10.000 / 30% cap (``min(0467, 10000, 30% of 0432)``), but that cap alone does not
enforce the art. 52.1 individual sub-limit: a taxpayer whose aportaciones are purely
individual — with no plan-de-empleo worker contribution (casilla 0426) and no
contribución empresarial (casilla 0427) backing the EUR 8.500 increment — is bound by
the lower EUR 1.500 general limit, not the combined EUR 10.000 ceiling. This module
implements the ADR's Phase-1 choice: emit a non-blocking
:class:`~aeat.domain.modelos.ModeloVerificationFinding` when the granted reducción
exceeds the individual sub-limit with no employer-linked backing declared, but do not
block a legitimate employer-backed or plan-de-empleo-backed reducción above EUR 1.500.

See Also:
    :func:`aeat.application.modelo._verification_actions._collect_revision_verification_findings`
        Verification collector that appends this advisory beside the art. 20 and
        DT 12ª advisories.
    :func:`aeat.application.modelo._art20_advisory._art20_reduccion_advisory_finding`
        Sibling advisory using the same semantic-role resolution mechanism.
    :func:`aeat.application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`
        Structural revision semantic-role lookup used to find the reducción and
        contribution casillas without hard-coding numbers.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.external_constants import MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR
from ...core.i18n import tr
from ...domain.calculations.registry import CasillaId
from ...domain.modelos import (
    ModeloError,
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ._semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_revision_semantic_role,
)

_ART52_REDUCCION_TOTAL_ROLE = "irpf_reduccion_prevision_social_total"
_ART52_APORTACIONES_TRABAJADOR_CON_CONTRIBUCION_EMPRESARIAL_ROLE = (
    "irpf_red_prevision_social_aportaciones_trabajador_con_contribucion_empresarial"
)
_ART52_CONTRIBUCIONES_EMPRESARIALES_ROLE = "irpf_red_prevision_social_contribuciones_empresariales_excepto_scd"


def _art52_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
) -> ModeloVerificationFinding | None:
    """Warn when the previsión-social reducción exceeds the individual sub-limit.

    The joint art. 52.1 LIRPF cap on casilla 0468 is ``min(0467, 10.000, 30% of
    0432)``, but the EUR 10.000 combined ceiling only applies when the EUR 8.500
    increment is backed by a plan-de-empleo worker contribution (casilla role
    ``irpf_red_prevision_social_aportaciones_trabajador_con_contribucion_empresarial``)
    or an employer contribución empresarial (casilla role
    ``irpf_red_prevision_social_contribuciones_empresariales_excepto_scd``). A
    taxpayer whose reducción (role ``irpf_reduccion_prevision_social_total``)
    exceeds :data:`~aeat.core.external_constants.MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR`
    while BOTH of those casillas are zero is bound by the lower EUR 1.500 general
    limit, not the combined ceiling — a possible over-reduction.

    The finding is ADVISORY because the engine does not yet split individual from
    employer-linked aportaciones within casilla 0463 (Phase 2b of the
    ``2026-07-01-modelo-100-trabajo-casilla-compute-adr``), so a legitimately
    employer-backed or plan-de-empleo-backed reducción above EUR 1.500 must remain
    permissible (``no-silent-under-declaration``).

    The ``revision`` is a structural registry revision compatible with
    :func:`aeat.application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`.
    A matching case returns a :class:`ModeloVerificationFinding` with
    ``ley-35-2006:art-52`` grounding; absent roles or in-limit/employer-backed values
    return ``None``.
    """
    try:
        reduccion_id = casilla_id_for_unique_revision_semantic_role(revision, _ART52_REDUCCION_TOTAL_ROLE)
        trabajador_con_contribucion_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            _ART52_APORTACIONES_TRABAJADOR_CON_CONTRIBUCION_EMPRESARIAL_ROLE,
        )
        empresarial_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            _ART52_CONTRIBUCIONES_EMPRESARIALES_ROLE,
        )
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc

    if reduccion_id is None or trabajador_con_contribucion_id is None or empresarial_id is None:
        return None

    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))
    trabajador_con_contribucion_value = casilla_values.get(trabajador_con_contribucion_id, Decimal(0))
    empresarial_value = casilla_values.get(empresarial_id, Decimal(0))

    if (
        reduccion_value > MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR
        and trabajador_con_contribucion_value == Decimal(0)
        and empresarial_value == Decimal(0)
    ):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=reduccion_id,
            message=tr(
                "application.modelo.findings.art52_reduccion_individual_sublimit_possible",
                reduccion_id=reduccion_id,
                reduccion_value=str(reduccion_value),
                sublimit=str(MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR),
            ),
            next_action=tr("application.modelo.findings.art52_reduccion_individual_sublimit_next_action"),
            legal_refs=("ley-35-2006:art-52",),
        )
    return None


__all__ = ["_art52_reduccion_advisory_finding"]
