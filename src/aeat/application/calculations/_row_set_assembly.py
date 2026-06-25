"""Reassemble pull-side `RowSetEdit` records into typed observations.

The pull adapter captures Detalle-tab detail rows as a flat tuple of
``RowSetCellEdit(binding, row_index, value)`` records grouped by the
row-set's grouping key. To consume those rows in the local-store
ingest path the codebase needs typed observations of the matching
domain shape (``WithholdingObservation`` for modelo 190 / 193,
``Modelo720RowObservation`` for modelo 720, etc.). Each assembler
looks up binding selectors in the :class:`ModeloRevision` supplied
through the snapshot argument.

The assemblers in this module bridge the two: they walk a row-set's
cells, group them by ``row_index``, look up each cell's binding in
the snapshot's revision to derive its ``row_field`` selector key,
and construct the matching observation type from the per-row field
mapping plus a small set of synthesized defaults (``source_id``,
``transaction_date``) that the Detalle layout doesn't carry.

Each assembler is self-contained per source kind so the per-modelo
field mapping is explicit at the call site rather than threaded
through a generic abstraction. Adding a new detail-record source
adds a new assembler here; nothing else in the calling code has
to change.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Protocol

from pydantic import ValidationError

from ...core.aggregation import RowSetGroupingKind
from ...core.decimal import coerce_decimal
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.parsing._dates import _parse_iso8601_date
from ...domain.calculations.registry import (
    AtributionMemberObservation,
    BindingAggregationOp,
    Modelo720RowObservation,
    ModeloRevision,
    RefundOperationObservation,
    RegistryValidationError,
    RelatedPartyOperationObservation,
    WithholdingObservation,
    binding_aggregation_op,
)

__all__ = [
    "AssembledObservations",
    "assemble_atribucion_observations",
    "assemble_foreign_asset_observations",
    "assemble_observations_for_grouping",
    "assemble_refund_observations",
    "assemble_related_party_observations",
    "assemble_withholding_observations",
]


# Mapping from a row-set's ``grouping`` selector value to the assembler
# that consumes its cells. The set of supported groupings is closed:
# any grouping not in this map signals a registry binding declared
# without a matching application-layer ingestor.
_GROUPING_DISPATCH: Mapping[str, RowSetGroupingKind] = {
    "per_perceptor": RowSetGroupingKind.WITHHOLDING,
    "per_perceptor_clave": RowSetGroupingKind.WITHHOLDING,
    "per_related_party_operation": RowSetGroupingKind.RELATED_PARTY,
    "per_foreign_asset": RowSetGroupingKind.FOREIGN_ASSET,
    "per_atribucion_member": RowSetGroupingKind.ATRIBUCION,
    "per_refund_operation": RowSetGroupingKind.REFUND,
}


# Tuple of typed observations dispatched by source-kind name. Returned
# by ``assemble_observations_for_grouping`` as a discriminated union
# the caller pattern-matches on. The string discriminator avoids
# pinning ``isinstance`` checks against five separate observation
# classes at every call site.
AssembledObservations = (
    tuple[str, tuple[WithholdingObservation, ...]]
    | tuple[str, tuple[RelatedPartyOperationObservation, ...]]
    | tuple[str, tuple[Modelo720RowObservation, ...]]
    | tuple[str, tuple[AtributionMemberObservation, ...]]
    | tuple[str, tuple[RefundOperationObservation, ...]]
)


def assemble_observations_for_grouping(
    grouping: str,
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> AssembledObservations:
    """Dispatch the right assembler based on the row-set's grouping value.

    Args:
        grouping: Row-set grouping token; selects which assembler runs
            (``withholding`` / ``related_party`` / ``foreign_asset`` /
            ``atribucion`` / ``refund``).
        cells: Per-row cell shapes consumed by the chosen assembler.
        revision: The :class:`ModeloRevision` used to look up binding selectors.
        filing_year: AEAT filing year carried through to the produced
            observations' provenance.

    Returns a 2-tuple ``(source_kind, observations)`` where
    ``source_kind`` identifies the assembler that ran (``withholding`` /
    ``related_party`` / ``foreign_asset`` / ``atribucion`` /
    ``refund``). Raises :class:`RegistryValidationError` for groupings
    that have no matching assembler — those are registry layout
    declarations the application layer cannot consume yet.
    """
    source_kind = _GROUPING_DISPATCH.get(grouping)
    if source_kind is None:
        raise RegistryValidationError(
            f"row-set grouping {grouping!r} has no application-layer assembler; "
            f"declared but unassemblable groupings are: "
            f"{sorted(set(_GROUPING_DISPATCH) ^ {grouping})}",
        )
    if source_kind == RowSetGroupingKind.WITHHOLDING:
        return (source_kind, assemble_withholding_observations(cells, revision, filing_year=filing_year))
    if source_kind == RowSetGroupingKind.RELATED_PARTY:
        return (source_kind, assemble_related_party_observations(cells, revision, filing_year=filing_year))
    if source_kind == RowSetGroupingKind.FOREIGN_ASSET:
        return (source_kind, assemble_foreign_asset_observations(cells, revision, filing_year=filing_year))
    if source_kind == RowSetGroupingKind.ATRIBUCION:
        return (source_kind, assemble_atribucion_observations(cells, revision, filing_year=filing_year))
    if source_kind == RowSetGroupingKind.REFUND:
        return (source_kind, assemble_refund_observations(cells, revision, filing_year=filing_year))
    # Unreachable: dispatch table is exhaustive.
    raise RegistryValidationError(f"row-set grouping {grouping!r} dispatch fell through")


class _RowCellShape(Protocol):
    """Structural protocol for the pull adapter's `RowSetCellEdit`.

    Kept here as a Protocol so the assembler module never imports the
    outbound adapter package — preserving the application→adapter
    direction of the hexagonal contract.

    Fields are declared as read-only properties so frozen-dataclass
    implementations (e.g. test doubles) satisfy the protocol without
    pyrefly flagging a read-only/read-write mismatch against the
    pydantic ``RowSetCellEdit`` model.
    """

    @property
    def binding(self) -> str: ...
    @property
    def row_index(self) -> int: ...
    @property
    def value(self) -> Decimal | str | None: ...


def _cells_by_row(cells: Iterable[_RowCellShape]) -> dict[int, dict[str, Decimal | str | None]]:
    """Group cell edits by row_index → {binding_id: value}.

    Accepts any object with ``binding`` / ``row_index`` / ``value``
    attributes (including the pull adapter's frozen ``RowSetCellEdit``).
    """
    grouped: dict[int, dict[str, Decimal | str | None]] = {}
    for cell in cells:
        binding = str(cell.binding)
        row_index_raw = cell.row_index
        if not isinstance(row_index_raw, int) or row_index_raw < 1:
            raise RegistryValidationError(f"row-set cell row_index must be a positive int, got {row_index_raw!r}")
        value = cell.value
        grouped.setdefault(row_index_raw, {})[binding] = value
    return grouped


def _row_field_lookup(revision: ModeloRevision) -> Mapping[str, str]:
    """Return ``binding_id → selector.row_field`` for every row-producer binding."""
    lookup: dict[str, str] = {}
    for binding in revision.bindings:
        if binding_aggregation_op(binding) != BindingAggregationOp.ROWS:
            continue
        row_field = binding.selector.get("row_field")
        if isinstance(row_field, str) and row_field:
            lookup[binding.id] = row_field
    return lookup


def _coerce_text(value: Decimal | str | None, *, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _coerce_iso_date(value: Decimal | str | None, *, default: date) -> date:
    if value is None or value == "":
        return default
    if isinstance(value, str):
        try:
            return _parse_iso8601_date(value) or default
        except ValueError:
            return default
    return default


def _optional_text_kwarg(
    fields: Mapping[str, Decimal | str],
    key: str,
) -> dict[str, str]:
    """Pass a text kwarg only when the row supplies a non-empty value.

    Forward the field to the typed observation only when the row
    carries it. The observation model's declared default (if any)
    handles truly-absent rows, and ``min_length`` invariants reject
    explicit empties from the wire. Callers must NOT supply hardcoded
    fallback strings like ``"ES"`` / ``"A"`` / ``"01"`` for
    AEAT-required fields — fabricating a legal value at the assembler
    boundary masks incomplete operator input.
    """
    raw = fields.get(key)
    if raw is None:
        return {}
    text = _coerce_text(raw)
    if not text:
        return {}
    return {key: text}


def assemble_withholding_observations(
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> tuple[WithholdingObservation, ...]:
    """Reassemble per-perceptor withholding observations from row-set cells.

    Args:
        cells: Row-set cells exported from the calc sheet.
        revision: The :class:`ModeloRevision` used to map binding ids to row fields.
        filing_year: Calendar year of the filing; used to derive default dates.

    Synthesised fields (not carried by the Detalle tab):
      * ``source_id`` -- derived from the row index for traceability.
      * ``transaction_date`` -- defaults to the filing-year end since
        modelo 190 / 193 are annual summaries.
      * ``country_code`` -- defaults to ``ES`` per the AEAT diseno de
        registro convention for unspecified perceptors.

    Each element in the returned tuple is a :class:`WithholdingObservation`.
    """
    by_row = _cells_by_row(cells)
    row_field = _row_field_lookup(revision)
    default_date = date(filing_year, 12, 31)

    observations: list[WithholdingObservation] = []
    for row_index in sorted(by_row):
        row = by_row[row_index]
        fields: dict[str, Decimal | str] = {}
        for binding_id, value in row.items():
            field = row_field.get(binding_id)
            if field is None:
                continue
            fields[field] = value if value is not None else ""

        # A percepción is keyed by its AEAT clave/subclave ("número de registros de
        # tipo 2" per perceptor + clave, Modelo 190/193 Diseño de Registros). Refuse
        # a row that carries no clave rather than silently defaulting it to "A": a
        # defaulted clave mis-buckets the percepción and corrupts the
        # distinct-(perceptor, clave) count. The source must supply the real clave.
        clave_value = _coerce_text(fields.get("clave"))
        if not clave_value:
            raise RegistryValidationError(
                f"row-set assembly: row {row_index} has no clave; a percepción must declare its "
                "AEAT clave (Modelo 190/193 Diseño de Registros, registro de tipo 2), not a default",
            )

        try:
            observations.append(
                WithholdingObservation(
                    source_id=f"detalle:per_perceptor_clave:row-{row_index}",
                    perceptor_tax_id=_coerce_text(fields.get("perceptor_tax_id")),
                    perceptor_legal_name=_coerce_text(fields.get("perceptor_legal_name")),
                    country_code=_coerce_text(fields.get("country_code"), default="ES") or "ES",
                    transaction_date=default_date,
                    clave=clave_value,
                    subclave=_coerce_text(fields.get("subclave")),
                    percibido_dinerario=coerce_decimal(fields.get("percibido_dinerario"), default=Decimal("0")),
                    percibido_especie=coerce_decimal(fields.get("percibido_especie"), default=Decimal("0")),
                    retencion_practicada=coerce_decimal(fields.get("retencion_practicada"), default=Decimal("0")),
                    ingreso_a_cuenta=coerce_decimal(fields.get("ingreso_a_cuenta"), default=Decimal("0")),
                ),
            )
        except ValidationError as exc:
            raise RegistryValidationError(f"row-set assembly failed for row {row_index}: {exc}") from exc
    return tuple(observations)


def assemble_related_party_observations(
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> tuple[RelatedPartyOperationObservation, ...]:
    """Reassemble per-operation related-party observations from row-set cells.

    Args:
        cells: Per-row cell shapes the assembler projects into typed
            observations.
        revision: The :class:`ModeloRevision` used to look up binding selectors.
        filing_year: AEAT filing year carried through to each observation's
            provenance.

    Returns a tuple of :class:`RelatedPartyOperationObservation` instances.
    """
    by_row = _cells_by_row(cells)
    row_field = _row_field_lookup(revision)
    default_date = date(filing_year, 12, 31)

    observations: list[RelatedPartyOperationObservation] = []
    for row_index in sorted(by_row):
        row = by_row[row_index]
        fields: dict[str, Decimal | str] = {}
        for binding_id, value in row.items():
            field = row_field.get(binding_id)
            if field is None:
                continue
            fields[field] = value if value is not None else ""
        try:
            observations.append(
                RelatedPartyOperationObservation(
                    source_id=f"detalle:per_related_party_operation:row-{row_index}",
                    counterparty_tax_id=_coerce_text(fields.get("counterparty_tax_id")),
                    counterparty_legal_name=_coerce_text(fields.get("counterparty_legal_name")),
                    country_code=_coerce_text(fields.get("country_code"), default="ES") or "ES",
                    transaction_date=default_date,
                    operation_kind_code=_coerce_text(fields.get("operation_kind_code"), default="01") or "01",
                    transfer_pricing_method_code=_coerce_text(fields.get("transfer_pricing_method_code")),
                    amount=coerce_decimal(fields.get("amount"), default=Decimal("0")),
                ),
            )
        except ValidationError as exc:
            raise RegistryValidationError(f"row-set assembly failed for row {row_index}: {exc}") from exc
    return tuple(observations)


def assemble_foreign_asset_observations(
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> tuple[Modelo720RowObservation, ...]:
    """Reassemble per-asset :class:`Modelo720RowObservation` rows from row-set cells (modelo 720).

    Args:
        cells: Row-set cells exported from the calc sheet.
        revision: The :class:`ModeloRevision` used to map binding ids to row fields.
        filing_year: Calendar year of the filing; used to derive default acquisition dates.
    """
    by_row = _cells_by_row(cells)
    row_field = _row_field_lookup(revision)
    default_acquisition_date = date(filing_year, 12, 31)

    observations: list[Modelo720RowObservation] = []
    for row_index in sorted(by_row):
        row = by_row[row_index]
        fields: dict[str, Decimal | str] = {}
        for binding_id, value in row.items():
            field = row_field.get(binding_id)
            if field is None:
                continue
            fields[field] = value if value is not None else ""
        try:
            observations.append(
                Modelo720RowObservation(
                    source_id=f"detalle:per_foreign_asset:row-{row_index}",
                    asset_class_code=_coerce_text(fields.get("asset_class_code"), default="C") or "C",
                    country_code=_coerce_text(fields.get("country_code"), default="ES") or "ES",
                    currency_code=_coerce_text(fields.get("currency_code"), default=DEFAULT_CURRENCY)
                    or DEFAULT_CURRENCY,
                    asset_identifier=_coerce_text(fields.get("asset_identifier")),
                    acquisition_date=_coerce_iso_date(fields.get("acquisition_date"), default=default_acquisition_date),
                    valuation_amount=coerce_decimal(fields.get("valuation_amount"), default=Decimal("0")),
                ),
            )
        except ValidationError as exc:
            raise RegistryValidationError(f"row-set assembly failed for row {row_index}: {exc}") from exc
    return tuple(observations)


def assemble_atribucion_observations(
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> tuple[AtributionMemberObservation, ...]:
    """Reassemble per-member atribución observations from row-set cells (modelo 184).

    Args:
        cells: Per-row cell shapes the assembler projects into typed
            member observations.
        revision: The :class:`ModeloRevision` used to look up binding selectors.
        filing_year: AEAT filing year carried through to each observation's
            provenance.

    Each element in the returned tuple is an :class:`AtributionMemberObservation`.
    """
    by_row = _cells_by_row(cells)
    row_field = _row_field_lookup(revision)
    default_date = date(filing_year, 12, 31)

    observations: list[AtributionMemberObservation] = []
    for row_index in sorted(by_row):
        row = by_row[row_index]
        fields: dict[str, Decimal | str] = {}
        for binding_id, value in row.items():
            field = row_field.get(binding_id)
            if field is None:
                continue
            fields[field] = value if value is not None else ""
        try:
            observations.append(
                AtributionMemberObservation(
                    source_id=f"detalle:per_atribucion_member:row-{row_index}",
                    member_tax_id=_coerce_text(fields.get("member_tax_id")),
                    member_legal_name=_coerce_text(fields.get("member_legal_name")),
                    country_code=_coerce_text(fields.get("country_code"), default="ES") or "ES",
                    transaction_date=default_date,
                    share_percentage=coerce_decimal(fields.get("share_percentage"), default=Decimal("0")),
                    base_imponible_assigned=coerce_decimal(fields.get("base_imponible_assigned"), default=Decimal("0")),
                ),
            )
        except ValidationError as exc:
            raise RegistryValidationError(f"row-set assembly failed for row {row_index}: {exc}") from exc
    return tuple(observations)


def assemble_refund_observations(
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> tuple[RefundOperationObservation, ...]:
    """Reassemble per-operation :class:`RefundOperationObservation` records from row-set cells (modelo 360).

    Args:
        cells: Row-set cells exported from the calc sheet.
        revision: The :class:`ModeloRevision` used to map binding ids to row fields.
        filing_year: Calendar year of the filing; used to derive default operation dates.
    """
    by_row = _cells_by_row(cells)
    row_field = _row_field_lookup(revision)
    default_operation_date = date(filing_year, 12, 31)

    observations: list[RefundOperationObservation] = []
    for row_index in sorted(by_row):
        row = by_row[row_index]
        fields: dict[str, Decimal | str] = {}
        for binding_id, value in row.items():
            field = row_field.get(binding_id)
            if field is None:
                continue
            fields[field] = value if value is not None else ""
        try:
            observations.append(
                RefundOperationObservation(
                    source_id=f"detalle:per_refund_operation:row-{row_index}",
                    **_optional_text_kwarg(fields, "member_state_code"),
                    **_optional_text_kwarg(fields, "operation_kind_code"),
                    operation_date=_coerce_iso_date(fields.get("operation_date"), default=default_operation_date),
                    supplier_tax_id=_coerce_text(fields.get("supplier_tax_id")),
                    refund_amount=coerce_decimal(fields.get("refund_amount"), default=Decimal("0")),
                ),
            )
        except ValidationError as exc:
            raise RegistryValidationError(f"row-set assembly failed for row {row_index}: {exc}") from exc
    return tuple(observations)
