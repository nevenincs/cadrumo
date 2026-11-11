"""Filing a party's declared name into the row cells whose layout field states its composition rule."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, NamedTuple, Protocol

from ...filing.declared_party_name import DeclaredPartyFilingName
from ...filing.declared_party_name_filing import PartyNameRefusals, PartyNameSlot, party_name_filing_text
from ...filing.errors import FilingExportDeclaredPartyNameError
from .errors import RegistryValidationError
from .ids import BindingId
from .invoice_row_materialization import invoice_party_reference
from .party_name_composition import PartyNameComposition
from .schema_exports import ExportFieldDefinition, ExportRecordDefinition

if TYPE_CHECKING:
    from .schema import ModeloRevision


class DeclaredPartyObservation(Protocol):
    """The observation facts a party's declared name is looked up by."""

    @property
    def country_code(self) -> str:
        """The country code the declared name is looked up by."""
        ...

    @property
    def party_tax_id(self) -> str:
        """The party tax id the declared name is looked up by."""
        ...

    @property
    def party_handle(self) -> str | None:
        """The party handle the declared name is looked up by."""
        ...

    @property
    def party_filing_name(self) -> DeclaredPartyFilingName | None:
        """The party filing name the declared name is looked up by."""
        ...


class PartyNameField(NamedTuple):
    """The layout field that files a party-name binding, with its design rule and width."""

    record: ExportRecordDefinition
    field: ExportFieldDefinition
    composition: PartyNameComposition
    length: int


type RowValues = dict[tuple[BindingId, int], Decimal | str]


def party_name_fields(revision: ModeloRevision, name_bindings: frozenset[BindingId]) -> dict[BindingId, PartyNameField]:
    """Index the layout field that files each ``party_filing_name`` binding, with its design rule and width.

    Raises:
        RegistryValidationError: A binding files a party name but no layout
            field states how, or two fields filing it state different rules.
    """
    fields: dict[BindingId, PartyNameField] = {}
    for layout in revision.export_layouts:
        for record in layout.records:
            for field in record.fields:
                if field.binding not in name_bindings or field.party_name is None or field.length is None:
                    continue
                found = PartyNameField(record, field, field.party_name, field.length)
                known = fields.setdefault(field.binding, found)
                if (known.composition, known.length) != (found.composition, found.length):
                    raise RegistryValidationError(
                        f"binding {field.binding!r} files a party name in fields with different design rules",
                    )
    missing = sorted(name_bindings - fields.keys())
    if missing:
        raise RegistryValidationError(
            f"bindings {missing!r} file a party name but no export field states its composition rule",
        )
    return fields


def index_declared_parties[ObservationT: DeclaredPartyObservation](
    observations: Iterable[ObservationT],
) -> dict[str, ObservationT]:
    """Index observations by party reference, preferring one that carries a declared name."""
    parties: dict[str, ObservationT] = {}
    for observation in observations:
        reference = invoice_party_reference(observation.country_code, observation.party_tax_id)
        known = parties.get(reference)
        if known is None or (known.party_filing_name is None and observation.party_filing_name is not None):
            parties[reference] = observation
    return parties


def file_party_names[ObservationT: DeclaredPartyObservation](
    revision: ModeloRevision,
    rows: RowValues,
    observations: Iterable[ObservationT],
    *,
    name_bindings: frozenset[BindingId],
    refusals: PartyNameRefusals | None,
) -> RowValues:
    """Replace each row's party reference in a ``party_filing_name`` cell with the name its slot files.

    A revision read without its export layouts has no slot to file into, so its
    name cells are dropped rather than left holding the reference.
    """
    if not name_bindings:
        return rows
    if not revision.export_layouts:
        return {key: value for key, value in rows.items() if key[0] not in name_bindings}
    return _compose_party_name_rows(
        rows,
        party_name_fields(revision, name_bindings),
        index_declared_parties(observations),
        refusals=refusals,
    )


def _compose_party_name_rows(
    rows: RowValues,
    name_fields: dict[BindingId, PartyNameField],
    parties: Mapping[str, DeclaredPartyObservation],
    *,
    refusals: PartyNameRefusals | None,
) -> RowValues:
    """Replace each name cell's party reference with the name its slot files.

    A cell whose party has no name the slot's rule composes within its width is
    left out and recorded in ``refusals``.
    """
    composed: RowValues = {}
    for (binding_id, row_index), value in rows.items():
        name_field = name_fields.get(binding_id)
        if name_field is None:
            composed[(binding_id, row_index)] = value
            continue
        party = parties.get(str(value))
        slot = _party_name_slot(name_field, party, row_index=row_index, refusals=refusals)
        try:
            composed[(binding_id, row_index)] = party_name_filing_text(
                None if party is None else party.party_filing_name,
                composition=name_field.composition,
                slot=slot,
            )
        except FilingExportDeclaredPartyNameError as refusal:
            if refusals is not None:
                refusals.refusals.append(refusal)
    return composed


def _party_name_slot(
    name_field: PartyNameField,
    party: DeclaredPartyObservation | None,
    *,
    row_index: int,
    refusals: PartyNameRefusals | None,
) -> PartyNameSlot:
    return PartyNameSlot(
        modelo=refusals.modelo if refusals is not None else str(name_field.record.id),
        export_record_id=str(name_field.record.id),
        export_field_id=str(name_field.field.id),
        field_length=name_field.length,
        party_handle=None if party is None else party.party_handle,
        row_index=row_index,
    )


__all__ = [
    "DeclaredPartyObservation",
    "PartyNameField",
    "RowValues",
    "file_party_names",
    "index_declared_parties",
    "party_name_fields",
]
