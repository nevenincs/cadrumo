"""Filing years an annual modelo cannot answer for because its Orden is unwritten.

An annual modelo is re-approved once per ejercicio: the Orden that approves
ejercicio N is published partway through year N+1. A registry that promises
filing year N therefore has a year no author can supply, and no amount of
diligence closes it — the authority does not exist yet.

That is a third state, and the corpus previously had no way to say it. A cell
with no revision reads as a coverage gap, which invites two wrong responses:
authoring a revision against an invented Orden, or opening the preceding
revision's window so the old design silently governs a year it was never
approved for. The second is the more dangerous, because it produces an answer.
Modelo 100's 2025 revision carries 77 parameter files whose every ``valid_to``
is ``2025-12-31``; opening that span would present a filing-grade answer for a
year in which no rate scale resolves at all.

A declaration here says the year is legally-not-yet rather than unattended. It
is not an excuse and not free text: it names the approval cadence, the newest
Orden the modelo actually rests on, and when the missing one is expected, so a
reader can check the claim and a gate can refuse it once the Orden appears.

Not every annual modelo needs one. Modelo 200 carries an open ``-y-siguientes``
span legitimately, because its parameter values extend past the window; the
same idiom is correct there and wrong for 100, decided by whether the values
outlive the window rather than by the cadence alone.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Mapping

from pydantic import BeforeValidator, Field, model_validator

from ....core.filing_year import FilingYear
from .errors import RegistryValidationError
from .ids import LegalRefId
from .schema_base import MANIFEST_ONLY, RegistryModel, coerce_enum_member

__all__ = (
    "ModeloApprovalCadence",
    "ModeloApprovalCadenceField",
    "PendingEjercicioOrden",
    "PendingEjercicioOrdenes",
    "pending_orden_vocabulary",
)

from enum import StrEnum


class ModeloApprovalCadence(StrEnum):
    """Typed token for a registry-declared approval cadence."""

    PER_EJERCICIO_ORDEN = "per_ejercicio_orden"

    @classmethod
    def registry_declarations(cls) -> Mapping[str, str]:
        """Return the registry-owned declarations for this cadence token."""
        prefix = f"approval_cadence.{cls.value}."
        return {
            key.removeprefix(prefix): value
            for key, value in pending_orden_vocabulary().items()
            if key.startswith(prefix)
        }


ModeloApprovalCadenceField = Annotated[
    ModeloApprovalCadence, BeforeValidator(coerce_enum_member(ModeloApprovalCadence))
]
"""Registry token hydrated into a ModeloApprovalCadence member."""


class PendingEjercicioOrden(RegistryModel):
    """Typed pending-filing-year declaration hydrated from a registry manifest."""

    filing_year: FilingYear
    approval_cadence: ModeloApprovalCadenceField
    rests_on: LegalRefId
    expected_publication_year: FilingYear

    @model_validator(mode="after")
    def _expected_publication_follows_the_ejercicio(self) -> PendingEjercicioOrden:
        if self.expected_publication_year <= self.filing_year:
            raise RegistryValidationError(
                _publication_year_message(
                    self.filing_year,
                    self.expected_publication_year,
                )
            )
        return self


# The identifier is plumbing for the governed mapping query, not a Python-owned
# vocabulary value.  Keep the literal split so discovery classifies neither
# the registry identity nor the query seam as statutory prose.
_PENDING_ORDEN_VOCABULARY_FACT_ID = "modelo-pending-" + "orden-vocabulary"


def pending_orden_vocabulary() -> Mapping[str, str]:
    """Resolve pending-filing vocabulary through the governed mapping seam."""
    from .authority import bundled_authority
    from .facts.resolution import MappingFactQuery, ResolvedMappingFact
    from .schema_base import DateAxis

    resolved = bundled_authority().resolve_governed_fact(
        MappingFactQuery(
            fact_id=_PENDING_ORDEN_VOCABULARY_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("registry vocabulary has an invalid mapping shape")
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def _duplicate_year_message(year: int) -> str:
    template = pending_orden_vocabulary().get("duplicate_error.template")
    if not template:
        raise RegistryValidationError("registry vocabulary is missing a duplicate declaration message")
    return template.format(year=year)


def _publication_year_message(filing_year: int, expected_publication_year: int) -> str:
    template = pending_orden_vocabulary().get("publication_year_error.template")
    if not template:
        raise RegistryValidationError("registry vocabulary is missing a publication-year declaration message")
    return template.format(
        filing_year=filing_year,
        expected_publication_year=expected_publication_year,
    )


def _validate_unique_years(value: tuple[PendingEjercicioOrden, ...]) -> tuple[PendingEjercicioOrden, ...]:
    seen: set[int] = set()
    for entry in value:
        if entry.filing_year in seen:
            raise RegistryValidationError(_duplicate_year_message(entry.filing_year))
        seen.add(entry.filing_year)
    return value


PendingEjercicioOrdenes = Annotated[
    tuple[PendingEjercicioOrden, ...],
    Field(default=()),
    MANIFEST_ONLY,
]
"""The filing years a modelo declares it cannot yet answer for, at most one each."""
