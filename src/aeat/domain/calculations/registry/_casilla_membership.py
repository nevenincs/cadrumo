"""Registry-scoped casilla id membership helpers."""

from __future__ import annotations

from collections.abc import Iterable

from ._errors import RegistryValidationError
from ._ids import CasillaId
from ._schema import CasillaDefinition, ModeloRevision


def casillas_by_id(revision: ModeloRevision) -> dict[CasillaId, CasillaDefinition]:
    """Return revision casillas keyed by canonical ``casilla.id``."""
    casillas: dict[CasillaId, CasillaDefinition] = {}
    duplicates: set[CasillaId] = set()
    for casilla in revision.casillas:
        if casilla.id in casillas:
            duplicates.add(casilla.id)
        casillas[casilla.id] = casilla
    if duplicates:
        duplicate_ids = tuple(sorted(duplicates))
        raise RegistryValidationError(
            f"revision {revision.id!r} declares duplicate casilla.id values; "
            f"casilla references are ambiguous: {duplicate_ids!r}",
            context={"revision_id": revision.id, "casilla_ids": ",".join(duplicate_ids)},
        )
    return casillas


def declared_casilla_ids(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return the canonical ``casilla.id`` values declared by ``revision``."""
    return frozenset(casillas_by_id(revision))


def undeclared_casilla_ids(
    revision: ModeloRevision,
    casilla_ids: Iterable[CasillaId],
) -> tuple[CasillaId, ...]:
    """Return supplied ids that are not declared as canonical ids by ``revision``."""
    return tuple(sorted(set(casilla_ids) - declared_casilla_ids(revision)))


def casilla_metadata_aliases(revision: ModeloRevision) -> dict[str, tuple[CasillaId, ...]]:
    """Return display/export metadata tokens that must not be accepted as casilla refs."""
    aliases: dict[str, list[CasillaId]] = {}
    for casilla in revision.casillas:
        for token in _casilla_metadata_tokens(casilla):
            if token is None or token == casilla.id:
                continue
            aliases.setdefault(token, []).append(casilla.id)
    return {token: tuple(sorted(casilla_ids)) for token, casilla_ids in aliases.items()}


def casilla_metadata_alias_targets(revision: ModeloRevision, token: str) -> tuple[CasillaId, ...]:
    """Return canonical casilla ids whose display/export metadata matches ``token``."""
    return casilla_metadata_aliases(revision).get(token, ())


def _casilla_metadata_tokens(casilla: CasillaDefinition) -> tuple[str | None, ...]:
    return (casilla.number, casilla.form_number, *casilla.export_refs)
