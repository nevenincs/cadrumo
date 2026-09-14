"""Shared temporal-delta and predecessor contracts for registry authorities.

Modelo editions and governed-fact revisions are two authored projections of
the same mechanism: a revision has a scoped validity window and may name one
sibling predecessor, explicitly declare a grounded root, or omit the key to
remain a full copy. This module owns that mechanism once. Domain schemas add
their payloads by subclassing :class:`RegistryRevisionDeclaration`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Annotated, Final, override

from pydantic import (
    BeforeValidator,
    Discriminator,
    Field,
    SerializerFunctionWrapHandler,
    Tag,
    model_serializer,
    model_validator,
)

from ....core.toml import freeze_toml_value
from .errors import RegistryValidationError
from .ids import RegistryRevisionNodeId, RevisionId
from .period_selector_overlap import period_selectors_overlap
from .schema_base import MANIFEST_ONLY, LegalRefs, RegistryModel, SourceRefs, coerce_enum_member
from .schema_references import PeriodScopedValidityWindow, PeriodSelector, RegistryTemporalBounds

__all__ = (
    "DeclaredPredecessor",
    "DeclaredPredecessorField",
    "NoPredecessor",
    "NoPredecessorCause",
    "RegistryRevisionDeclaration",
    "RegistryRevisionNode",
    "RegistryTemporalDeltaDeclaration",
    "RevisionPredecessorProjection",
    "RevisionWindow",
    "project_predecessor_declarations",
    "validate_predecessor_date_agreement",
    "validate_predecessor_forest",
    "validate_revision_predecessors",
)


class DeclaredPredecessor(RegistryModel):
    """An explicit claim that a revision is authored relative to a sibling."""

    revision_id: RegistryRevisionNodeId

    @model_serializer(mode="plain")
    def _serialise_as_authored(self) -> str:
        return self.revision_id


_NO_PREDECESSOR_KEY: Final = "none"
_DECLARED_PREDECESSOR_TAG: Final = "revision"
_PREDECESSOR_KIND_REFUSAL: Final = (
    "predecessor must be the revision id of a sibling edition, or a single 'none' table "
    "grounding why no earlier sibling edition exists"
)


class NoPredecessorCause(StrEnum):
    """The closed set of grounded reasons a revision has no earlier sibling edition.

    The ``reason`` prose of a :class:`NoPredecessor` states the grounding in
    full and stays required; this token is the machine-readable classification
    of that same fact, so a census can answer which cause a root stands on
    without parsing prose. The set is closed: a root whose grounding is none of
    these is refused at the typed boundary rather than carried as a free-text
    token a later consumer would have to interpret.
    """

    predecessor_row_without_lineage = "predecessor_row_without_lineage"
    """The earlier edition carries rows with no grounded continuity, so nothing can be inherited from it."""

    parallel_scheme_variants = "parallel_scheme_variants"
    """The edition is one of several concurrent scheme variants, not a step in a sequence."""

    overlapping_predecessor = "overlapping_predecessor"
    """The candidate earlier edition's validity scope overlaps this one, so neither strictly precedes the other."""

    forbidden_by_norm = "forbidden_by_norm"
    """The governing norm approves this edition independently, so no earlier edition is its authored basis."""

    lower_grade = "lower_grade"
    """Existing authored root pending source-data replanning; never inferred by migration or loading."""

    unretired_withdrawal = "unretired_withdrawal"
    """The earlier edition withdraws content without retiring it, so inheritance would carry withdrawn rows."""

    official_structure_differs = "official_structure_differs"
    """The official record structure is reordered or shifted, so supersede-in-place would not reproduce it."""


class NoPredecessor(RegistryModel):
    """A grounded claim that a revision has no earlier sibling revision."""

    reason: str = Field(min_length=1, max_length=1024)
    legal_refs: LegalRefs
    source_refs: SourceRefs
    cause: Annotated[NoPredecessorCause | None, BeforeValidator(coerce_enum_member(NoPredecessorCause))] = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @model_serializer(mode="wrap")
    def _serialise_as_authored(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        return {_NO_PREDECESSOR_KEY: handler(self)}


def _predecessor_declaration_kind(value: object) -> str | None:
    if isinstance(value, DeclaredPredecessor | str):
        return _DECLARED_PREDECESSOR_TAG
    if isinstance(value, NoPredecessor):
        return _NO_PREDECESSOR_KEY
    if isinstance(value, Mapping) and set(value) == {_NO_PREDECESSOR_KEY}:
        return _NO_PREDECESSOR_KEY
    return None


def _hydrate_declared_predecessor(value: object) -> object:
    if isinstance(value, str):
        return {"revision_id": value}
    return value


def _hydrate_no_predecessor(value: object) -> object:
    if isinstance(value, Mapping):
        return freeze_toml_value(value[_NO_PREDECESSOR_KEY])
    return value


DeclaredPredecessorField = Annotated[
    Annotated[
        DeclaredPredecessor,
        BeforeValidator(_hydrate_declared_predecessor),
        Tag(_DECLARED_PREDECESSOR_TAG),
    ]
    | Annotated[NoPredecessor, BeforeValidator(_hydrate_no_predecessor), Tag(_NO_PREDECESSOR_KEY)],
    Discriminator(
        _predecessor_declaration_kind,
        custom_error_type="predecessor_kind",
        custom_error_message=_PREDECESSOR_KIND_REFUSAL,
    ),
]
"""Authored predecessor token shared by every revisioned registry schema."""


class RegistryRevisionNode(RegistryModel, ABC):
    """Common predecessor-bearing node independent of identity/window spelling.

    Concrete registries implement :meth:`revision_identity`; this keeps the
    self-edge invariant in the base even when one schema spells the identity
    ``id`` and another spells it ``variant_id``.
    """

    predecessor: Annotated[DeclaredPredecessorField | None, MANIFEST_ONLY] = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @abstractmethod
    def revision_identity(self) -> str:
        """Return the schema-specific identity of this revision node."""
        raise NotImplementedError

    @model_validator(mode="after")
    def _predecessor_is_another_revision(self) -> RegistryRevisionNode:
        identity = self.revision_identity()
        if isinstance(self.predecessor, DeclaredPredecessor) and self.predecessor.revision_id == identity:
            raise RegistryValidationError(f"revision {identity!r} declares itself as its own predecessor")
        return self


class RegistryRevisionDeclaration(RegistryRevisionNode, PeriodScopedValidityWindow):
    """Common envelope for a period-scoped full-copy or delta revision."""

    id: RevisionId
    valid_to: Annotated[date | None, MANIFEST_ONLY] = None

    @override
    def revision_identity(self) -> str:
        """Return the stable Modelo revision identity."""
        return self.id


class RegistryTemporalDeltaDeclaration(RegistryRevisionNode, RegistryTemporalBounds):
    """A predecessor-bearing delta with optional bounds and optional period scope."""

    period_selector: PeriodSelector | None = Field(default=None, exclude_if=lambda value: value is None)


@dataclass(frozen=True, slots=True)
class RevisionWindow:
    """The validity dates and period coordinate of one revision."""

    valid_from: date
    valid_to: date | None
    period_selector: PeriodSelector | None


@dataclass(frozen=True, slots=True)
class RevisionPredecessorProjection:
    """The three declaration states projected from typed revisions."""

    named: Mapping[str, str]
    declared_roots: frozenset[str]
    keyless: frozenset[str]


def project_predecessor_declarations(
    revisions: Mapping[str, RegistryRevisionNode],
) -> RevisionPredecessorProjection:
    """Project typed declarations once for forest validation and delta loading."""
    declarations = {key: revision.predecessor for key, revision in revisions.items()}
    return RevisionPredecessorProjection(
        named={
            key: declaration.revision_id
            for key, declaration in declarations.items()
            if isinstance(declaration, DeclaredPredecessor)
        },
        declared_roots=frozenset(
            key for key, declaration in declarations.items() if isinstance(declaration, NoPredecessor)
        ),
        keyless=frozenset(key for key, declaration in declarations.items() if declaration is None),
    )


def validate_revision_predecessors(
    subject_id: str,
    revisions: Mapping[str, RegistryRevisionNode],
    *,
    windows: Mapping[str, RevisionWindow] | None = None,
    subject_kind: str = "modelo",
    overlap_allows_parallel: bool = True,
) -> RevisionPredecessorProjection:
    """Validate one revision map's forest and materialized date direction.

    Period-scoped concrete revisions need not pass ``windows``. Delta schemas
    pass the windows produced by their shared materializer, keeping forest and
    date checks independent of how their optional bounds were authored.
    """
    projection = project_predecessor_declarations(revisions)
    validate_predecessor_forest(
        subject_id,
        named=projection.named,
        declared_roots=projection.declared_roots,
        keyless=projection.keyless,
        subject_kind=subject_kind,
    )
    effective_windows = windows
    if effective_windows is None:
        if any(not isinstance(revision, RegistryRevisionDeclaration) for revision in revisions.values()):
            raise RegistryValidationError(
                f"{subject_kind} {subject_id!r} uses delta-authored revision windows; "
                "materialized windows are required for predecessor date validation"
            )
        effective_windows = {
            key: RevisionWindow(
                valid_from=revision.valid_from,
                valid_to=revision.valid_to,
                period_selector=revision.period_selector,
            )
            for key, revision in revisions.items()
            if isinstance(revision, RegistryRevisionDeclaration)
        }
    validate_predecessor_date_agreement(
        subject_id,
        named=projection.named,
        windows=effective_windows,
        subject_kind=subject_kind,
        overlap_allows_parallel=overlap_allows_parallel,
    )
    return projection


def validate_predecessor_forest(
    subject_id: str,
    *,
    named: Mapping[str, str],
    declared_roots: frozenset[str],
    keyless: frozenset[str],
    subject_kind: str = "modelo",
) -> None:
    """Refuse predecessor declarations that do not form a rooted forest."""
    overlap = (frozenset(named) & declared_roots) | (frozenset(named) & keyless) | (declared_roots & keyless)
    if overlap:
        raise RegistryValidationError(
            f"{subject_kind} {subject_id!r} editions {sorted(overlap)!r} carry more than one "
            "predecessor declaration state",
        )
    if not named and not declared_roots:
        return
    # Keyless revisions are authored full copies: roots of the storage
    # dependency forest, not claims that they are chronologically first. More
    # than one is valid when independent branches are compacted separately.
    editions = frozenset(named) | declared_roots | keyless
    for edition, target in sorted(named.items()):
        if target == edition:
            raise RegistryValidationError(
                f"{subject_kind} {subject_id!r} revision {edition!r} declares itself as its own predecessor",
            )
        if target not in editions:
            raise RegistryValidationError(
                f"{subject_kind} {subject_id!r} revision {edition!r} declares predecessor {target!r}, "
                f"which is not a revision of this {subject_kind}; declared revisions are {sorted(editions)!r}",
            )
    _refuse_cycles(subject_id, named, subject_kind=subject_kind)


def _refuse_cycles(subject_id: str, named: Mapping[str, str], *, subject_kind: str) -> None:
    settled: set[str] = set()
    for start in sorted(named):
        path: list[str] = []
        on_path: set[str] = set()
        current = start
        while current in named and current not in settled:
            if current in on_path:
                cycle = [*path[path.index(current) :], current]
                chain = " -> ".join(repr(edition) for edition in cycle)
                raise RegistryValidationError(
                    f"{subject_kind} {subject_id!r} predecessor declarations form a cycle {chain}; "
                    "no edition on it is reachable from a root",
                )
            path.append(current)
            on_path.add(current)
            current = named[current]
        settled.update(path)


def validate_predecessor_date_agreement(
    subject_id: str,
    *,
    named: Mapping[str, str],
    windows: Mapping[str, RevisionWindow],
    subject_kind: str = "modelo",
    overlap_allows_parallel: bool = True,
) -> None:
    """Refuse a predecessor that is not earlier when revision scopes do not overlap."""
    for edition, target in sorted(named.items()):
        successor = windows.get(edition)
        predecessor = windows.get(target)
        if successor is None or predecessor is None:
            missing = edition if successor is None else target
            raise RegistryValidationError(
                f"{subject_kind} {subject_id!r} revision {missing!r} has no declared validity window "
                f"to check the predecessor edge {edition!r} -> {target!r} against",
            )
        if overlap_allows_parallel and _period_scopes_overlap(
            successor.period_selector,
            predecessor.period_selector,
        ):
            continue
        if predecessor.valid_from < successor.valid_from:  # type: ignore[operator]
            continue
        raise RegistryValidationError(
            f"{subject_kind} {subject_id!r} revision {edition!r} {_describe(successor)} declares predecessor "
            f"{target!r} {_describe(predecessor)}, which does not take effect before it; the two editions "
            "do not overlap, so the declared predecessor must be the earlier edition",
        )


def _describe(window: RevisionWindow) -> str:
    valid_from = window.valid_from
    valid_to = window.valid_to
    selector = window.period_selector
    end = valid_to.isoformat() if valid_to is not None else "open"  # type: ignore[union-attr]
    if selector is None:
        years = "any year"
        periods = "any period"
    elif selector.years:
        years = ", ".join(str(year) for year in selector.years)
        periods = ", ".join(str(period) for period in selector.declared_periods)
    elif selector.year_from is None:  # type: ignore[union-attr]
        years = "any year"
        periods = ", ".join(str(period) for period in selector.declared_periods)
    else:
        years = f"{selector.year_from} to {selector.year_to if selector.year_to is not None else 'open'}"
        periods = ", ".join(str(period) for period in selector.declared_periods)
    return f"(valid {valid_from.isoformat()} to {end}; years {years}; periods {periods})"  # type: ignore[union-attr]


def _period_scopes_overlap(left: PeriodSelector | None, right: PeriodSelector | None) -> bool:
    """Treat an omitted selector as the universal scope on either side."""
    if left is None or right is None:
        return True
    return period_selectors_overlap(left, right)
