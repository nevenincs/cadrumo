"""Perceptor names on annual withholding rows.

A withholding row names its perceptor by country and tax id; the filing name
declared for that party is composed into the row afterwards, so no stored field
on a withholding observation carries it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from ...filing.declared_party_name import DeclaredPartyFilingName

if TYPE_CHECKING:
    from .withholding_bindings import WithholdingObservation

__all__ = [
    "PARTY_FILING_NAME_ROW_FIELD",
    "PENDING_PERCEPTOR_NAME",
    "PENDING_PERCEPTOR_NIF",
    "DeclaredWithholdingParty",
    "is_prescribed_pending_record",
    "withholding_party",
]

#: The row field whose cell holds the perceptor's declared filing name rather than any text a source printed.
PARTY_FILING_NAME_ROW_FIELD: Final = "party_filing_name"

#: The identifier the Modelo 193 design prescribes for a record whose payments are pending collection.
PENDING_PERCEPTOR_NIF: Final = "999999999"
#: The name the Modelo 193 design prescribes, literally, for that record; it names no party.
PENDING_PERCEPTOR_NAME: Final = "VALORES PENDIENTE DE ABONO"


@dataclass(frozen=True, slots=True)
class DeclaredWithholdingParty:
    """A perceptor as a withholding row names it, with the filing name declared for it.

    ``country_code`` is empty when the source stated none; the declared name is
    then looked up by the identifier's own prefix. This satisfies the party
    protocol of :func:`~.party_name_rows.file_party_names` without adding a
    stored field to :class:`WithholdingObservation`.
    """

    country_code: str
    party_tax_id: str
    party_handle: str | None
    party_filing_name: DeclaredPartyFilingName | None


def withholding_party(observation: WithholdingObservation) -> tuple[str, str]:
    """Return the country (empty when unstated) and tax id a perceptor row is named by."""
    return observation.country_code or "", observation.perceptor_tax_id


def is_prescribed_pending_record(row_observations: Iterable[WithholdingObservation]) -> bool:
    """Whether the row is the Modelo 193 pending-collection record, whose name the design fixes."""
    return all(
        observation.perceptor_tax_id == PENDING_PERCEPTOR_NIF
        and observation.perceptor_legal_name == PENDING_PERCEPTOR_NAME
        and bool((observation.pendiente_flag or "").strip())
        for observation in row_observations
    )
