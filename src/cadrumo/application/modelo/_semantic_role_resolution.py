"""Single-casilla semantic-role resolution for modelo application services.

Snapshot-backed callers pass a :class:`RegistrySnapshot` so semantic roles
resolve only to declared canonical ``casilla.id`` values for that revision.
Advisory helpers that already hold a revision object use the structural
revision resolver and get the same ambiguity guard.

See Also:
    :mod:`~application.modelo._calculate_input`
        Work-unit input shortcuts that resolve operator-facing semantic-role
        tokens through a registry snapshot.
    :mod:`~application.modelo._binding_resolution`
        Declaration-period metadata binding path that only accepts
        informational semantic-role casillas.
    :mod:`~application.modelo._taxation_comparison`
        Snapshot-backed comparison surface that uses semantic roles for the
        Modelo 100 result and quota casillas.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ...core import CasillaId, validated_casilla_id
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.modelos import ModeloError


@runtime_checkable
class _CasillaLike(Protocol):
    """Structural shape a casilla-carrying object must expose to resolve an id.

    Mirrors the ``id`` attribute the registry :class:`CasillaDefinition` shape
    carries, without importing the concrete registry type for this ``object``
    -typed structural walk.
    """

    id: object


@dataclass(frozen=True, slots=True)
class SemanticRoleCasillaAmbiguity:
    """Structured detail for a semantic role that resolves to multiple casillas.

    Attached to :class:`AmbiguousSemanticRoleCasillaError` so callers can relay
    the ambiguous role, modelo, revision, and candidate casillas without parsing
    the error message.
    """

    semantic_role: str
    modelo_id: str | None
    revision_id: RevisionId | None
    casilla_ids: tuple[CasillaId, ...]

    def context(self) -> dict[str, object]:
        """Return structured error context for CadrumoError envelopes."""
        return {
            "semantic_role": self.semantic_role,
            "modelo": self.modelo_id,
            "revision": self.revision_id,
            "casilla_ids": self.casilla_ids,
        }


class AmbiguousSemanticRoleCasillaError(ModeloError, ValueError):
    """Raised when a semantic-role resolver would emit an arbitrary casilla id.

    The exception carries a :class:`SemanticRoleCasillaAmbiguity` payload instead
    of selecting one candidate, preserving the canonical ``casilla.id`` contract.
    """

    def __init__(self, ambiguity: SemanticRoleCasillaAmbiguity) -> None:
        self.ambiguity = ambiguity
        scope: list[str] = []
        if ambiguity.modelo_id is not None:
            scope.append(f"modelo {ambiguity.modelo_id}")
        if ambiguity.revision_id is not None:
            scope.append(f"revision {ambiguity.revision_id}")
        scope_text = " ".join(scope) or "registry revision"
        message = (
            f"{scope_text} resolves semantic_role={ambiguity.semantic_role!r} "
            f"to multiple casillas {ambiguity.casilla_ids!r}; a semantic-role "
            "casilla reference must resolve to exactly one canonical casilla.id"
        )
        super().__init__(message, context=ambiguity.context())


def casilla_id_for_unique_semantic_role(snapshot: RegistrySnapshot, semantic_role: str) -> CasillaId | None:
    """Return the unique casilla id for ``semantic_role`` in ``snapshot``.

    ``None`` means the concrete revision does not declare the role. Multiple
    matches are refused because returning one would silently convert a non-
    canonical reference into an arbitrary canonical ``casilla.id``.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose revision is inspected.
        semantic_role: Semantic role token to resolve.
    """
    return casilla_id_for_unique_revision_semantic_role(
        snapshot.revision,
        semantic_role,
        modelo_id=snapshot.modelo.id,
    )


def casilla_id_for_unique_revision_semantic_role(
    revision: object,
    semantic_role: str,
    *,
    modelo_id: str | None = None,
) -> CasillaId | None:
    """Return the unique casilla id for ``semantic_role`` in ``revision``.

    This accepts a structural revision object so advisory helpers that only
    receive a revision can share the same ambiguity guard as snapshot-backed
    services. The object must expose ``id`` and ``casillas`` attributes
    compatible with the registry :class:`ModeloRevision` shape.
    """
    revision_id = _optional_str(getattr(revision, "id", None))
    casilla_ids = _casilla_ids_for_semantic_role(getattr(revision, "casillas", ()), semantic_role)
    if len(casilla_ids) == 1:
        return casilla_ids[0]
    if len(casilla_ids) > 1:
        raise AmbiguousSemanticRoleCasillaError(
            SemanticRoleCasillaAmbiguity(
                semantic_role=semantic_role,
                modelo_id=modelo_id,
                revision_id=revision_id,
                casilla_ids=casilla_ids,
            ),
        )
    return None


def casilla_id_for_unambiguous_revision_semantic_role(
    revision: object,
    semantic_role: str,
    *,
    modelo_id: str | None = None,
) -> CasillaId | None:
    """Return the casilla id only when ``semantic_role`` resolves unambiguously.

    The sibling above raises on ambiguity so a caller that must not proceed on a
    guess gets an instructive refusal. An advisory has the opposite need: it is
    a non-blocking diagnostic, so a revision it cannot address unambiguously is
    a revision it declines to speak about, and ``None`` already means "no
    casilla to address" for the absent case. This collapses both to that one
    answer.

    Two returns share it, and they are not the same fact: an absent role and an
    ambiguous one. A caller that needs to tell them apart must use the raising
    sibling, because this function deliberately cannot.
    """
    try:
        return casilla_id_for_unique_revision_semantic_role(revision, semantic_role, modelo_id=modelo_id)
    except AmbiguousSemanticRoleCasillaError:
        return None


def _casilla_ids_for_semantic_role(casillas: Iterable[object], semantic_role: str) -> tuple[CasillaId, ...]:
    resolved: list[CasillaId] = []
    for casilla in casillas:
        if getattr(casilla, "semantic_role", None) != semantic_role:
            continue
        if not isinstance(casilla, _CasillaLike):
            raise ValueError(f"semantic_role={semantic_role!r} matched a casilla without canonical casilla.id")
        resolved.append(
            validated_casilla_id(
                casilla.id,
                surface=f"semantic_role {semantic_role!r} casilla.id",
            ),
        )
    return tuple(resolved)


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


__all__ = [
    "AmbiguousSemanticRoleCasillaError",
    "SemanticRoleCasillaAmbiguity",
    "casilla_id_for_unambiguous_revision_semantic_role",
    "casilla_id_for_unique_revision_semantic_role",
    "casilla_id_for_unique_semantic_role",
]
