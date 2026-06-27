"""Single-casilla semantic-role resolution for modelo application services.

Snapshot-backed callers pass a :class:`RegistrySnapshot` so semantic roles
resolve only to declared canonical ``casilla.id`` values for that revision.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ...domain.calculations.registry import CasillaId, RegistrySnapshot, validated_casilla_id
from ...domain.modelos._errors import ModeloError


@dataclass(frozen=True, slots=True)
class SemanticRoleCasillaAmbiguity:
    """Structured detail for a semantic role that resolves to multiple casillas."""

    semantic_role: str
    modelo_id: str | None
    revision_id: str | None
    casilla_ids: tuple[CasillaId, ...]

    def context(self) -> dict[str, object]:
        """Return structured error context for AeatError envelopes."""
        return {
            "semantic_role": self.semantic_role,
            "modelo": self.modelo_id,
            "revision": self.revision_id,
            "casilla_ids": self.casilla_ids,
        }


class AmbiguousSemanticRoleCasillaError(ModeloError, ValueError):
    """Raised when a semantic-role resolver would emit an arbitrary casilla id."""

    def __init__(self, ambiguity: SemanticRoleCasillaAmbiguity) -> None:
        self.ambiguity = ambiguity
        scope = []
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
    services.
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


def _casilla_ids_for_semantic_role(casillas: Iterable[object], semantic_role: str) -> tuple[CasillaId, ...]:
    resolved: list[CasillaId] = []
    for casilla in casillas:
        if getattr(casilla, "semantic_role", None) != semantic_role:
            continue
        if not hasattr(casilla, "id"):
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
    "casilla_id_for_unique_revision_semantic_role",
    "casilla_id_for_unique_semantic_role",
]
