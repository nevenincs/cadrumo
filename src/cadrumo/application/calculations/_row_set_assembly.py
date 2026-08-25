"""Reassemble pull-side row-set records into typed observations.

The pull adapter captures
:class:`~adapters.outbound.google._calc_sheets_pull.RowSetEdit` Detalle-tab
detail rows as a flat tuple of
:class:`~adapters.outbound.google._calc_sheets_pull.RowSetCellEdit`
records grouped by the row-set's grouping key. To consume those rows in the
local-store ingest path the codebase needs typed observations of the matching
domain shape (for example,
:class:`~domain.calculations.registry.WithholdingObservation` for modelo
190 / 193, or
:class:`~domain.calculations.registry.Modelo720RowObservation` for modelo
720). Each assembler looks up binding selectors in the
:class:`~domain.calculations.registry.ModeloRevision` supplied by the
caller.

The assemblers in this module bridge the two: they walk a row-set's
cells, group them by ``row_index``, look up each cell's binding in
the revision to derive its
:class:`~domain.calculations.registry.BindingRowSetSelector`
``row_field`` key, and construct the matching observation type from the
per-row field mapping plus a small set of synthesized defaults
(``source_id``, ``transaction_date``) that the Detalle layout doesn't carry.

Each assembler is self-contained per source kind so the per-modelo field mapping
is explicit at the call site rather than threaded through a generic abstraction.
The module only reassembles typed observations; persistence stays in the
source-specific repository helpers. Adding a new detail-record source adds a new
assembler here and a dispatch entry for its row-set grouping.

See Also:
    :func:`~domain.calculations.registry.binding_row_set_selector`
        Typed projection used to read row-set selector fields without probing raw
        selector dictionaries.
    :class:`~core.aggregation.RowSetGroupingKind`
        Closed grouping-axis values consumed by this module's dispatcher.
    :mod:`~domain.calculations.registry`
        Registry-side row-value resolvers that perform the inverse operation for
        export and sheet population.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, TypedDict

from pydantic import ValidationError

from cadrumo.core.aggregation import BindingAggregationOp
from cadrumo.domain.calculations.registry.binding_aggregation import binding_aggregation_op
from cadrumo.domain.calculations.registry.detail_record_bindings import (
    AtributionMemberObservation,
    Modelo720RowObservation,
    RefundOperationObservation,
    RelatedPartyOperationObservation,
)
from cadrumo.domain.calculations.registry.donativo_bindings import DonativoDonorObservation
from cadrumo.domain.calculations.registry.gasto193_bindings import Gasto193Observation
from cadrumo.domain.calculations.registry.withholding296_bindings import Withholding296Observation
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation

from ...core import M720AssetClassCode, MetodoValoracion, TipoOperacionVinculada
from ...core.aggregation import RetencionClave, RowSetGroupingKind
from ...core.decimal import coerce_decimal
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.parsing import parse_iso8601_date
from ...domain.calculations.registry.binding_selector_utils import binding_row_set_selector
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.schema import (
    ModeloRevision,
    RegistrySnapshot,
)

__all__ = [
    "AssembledObservations",
    "assemble_atribucion_observations",
    "assemble_donativo_observations",
    "assemble_foreign_asset_observations",
    "assemble_gasto193_observations",
    "assemble_observations_for_grouping",
    "assemble_observations_for_snapshot",
    "assemble_refund_observations",
    "assemble_related_party_observations",
    "assemble_withholding296_observations",
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
    "per_donativo_donor": RowSetGroupingKind.DONATIVO,
    "per_gasto193_contribuyente": RowSetGroupingKind.GASTO193,
    "per_perceptor_296": RowSetGroupingKind.WITHHOLDING296,
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
    | tuple[str, tuple[DonativoDonorObservation, ...]]
    | tuple[str, tuple[Gasto193Observation, ...]]
    | tuple[str, tuple[Withholding296Observation, ...]]
)


def assemble_observations_for_grouping(
    grouping: str,
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> AssembledObservations:
    """Dispatch the right assembler based on the row-set's grouping value.

    The dispatcher maps registry-authored grouping tokens onto the closed
    :class:`~core.aggregation.RowSetGroupingKind` axis, then returns an
    :data:`~application.calculations._row_set_assembly.AssembledObservations`
    payload whose source-kind discriminator names the typed observation family
    produced.

    Args:
        grouping: Row-set grouping token; selects which assembler runs
            (``withholding`` / ``related_party`` / ``foreign_asset`` /
            ``atribucion`` / ``refund`` / ``donativo``).
        cells: Per-row cell shapes consumed by the chosen assembler.
        revision: The
            :class:`~domain.calculations.registry.ModeloRevision` used to
            look up typed
            :class:`~domain.calculations.registry.BindingRowSetSelector`
            projections.
        filing_year: AEAT filing year carried through to the produced
            observations' provenance.

    Returns a 2-tuple ``(source_kind, observations)`` where
    ``source_kind`` identifies the assembler that ran (``withholding`` /
    ``related_party`` / ``foreign_asset`` / ``atribucion`` /
    ``refund`` / ``donativo``). Raises
    :class:`~domain.calculations.registry.RegistryValidationError` for groupings
    that have no matching assembler — those are registry layout
    declarations the application layer cannot consume yet.
    """
    source_kind = _GROUPING_DISPATCH.get(grouping)
    if source_kind is None:
        raise RegistryValidationError(
            translated_message="application.calculations.row_set.errors.grouping_has_no_assembler",
            context={
                "grouping": str(grouping),
                "unassemblable_groupings": sorted(str(item) for item in set(_GROUPING_DISPATCH) ^ {grouping}),
            },
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
    if source_kind == RowSetGroupingKind.DONATIVO:
        return (source_kind, assemble_donativo_observations(cells, revision, filing_year=filing_year))
    if source_kind == RowSetGroupingKind.GASTO193:
        return (source_kind, assemble_gasto193_observations(cells, revision, filing_year=filing_year))
    if source_kind == RowSetGroupingKind.WITHHOLDING296:
        return (source_kind, assemble_withholding296_observations(cells, revision, filing_year=filing_year))
    # Unreachable: dispatch table is exhaustive.
    raise RegistryValidationError(
        translated_message="application.calculations.row_set.errors.grouping_dispatch_fell_through",
        context={"grouping": str(grouping)},
    )


def assemble_observations_for_snapshot(
    grouping: str,
    cells: Iterable[_RowCellShape],
    snapshot: RegistrySnapshot,
) -> AssembledObservations:
    """Assemble one row set against the authoritative selected registry snapshot.

    This is the application command at the row-observation boundary.  It
    deliberately accepts a :class:`~domain.calculations.registry.RegistrySnapshot`
    rather than a caller-selected ``ModeloRevision`` so its assembly uses the
    same law-selected revision and filing year as calculation.  It delegates
    all grouping and row validation to the closed dispatcher.

    The returned typed observations are an input to a source-specific resolver
    or handoff.  This command does not infer source ownership, construct row
    identities or provenance, choose a row-to-casilla materialisation, or write
    a calculation revision; those facts remain owned by the applicable source
    slice and the existing calculation source mesh.

    Args:
        grouping: Registry-authored row-set grouping token.
        cells: Cells captured by an inbound surface or another application
            caller.  The command does not claim that any particular adapter is
            a calculation ingress.
        snapshot: The validated registry snapshot selected for the work
            context.

    Returns:
        The closed typed observation union produced by the grouping dispatcher.

    Raises:
        RegistryValidationError: If the grouping is not assembled by the
            application or any supplied row is invalid.
    """
    return assemble_observations_for_grouping(
        grouping,
        cells,
        snapshot.revision,
        filing_year=snapshot.filing_year,
    )


class _RowCellShape(Protocol):
    """Structural protocol for pull-side row-set cells.

    This mirrors the pull adapter's
    :class:`~adapters.outbound.google._calc_sheets_pull.RowSetCellEdit`
    shape without importing the adapter module.

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


def _row_assembly_refusal(row_index: int, exc: Exception) -> RegistryValidationError:
    """Return the one refusal every per-row assembler raises when a row will not validate.

    The validator's own diagnostic rides in machine facts rather than in the
    refusal sentence, so the operator-facing text resolves from the registered
    key in the operator's locale while the field-level detail stays available to
    whoever triages the row.
    """
    return RegistryValidationError(
        translated_message="application.calculations.row_set.errors.row_assembly_failed",
        context={
            "row_index": row_index,
            "validation_error_type": type(exc).__name__,
            "validation_error_detail": str(exc),
        },
    )


def _cells_by_row(cells: Iterable[_RowCellShape]) -> dict[int, dict[str, Decimal | str | None]]:
    """Group cell edits by row_index → {binding_id: value}.

    Accepts any object with ``binding`` / ``row_index`` / ``value``
    attributes (including the pull adapter's frozen ``RowSetCellEdit``).
    """
    grouped: dict[int, dict[str, Decimal | str | None]] = {}
    for cell in cells:
        binding = str(cell.binding)
        row_index_raw = cell.row_index
        if row_index_raw < 1:
            raise RegistryValidationError(
                translated_message="application.calculations.row_set.errors.row_index_not_positive",
                context={"row_index": row_index_raw},
            )
        value = cell.value
        grouped.setdefault(row_index_raw, {})[binding] = value
    return grouped


def _row_field_lookup(revision: ModeloRevision) -> Mapping[str, str]:
    """Return ``binding_id → selector.row_field`` for every row-producer binding.

    Uses
    :func:`~domain.calculations.registry.binding_row_set_selector`
    rather than raw selector access, preserving the typed
    :class:`~domain.calculations.registry.BindingRowSetSelector` contract
    closed by the registry selector validation gates.
    """
    lookup: dict[str, str] = {}
    for binding in revision.bindings:
        if binding_aggregation_op(binding) != BindingAggregationOp.ROWS:
            continue
        selector = binding_row_set_selector(binding)
        if selector is None:
            continue
        lookup[str(binding.id)] = selector.row_field
    return lookup


def _coerce_text(value: Decimal | str | None, *, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _coerce_optional_int(value: Decimal | str | None) -> int | None:
    """Read an optional whole-number cell, treating blank as ABSENT, not zero.

    The distinction is load-bearing across this whole family. Modelo 190's
    design campo 15 declares AÑO DE NACIMIENTO for claves A, B.01 and C, and
    the withholding validator refuses such a row when no observation carries
    it; a blank coerced to 0 would clear that refusal while telling AEAT the
    perceptor was born in year zero. The same holds for the personal and family
    circumstance counts: "no descendants declared" and "zero descendants
    declared" are different statements, and only the second is a declaration.
    """
    if value is None or value == "":
        return None
    text = _coerce_text(value).strip()
    if not text:
        return None
    try:
        return int(Decimal(text))
    except (ArithmeticError, ValueError):
        return None


def _coerce_iso_date(value: Decimal | str | None, *, default: date) -> date:
    if value is None or value == "":
        return default
    if isinstance(value, str):
        try:
            return parse_iso8601_date(value) or default
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
    # Stripped: the resolver's no-content for space-filled design slots is a
    # run of spaces, which must read back as absent rather than as a value.
    text = _coerce_text(raw).strip()
    if not text:
        return {}
    return {key: text}


def _row_optional_int(fields: Mapping[str, Decimal | str], key: str) -> int | None:
    """Read an optional integer-clave fact without truncating fractional cells."""
    raw = fields.get(key)
    if raw is None:
        return None
    text = format(raw, "f") if isinstance(raw, Decimal) else str(raw).strip()
    if not text:
        return None
    return int(text)


class _OperationKindCodeKwarg(TypedDict, total=False):
    operation_kind_code: TipoOperacionVinculada


class _TransferPricingMethodCodeKwarg(TypedDict, total=False):
    transfer_pricing_method_code: MetodoValoracion


def _hydrate_coded_field[EnumT: StrEnum](*, field_name: str, text: str, code_set: type[EnumT]) -> EnumT:
    """Widen a raw registry token into its typed DR23200-style code, or raise.

    Mirrors the case-folding the observation model's own ``BeforeValidator``
    applies, so a token outside the accepted set raises the identical
    accepted-set message the model would have raised from inside its own
    validator.
    """
    try:
        return code_set(text.upper())
    except ValueError:
        accepted = ", ".join(repr(str(member)) for member in code_set)
        raise ValueError(f"{field_name} must be one of {accepted}; got {text!r}") from None


def _optional_operation_kind_code_kwarg(fields: Mapping[str, Decimal | str]) -> _OperationKindCodeKwarg:
    """Pass ``operation_kind_code`` only when the row supplies a non-empty value.

    The coded counterpart of :func:`_optional_text_kwarg`: the target field is
    typed as the closed ``TipoOperacionVinculada`` enum rather than plain
    text, so it cannot be forwarded as a bare ``str``.
    """
    raw = fields.get("operation_kind_code")
    if raw is None:
        return {}
    text = _coerce_text(raw)
    if not text:
        return {}
    return {
        "operation_kind_code": _hydrate_coded_field(
            field_name="operation_kind_code",
            text=text,
            code_set=TipoOperacionVinculada,
        ),
    }


def _optional_transfer_pricing_method_code_kwarg(
    fields: Mapping[str, Decimal | str],
) -> _TransferPricingMethodCodeKwarg:
    """Pass ``transfer_pricing_method_code`` only when the row supplies a non-empty value.

    The coded counterpart of :func:`_optional_text_kwarg`: the target field is
    typed as the closed ``MetodoValoracion`` enum rather than plain text, so
    it cannot be forwarded as a bare ``str``.
    """
    raw = fields.get("transfer_pricing_method_code")
    if raw is None:
        return {}
    text = _coerce_text(raw)
    if not text:
        return {}
    return {
        "transfer_pricing_method_code": _hydrate_coded_field(
            field_name="transfer_pricing_method_code",
            text=text,
            code_set=MetodoValoracion,
        ),
    }


def _coerce_flag(value: Decimal | str | None) -> bool:
    """Parse a row-set boolean-flag cell (``"1"``/``"0"``) into a real bool.

    Mirrors the ``"1"`` / ``"0"`` string convention
    :func:`~domain.calculations.registry._donativo_bindings._build_donativo_rows`
    writes for the ``is_recurrent`` field on the resolve-time (registry ->
    Sheets) side of the same detail-record family, so the pull-side reassembly
    round-trips the same wire shape.
    """
    if value is None:
        return False
    if isinstance(value, Decimal):
        return value != Decimal("0")
    return value.strip() == "1"


def assemble_withholding_observations(
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> tuple[WithholdingObservation, ...]:
    """Reassemble per-perceptor withholding observations from row-set cells.

    Args:
        cells: Row-set cells exported from the calc sheet.
        revision: The
            :class:`~domain.calculations.registry.ModeloRevision` used to
            map binding ids to row fields.
        filing_year: Calendar year of the filing; used to derive default dates.

    Synthesised fields (not carried by the Detalle tab):
      * ``source_id`` -- derived from the row index for traceability.
      * ``transaction_date`` -- defaults to the filing-year end since
        modelo 190 / 193 are annual summaries.
      * ``country_code`` -- defaults to ``ES`` per the AEAT diseno de
        registro convention for unspecified perceptors.
      * ``clave`` is NOT synthesised. A missing clave raises
        :class:`~domain.calculations.registry.RegistryValidationError`
        because the Modelo 190/193 distinct percepciones count is keyed by
        perceptor plus clave/subclave; supplied values are validated against
        :class:`~core.aggregation.RetencionClave`.

    Each element in the returned tuple is a
    :class:`~domain.calculations.registry.WithholdingObservation`.
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
                translated_message="application.calculations.row_set.errors.percepcion_clave_missing",
                context={"row_index": row_index},
            )
        try:
            clave = RetencionClave(clave_value)
        except ValueError as exc:
            raise RegistryValidationError(
                translated_message="application.calculations.row_set.errors.percepcion_clave_unsupported",
                context={"row_index": row_index, "clave": clave_value},
            ) from exc

        try:
            observations.append(
                WithholdingObservation(
                    source_id=f"detalle:per_perceptor_clave:row-{row_index}",
                    perceptor_tax_id=_coerce_text(fields.get("perceptor_tax_id")),
                    perceptor_legal_name=_coerce_text(fields.get("perceptor_legal_name")),
                    # Blank is ABSENT, not an empty country. The coercer returns the
                    # value itself for an empty string, so without this a blank field
                    # reaches the model as "" -- which is neither a country nor the
                    # honest "not stated" this row exists to make representable.
                    transaction_date=default_date,
                    clave=clave,
                    subclave=_coerce_text(fields.get("subclave")),
                    perceptor_birth_year=_coerce_optional_int(fields.get("perceptor_birth_year")),
                    perceptor_situacion_familiar=_coerce_optional_int(fields.get("perceptor_situacion_familiar")),
                    province_code=_coerce_text(fields.get("province_code")) or None,
                    territorial_deduction_clave=_coerce_optional_int(fields.get("territorial_deduction_clave")),
                    percibido_dinerario=coerce_decimal(fields.get("percibido_dinerario"), default=Decimal("0")),
                    percibido_especie=coerce_decimal(fields.get("percibido_especie"), default=Decimal("0")),
                    retencion_practicada=coerce_decimal(fields.get("retencion_practicada"), default=Decimal("0")),
                    ingreso_a_cuenta=coerce_decimal(fields.get("ingreso_a_cuenta"), default=Decimal("0")),
                    ingreso_a_cuenta_repercutido=coerce_decimal(
                        fields.get("ingreso_a_cuenta_repercutido"), default=Decimal("0")
                    ),
                    reducciones_aplicables=coerce_decimal(fields.get("reducciones_aplicables"), default=Decimal("0")),
                    gastos_deducibles=coerce_decimal(fields.get("gastos_deducibles"), default=Decimal("0")),
                    pension_compensatoria=coerce_decimal(fields.get("pension_compensatoria"), default=Decimal("0")),
                    anualidades_alimentos=coerce_decimal(fields.get("anualidades_alimentos"), default=Decimal("0")),
                    incapacity_cash_perception=coerce_decimal(
                        fields.get("incapacity_cash_perception"), default=Decimal("0")
                    ),
                    incapacity_cash_withholding=coerce_decimal(
                        fields.get("incapacity_cash_withholding"), default=Decimal("0")
                    ),
                    incapacity_kind_value=coerce_decimal(fields.get("incapacity_kind_value"), default=Decimal("0")),
                    incapacity_kind_ingreso_a_cuenta=coerce_decimal(
                        fields.get("incapacity_kind_ingreso_a_cuenta"), default=Decimal("0")
                    ),
                    incapacity_kind_repercutido=coerce_decimal(
                        fields.get("incapacity_kind_repercutido"), default=Decimal("0")
                    ),
                    foral_retention_estatal=coerce_decimal(fields.get("foral_retention_estatal"), default=Decimal("0")),
                    foral_retention_navarra=coerce_decimal(fields.get("foral_retention_navarra"), default=Decimal("0")),
                    foral_retention_araba=coerce_decimal(fields.get("foral_retention_araba"), default=Decimal("0")),
                    foral_retention_gipuzkoa=coerce_decimal(
                        fields.get("foral_retention_gipuzkoa"), default=Decimal("0")
                    ),
                    foral_retention_bizkaia=coerce_decimal(fields.get("foral_retention_bizkaia"), default=Decimal("0")),
                    # The design's optional identity facts: forwarded verbatim
                    # when the row carries them, left to the observation model's
                    # None defaults otherwise -- the resolver applies the design's
                    # per-clave completion rules at resolve time.
                    representative_tax_id=_coerce_text(fields.get("representative_tax_id")).strip() or None,
                    spouse_or_unit_titular_tax_id=_coerce_text(fields.get("spouse_or_unit_titular_tax_id")).strip()
                    or None,
                    disability_clave=_row_optional_int(fields, "disability_clave"),
                    contract_relation_clave=_row_optional_int(fields, "contract_relation_clave"),
                    unit_convivencia_titular_clave=_row_optional_int(fields, "unit_convivencia_titular_clave"),
                    geographic_mobility_clave=_row_optional_int(fields, "geographic_mobility_clave"),
                    accrual_year=_row_optional_int(fields, "accrual_year"),
                    descendants_under_3_total=_row_optional_int(fields, "descendants_under_3_total"),
                    descendants_under_3_whole=_row_optional_int(fields, "descendants_under_3_whole"),
                    descendants_rest_total=_row_optional_int(fields, "descendants_rest_total"),
                    descendants_rest_whole=_row_optional_int(fields, "descendants_rest_whole"),
                    descendants_disabled_33_65_total=_row_optional_int(fields, "descendants_disabled_33_65_total"),
                    descendants_disabled_33_65_whole=_row_optional_int(fields, "descendants_disabled_33_65_whole"),
                    descendants_disabled_mobility_total=_row_optional_int(
                        fields, "descendants_disabled_mobility_total"
                    ),
                    descendants_disabled_mobility_whole=_row_optional_int(
                        fields, "descendants_disabled_mobility_whole"
                    ),
                    descendants_disabled_65_plus_total=_row_optional_int(fields, "descendants_disabled_65_plus_total"),
                    descendants_disabled_65_plus_whole=_row_optional_int(fields, "descendants_disabled_65_plus_whole"),
                    ascendants_under_75_total=_row_optional_int(fields, "ascendants_under_75_total"),
                    ascendants_under_75_whole=_row_optional_int(fields, "ascendants_under_75_whole"),
                    ascendants_75_plus_total=_row_optional_int(fields, "ascendants_75_plus_total"),
                    ascendants_75_plus_whole=_row_optional_int(fields, "ascendants_75_plus_whole"),
                    ascendants_disabled_33_65_total=_row_optional_int(fields, "ascendants_disabled_33_65_total"),
                    ascendants_disabled_33_65_whole=_row_optional_int(fields, "ascendants_disabled_33_65_whole"),
                    ascendants_disabled_mobility_total=_row_optional_int(fields, "ascendants_disabled_mobility_total"),
                    ascendants_disabled_mobility_whole=_row_optional_int(fields, "ascendants_disabled_mobility_whole"),
                    ascendants_disabled_65_plus_total=_row_optional_int(fields, "ascendants_disabled_65_plus_total"),
                    ascendants_disabled_65_plus_whole=_row_optional_int(fields, "ascendants_disabled_65_plus_whole"),
                    first_child_compute=_row_optional_int(fields, "first_child_compute"),
                    second_child_compute=_row_optional_int(fields, "second_child_compute"),
                    third_child_compute=_row_optional_int(fields, "third_child_compute"),
                    housing_loan_communication_clave=_row_optional_int(fields, "housing_loan_communication_clave"),
                    complemento_infancia_clave=_row_optional_int(fields, "complemento_infancia_clave"),
                    emerging_stock_excess_clave=_row_optional_int(fields, "emerging_stock_excess_clave"),
                    startup_fund_rendimientos_clave=_row_optional_int(fields, "startup_fund_rendimientos_clave"),
                    pension_prestacion_jubilacion=_row_optional_int(fields, "pension_prestacion_jubilacion"),
                    pension_prestacion_viudedad=_row_optional_int(fields, "pension_prestacion_viudedad"),
                    pension_prestacion_incapacidad=_row_optional_int(fields, "pension_prestacion_incapacidad"),
                    pension_prestacion_no_contributiva=_row_optional_int(fields, "pension_prestacion_no_contributiva"),
                    pension_prestacion_resto=_row_optional_int(fields, "pension_prestacion_resto"),
                ),
            )
        except (ValidationError, ValueError) as exc:
            raise _row_assembly_refusal(row_index, exc) from exc
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
        revision: The
            :class:`~domain.calculations.registry.ModeloRevision` used to
            look up typed row-set selector projections.
        filing_year: AEAT filing year carried through to each observation's
            provenance.

    Returns a tuple of
    :class:`~domain.calculations.registry.RelatedPartyOperationObservation`
    instances.
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
                    # No invented default: "01" is a real clave (bienes
                    # tangibles), so substituting it for an absent value
                    # would declare an operation kind the row never carried.
                    # The coded-kwarg helpers (rather than the plain-text one)
                    # because the field is the typed
                    # TipoOperacionVinculada/MetodoValoracion enum, not text.
                    # Spread before the generic ``dict[str, str]`` kwargs below:
                    # a type checker that cannot see a plain dict's key set
                    # must assume it might supply any parameter, so ordering
                    # the precisely-keyed ``TypedDict`` spreads first lets it
                    # narrow the remaining parameter set before that.
                    **_optional_operation_kind_code_kwarg(fields),
                    **_optional_transfer_pricing_method_code_kwarg(fields),
                    # No invented default: modelo 232 declares paraíso-fiscal
                    # operations, so substituting Spain for an absent country
                    # marks a tax-haven counterparty as domestic on the exact
                    # axis the declaration exists to surface.
                    **_optional_text_kwarg(fields, "country_code"),
                    transaction_date=default_date,
                    amount=coerce_decimal(fields.get("amount"), default=Decimal("0")),
                ),
            )
        except (ValidationError, ValueError) as exc:
            raise _row_assembly_refusal(row_index, exc) from exc
    return tuple(observations)


def assemble_foreign_asset_observations(
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> tuple[Modelo720RowObservation, ...]:
    """Reassemble per-asset Modelo 720 rows from row-set cells.

    Args:
        cells: Row-set cells exported from the calc sheet.
        revision: The
            :class:`~domain.calculations.registry.ModeloRevision` used to
            map binding ids to row fields.
        filing_year: Calendar year of the filing; used to derive default
            acquisition dates.

    Each element in the returned tuple is a
    :class:`~domain.calculations.registry.Modelo720RowObservation`.
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
                    asset_class_code=_hydrate_coded_field(
                        field_name="asset_class_code",
                        text=_coerce_text(fields.get("asset_class_code"), default="C") or "C",
                        code_set=M720AssetClassCode,
                    ),
                    # No invented default, and Spain least of all: modelo 720
                    # declares bienes y derechos situados en el EXTRANJERO, so
                    # ES is not merely unstated here but the one value the
                    # declaration cannot carry. The observation model already
                    # requires the field; this fallback was the sole reason
                    # that requirement never reached a row.
                    **_optional_text_kwarg(fields, "country_code"),
                    currency_code=_coerce_text(fields.get("currency_code"), default=DEFAULT_CURRENCY)
                    or DEFAULT_CURRENCY,
                    asset_identifier=_coerce_text(fields.get("asset_identifier")),
                    acquisition_date=_coerce_iso_date(fields.get("acquisition_date"), default=default_acquisition_date),
                    valuation_amount=coerce_decimal(fields.get("valuation_amount"), default=Decimal("0")),
                ),
            )
        except ValidationError as exc:
            raise _row_assembly_refusal(row_index, exc) from exc
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
        revision: The
            :class:`~domain.calculations.registry.ModeloRevision` used to
            look up typed row-set selector projections.
        filing_year: AEAT filing year carried through to each observation's
            provenance.

    Each element in the returned tuple is an
    :class:`~domain.calculations.registry.AtributionMemberObservation`.
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
                    # Blank is ABSENT, not an empty country. The coercer returns the
                    # value itself for an empty string, so without this a blank field
                    # reaches the model as "" -- which is neither a country nor the
                    # honest "not stated" this row exists to make representable.
                    transaction_date=default_date,
                    share_percentage=coerce_decimal(fields.get("share_percentage"), default=Decimal("0")),
                    base_imponible_assigned=coerce_decimal(fields.get("base_imponible_assigned"), default=Decimal("0")),
                ),
            )
        except ValidationError as exc:
            raise _row_assembly_refusal(row_index, exc) from exc
    return tuple(observations)


def assemble_refund_observations(
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> tuple[RefundOperationObservation, ...]:
    """Reassemble Modelo 360 refund-operation records from row-set cells.

    Args:
        cells: Row-set cells exported from the calc sheet.
        revision: The
            :class:`~domain.calculations.registry.ModeloRevision` used to
            map binding ids to row fields.
        filing_year: Calendar year of the filing; used to derive default
            operation dates.

    Each element in the returned tuple is a
    :class:`~domain.calculations.registry.RefundOperationObservation`.
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
            raise _row_assembly_refusal(row_index, exc) from exc
    return tuple(observations)


def assemble_withholding296_observations(
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> tuple[Withholding296Observation, ...]:
    """Reassemble Modelo 296 perceptor rows from row-set cells.

    Args:
        cells: Row-set cells exported from the calc sheet.
        revision: The
            :class:`~domain.calculations.registry.ModeloRevision` used to
            map binding ids to row fields.
        filing_year: Calendar year of the filing; used to derive default dates.
    """
    by_row = _cells_by_row(cells)
    row_field = _row_field_lookup(revision)
    default_date = date(filing_year, 12, 31)

    observations: list[Withholding296Observation] = []
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
                Withholding296Observation(
                    source_id=f"detalle:per_perceptor_296:row-{row_index}",
                    perceptor_tax_id=_coerce_text(fields.get("perceptor_tax_id")),
                    perceptor_legal_name=_coerce_text(fields.get("perceptor_legal_name")),
                    representative_tax_id=_coerce_text(fields.get("representative_tax_id")).strip() or None,
                    persona_juridica_flag=_coerce_text(fields.get("persona_juridica_flag")).strip() or None,
                    codigo_bic=_coerce_text(fields.get("codigo_bic")).strip() or None,
                    fecha_devengo=_coerce_text(fields.get("fecha_devengo")).strip() or None,
                    naturaleza=_coerce_text(fields.get("naturaleza"), default="D") or "D",
                    clave=_coerce_text(fields.get("clave"), default="01") or "01",
                    subclave=_coerce_text(fields.get("subclave")),
                    perceptor_mediador_flag=_coerce_text(fields.get("perceptor_mediador_flag")).strip() or None,
                    codigo=_coerce_text(fields.get("codigo")).strip() or None,
                    codigo_emisor=_coerce_text(fields.get("codigo_emisor")).strip() or None,
                    pago=_row_optional_int(fields, "pago"),
                    tipo_codigo=_coerce_text(fields.get("tipo_codigo")).strip() or None,
                    codigo_cuenta=_coerce_text(fields.get("codigo_cuenta")).strip() or None,
                    pendiente_flag=_coerce_text(fields.get("pendiente_flag")).strip() or None,
                    accrual_year=_row_optional_int(fields, "accrual_year"),
                    fecha_inicio_prestamo=_coerce_text(fields.get("fecha_inicio_prestamo")).strip() or None,
                    fecha_vencimiento_prestamo=_coerce_text(fields.get("fecha_vencimiento_prestamo")).strip() or None,
                    direccion_perceptor=_coerce_text(fields.get("direccion_perceptor")).strip() or None,
                    nif_pagador_anterior=_coerce_text(fields.get("nif_pagador_anterior")).strip() or None,
                    procedimiento_especial_flag=_coerce_text(fields.get("procedimiento_especial_flag")).strip() or None,
                    clave_mercado=_coerce_text(fields.get("clave_mercado")).strip() or None,
                    codigo_lei=_coerce_text(fields.get("codigo_lei")).strip() or None,
                    nif_pais_residencia=_coerce_text(fields.get("nif_pais_residencia")).strip() or None,
                    fecha_nacimiento=_coerce_text(fields.get("fecha_nacimiento")).strip() or None,
                    ciudad_nacimiento=_coerce_text(fields.get("ciudad_nacimiento")).strip() or None,
                    codigo_pais=_coerce_text(fields.get("codigo_pais")).strip() or None,
                    pais_residencia_fiscal=_coerce_text(fields.get("pais_residencia_fiscal")).strip() or None,
                    transaction_date=default_date,
                    base_retenciones=coerce_decimal(fields.get("base_retenciones"), default=Decimal("0")),
                    porcentaje_retencion=coerce_decimal(fields.get("porcentaje_retencion"), default=Decimal("0")),
                    retencion_practicada=coerce_decimal(fields.get("retencion_practicada"), default=Decimal("0")),
                    compensaciones=coerce_decimal(fields.get("compensaciones"), default=Decimal("0")),
                    garantias=coerce_decimal(fields.get("garantias"), default=Decimal("0")),
                    otros_importes=coerce_decimal(fields.get("otros_importes"), default=Decimal("0")),
                    ingreso_a_cuenta_repercutido=coerce_decimal(
                        fields.get("ingreso_a_cuenta_repercutido"), default=Decimal("0")
                    ),
                ),
            )
        except (ValidationError, ValueError) as exc:
            raise _row_assembly_refusal(row_index, exc) from exc
    return tuple(observations)


def assemble_gasto193_observations(
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> tuple[Gasto193Observation, ...]:
    """Reassemble Modelo 193 gastos-relationship rows from row-set cells.

    Args:
        cells: Row-set cells exported from the calc sheet.
        revision: The
            :class:`~domain.calculations.registry.ModeloRevision` used to
            map binding ids to row fields.
        filing_year: Calendar year of the filing; used to derive default dates.

    Synthesised fields (not carried by the Detalle tab):
      * ``source_id`` -- derived from the row index for traceability.
      * ``transaction_date`` -- defaults to the filing-year end since
        modelo 193 is an annual summary.
    """
    by_row = _cells_by_row(cells)
    row_field = _row_field_lookup(revision)
    default_date = date(filing_year, 12, 31)

    observations: list[Gasto193Observation] = []
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
                Gasto193Observation(
                    source_id=f"detalle:per_gasto193_contribuyente:row-{row_index}",
                    contributor_tax_id=_coerce_text(fields.get("contributor_tax_id")),
                    contributor_legal_name=_coerce_text(fields.get("contributor_legal_name")),
                    # The representative NIF is declared by the design only for
                    # minor contribuyentes; spaces read back as absent.
                    **_optional_text_kwarg(fields, "representative_tax_id"),
                    transaction_date=default_date,
                    importe_gastos=coerce_decimal(fields.get("importe_gastos"), default=Decimal("0")),
                ),
            )
        except (ValidationError, ValueError) as exc:
            raise _row_assembly_refusal(row_index, exc) from exc
    return tuple(observations)


def assemble_donativo_observations(
    cells: Iterable[_RowCellShape],
    revision: ModeloRevision,
    *,
    filing_year: int,
) -> tuple[DonativoDonorObservation, ...]:
    """Reassemble Modelo 182 per-donor donativo records from row-set cells.

    Args:
        cells: Row-set cells exported from the calc sheet.
        revision: The
            :class:`~domain.calculations.registry.ModeloRevision` used to
            map binding ids to row fields.
        filing_year: Calendar year of the filing; used to derive the default
            transaction date.

    Each element in the returned tuple is a
    :class:`~domain.calculations.registry.DonativoDonorObservation`.
    """
    by_row = _cells_by_row(cells)
    row_field = _row_field_lookup(revision)
    default_date = date(filing_year, 12, 31)

    observations: list[DonativoDonorObservation] = []
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
                DonativoDonorObservation(
                    source_id=f"detalle:per_donativo_donor:row-{row_index}",
                    donor_tax_id=_coerce_text(fields.get("donor_tax_id")),
                    donor_legal_name=_coerce_text(fields.get("donor_legal_name")),
                    transaction_date=default_date,
                    amount_donated=coerce_decimal(fields.get("amount_donated"), default=Decimal("0")),
                    deduction_percentage=coerce_decimal(fields.get("deduction_percentage"), default=Decimal("0")),
                    is_recurrent=_coerce_flag(fields.get("is_recurrent")),
                ),
            )
        except ValidationError as exc:
            raise _row_assembly_refusal(row_index, exc) from exc
    return tuple(observations)
