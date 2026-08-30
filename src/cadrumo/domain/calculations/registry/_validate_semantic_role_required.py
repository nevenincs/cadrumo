"""Required-role hard-flip gate and cross-reference accessor.

Enforces that every casilla whose label matches a registered pattern
in :data:`_REQUIRED_ROLE_LABEL_PATTERNS` declares the expected
``semantic_role``. A miss-declared or absent declaration is a hard
:class:`~cadrumo.domain.calculations.registry.schema.ModeloDefinition`
validation failure surfaced by
:func:`_validate_required_role_declarations`.

Also exposes :func:`collect_casillas_by_semantic_role`, the public
cross-reference accessor used by downstream consumers to walk every
casilla sharing a semantic role across the registry corpus.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping

from ....core.casilla_id import CasillaId
from ....core.i18n import MissingTranslationError
from .ids import ModeloId, RevisionId
from .schema import ModeloDefinition

type SemanticRoleCasillaOccurrence = tuple[ModeloId, RevisionId, CasillaId]

# Enforced semantic_role requirements: each entry is (label_pattern,
# expected_role). A casilla whose label matches the pattern must declare
# the expected semantic_role; missing declarations raise
# RegistryValidationError at snapshot build. The set starts conservative
# — only patterns where corpus rollout is provably complete should land
# here. Modellers extending this set must run a discovery audit first to
# confirm all in-corpus casillas already carry the role.
#
# Today's enforcement set:
# - "Ejercicio al que se refiere la declaracion" -> filing_year
#   (16 casillas covered across 13 modelos, complete rollout
#   per the role-rollout-strategy audit).
_REQUIRED_ROLE_LABEL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^Ejercicio al que se refiere la declaracion$", re.IGNORECASE), "filing_year"),
    # Exact-match "Resultado a ingresar" (not "...o a devolver" or
    # "...de autoliquidaciones anteriores"; those carry distinct
    # semantics - signed cuota vs. prior-period balance - and would
    # need their own roles).
    (re.compile(r"^Resultado a ingresar$", re.IGNORECASE), "cuota_a_ingresar"),
    # M100 IRPF base surfaces: the general base and special-regime
    # imputed base are distinct roles despite similar labels.
    (re.compile(r"^Base imponible general\s*$", re.IGNORECASE), "irpf_base_imponible_general"),
    (
        re.compile(r"^Base imponible imputada\s*$", re.IGNORECASE),
        "irpf_re_agrup_interes_economico_base_imponible_imputada",
    ),
    # "Base imponible o importe..." / "Base imponible o importes
    # rectificados" - M349 intracomunitario amount + rectifications.
    (re.compile(r"^Base imponible o importe", re.IGNORECASE), "base_intracomunitaria"),
    # "Base imponible negativa o cero" - M200 IS carry-forward.
    (re.compile(r"^Base imponible negativa o cero", re.IGNORECASE), "base_imponible_negativa_is"),
)


def _validate_required_role_declarations(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Hard-flip: every casilla matching a required-role label pattern must declare that role.

    Each entry in :data:`_REQUIRED_ROLE_LABEL_PATTERNS` names a label
    pattern plus the canonical role expected on every matching
    :class:`CasillaDefinition`. A miss-declared casilla (wrong role or
    missing role) is a snapshot-build failure. Start the set narrow and
    widen as role rollouts complete.
    """
    failures: list[str] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                try:
                    label = casilla.label
                except MissingTranslationError:
                    # Registry validation can inspect an operator-supplied
                    # structural root before its shared catalogue is
                    # enrolled. The bundled corpus coverage gate owns the
                    # completeness check; this label-derived rule has no
                    # evidence to evaluate until the catalogue is present.
                    continue
                failures.extend(
                    _required_role_failures_for_label(
                        location=f"{modelo.id}.{revision.id}.{casilla.id}",
                        label=label,
                        declared_role=casilla.semantic_role,
                    ),
                )
    return tuple(failures)


def _required_role_failures_for_label(
    *,
    location: str,
    label: str,
    declared_role: str | None,
) -> list[str]:
    """Match one resolved casilla label against every enforced role pattern."""
    failures: list[str] = []
    for pattern, expected_role in _REQUIRED_ROLE_LABEL_PATTERNS:
        if not pattern.match(label):
            continue
        if declared_role is None:
            failures.append(
                f"required-role gate: casilla "
                f"{location} label "
                f"{label!r} matches pattern {pattern.pattern!r} "
                f"but declares no semantic_role (expected "
                f"{expected_role!r})",
            )
        elif declared_role != expected_role:
            failures.append(
                f"required-role gate: casilla "
                f"{location} label "
                f"{label!r} matches pattern {pattern.pattern!r} "
                f"but declares semantic_role "
                f"{declared_role!r} (expected "
                f"{expected_role!r})",
            )
    return failures


def collect_casillas_by_semantic_role(
    modelos: Iterable[ModeloDefinition],
) -> Mapping[str, tuple[SemanticRoleCasillaOccurrence, ...]]:
    """Cross-reference accessor: role -> tuple of (modelo_id, revision_id, casilla_id).

    Used by downstream consumers that need to walk every casilla
    sharing a semantic role across the corpus. The returned mapping
    is immutable and document-order stable per role; the validator
    consumes the same accessor through
    :func:`~cadrumo.domain.calculations.registry.validate_semantic_roles._collect_role_observations`
    internally.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` instances to index
            by the semantic roles declared on their casillas.
    """
    grouped: dict[str, list[SemanticRoleCasillaOccurrence]] = defaultdict(list)
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                if casilla.semantic_role is None:
                    continue
                grouped[casilla.semantic_role].append((modelo.id, revision.id, casilla.id))
    return {role: tuple(occs) for role, occs in grouped.items()}


required_role_declaration_failures = _validate_required_role_declarations
REQUIRED_ROLE_LABEL_PATTERNS = _REQUIRED_ROLE_LABEL_PATTERNS
