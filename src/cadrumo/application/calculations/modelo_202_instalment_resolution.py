"""What one Modelo 202 instalment contributes to the later settlement of its ejercicio.

Orden HFP/227/2017 art. 1.3 makes the Modelo 202 owed below the LIS art. 40.3
threshold only in an instalment where an ingreso results, so an instalment that
was never filed is one of two different things: an instalment whose own verdict
says nothing was owed, which contributes a proven 0.00, or an instalment the
application cannot show was not owed, which leaves the settlement unresolved.
This module holds the typed answer every consumer reads, the cross-period gate
and the Modelo 200 instalment producers alike, so no consumer re-derives it. The
answer is decided where the instalment verdict is decided
(:func:`~cadrumo.application.overview.modelo202_instalment.resolve_modelo_202_instalment`);
consumers receive it through a :data:`Modelo202InstalmentResolver` port.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ...core.period import Period
from ...domain.calculations.registry.applicability_modelo202 import (
    Modelo202BaseBasis,
    Modelo202InstalmentGrounds,
)
from .observations_repository import ObservationEnvelopePayload


class Modelo202InstalmentResolutionKind(StrEnum):
    """Whether an instalment was filed, was not owed, or cannot be settled yet."""

    FILED = "filed"
    """A presented filing holds the instalment: its local filing or captured AEAT evidence."""
    NOT_OWED = "not_owed"
    """No filing is held and the instalment's own verdict says none was owed: it contributes 0.00."""
    UNRESOLVED = "unresolved"
    """No filing is held and nothing shows the instalment was not owed."""


class Modelo202InstalmentUnresolvedReason(StrEnum):
    """Why an unfiled instalment cannot count as nothing paid."""

    VERDICT_UNDECIDED = "verdict_undecided"
    """The instalment's verdict is incomplete or its modality could not be derived."""
    OWED_UNFILED = "owed_unfiled"
    """The instalment's verdict says it was owed, and no filing of it is held."""


@dataclass(frozen=True, slots=True)
class Modelo202InstalmentBase:
    """The art. 40.2 base an instalment's verdict rested on and the return it was read from."""

    value: Decimal
    basis: Modelo202BaseBasis
    source_modelo: str
    source_period: Period


@dataclass(frozen=True, slots=True)
class Modelo202InstalmentResolution:
    """One Modelo 202 instalment's contribution to the settlement of its ejercicio.

    Attributes:
        instalment: The Modelo 202 period.
        kind: Filed, not owed, or unresolved.
        amount: The filed result for a filed instalment, ``0.00`` for one not
            owed, ``None`` when unresolved.
        filing: The presented filing a filed instalment rests on.
        grounds: For an instalment decided by its own verdict, the outcome with
            the catalogue's served reason and legal references; ``None`` for a
            filed instalment and for one whose modality was never derived.
        base: The art. 40.2 base the verdict rested on, when one was read.
        unresolved_reason: Why an unresolved instalment cannot count as zero.
    """

    instalment: Period
    kind: Modelo202InstalmentResolutionKind
    amount: Decimal | None = None
    filing: ObservationEnvelopePayload | None = None
    grounds: Modelo202InstalmentGrounds | None = None
    base: Modelo202InstalmentBase | None = None
    unresolved_reason: Modelo202InstalmentUnresolvedReason | None = None

    def __post_init__(self) -> None:
        """Refuse a resolution whose fields contradict its kind."""
        if not _FIELDS_MATCH_KIND[self.kind](self):
            raise ValueError(f"Modelo 202 instalment resolution {self.kind.value} has contradicting fields")


def _filed_fields_match(resolution: Modelo202InstalmentResolution) -> bool:
    return resolution.filing is not None and resolution.unresolved_reason is None


def _not_owed_fields_match(resolution: Modelo202InstalmentResolution) -> bool:
    return (
        resolution.amount == 0
        and resolution.filing is None
        and resolution.grounds is not None
        and resolution.unresolved_reason is None
    )


def _unresolved_fields_match(resolution: Modelo202InstalmentResolution) -> bool:
    return resolution.amount is None and resolution.filing is None and resolution.unresolved_reason is not None


_FIELDS_MATCH_KIND: Final[
    Mapping[Modelo202InstalmentResolutionKind, Callable[[Modelo202InstalmentResolution], bool]]
] = MappingProxyType(
    {
        Modelo202InstalmentResolutionKind.FILED: _filed_fields_match,
        Modelo202InstalmentResolutionKind.NOT_OWED: _not_owed_fields_match,
        Modelo202InstalmentResolutionKind.UNRESOLVED: _unresolved_fields_match,
    }
)


type Modelo202InstalmentResolver = Callable[[Period], Modelo202InstalmentResolution]
"""Resolve one Modelo 202 instalment from the stores one read is bound to."""


__all__ = [
    "Modelo202InstalmentBase",
    "Modelo202InstalmentResolution",
    "Modelo202InstalmentResolutionKind",
    "Modelo202InstalmentResolver",
    "Modelo202InstalmentUnresolvedReason",
]
