"""Typed evidence of whether an observed declaration is an original or a correction.

A filed declaration's legal kind is not a casilla, so the calculation-only
:class:`~cadrumo.domain.calculations.registry.bindings.RegistryModeloObservation`
never carries it. This module owns the evidence record that travels beside the
observation instead: the kind, the closed basis that admitted it, and every
reading that was seen but is not admitted as proof.

Only two bases admit a kind. ``SUBMITTED_FILE_MARKER`` is AEAT's own submitted
fichero parsed against the pinned record design, whose "Declaración
complementaria" byte has the closed value domain blank or ``X``.
``LOCAL_REVISION`` is the kind of a revision Cadrumo itself filed locally; it is
a local assertion and never filing grade by itself. Everything else -- the
register request type and the declaration PDF -- is recorded as a reading and
admits nothing. A page-level indicator marks a continuation page and is not
filing-kind evidence of any grade.
Unknown is basis ``NONE`` with no kind, never a default ``ORIGINAL``.

The shared predicate :func:`complementaria_only_source_outcome` is the one place
that turns an absent complementaria-only casilla into a proven zero, and only
for an admitted ``ORIGINAL``.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.type_guards import is_object_list_or_tuple, is_object_mapping
from .filing_record import FilingDeclarationKind, declaration_kind_for_tipo_solicitud


class FilingKindEvidenceBasis(StrEnum):
    """Closed catalogue of what established an observed filing kind.

    Attributes:
        SUBMITTED_FILE_MARKER: AEAT's submitted fichero parsed against the pinned
            layout, read at the record design's "Declaración complementaria"
            position.
        LOCAL_REVISION: The amendment identity of a revision filed locally.
        NONE: No admitted evidence; the kind is unknown.
    """

    SUBMITTED_FILE_MARKER = "submitted_file_marker"
    LOCAL_REVISION = "local_revision"
    NONE = "none"


ADMITTED_FILING_KIND_BASES: Final[frozenset[FilingKindEvidenceBasis]] = frozenset(
    {FilingKindEvidenceBasis.SUBMITTED_FILE_MARKER, FilingKindEvidenceBasis.LOCAL_REVISION},
)
"""The bases whose kind a consumer may rely on."""


class FilingKindReadingSource(StrEnum):
    """Where one filing-kind reading was taken from.

    Attributes:
        SUBMITTED_FILE_MARKER: The submitted fichero's declaration-level
            complementaria byte; the only reading that can become a basis.
        REGISTER_TIPO_SOLICITUD: The register row's request type naming exactly
            one correction kind. Recorded, never admitted.
    """

    SUBMITTED_FILE_MARKER = "submitted_file_marker"
    REGISTER_TIPO_SOLICITUD = "register_tipo_solicitud"


#: Source token of the page-position reading that earlier captures stored. The
#: page indicator marks a continuation page, not a filing kind, so stored
#: readings carrying it are ignored when an observation loads.
_RETIRED_PAGE_INDICATOR_SOURCE: Final = "submitted_file_page_indicator"


class FilingKindUnknownReason(StrEnum):
    """Why an observed filing kind is unknown.

    Attributes:
        NO_ADMITTED_EVIDENCE: No admitted basis was read, including every
            observation stored before the kind was captured.
        UNREADABLE_MARKER: The submitted-file marker carried a token outside the
            record design's value domain.
        DISAGREEMENT: Readings of the same filing named different kinds, so no
            side is allowed to win.
    """

    NO_ADMITTED_EVIDENCE = "no_admitted_evidence"
    UNREADABLE_MARKER = "unreadable_marker"
    DISAGREEMENT = "disagreement"


def _is_retired_page_indicator_reading(reading: object) -> bool:
    if not is_object_mapping(reading):
        return False
    return reading.get("source") == _RETIRED_PAGE_INDICATOR_SOURCE


def _parse_kind(value: object) -> FilingDeclarationKind | None:
    return None if value is None else FilingDeclarationKind(value)


class FilingKindReading(BaseModel):
    """One filing-kind token read from an artefact, with where it was read.

    ``token`` is the artefact's own spelling, stripped of padding; an empty
    token is a parsed blank, which the record design gives a meaning, and is
    distinct from a reading that was never taken. ``kind`` is the token's
    meaning under its source's value domain, or ``None`` when the token lies
    outside it.
    """

    model_config = STRICT_FROZEN_CONFIG

    source: FilingKindReadingSource
    kind: FilingDeclarationKind | None
    token: str = Field(max_length=256)
    source_locator: str = Field(min_length=1, max_length=512)

    @field_validator("source", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_source(cls, value: object) -> FilingKindReadingSource:
        return FilingKindReadingSource(value)

    @field_validator("kind", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_kind(cls, value: object) -> FilingDeclarationKind | None:
        return _parse_kind(value)


class SubmittedFileFilingKindMarker(BaseModel):
    """The filing-kind readings parsed from one submitted fichero.

    Present only when the fichero parsed against the pinned layout and the
    layout declares a declaration-level marker; absence means the marker was
    not read, never that it was blank.
    """

    model_config = STRICT_FROZEN_CONFIG

    declaration_marker: FilingKindReading

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _sources_match_roles(self) -> Self:
        if self.declaration_marker.source is not FilingKindReadingSource.SUBMITTED_FILE_MARKER:
            raise ValueError("a submitted-file declaration marker must be read from the marker position")
        return self


class ObservedFilingKind(BaseModel):
    """The filing kind of one observed declaration and the evidence behind it.

    A kind is present exactly when the basis is admitted; basis ``NONE``
    carries the reason the kind is unknown instead. ``readings`` keeps every
    token seen, admitted or not, so a later amendment of the admission rules
    can be applied to stored evidence without a re-capture.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: FilingDeclarationKind | None = None
    basis: FilingKindEvidenceBasis
    source_locator: str | None = Field(default=None, min_length=1, max_length=512)
    unknown_reason: FilingKindUnknownReason | None = None
    readings: tuple[FilingKindReading, ...] = ()

    @field_validator("readings", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _drop_retired_page_indicator_readings(cls, value: object) -> object:
        if not is_object_list_or_tuple(value):
            return value
        stored: list[object] = list(value)
        return tuple(reading for reading in stored if not _is_retired_page_indicator_reading(reading))

    @field_validator("kind", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_kind(cls, value: object) -> FilingDeclarationKind | None:
        return _parse_kind(value)

    @field_validator("basis", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_basis(cls, value: object) -> FilingKindEvidenceBasis:
        return FilingKindEvidenceBasis(value)

    @field_validator("unknown_reason", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_unknown_reason(cls, value: object) -> FilingKindUnknownReason | None:
        return None if value is None else FilingKindUnknownReason(value)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _kind_iff_admitted_basis(self) -> Self:
        unknown = self.basis is FilingKindEvidenceBasis.NONE
        if unknown != (self.kind is None):
            raise ValueError("an observed filing kind carries a kind if and only if its basis is not NONE")
        if unknown != (self.source_locator is None):
            raise ValueError("an observed filing kind carries a source locator if and only if its basis is not NONE")
        if unknown != (self.unknown_reason is not None):
            raise ValueError("an observed filing kind states an unknown reason if and only if its basis is NONE")
        return self

    @property
    def admitted_kind(self) -> FilingDeclarationKind | None:
        """Return the kind a consumer may rely on, or ``None`` when unknown."""
        return self.kind if self.basis in ADMITTED_FILING_KIND_BASES else None


UNKNOWN_FILING_KIND: Final[ObservedFilingKind] = ObservedFilingKind(
    basis=FilingKindEvidenceBasis.NONE,
    unknown_reason=FilingKindUnknownReason.NO_ADMITTED_EVIDENCE,
)
"""The reading of an observation that carries no filing-kind evidence."""


def filing_kind_or_unknown(projection: ObservedFilingKind | None) -> ObservedFilingKind:
    """Return ``projection``, reading an absent one as unknown.

    The one mapping every reader uses, so no consumer can tell an observation
    stored before filing kinds were captured from one whose kind is unknown.
    """
    return UNKNOWN_FILING_KIND if projection is None else projection


#: The record designs' flag mark: the declaration-level marker is blank or this byte.
_RECORD_FLAG_MARK: Final = "X"

_DECLARATION_MARKER_KINDS: Final[dict[str, FilingDeclarationKind]] = {
    "": FilingDeclarationKind.ORIGINAL,
    _RECORD_FLAG_MARK: FilingDeclarationKind.COMPLEMENTARIA,
}


def submitted_file_marker_reading(token: str, *, source_locator: str) -> FilingKindReading:
    """Read the declaration-level complementaria byte of a submitted fichero."""
    stripped = token.strip()
    return FilingKindReading(
        source=FilingKindReadingSource.SUBMITTED_FILE_MARKER,
        kind=_DECLARATION_MARKER_KINDS.get(stripped),
        token=stripped,
        source_locator=source_locator,
    )


def register_tipo_solicitud_reading(
    tipo_solicitud: str | None,
    *,
    source_locator: str,
) -> FilingKindReading | None:
    """Return the register reading when the request type names exactly one correction kind.

    A request type naming none yields no reading: what AEAT's register shows for
    an original is not documented, so its silence is not read as anything.
    """
    kind = declaration_kind_for_tipo_solicitud(tipo_solicitud)
    if kind is None or tipo_solicitud is None:
        return None
    return FilingKindReading(
        source=FilingKindReadingSource.REGISTER_TIPO_SOLICITUD,
        kind=kind,
        token=tipo_solicitud.strip()[:256],
        source_locator=source_locator,
    )


def _unknown(reason: FilingKindUnknownReason, readings: Iterable[FilingKindReading]) -> ObservedFilingKind:
    return ObservedFilingKind(
        basis=FilingKindEvidenceBasis.NONE,
        unknown_reason=reason,
        readings=tuple(readings),
    )


def observed_filing_kind_from_capture(
    marker: SubmittedFileFilingKindMarker | None,
    *,
    register_reading: FilingKindReading | None = None,
) -> ObservedFilingKind:
    """Derive the filing kind of one captured AEAT declaration.

    Only the submitted-file marker admits a kind. Every other reading is kept,
    and any reading naming a different kind, or none, makes the kind unknown
    with reason ``DISAGREEMENT`` rather than letting either side win.
    """
    unadmitted = () if register_reading is None else (register_reading,)
    if marker is None:
        return _unknown(FilingKindUnknownReason.NO_ADMITTED_EVIDENCE, unadmitted)
    readings = (marker.declaration_marker, *unadmitted)
    kind = marker.declaration_marker.kind
    if kind is None:
        return _unknown(FilingKindUnknownReason.UNREADABLE_MARKER, readings)
    if any(reading.kind is not kind for reading in readings):
        return _unknown(FilingKindUnknownReason.DISAGREEMENT, readings)
    return ObservedFilingKind(
        kind=kind,
        basis=FilingKindEvidenceBasis.SUBMITTED_FILE_MARKER,
        source_locator=marker.declaration_marker.source_locator,
        readings=readings,
    )


def observed_filing_kind_for_local_revision(
    kind: FilingDeclarationKind,
    *,
    source_locator: str,
) -> ObservedFilingKind:
    """Return the locally asserted kind of a revision Cadrumo filed itself."""
    return ObservedFilingKind(
        kind=kind,
        basis=FilingKindEvidenceBasis.LOCAL_REVISION,
        source_locator=source_locator,
    )


class ComplementariaOnlySourceOutcome(StrEnum):
    """How one declared source casilla of an observed filing resolves.

    Attributes:
        OBSERVED: The casilla was observed and its value is used as read.
        PROVEN_ZERO: The casilla is absent, declared complementaria-only, and
            the filing is an admitted original, so it holds nothing by law.
        UNRESOLVED: The casilla is absent and nothing proves its value.
        CONTRADICTED: An admitted original carries a nonzero value in a casilla
            only a complementaria fills.
    """

    OBSERVED = "observed"
    PROVEN_ZERO = "proven_zero"
    UNRESOLVED = "unresolved"
    CONTRADICTED = "contradicted"


def complementaria_only_source_outcome(
    casilla_id: CasillaId,
    *,
    observed_value: Decimal | None,
    filing_kind: ObservedFilingKind,
    complementaria_only_casilla_ids: frozenset[CasillaId],
) -> ComplementariaOnlySourceOutcome:
    """Resolve one declared source casilla of an observed filing.

    The single predicate the relation fold, the live relation capture and the
    clean-state presence check apply. An absent casilla folds as zero only when
    the registry declares it complementaria-only and the filing is an
    ``ORIGINAL`` on an admitted basis; a complementaria or an unknown kind
    leaves it unresolved, never zero.
    """
    declared = casilla_id in complementaria_only_casilla_ids
    original = filing_kind.admitted_kind is FilingDeclarationKind.ORIGINAL
    if observed_value is not None:
        if declared and original and observed_value != Decimal("0"):
            return ComplementariaOnlySourceOutcome.CONTRADICTED
        return ComplementariaOnlySourceOutcome.OBSERVED
    if declared and original:
        return ComplementariaOnlySourceOutcome.PROVEN_ZERO
    return ComplementariaOnlySourceOutcome.UNRESOLVED


__all__ = [
    "ADMITTED_FILING_KIND_BASES",
    "UNKNOWN_FILING_KIND",
    "ComplementariaOnlySourceOutcome",
    "FilingKindEvidenceBasis",
    "FilingKindReading",
    "FilingKindReadingSource",
    "FilingKindUnknownReason",
    "ObservedFilingKind",
    "SubmittedFileFilingKindMarker",
    "complementaria_only_source_outcome",
    "filing_kind_or_unknown",
    "observed_filing_kind_for_local_revision",
    "observed_filing_kind_from_capture",
    "register_tipo_solicitud_reading",
    "submitted_file_marker_reading",
]
