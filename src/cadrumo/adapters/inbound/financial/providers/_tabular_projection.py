"""Deterministic projection of normalized tabular rows under a column-role mapping.

Consumes a :class:`~core.tabular.NormalizedTable` plus a
:class:`ColumnRoleMapping` — one :class:`~core.FieldRole` per column, decided
once for the whole file — and copies every cell into its role. The copy is the
whole of the operation: :func:`project_table` performs no stripping, no
separator rewriting, no date parsing and no type coercion, so a projected value
is byte-equal to the cell it came from.

That guarantee is the anti-fabrication control for the tabular lane. Deciding
what a column *means* is a judgement that may be made by a model; moving a
value is not, and is done only by this module. A projection step that
"helpfully" normalized ``1.234,56`` on the way through would be indistinguishable
at the far end from one that invented the number, which is why the property is
byte equality rather than equality-after-normalization.

A column whose role is :attr:`~core.FieldRole.UNMAPPED` is reported in
:attr:`ProjectedTable.unmapped_columns` and copied nowhere. The file is never
refused for carrying one: an export the product does not fully understand still
yields every column it does.

See Also:
    :class:`~core.FieldRole`
        The closed vocabulary a column's meaning is mapped onto.
    :mod:`core.tabular`
        Produces the normalized table this module projects.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.field_role import FieldRole
from .....core.tabular import NormalizedTable

#: Roles that address at most one column of a table. A source carrying two
#: columns for the same one of these is ambiguous about which holds the value,
#: and is reported rather than silently resolved to whichever came first.
_SINGLE_OCCUPANCY_ROLES: frozenset[FieldRole] = frozenset(FieldRole) - {FieldRole.UNMAPPED, FieldRole.NOTES}


class ColumnRoleMapping(BaseModel):
    """What each column of one table means, decided once for the whole file.

    Positional rather than keyed by header text: real exports carry blank and
    duplicated header cells, so a column's position is the only identifier
    guaranteed to address exactly one column.

    Attributes:
        roles: One role per column, in column order.
    """

    model_config = _STRICT_FROZEN

    roles: tuple[FieldRole, ...] = Field(min_length=1)

    def role_for(self, column_index: int) -> FieldRole:
        """Return the role of ``column_index``, or ``UNMAPPED`` beyond the mapping."""
        if 0 <= column_index < len(self.roles):
            return self.roles[column_index]
        return FieldRole.UNMAPPED


class ProjectedCell(BaseModel):
    """One source cell copied under its column's role.

    Attributes:
        column_index: Zero-based column the value came from.
        header: The source header text for that column, verbatim.
        role: The role the column was mapped to.
        value: The source cell, byte-equal to how the file printed it.
    """

    model_config = _STRICT_FROZEN

    column_index: int = Field(ge=0)
    header: str
    role: FieldRole
    value: str


class ProjectedRow(BaseModel):
    """One normalized row projected under the mapping.

    Attributes:
        source_line_number: Physical 1-based line the source row started on.
        cells: The mapped cells, in column order. Unmapped columns are absent.
    """

    model_config = _STRICT_FROZEN

    source_line_number: int = Field(ge=1)
    cells: tuple[ProjectedCell, ...]

    def value_for(self, role: FieldRole) -> str | None:
        """Return the first value carried under ``role``, or ``None``."""
        return next((cell.value for cell in self.cells if cell.role is role), None)


class UnmappedColumn(BaseModel):
    """One column whose meaning was not established.

    Attributes:
        column_index: Zero-based column position.
        header: The source header text, verbatim, so an operator can see what
            the product did not recognise.
    """

    model_config = _STRICT_FROZEN

    column_index: int = Field(ge=0)
    header: str


class AmbiguousRole(BaseModel):
    """One role claimed by more than one column.

    Attributes:
        role: The contested role.
        column_indexes: Every column mapped to it, in column order.
        headers: Those columns' header texts, in the same order.
    """

    model_config = _STRICT_FROZEN

    role: FieldRole
    column_indexes: tuple[int, ...] = Field(min_length=2)
    headers: tuple[str, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _index_and_header_counts_agree(self) -> AmbiguousRole:
        if len(self.column_indexes) != len(self.headers):
            raise ValueError("column_indexes and headers must describe the same columns")
        return self


class ProjectedTable(BaseModel):
    """A normalized table projected under a confirmed column-role mapping.

    Attributes:
        rows: The projected rows, in source order.
        unmapped_columns: Columns carried by the source whose meaning was not
            established. Reported, never copied.
        ambiguous_roles: Roles claimed by more than one column. Every claiming
            column is still projected; the ambiguity is surfaced for an
            operator to resolve rather than guessed at.
    """

    model_config = _STRICT_FROZEN

    rows: tuple[ProjectedRow, ...]
    unmapped_columns: tuple[UnmappedColumn, ...] = ()
    ambiguous_roles: tuple[AmbiguousRole, ...] = ()


def project_table(table: NormalizedTable, mapping: ColumnRoleMapping) -> ProjectedTable:
    """Copy every mapped cell of ``table`` into its role under ``mapping``.

    Values are copied, never interpreted: each :attr:`ProjectedCell.value` is
    byte-equal to the :class:`~core.tabular.NormalizedRow` cell it came
    from. A row shorter than the header (a ragged export) yields only the cells
    it actually carries rather than being padded or refused.

    Args:
        table: The normalized source.
        mapping: One role per column, decided once for the whole file.

    Returns:
        The projected table, with unmapped and contested columns reported.
    """
    headers = table.headers
    unmapped = tuple(
        UnmappedColumn(column_index=index, header=headers[index])
        for index in range(len(headers))
        if mapping.role_for(index) is FieldRole.UNMAPPED
    )

    claims: dict[FieldRole, list[int]] = {}
    for index in range(len(headers)):
        role = mapping.role_for(index)
        if role in _SINGLE_OCCUPANCY_ROLES:
            claims.setdefault(role, []).append(index)
    ambiguous = tuple(
        AmbiguousRole(
            role=role,
            column_indexes=tuple(indexes),
            headers=tuple(headers[index] for index in indexes),
        )
        for role, indexes in claims.items()
        if len(indexes) > 1
    )

    rows = tuple(
        ProjectedRow(
            source_line_number=row.source_line_number,
            cells=tuple(
                ProjectedCell(
                    column_index=index,
                    header=headers[index] if index < len(headers) else "",
                    role=mapping.role_for(index),
                    value=value,
                )
                for index, value in enumerate(row.cells)
                if mapping.role_for(index) is not FieldRole.UNMAPPED
            ),
        )
        for row in table.rows
    )

    return ProjectedTable(rows=rows, unmapped_columns=unmapped, ambiguous_roles=ambiguous)
