"""Art. 52 LIRPF previsión-social individual sub-limit advisory for modelo verification.

The Modelo 100 previsión-social reducción (casilla 0468) is still a bare MANUAL
input in the 2021-2023 revisions, so nothing in those revisions enforces the art.
52.1 individual sub-limit: a taxpayer whose aportaciones are purely individual —
with no plan-de-empleo worker contribution (casilla 0426), no contribución
empresarial (casilla 0427), and no autónomo/empresario-individual aportación
(casilla 0499) backing an art. 52.1 increment — is bound by the lower EUR 1.500
general limit, not a higher combined ceiling. This module emits a non-blocking
:class:`~domain.modelos.ModeloVerificationFinding` when the granted reducción
exceeds the individual sub-limit with no backing casilla declared, but does not
block a legitimate employer-backed, plan-de-empleo-backed, or autónomo-backed
reducción above EUR 1.500.

On the 2024/2025 revisions, casilla 0468 is COMPUTED directly by the tiered art.
52.1 formula, so this advisory's firing
predicate is structurally unreachable there: the formula itself enforces the
individual/1º/2º sub-limits, and the resolved reducción can never exceed what the
declared backing casillas legitimately unlock.

See Also:
    :func:`~application.modelo._verification_actions._collect_revision_verification_findings`
        Verification collector that appends this advisory beside the art. 20 and
        DT 12ª advisories.
    :func:`~application.modelo._art20_advisory._art20_reduccion_advisory_finding`
        Sibling advisory using the same semantic-role resolution mechanism.
    :func:`~application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`
        Structural revision semantic-role lookup used to find the reducción and
        contribution casillas without hard-coding numbers.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import CasillaId
from ...core.external_constants import MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR
from ...domain.modelos import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.errors import ModeloError
from ._semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_revision_semantic_role,
)

_ART52_REDUCCION_TOTAL_ROLE = "irpf_reduccion_prevision_social_total"
_ART52_APORTACIONES_TRABAJADOR_CON_CONTRIBUCION_EMPRESARIAL_ROLE = (
    "irpf_red_prevision_social_aportaciones_trabajador_con_contribucion_empresarial"
)
_ART52_CONTRIBUCIONES_EMPRESARIALES_ROLE = "irpf_red_prevision_social_contribuciones_empresariales_excepto_scd"
_ART52_APORTACIONES_AUTONOMOS_EMPRESARIOS_ROLE = "irpf_red_prevision_social_aportaciones_autonomos_empresarios"


def _art52_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
) -> ModeloVerificationFinding | None:
    """Warn when the previsión-social reducción exceeds the individual sub-limit.

    A taxpayer whose reducción (role ``irpf_reduccion_prevision_social_total``)
    exceeds :data:`~core.external_constants.MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR`
    while the plan-de-empleo worker contribution (role
    ``irpf_red_prevision_social_aportaciones_trabajador_con_contribucion_empresarial``),
    the contribución empresarial (role
    ``irpf_red_prevision_social_contribuciones_empresariales_excepto_scd``), AND the
    autónomo/empresario-individual aportación (role
    ``irpf_red_prevision_social_aportaciones_autonomos_empresarios``) are all zero
    is bound by the lower EUR 1.500 general limit, not a higher combined ceiling —
    a possible over-reduction. A declared autónomo aportación legitimately unlocks
    only the art. 52.1.2º EUR 4.250 increment (not the full art. 52.1.1º EUR 8.500
    increment the employer-linked casillas unlock), so its presence still suppresses
    the advisory rather than tightening it: this module only detects the
    no-backing-at-all case, leaving the exact 1º/2º split to the COMPUTED formula.

    The finding is ADVISORY because the 2021-2023 revisions do not yet compute
    casilla 0468 directly, so a legitimately backed reducción above EUR 1.500 must
    remain permissible (``no-silent-under-declaration``).

    The ``revision`` is a structural registry revision compatible with
    :func:`~application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`.
    A matching case returns a :class:`ModeloVerificationFinding` with
    ``ley-35-2006:art-52`` grounding; absent roles or in-limit/backed values return
    ``None``.
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
        autonomos_empresarios_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            _ART52_APORTACIONES_AUTONOMOS_EMPRESARIOS_ROLE,
        )
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc

    if (
        reduccion_id is None
        or trabajador_con_contribucion_id is None
        or empresarial_id is None
        or autonomos_empresarios_id is None
    ):
        return None

    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))
    trabajador_con_contribucion_value = casilla_values.get(trabajador_con_contribucion_id, Decimal(0))
    empresarial_value = casilla_values.get(empresarial_id, Decimal(0))
    autonomos_empresarios_value = casilla_values.get(autonomos_empresarios_id, Decimal(0))

    if (
        reduccion_value > MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR
        and trabajador_con_contribucion_value == Decimal(0)
        and empresarial_value == Decimal(0)
        and autonomos_empresarios_value == Decimal(0)
    ):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=reduccion_id,
            message_locale_key="application.modelo.findings.art52_reduccion_individual_sublimit_possible",
            message_facts={
                "reduccion_id": reduccion_id,
                "reduccion_value": reduccion_value,
                "sublimit": MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR,
            },
            legal_refs=("ley-35-2006:art-52",),
        )
    return None


__all__ = ["_art52_reduccion_advisory_finding"]
