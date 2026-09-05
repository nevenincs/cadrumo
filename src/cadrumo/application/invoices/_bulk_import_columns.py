"""Resolve a bulk-invoice-import file's own headers onto importer fields.

A real libro registro carries every field the importer needs under names it has
never seen — ``fecha_expedicion``, ``base_imponible``, ``nif_destinatario`` —
and not one of them matches a canonical column name. The importer used to refuse
such a file whole, so a book with every required field present imported nothing.

Resolution is deterministic first: a column whose header is already a canonical
importer column keeps that field without consulting anything. Only the columns
left over are put to the semantic mapping lane, once per file, over the closed
:class:`~core.FieldRole` vocabulary. Exact-first matters for the same reason it
does in the statement lane — a file already written in the product's own
vocabulary must never depend on a judgement to be read.

A column that resolves to no importer field is **reported, never refused**. The
book that carries ``cuota_iva`` and ``total_factura`` — figures the importer
derives rather than accepts — still imports every row; the operator is told
which columns were not used instead of being handed a rejected file.

See Also:
    :class:`~core.FieldRole`
        The closed vocabulary the mapping lane selects from.
    :mod:`.bulk_import`
        Reads the file and applies this resolution to each row.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from pydantic import BaseModel, NonNegativeInt

from ...core.field_role import FieldRole
from ...core.models import STRICT_FROZEN_CONFIG

__all__ = [
    "BULK_IMPORT_FIELD_BY_ROLE",
    "BulkImportColumnResolution",
    "ColumnRoleMapper",
    "ResolvedColumn",
    "resolve_bulk_import_columns",
]

#: Which importer field each role feeds. Deliberately partial: a role the
#: importer has no field for (the IVA cuota and the grand total, both of which
#: it derives rather than accepts) is absent here, so a column carrying one
#: resolves to no field and is reported rather than quietly discarded.
#:
#: ``FieldRole`` carries no member for a retención *rate*, only its amount, so a
#: book's ``tipo_retencion`` column reports as unmapped while
#: ``importe_retencion`` lands. The declared amount is what the filing needs; the
#: rate is re-derivable from it and the base.
BULK_IMPORT_FIELD_BY_ROLE: dict[FieldRole, str] = {
    FieldRole.COUNTERPARTY_NIF: "counterparty_nif",
    FieldRole.COUNTERPARTY_NAME: "counterparty_name",
    FieldRole.INVOICE_NUMBER: "invoice_number",
    FieldRole.INVOICE_DATE: "invoice_date",
    FieldRole.TAXABLE_BASE: "taxable_base",
    FieldRole.IVA_RATE: "iva_rate",
    FieldRole.RETENCION_AMOUNT: "retencion_amount",
    FieldRole.CURRENCY: "currency",
    FieldRole.COUNTRY_CODE: "country_code",
    FieldRole.NOTES: "notes",
}

ColumnRoleMapper = Callable[[Sequence[str]], Sequence[FieldRole] | None]
"""Establishes one role per column for a header row, or ``None`` when it cannot."""


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
    """

    model_config = STRICT_FROZEN_CONFIG

    column_index: NonNegativeInt
    header: str
    field: str | None = None
    role: FieldRole = FieldRole.UNMAPPED


class BulkImportColumnResolution(BaseModel):
    """How one file's header row resolved onto importer fields.

    Attributes:
        columns: Every source column, in order.
        consulted_mapping_lane: Whether the semantic lane was called. ``False``
            means every column matched a canonical name outright.
    """

    model_config = STRICT_FROZEN_CONFIG

    columns: tuple[ResolvedColumn, ...]
    consulted_mapping_lane: bool = False

    @property
    def field_by_index(self) -> dict[int, str]:
        """Return the importer field for each column that feeds one."""
        return {column.column_index: column.field for column in self.columns if column.field is not None}

    @property
    def unmapped_columns(self) -> tuple[ResolvedColumn, ...]:
        """Return every column that feeds no importer field, for reporting."""
        return tuple(column for column in self.columns if column.field is None)

    @property
    def fields_present(self) -> frozenset[str]:
        """Return the importer fields this file can supply."""
        return frozenset(self.field_by_index.values())


def _canonical_field(header: str) -> str | None:
    """Return the importer field a header names outright, or ``None``."""
    candidate = header.strip().lstrip("﻿").casefold()
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
    exact_fields: list[str | None],
    roles: list[FieldRole],
    *,
    mapper: ColumnRoleMapper | None,
    required_fields: frozenset[str],
) -> bool:
    """Fill unresolved columns from one mapping-lane verdict without displacing exact fields."""
    claimed_fields = {field for field in exact_fields if field is not None}
    if mapper is None or _mapping_lane_not_needed(mapper, required_fields, claimed_fields):
        return False
    proposed_roles = mapper(list(headers))
    if proposed_roles is None:
        return False
    for index, role in enumerate(proposed_roles):
        _apply_proposed_role(index, role, headers, exact_fields, roles, claimed_fields)
    return True


def _mapping_lane_not_needed(
    mapper: ColumnRoleMapper | None,
    required_fields: frozenset[str],
    claimed_fields: set[str],
) -> bool:
    return mapper is None or not required_fields - claimed_fields


def _apply_proposed_role(
    index: int,
    role: FieldRole,
    headers: Sequence[str],
    exact_fields: list[str | None],
    roles: list[FieldRole],
    claimed_fields: set[str],
) -> None:
    if index >= len(headers) or exact_fields[index] is not None:
        return
    field = BULK_IMPORT_FIELD_BY_ROLE.get(role)
    roles[index] = role
    if field is None or field in claimed_fields:
        return
    exact_fields[index] = field
    claimed_fields.add(field)


def resolve_bulk_import_columns(
    headers: Sequence[str],
    *,
    mapper: ColumnRoleMapper | None = None,
    required_fields: frozenset[str] = frozenset(),
) -> BulkImportColumnResolution:
    """Resolve ``headers`` onto importer fields, exact names first.

    A header that already names a canonical importer column is bound to it
    without consulting ``mapper`` at all. The mapping lane is called at most
    once, and **only when exact matching cannot supply every required field** —
    a file already written in the product's own vocabulary is read without any
    judgement, even when it carries extra columns the importer has no slot for.
    Those extras are simply reported. Its verdict is applied only to columns
    exact matching left open, so it can never displace an exact match.

    Args:
        headers: The source header cells, in column order.
        mapper: Establishes roles for the columns exact matching did not
            resolve. ``None`` leaves them unmapped and reported.
        required_fields: Fields the importer cannot proceed without. The
            mapping lane is consulted only if exact matching misses one.

    Returns:
        The per-column resolution, with everything unresolved reported rather
        than refused.
    """
    exact: list[str | None] = [_canonical_field(header) for header in headers]
    roles = [_role_for_exact_field(field) for field in exact]
    consulted = _apply_semantic_column_mapping(
        headers,
        exact,
        roles,
        mapper=mapper,
        required_fields=required_fields,
    )

    return BulkImportColumnResolution(
        columns=tuple(
            ResolvedColumn(column_index=index, header=header, field=exact[index], role=roles[index])
            for index, header in enumerate(headers)
        ),
        consulted_mapping_lane=consulted,
    )
