"""Resolve a bulk-invoice-import file's own headers onto importer fields.

A real libro registro carries every field the importer needs under names it has
never seen — ``fecha_expedicion``, ``base_imponible``, ``nif_destinatario`` —
and not one of them matches a canonical column name. The importer used to refuse
such a file whole, so a book with every required field present imported nothing.

Resolution is deterministic first: a role the operator assigned to a column binds
it, and a column whose header is already a canonical importer column keeps that
field without consulting anything. Only the columns
left over are put to the semantic mapping lane, once per file, over the closed
:class:`~core.field_role.FieldRole` vocabulary. Exact-first matters for the same reason it
does in the statement lane — a file already written in the product's own
vocabulary must never depend on a judgement to be read.

A column that resolves to no importer field is **reported, never refused**. The
book that carries ``cuota_iva`` and ``total_factura`` — figures the importer
derives rather than accepts — still imports every row; the operator is told
which columns were not used instead of being handed a rejected file.

See Also:
    :class:`~core.field_role.FieldRole`
        The closed vocabulary the mapping lane selects from.
    :mod:`.bulk_import`
        Reads the file and applies this resolution to each row.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, NonNegativeInt

from ...core.field_role import FieldRole
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.invoices.errors import InvoiceValidationError
from ..ledger.column_roles import ColumnRoleReaderUnavailable
from ..operator_actions.models import PreconditionVerdict

__all__ = [
    "BULK_IMPORT_FIELD_BY_ROLE",
    "BulkImportColumnResolution",
    "ColumnRoleMapper",
    "ColumnSource",
    "ResolvedColumn",
    "resolve_bulk_import_columns",
]

#: Which importer field each role feeds. Deliberately partial: a role the
#: importer has no field for (the IVA cuota and the grand total, both of which
#: it derives rather than accepts) is absent here, so a column carrying one
#: resolves to no field and is reported rather than quietly discarded.
#:
#: A retención *rate* is accepted only beside its amount: the importer checks
#: the two against each other and never derives the amount from the rate.
BULK_IMPORT_FIELD_BY_ROLE: dict[FieldRole, str] = {
    FieldRole.COUNTERPARTY_NIF: "counterparty_nif",
    FieldRole.COUNTERPARTY_NAME: "counterparty_name",
    FieldRole.INVOICE_NUMBER: "invoice_number",
    FieldRole.INVOICE_DATE: "invoice_date",
    FieldRole.TAXABLE_BASE: "taxable_base",
    FieldRole.IVA_RATE: "iva_rate",
    FieldRole.RETENCION_AMOUNT: "retencion_amount",
    FieldRole.RETENCION_RATE: "retencion_rate",
    FieldRole.CURRENCY: "currency",
    FieldRole.COUNTRY_CODE: "country_code",
    FieldRole.NOTES: "notes",
}

ColumnRoleMapper = Callable[[Sequence[str]], Sequence[FieldRole] | ColumnRoleReaderUnavailable | None]
"""Establishes one role per column for a header row, or says why it could not.

:class:`~application.ledger.column_roles.ColumnRoleReaderUnavailable` means the
model that names columns was never asked; ``None`` means it established nothing.
"""


ColumnSource = Literal["operator", "exact", "model", "unmapped"]
"""Who settled a column's role: the operator, a canonical header, the mapping lane, or no one."""


class ResolvedColumn(BaseModel):
    """One source column and the importer field it feeds.

    Attributes:
        column_index: Zero-based position in the source header.
        header: The header text exactly as the file printed it.
        field: The importer field this column supplies, or ``None`` when the
            column's meaning was not established or maps to nothing the
            importer accepts.
        role: The role the column was mapped to. ``UNMAPPED`` when the mapping
            lane could not place it; a real role with ``field`` still ``None``
            means the product understood the column but has no slot for it.
        source: Who settled the role. ``operator`` also covers a column the
            operator stated is not used.
    """

    model_config = STRICT_FROZEN_CONFIG

    column_index: NonNegativeInt
    header: str
    field: str | None = None
    role: FieldRole = FieldRole.UNMAPPED
    source: ColumnSource = "unmapped"


class BulkImportColumnResolution(BaseModel):
    """How one file's header row resolved onto importer fields.

    Attributes:
        columns: Every source column, in order.
        consulted_mapping_lane: Whether the semantic lane was called. ``False``
            means every column matched a canonical name outright.
        reader_unavailable_verdict: Why the model that names columns could not
            be asked, when the lane was needed and its reader was unavailable.
            Nothing beyond the exact matches was then read.
    """

    model_config = STRICT_FROZEN_CONFIG

    columns: tuple[ResolvedColumn, ...]
    consulted_mapping_lane: bool = False
    reader_unavailable_verdict: PreconditionVerdict | None = None

    @property
    def field_by_index(self) -> dict[int, str]:
        """Return the importer field for each column that feeds one."""
        return {column.column_index: column.field for column in self.columns if column.field is not None}

    @property
    def unmapped_columns(self) -> tuple[ResolvedColumn, ...]:
        """Return every column that feeds no importer field, for reporting."""
        return tuple(column for column in self.columns if column.field is None)

    @property
    def operator_assigned(self) -> bool:
        """Return whether the operator stated a role for any column."""
        return any(column.source == "operator" for column in self.columns)

    @property
    def fields_present(self) -> frozenset[str]:
        """Return the importer fields this file can supply."""
        return frozenset(self.field_by_index.values())


#: Header spellings that name an importer field outright under another name.
_BULK_IMPORT_FIELD_ALIASES: dict[str, str] = {
    "irpf_retention_rate": "retencion_rate",
    "retention_rate": "retencion_rate",
    "irpf_retention_amount": "retencion_amount",
    "retention_amount": "retencion_amount",
}


def _canonical_field(header: str) -> str | None:
    """Return the importer field a header names outright, or ``None``."""
    candidate = header.strip().lstrip("﻿").casefold()
    candidate = _BULK_IMPORT_FIELD_ALIASES.get(candidate, candidate)
    return candidate if candidate in set(BULK_IMPORT_FIELD_BY_ROLE.values()) else None


def _role_for_exact_field(field: str | None) -> FieldRole:
    """Return the declared role for an exact importer field, if it has one."""
    if field is None:
        return FieldRole.UNMAPPED
    return next(
        (role for role, mapped_field in BULK_IMPORT_FIELD_BY_ROLE.items() if mapped_field == field), FieldRole.UNMAPPED
    )


def _apply_semantic_column_mapping(
    headers: Sequence[str],
    fields: list[str | None],
    roles: list[FieldRole],
    sources: list[ColumnSource],
    *,
    mapper: ColumnRoleMapper | None,
    required_fields: frozenset[str],
) -> bool | ColumnRoleReaderUnavailable:
    """Fill open columns from one mapping-lane verdict without displacing stated or exact fields.

    Returns whether the lane's roles were applied, or the lane's report that
    its reader could not be asked.
    """
    claimed_fields = {field for field in fields if field is not None}
    if mapper is None or not required_fields - claimed_fields:
        return False
    proposed_roles = mapper(list(headers))
    if proposed_roles is None:
        return False
    if isinstance(proposed_roles, ColumnRoleReaderUnavailable):
        return proposed_roles
    for index, role in enumerate(proposed_roles):
        _apply_proposed_role(index, role, headers, fields, roles, sources, claimed_fields)
    return True


def _apply_proposed_role(
    index: int,
    role: FieldRole,
    headers: Sequence[str],
    fields: list[str | None],
    roles: list[FieldRole],
    sources: list[ColumnSource],
    claimed_fields: set[str],
) -> None:
    if index >= len(headers) or sources[index] != "unmapped" or role is FieldRole.UNMAPPED:
        return
    field = BULK_IMPORT_FIELD_BY_ROLE.get(role)
    roles[index] = role
    sources[index] = "model"
    if field is None or field in claimed_fields:
        return
    fields[index] = field
    claimed_fields.add(field)


def _check_operator_roles(operator_roles: Mapping[int, FieldRole], column_count: int) -> None:
    """Refuse a stated assignment the importer cannot honour, before anything is resolved.

    Raises:
        InvoiceValidationError: A column index is not in the file, a role is not
            one the importer accepts, or a role is stated for two columns.
    """
    claimed_roles: set[FieldRole] = set()
    prefix = "the column roles stated for the invoice book are invalid"
    for index, role in operator_roles.items():
        if not 0 <= index < column_count:
            raise InvoiceValidationError(
                f"{prefix}: column {index} is not in the file, which has {column_count} columns",
                translated_message="application.invoices.bulk_import.errors.column_role_out_of_range",
                context={"column": index + 1, "columns": column_count},
            )
        if role is not FieldRole.UNMAPPED and role not in BULK_IMPORT_FIELD_BY_ROLE:
            raise InvoiceValidationError(
                f"{prefix}: role {role.value!r} is not one the importer accepts",
                translated_message="application.invoices.bulk_import.errors.column_role_not_accepted",
                context={"role": role.value},
            )
        if role is not FieldRole.UNMAPPED and role in claimed_roles:
            raise InvoiceValidationError(
                f"{prefix}: role {role.value!r} is stated for more than one column",
                translated_message="application.invoices.bulk_import.errors.column_role_repeated",
                context={"role": role.value},
            )
        claimed_roles.add(role)


def resolve_bulk_import_columns(
    headers: Sequence[str],
    *,
    mapper: ColumnRoleMapper | None = None,
    required_fields: frozenset[str] = frozenset(),
    operator_roles: Mapping[int, FieldRole] | None = None,
) -> BulkImportColumnResolution:
    """Resolve ``headers`` onto importer fields: the operator's roles, then exact names, then the mapping lane.

    A column the operator assigned a role keeps it whatever its header says,
    and a field the operator assigned is never given to another column by its
    exact name. A header that already names a canonical importer column is
    bound to it without consulting ``mapper`` at all. The mapping lane is called
    at most once, and **only when the stated roles and exact matching cannot
    supply every required field** — a file already written in the product's own
    vocabulary is read without any judgement, even when it carries extra columns
    the importer has no slot for. Those extras are simply reported. Its verdict
    is applied only to columns still open, so it can never displace a stated
    role or an exact match.

    Args:
        headers: The source header cells, in column order.
        mapper: Establishes roles for the columns neither the operator nor exact
            matching resolved. ``None`` leaves them unmapped and reported.
        required_fields: Fields the importer cannot proceed without. The
            mapping lane is consulted only if the stated roles and exact
            matching miss one.
        operator_roles: The role the operator assigned to a column, by its
            zero-based index. ``UNMAPPED`` states that the column is not used.

    Returns:
        The per-column resolution, with everything unresolved reported rather
        than refused, and the reader's verdict when the lane was needed and
        could not be asked.

    Raises:
        InvoiceValidationError: A stated assignment names a column the file does
            not have, a role the importer does not accept, or one role twice.
    """
    stated = dict(operator_roles or {})
    _check_operator_roles(stated, len(headers))
    fields: list[str | None] = [None] * len(headers)
    roles = [FieldRole.UNMAPPED] * len(headers)
    sources: list[ColumnSource] = ["unmapped"] * len(headers)
    for index, role in stated.items():
        fields[index] = BULK_IMPORT_FIELD_BY_ROLE.get(role)
        roles[index] = role
        sources[index] = "operator"
    stated_fields = {field for field in fields if field is not None}
    for index, header in enumerate(headers):
        field = _canonical_field(header)
        if sources[index] != "unmapped" or field is None or field in stated_fields:
            continue
        fields[index] = field
        roles[index] = _role_for_exact_field(field)
        sources[index] = "exact"
    consulted = _apply_semantic_column_mapping(
        headers,
        fields,
        roles,
        sources,
        mapper=mapper,
        required_fields=required_fields,
    )
    unavailable = consulted if isinstance(consulted, ColumnRoleReaderUnavailable) else None

    return BulkImportColumnResolution(
        columns=tuple(
            ResolvedColumn(
                column_index=index, header=header, field=fields[index], role=roles[index], source=sources[index]
            )
            for index, header in enumerate(headers)
        ),
        consulted_mapping_lane=consulted is True,
        reader_unavailable_verdict=None if unavailable is None else unavailable.precondition_verdict,
    )
