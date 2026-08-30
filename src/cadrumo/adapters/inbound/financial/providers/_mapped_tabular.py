"""Statement ingest for tabular exports of no recognised fixed layout.

:class:`MappedTabularProvider` is the last provider detection tries. Every
exact fixed-layout parser — the bank CSV layouts, the spreadsheet, OFX, the N26
statement PDF — is offered the file first, and this lane sees it only when none
of them claimed it. That ordering is load-bearing: a known bank export must
keep taking its exact parser, because an exact layout match is a deterministic
read of a known structure, while this lane's read depends on a column-role
mapping decided per file. Letting the fallback shadow an exact provider would
silently turn the deterministic parse into an inferred one.

The lane itself is deterministic end to end. :mod:`core.tabular` resolves
the file's shape, a mapping supplies one :class:`~core.FieldRole` per column,
and :mod:`._tabular_projection` copies each cell into its role byte-for-byte.
Only the mapping is a judgement, and it is made once per file over a closed
allow-list of roles, never over a cell value.

A file is never refused for a row or a column the product does not understand:
an unmapped column is reported, and a row that will not parse is reported and
skipped while every other row still imports.

See Also:
    :func:`default_tabular_mapping_resolver`
        The single wiring point through which detection obtains a mapping.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import override

from .....core import FieldRole, MissingOptionalExtraError
from .....core.errors import CadrumoError, CoreValidationError, resolve_error_message
from .....core.logging import get_logger
from .....core.parsing import normalise_iso_4217_currency
from .....core.tabular import NormalizedTable, TabularSourceError, normalize_tabular_bytes
from .....domain.transactions.raw_transaction import SourceFormat
from ._base import (
    FinancialProvider,
    FinancialProviderError,
    FinancialValidationError,
    InvalidFinancialSourceError,
    ParsedLedgerRow,
    ProviderValidation,
    build_raw_transaction,
    default_currency,
    parse_amount_value,
    parse_date_value,
    synthesize_transaction_id,
)
from ._constants import CSV_EXTENSIONS
from ._tabular_projection import ColumnRoleMapping, ProjectedRow, project_table

_logger = get_logger(__name__)

#: Extensions this lane will consider. A delimited text export can arrive under
#: any of them; content normalization decides whether it is really tabular.
MAPPED_TABULAR_EXTENSIONS: frozenset[str] = CSV_EXTENSIONS | frozenset({".tsv", ".txt"})

#: Roles a bank-movement row cannot do without. ``FieldRole`` is shared with
#: the invoice-book lane and carries no statement-specific date or movement
#: amount member, so a statement's booked date reads under
#: :attr:`~core.FieldRole.INVOICE_DATE` and its amount under
#: :attr:`~core.FieldRole.GRAND_TOTAL`.
REQUIRED_STATEMENT_ROLES: frozenset[FieldRole] = frozenset({FieldRole.INVOICE_DATE, FieldRole.GRAND_TOTAL})

TabularMappingResolver = Callable[[NormalizedTable], ColumnRoleMapping | None]
"""Supplies one role per column for a normalized table, or ``None`` when it cannot."""


@dataclass(frozen=True, slots=True)
class _MappedRowFields:
    """One projected row interpreted into the fields a raw transaction needs."""

    booked_date: date
    amount: Decimal
    currency: str
    description: str
    counterparty: str | None
    external_id: str | None


def _resolve_roles_semantically(table: NormalizedTable) -> ColumnRoleMapping | None:
    """Establish ``table``'s column roles with the semantic column-role mapper.

    The import is deferred to call time for two reasons: ``cadrumo.llm`` is an
    optional extra, and it is a SIBLING of this package in the layering
    contract rather than an inner tier. Reaching it here, only once a file has
    actually arrived at this lane, keeps a host without the extra able to
    detect and parse every exact-layout file as before.

    A host that cannot map resolves to ``None``, which the lane reports as
    "column roles could not be established". That is the right answer when the
    mapper is installed and declined: reaching a model is not the only way this
    can go, because the client consults its profile-bound response cache first,
    so an operator who has not unlocked a profile gets a storage refusal well
    before any request is built. Detecting a file must not depend on being
    logged in, and a genuine programming fault still raises.

    **A missing extra is not that case, and must not resolve to ``None``.**
    ``MissingOptionalExtraError`` is both a :class:`CadrumoError` and an
    :class:`ImportError`, so the broad guards below would otherwise swallow it
    and report the operator's FILE as unreadable when what is actually absent is
    a capability of their INSTALL -- pointing them at a CSV they cannot fix
    instead of the capability that resolves it. It is re-raised so the lane
    surfaces the extra's typed machine identity, which is what the governing
    decision requires of the tabular split: a known fixed-layout file imports
    with no extra, and an unknown header vocabulary refuses here, carrying the
    ``llm`` extra's identity rather than a rendered installation command.
    """
    try:
        from .....llm.column_role_mapping import SemanticColumnRoleMapper
    except MissingOptionalExtraError:
        raise
    except ImportError:
        _logger.debug("semantic column-role mapping is unavailable: the llm extra is not installed")
        return None
    try:
        proposal = SemanticColumnRoleMapper().map(table.headers)
    except MissingOptionalExtraError:
        raise
    except CadrumoError:
        _logger.warning("semantic column-role mapping could not establish roles for this table", exc_info=True)
        return None
    for rejected in proposal.rejected_role_proposals:
        # The positional mapping carries roles only, so a token the allow-list
        # refused would otherwise vanish between here and the operator, who
        # sees the column reported unmapped but not what was proposed for it.
        _logger.warning(
            "column %d %r was proposed the role %r, which is not a permitted role",
            rejected.column_index,
            rejected.header,
            rejected.proposed_role,
        )
    return ColumnRoleMapping(roles=proposal.roles)


def default_tabular_mapping_resolver() -> TabularMappingResolver | None:
    """Return the mapping resolver detection uses, or ``None`` when none is installed.

    The single wiring point between this lane and whatever establishes column
    roles. It resolves to the semantic column-role mapper, which decides one
    role per column from the file's header vocabulary alone, once per file.
    Every cell is still copied by :mod:`._tabular_projection` under that
    mapping, so nothing about how values reach a row changed when this stopped
    returning ``None``.
    """
    return _resolve_roles_semantically


class MappedTabularProvider(FinancialProvider):
    """Ingest bank movements from a tabular export under a column-role mapping.

    Attributes:
        mapping_resolver: Supplies the per-file column-role mapping. Defaults
            to :func:`default_tabular_mapping_resolver`, so production wiring
            has one home; tests and callers holding their own mapping pass it
            directly.
    """

    name = "Mapped tabular provider"
    supported_extensions = MAPPED_TABULAR_EXTENSIONS
    source_format = SourceFormat.CSV
    # The bundled operator exports exercising this lane are generated documents
    # modelled on real bank, ERP and expense-tool export schemas.
    verification_source = "synthetic_from_bank_published_text"
    provisional_pending_specimen = True

    def __init__(self, mapping_resolver: TabularMappingResolver | None = None) -> None:
        """Bind the resolver supplying this lane's per-file column-role mapping."""
        self.mapping_resolver: TabularMappingResolver | None = (
            mapping_resolver if mapping_resolver is not None else default_tabular_mapping_resolver()
        )

    @override
    def validate_source(self, path: Path) -> ProviderValidation:
        """Report whether the source normalizes and maps, and what was not understood.

        Validation is a full dry projection: every column the mapping did not
        establish and every row that will not parse is reported here, so the
        operator sees the whole picture before ingest rather than one row at a
        time. The source stays valid as long as at least one row parses.
        """
        try:
            table = normalize_tabular_bytes(self._read_source_bytes(path))
        except (FinancialProviderError, TabularSourceError) as exc:
            return ProviderValidation(is_valid=False, warnings=(str(exc),))
        dialect_note = f"delimiter={table.dialect.delimiter!r},decimal={table.dialect.decimal_separator!r}"
        if self.mapping_resolver is None:
            return ProviderValidation(
                is_valid=False,
                warnings=("no column-role mapping resolver is installed for the tabular mapping lane",),
                detected_encoding=table.dialect.encoding,
                detected_dialect=dialect_note,
            )
        mapping = self.mapping_resolver(table)
        if mapping is None:
            return ProviderValidation(
                is_valid=False,
                warnings=("column roles could not be established for this table",),
                detected_encoding=table.dialect.encoding,
                detected_dialect=dialect_note,
            )
        missing = REQUIRED_STATEMENT_ROLES - set(mapping.roles)
        if missing:
            return ProviderValidation(
                is_valid=False,
                warnings=(
                    "mapped table carries no column for "
                    f"{', '.join(sorted(role.value for role in missing))}; a bank movement needs both",
                ),
                detected_encoding=table.dialect.encoding,
                detected_dialect=dialect_note,
            )
        projected = project_table(table, mapping)
        warnings = [
            f"column {column.column_index} {column.header!r} was not mapped to a role and is not imported"
            for column in projected.unmapped_columns
        ]
        warnings.extend(
            f"role {ambiguity.role.value!r} is claimed by columns {list(ambiguity.column_indexes)}; "
            "the first is used and the rest are reported"
            for ambiguity in projected.ambiguous_roles
        )
        warnings.extend(notice.detail for notice in table.notices)
        parsed_count = 0
        for row in projected.rows:
            try:
                self._row_fields(row, table)
            except FinancialProviderError as exc:
                warnings.append(
                    f"row at line {row.source_line_number} cannot be imported: {resolve_error_message(exc)}"
                )
                continue
            parsed_count += 1
        if parsed_count == 0:
            warnings.append("no row of the mapped table could be parsed")
        return ProviderValidation(
            is_valid=parsed_count > 0,
            warnings=tuple(warnings),
            detected_encoding=table.dialect.encoding,
            detected_dialect=dialect_note,
        )

    @override
    def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:
        """Yield one :class:`ParsedLedgerRow` per importable row of the mapped table.

        A row that will not parse is logged and skipped; the rest still import.

        Raises:
            InvalidFinancialSourceError: The source does not normalize, or no
                column-role mapping could be established for it.
        """
        source_bytes = self._read_source_bytes(path)
        source_sha256 = self._compute_sha256(source_bytes)
        try:
            table = normalize_tabular_bytes(source_bytes)
        except TabularSourceError as exc:
            raise InvalidFinancialSourceError(f"{path.name} does not normalize: {exc}") from exc
        if self.mapping_resolver is None:
            raise InvalidFinancialSourceError(
                "no column-role mapping resolver is installed for the tabular mapping lane",
            )
        mapping = self.mapping_resolver(table)
        if mapping is None:
            raise InvalidFinancialSourceError(
                f"column roles could not be established for {path.name}",
            )
        projected = project_table(table, mapping)
        for row in projected.rows:
            try:
                fields = self._row_fields(row, table)
            except FinancialProviderError:
                _logger.warning(
                    "mapped_tabular: row at line %d of %s could not be parsed; skipping",
                    row.source_line_number,
                    path.name,
                    exc_info=True,
                )
                continue
            yield build_raw_transaction(
                provider=self,
                path=path,
                source_sha256=source_sha256,
                source_row_index=row.source_line_number,
                provider_transaction_id=fields.external_id
                or synthesize_transaction_id(
                    provider_name=self.name,
                    source_sha256=source_sha256,
                    source_row_index=row.source_line_number,
                ),
                booked_date=fields.booked_date,
                value_date=None,
                amount=fields.amount,
                currency=fields.currency,
                counterparty=fields.counterparty,
                description=fields.description,
                raw_fields={cell.header: cell.value for cell in row.cells},
            )

    def _row_fields(self, row: ProjectedRow, table: NormalizedTable) -> _MappedRowFields:
        """Interpret one projected row's copied values into transaction fields.

        Interpretation happens here and nowhere earlier: the projection copied
        the printed forms verbatim, and the *detected* dialect decides how the
        amount reads.
        """
        raw_date = row.value_for(FieldRole.INVOICE_DATE)
        raw_amount = row.value_for(FieldRole.GRAND_TOTAL)
        if raw_date is None or raw_amount is None:
            raise InvalidFinancialSourceError(
                f"row at line {row.source_line_number} is missing a date or an amount",
            )
        description = row.value_for(FieldRole.NOTES) or row.value_for(FieldRole.COUNTERPARTY_NAME) or ""
        if not description.strip():
            raise InvalidFinancialSourceError(
                f"row at line {row.source_line_number} carries no description",
            )
        return _MappedRowFields(
            booked_date=parse_date_value(raw_date, day_first=True, label="date"),
            amount=parse_amount_value(raw_amount, decimal_separator=table.dialect.decimal_separator),
            currency=self._row_currency(row),
            description=description,
            counterparty=row.value_for(FieldRole.COUNTERPARTY_NAME),
            external_id=row.value_for(FieldRole.TRANSACTION_ID),
        )

    @staticmethod
    def _row_currency(row: ProjectedRow) -> str:
        """Return the row's ISO 4217 currency, defaulting when the table carries none."""
        raw = row.value_for(FieldRole.CURRENCY)
        if raw is None or not raw.strip():
            return default_currency()
        try:
            return normalise_iso_4217_currency(raw)
        except CoreValidationError as exc:
            raise FinancialValidationError(
                f"row at line {row.source_line_number} currency {raw!r} is not a three-letter ISO 4217 code",
            ) from exc
