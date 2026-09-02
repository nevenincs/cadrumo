"""Private row materialisation for invoice-shaped registry bindings."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from ....core.identity import TaxIdIdentityToken
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period
from .errors import RegistryValidationError
from .ids import BindingId
from .schema import ModeloRevision

if TYPE_CHECKING:
    from .invoice_bindings import InvoiceObservation

_InvoiceGrouping = Literal["operator_clave", "operator_clave_period", "contraparte_clave"]

_M349_EXPORT_NIF_COUNTRY_BINDINGS: dict[BindingId, BindingId] = {
    "iva-349-operador-row-nif": "iva-349-operador-row-codigo-pais",
    "iva-349-rectificacion-row-nif": "iva-349-rectificacion-row-codigo-pais",
    "iva-349-operador-row-nif-adquisicion": "iva-349-operador-row-codigo-pais-adquisicion",
    "iva-349-rectificacion-row-nif-adquisicion": "iva-349-rectificacion-row-codigo-pais-adquisicion",
}
_M349_PAYABLE_ROW_BINDING_MIRRORS: dict[BindingId, BindingId] = {
    "iva-349-operador-row-codigo-pais-adquisicion": "iva-349-operador-row-codigo-pais",
    "iva-349-operador-row-nif-adquisicion": "iva-349-operador-row-nif",
    "iva-349-operador-row-apellidos-adquisicion": "iva-349-operador-row-apellidos",
    "iva-349-operador-row-clave-adquisicion": "iva-349-operador-row-clave",
    "iva-349-operador-row-base-adquisicion": "iva-349-operador-row-base",
    "iva-349-rectificacion-row-codigo-pais-adquisicion": "iva-349-rectificacion-row-codigo-pais",
    "iva-349-rectificacion-row-nif-adquisicion": "iva-349-rectificacion-row-nif",
    "iva-349-rectificacion-row-apellidos-adquisicion": "iva-349-rectificacion-row-apellidos",
    "iva-349-rectificacion-row-clave-adquisicion": "iva-349-rectificacion-row-clave",
    "iva-349-rectificacion-row-ejercicio-adquisicion": "iva-349-rectificacion-row-ejercicio",
    "iva-349-rectificacion-row-periodo-adquisicion": "iva-349-rectificacion-row-periodo",
    "iva-349-rectificacion-row-base-rectificada-adquisicion": "iva-349-rectificacion-row-base-rectificada",
    "iva-349-rectificacion-row-base-anterior-adquisicion": "iva-349-rectificacion-row-base-anterior",
}
_M349_OPERADOR_PUBLIC_ROW_BINDINGS: frozenset[BindingId] = frozenset(
    {
        "iva-349-operador-row-codigo-pais",
        "iva-349-operador-row-nif",
        "iva-349-operador-row-apellidos",
        "iva-349-operador-row-clave",
        "iva-349-operador-row-base",
    },
)
_M349_RECTIFICACION_PUBLIC_ROW_BINDINGS: frozenset[BindingId] = frozenset(
    {
        "iva-349-rectificacion-row-codigo-pais",
        "iva-349-rectificacion-row-nif",
        "iva-349-rectificacion-row-apellidos",
        "iva-349-rectificacion-row-clave",
        "iva-349-rectificacion-row-ejercicio",
        "iva-349-rectificacion-row-periodo",
        "iva-349-rectificacion-row-base-rectificada",
        "iva-349-rectificacion-row-base-anterior",
    },
)


class Modelo349OperadorClaveTotal(BaseModel):
    """One clave's operator count and base-imponible sum, reconstructed from the operador row set.

    Groups the per-operador ``iva-349-operador-row-*`` detail (the AEAT Diseño
    de Registros Tipo-2 "registro de operador" rows) by ``clave de operación``
    and carries that clave's distinct-operator count and summed base
    imponible. Mirrors :class:`WithholdingClaveBreakdown` for the Modelo 349
    intracommunity-operator axis.
    """

    model_config = STRICT_FROZEN_CONFIG

    clave: str = Field(min_length=1, max_length=1)
    operator_count: NonNegativeInt
    base_total: Decimal


class Modelo349OperadorTotalsParity(BaseModel):
    """Totals-parity verdict between the per-operador row set and the Modelo 349 declarant summary.

    Modelo 349's declarant-summary scalar casillas (``decl.numero-operadores``,
    ``decl.importe-operaciones``) and the per-operador-clave row-producer
    bindings (``iva-349-operador-row-*``) are resolved by two structurally
    INDEPENDENT code paths over the same :class:`InvoiceObservation` set:
    :func:`resolve_invoice_binding_values` folds the observations directly
    into a scalar (:func:`_aggregate_invoice_binding`'s ``operator_count`` /
    ``base_sum`` facts), while :func:`resolve_invoice_binding_row_values`
    groups them into per-``(country, party_tax_id, clave)`` rows
    (:func:`_build_operator_clave_rows`). Nothing in the registry
    cross-checks that the two paths agree, so a defect in either aggregator —
    or a manual-entry :class:`~Modelo349OperadorRow` set
    that omits an operator the summary already counted — would silently
    under- or over-declare one side without detection.

    This model is the pure comparison result of that cross-check: the sum of
    every reconstructed operador row's base imponible against the resolved
    ``decl.importe-operaciones`` value, and the count of distinct
    ``(country_code, party_tax_id, clave)`` operador rows against the resolved
    ``decl.numero-operadores`` value. ``is_consistent`` is ``True`` only when
    the operator-count delta is exactly zero and the base-imponible delta is
    within ``tolerance`` — a divergence on either axis surfaces as a loud,
    actionable finding (``no-silent-under-declaration``), never a silent pass.
    """

    model_config = STRICT_FROZEN_CONFIG

    by_clave: tuple[Modelo349OperadorClaveTotal, ...] = Field(default_factory=tuple)
    operator_row_total: NonNegativeInt
    operator_summary_total: NonNegativeInt
    operator_delta: int
    base_row_total: Decimal
    base_summary_total: Decimal
    base_delta: Decimal
    tolerance: Decimal = Field(ge=Decimal("0"))
    is_consistent: bool


def compute_modelo_349_operador_totals_parity(
    revision: ModeloRevision,
    observations: Iterable[InvoiceObservation],
    *,
    operator_summary_total: Decimal,
    base_summary_total: Decimal,
    tolerance: Decimal = Decimal("0"),
) -> Modelo349OperadorTotalsParity:
    """Cross-check the per-operador row set against the resolved Modelo 349 declarant summary.

    Args:
        revision: The :class:`ModeloRevision` whose ``iva-349-operador-row-*``
            row-producer bindings are resolved into the operador row set.
        observations: The :class:`InvoiceObservation` rows the revision's
            invoice-source bindings aggregate (exclude-rectifications scope
            only feeds the operador row set; rectification observations are a
            distinct AEAT record type and are excluded from this axis by the
            registry's own binding selectors).
        operator_summary_total: The resolved value of casilla
            ``decl.numero-operadores``, typically read from
            ``revision.casilla_values["decl.numero-operadores"]``.
        base_summary_total: The resolved value of casilla
            ``decl.importe-operaciones``, typically read from
            ``revision.casilla_values["decl.importe-operaciones"]``.
        tolerance: Maximum absolute EUR delta on the base-imponible axis that
            does not surface a divergence. THE REGISTRY IS THE AUTHORITY FOR
            THIS VALUE and publishes it per revision: resolve it with
            ``snapshot.verification_policy().tolerance`` and pass it. The
            default is exact equality rather than a cent: Modelo 349's own
            revisions declare no verification expectations at all, and with
            no published contract there is no authority to widen the
            comparison -- guessing strict yields a visible finding, guessing
            loose yields a silent omission. The operator-count axis is an
            exact integer match with no tolerance regardless.

    Returns:
        A :class:`Modelo349OperadorTotalsParity` verdict. ``is_consistent`` is
        ``False`` whenever the reconstructed operator count differs at all, or
        the reconstructed base imponible diverges from ``base_summary_total``
        by more than ``tolerance`` — a dropped or double-counted operador row
        must surface as a divergence, never silently collapse into
        ``is_consistent=True``.
    """
    from .invoice_bindings import resolve_invoice_binding_row_values

    rows = resolve_invoice_binding_row_values(revision, observations)
    nif_by_row = {
        row_index: value
        for (binding_id, row_index), value in rows.items()
        if binding_id == "iva-349-operador-row-nif" and isinstance(value, str)
    }
    country_by_row = {
        row_index: value
        for (binding_id, row_index), value in rows.items()
        if binding_id == "iva-349-operador-row-codigo-pais" and isinstance(value, str)
    }
    clave_by_row = {
        row_index: value
        for (binding_id, row_index), value in rows.items()
        if binding_id == "iva-349-operador-row-clave" and isinstance(value, str)
    }
    base_by_row = {
        row_index: value
        for (binding_id, row_index), value in rows.items()
        if binding_id == "iva-349-operador-row-base" and isinstance(value, Decimal)
    }
    operators: set[tuple[str, str, str]] = set()
    operator_base: dict[tuple[str, str, str], Decimal] = {}
    base_row_total = Decimal("0")
    for row_index in sorted(base_by_row):
        clave = clave_by_row.get(row_index)
        country = country_by_row.get(row_index)
        nif = nif_by_row.get(row_index)
        if clave is None or country is None or nif is None:
            continue
        key = (country, nif, clave)
        operators.add(key)
        operator_base[key] = operator_base.get(key, Decimal("0")) + base_by_row[row_index]
        base_row_total += base_by_row[row_index]
    by_clave_operators: dict[str, set[tuple[str, str]]] = {}
    by_clave_base: dict[str, Decimal] = {}
    for (country, nif, clave), base in operator_base.items():
        by_clave_operators.setdefault(clave, set()).add((country, nif))
        by_clave_base[clave] = by_clave_base.get(clave, Decimal("0")) + base
    by_clave = tuple(
        Modelo349OperadorClaveTotal(
            clave=clave,
            operator_count=len(by_clave_operators[clave]),
            base_total=by_clave_base[clave],
        )
        for clave in sorted(by_clave_operators)
    )
    operator_row_total = len(operators)
    operator_delta = operator_row_total - int(operator_summary_total)
    base_delta = base_row_total - base_summary_total
    is_consistent = operator_delta == 0 and abs(base_delta) <= tolerance
    return Modelo349OperadorTotalsParity(
        by_clave=by_clave,
        operator_row_total=operator_row_total,
        operator_summary_total=int(operator_summary_total),
        operator_delta=operator_delta,
        base_row_total=base_row_total,
        base_summary_total=base_summary_total,
        base_delta=base_delta,
        tolerance=tolerance,
        is_consistent=is_consistent,
    )


def normalise_m349_nif_export_rows(
    rows: dict[tuple[BindingId, int], Decimal | str],
) -> dict[tuple[BindingId, int], Decimal | str]:
    normalised = dict(rows)
    for (binding_id, row_index), value in rows.items():
        country_binding = _M349_EXPORT_NIF_COUNTRY_BINDINGS.get(binding_id)
        if country_binding is None:
            continue
        country_value = rows.get((country_binding, row_index))
        if not isinstance(value, str) or not isinstance(country_value, str):
            continue
        normalised[(binding_id, row_index)] = _m349_export_nif_number(value, country_value)
    return normalised


def m349_public_row_union(
    rows: dict[tuple[BindingId, int], Decimal | str],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Append payable acquisition rows onto the public Modelo 349 row ids."""
    merged = dict(rows)
    operador_offset = _max_row_index(rows, _M349_OPERADOR_PUBLIC_ROW_BINDINGS)
    rectificacion_offset = _max_row_index(rows, _M349_RECTIFICACION_PUBLIC_ROW_BINDINGS)
    for (binding_id, row_index), value in sorted(rows.items()):
        public_binding = _M349_PAYABLE_ROW_BINDING_MIRRORS.get(binding_id)
        if public_binding is None:
            continue
        offset = rectificacion_offset if public_binding in _M349_RECTIFICACION_PUBLIC_ROW_BINDINGS else operador_offset
        merged[(public_binding, row_index + offset)] = value
    return merged


def _max_row_index(rows: Mapping[tuple[BindingId, int], object], bindings: frozenset[BindingId]) -> int:
    return max((row_index for (binding_id, row_index) in rows if binding_id in bindings), default=0)


def build_invoice_rows(
    grouping: _InvoiceGrouping,
    observations: tuple[InvoiceObservation, ...],
    *,
    m347_threshold_filter: Callable[[tuple[InvoiceObservation, ...]], tuple[InvoiceObservation, ...]],
) -> tuple[Mapping[str, Decimal | str], ...]:
    if grouping == "operator_clave":
        return _build_operator_clave_rows(observations)
    if grouping == "operator_clave_period":
        return _build_operator_clave_period_rows(observations)
    if grouping == "contraparte_clave":
        return _build_contraparte_clave_rows(observations, m347_threshold_filter=m347_threshold_filter)
    raise RegistryValidationError(f"unsupported invoice row grouping {grouping!r}")


def _build_operator_clave_rows(
    observations: tuple[InvoiceObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    grouped: dict[tuple[str, str, str], _OperatorClaveAccumulator] = {}
    for observation in observations:
        if observation.intracommunity_clave is None:
            continue
        key = (
            observation.country_code,
            observation.party_tax_id,
            observation.intracommunity_clave,
        )
        bucket = grouped.setdefault(
            key,
            _OperatorClaveAccumulator(
                country_code=observation.country_code,
                party_tax_id=observation.party_tax_id,
                clave=observation.intracommunity_clave,
                party_legal_name=observation.party_legal_name,
                base_total=Decimal("0"),
            ),
        )
        bucket.base_total += observation.base_amount
        if bucket.party_legal_name is None and observation.party_legal_name is not None:
            bucket.party_legal_name = observation.party_legal_name
    rows: list[Mapping[str, Decimal | str]] = []
    for key in sorted(grouped):
        bucket = grouped[key]
        row: dict[str, Decimal | str] = {
            "country_code": bucket.country_code,
            "party_tax_id": bucket.party_tax_id,
            "clave": bucket.clave,
            "base_imponible": bucket.base_total,
        }
        if bucket.party_legal_name is not None:
            row["party_legal_name"] = bucket.party_legal_name
        rows.append(row)
    return tuple(rows)


_M347_QUARTER_TOKENS: tuple[Literal["1T", "2T", "3T", "4T"], ...] = ("1T", "2T", "3T", "4T")
_M347_QUARTER_ROW_FIELDS: Mapping[Literal["1T", "2T", "3T", "4T"], str] = {
    "1T": "importe_q1",
    "2T": "importe_q2",
    "3T": "importe_q3",
    "4T": "importe_q4",
}


def _m347_quarter_of(value: date) -> Literal["1T", "2T", "3T", "4T"]:
    """Return the calendar quarter token ``value`` falls in.

    Routed through :meth:`~core.Period.contains`, the one canonical period
    boundary authority (``aeat-registry-authority-flow``'s period-boundary
    rule) -- no locally re-derived month-range arithmetic. Uses ``value``'s
    OWN calendar year, not a filing-year argument this row-producer has no
    access to: the diseño's Q1-Q4 fields are the ordinary calendar quarter an
    operation falls in, independent of which filing year's declaration
    reports it.
    """
    for token in _M347_QUARTER_TOKENS:
        if Period.from_year_and_code(value.year, token).contains(value):
            return token
    msg = f"date {value!r} does not fall in any calendar quarter"  # pragma: no cover - contains() is exhaustive
    raise RegistryValidationError(msg)


#: Config for the private grouping buckets below.
#:
#: Strict and closed like every model here, but NOT frozen. These three exist to
#: be mutated -- the aggregation loops do ``bucket.base_total += ...`` and fill a
#: missing legal name in place -- and they carried STRICT_FROZEN_CONFIG, so every
#: aggregation over a non-empty observation set raised ``frozen_instance``.
#:
#: The docstrings said "mutable accumulator" the whole time. The config and the
#: prose disagreed and the prose was right: these are local buckets inside one
#: function, never persisted, never returned (the rows are built as plain
#: mappings afterwards), so the frozen discipline that protects a domain record
#: has nothing to protect here.
#:
#: ``validate_assignment`` is load-bearing rather than decorative. Dropping
#: ``frozen`` alone makes every assignment bypass validation, so the class would
#: have gone from refusing a Decimal sum to accepting an int in a country-code
#: field -- trading one wrong answer for a quieter one. A probe caught that.
_ACCUMULATOR_CONFIG: ConfigDict = ConfigDict(
    strict=True,
    extra="forbid",
    validate_default=True,
    validate_assignment=True,
)


class _ContraparteClaveAccumulator(BaseModel):
    """Mutable accumulator for contraparte_clave row aggregation (modelo 347)."""

    model_config = _ACCUMULATOR_CONFIG

    country_code: str
    party_tax_id: TaxIdIdentityToken
    clave: str
    party_legal_name: str | None
    importe_total: Decimal
    importe_q1: Decimal
    importe_q2: Decimal
    importe_q3: Decimal
    importe_q4: Decimal


def _build_contraparte_clave_rows(
    observations: tuple[InvoiceObservation, ...],
    *,
    m347_threshold_filter: Callable[[tuple[InvoiceObservation, ...]], tuple[InvoiceObservation, ...]],
) -> tuple[Mapping[str, Decimal | str], ...]:
    """Group invoice observations into modelo 347 contraparte rows.

    Mirrors :func:`_build_operator_clave_rows`'s (country, counterparty,
    clave) grouping shape exactly, keyed on ``operation_clave`` -- M347's own
    clave vocabulary -- rather than M349's ``intracommunity_clave``. The two
    fields are disjoint by construction (:class:`InvoiceObservation`'s
    validators enforce each against its own closed set), so an observation
    can only ever be grouped by the one this function reads.

    Aggregates ``invoice_total_amount`` rather than ``base_amount``: RD
    1065/2007 art. 34.2.a) requires the declared IMPORTE ANUAL to be the
    total contraprestacion including cuotas and recargos, not the taxable
    base alone (recorded in the tui-architecture modelo 347 contraparte
    binding inventory reference).

    Also buckets that same amount into the calendar quarter of
    ``transaction_date`` -- the diseño's mandatory, unconditional "IMPORTE DE
    LAS OPERACIONES [Nth] TRIMESTRE" fields (RD 1065/2007 art. 33.1's "se
    suministrará desglosada trimestralmente"), ungated by any "Sólo..."
    exception the way ``importe-metalico`` / ``operacion-seguro`` /
    ``arrendamiento-local-negocio`` / the transmisiones-inmuebles pair are.
    The quarterly buckets accumulate in the SAME loop that sums
    ``importe_total``, so the annual total is the sum of the four quarters by
    construction, not by a separate reconciling step.

    Applies the RD 1065/2007 art. 31 declaration floor to *this* family
    before grouping, routed through :func:`_m347_row_family_threshold_filter`,
    which itself delegates to the same canonical comparison
    (:func:`~._m347_threshold.m347_declarable_party_ids` /
    ``m347_clave_c_declarable_party_ids``) rather than a new one written out
    here. A party's TOTAL across every NON-clave-C clave decides general
    declarability (the floor is strictly exceeded, ``>``, never merely
    reached); a beneficiary's clave-C total is judged separately against its
    OWN, lower 300,51 EUR floor (arts. 32.c, 33.4), alongside rather than
    instead of the general one.
    """
    observations = m347_threshold_filter(observations)
    grouped: dict[tuple[str, str, str], _ContraparteClaveAccumulator] = {}
    for observation in observations:
        if observation.operation_clave is None:
            continue
        if observation.invoice_total_amount is None:
            raise RegistryValidationError(
                f"invoice observation {observation.invoice_id!r} declares operation_clave "
                f"{observation.operation_clave!r} but no invoice_total_amount",
            )
        key = (
            observation.country_code,
            observation.party_tax_id,
            observation.operation_clave,
        )
        bucket = grouped.setdefault(
            key,
            _ContraparteClaveAccumulator(
                country_code=observation.country_code,
                party_tax_id=observation.party_tax_id,
                clave=observation.operation_clave,
                party_legal_name=observation.party_legal_name,
                importe_total=Decimal("0"),
                importe_q1=Decimal("0"),
                importe_q2=Decimal("0"),
                importe_q3=Decimal("0"),
                importe_q4=Decimal("0"),
            ),
        )
        bucket.importe_total += observation.invoice_total_amount
        quarter_field = _M347_QUARTER_ROW_FIELDS[_m347_quarter_of(observation.transaction_date)]
        setattr(bucket, quarter_field, getattr(bucket, quarter_field) + observation.invoice_total_amount)
        if bucket.party_legal_name is None and observation.party_legal_name is not None:
            bucket.party_legal_name = observation.party_legal_name
    rows: list[Mapping[str, Decimal | str]] = []
    for key in sorted(grouped):
        bucket = grouped[key]
        row: dict[str, Decimal | str] = {
            "country_code": bucket.country_code,
            "party_tax_id": bucket.party_tax_id,
            "clave": bucket.clave,
            "importe_total": bucket.importe_total,
            "importe_q1": bucket.importe_q1,
            "importe_q2": bucket.importe_q2,
            "importe_q3": bucket.importe_q3,
            "importe_q4": bucket.importe_q4,
        }
        if bucket.party_legal_name is not None:
            row["party_legal_name"] = bucket.party_legal_name
        rows.append(row)
    return tuple(rows)


def _build_operator_clave_period_rows(
    observations: tuple[InvoiceObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    grouped: dict[
        tuple[str, str, str, int, str],
        _OperatorClavePeriodAccumulator,
    ] = {}
    for observation in observations:
        if observation.intracommunity_clave is None:
            continue
        if observation.rectified_year is None or observation.rectified_period is None:
            raise RegistryValidationError(
                "operator_clave_period grouping requires rectification metadata on every observation",
            )
        key = (
            observation.country_code,
            observation.party_tax_id,
            observation.intracommunity_clave,
            observation.rectified_year,
            observation.rectified_period,
        )
        bucket = grouped.setdefault(
            key,
            _OperatorClavePeriodAccumulator(
                country_code=observation.country_code,
                party_tax_id=observation.party_tax_id,
                clave=observation.intracommunity_clave,
                party_legal_name=observation.party_legal_name,
                rectified_year=observation.rectified_year,
                rectified_period=observation.rectified_period,
                base_total=Decimal("0"),
                base_previous_total=Decimal("0"),
            ),
        )
        bucket.base_total += observation.base_amount
        previous = observation.rectified_base_previous
        if previous is None:
            raise RegistryValidationError(
                f"rectification observation {observation.ledger_id!r} declares no rectified base to compare",
            )
        bucket.base_previous_total += previous
        if bucket.party_legal_name is None and observation.party_legal_name is not None:
            bucket.party_legal_name = observation.party_legal_name
    rows: list[Mapping[str, Decimal | str]] = []
    for key in sorted(grouped):
        bucket = grouped[key]
        row: dict[str, Decimal | str] = {
            "country_code": bucket.country_code,
            "party_tax_id": bucket.party_tax_id,
            "clave": bucket.clave,
            "rectified_year": str(bucket.rectified_year),
            "rectified_period": bucket.rectified_period,
            "base_imponible": bucket.base_total,
            "rectified_base_previous": bucket.base_previous_total,
        }
        if bucket.party_legal_name is not None:
            row["party_legal_name"] = bucket.party_legal_name
        rows.append(row)
    return tuple(rows)


def _m349_export_nif_number(party_tax_id: str, country_code: str) -> str:
    from ...modelos.row_models import m349_nif_number_for_export

    try:
        return m349_nif_number_for_export(party_tax_id, country_code)
    except ValueError as exc:
        raise RegistryValidationError(str(exc)) from exc


class _OperatorClaveAccumulator(BaseModel):
    """Mutable accumulator for operator_clave row aggregation."""

    model_config = _ACCUMULATOR_CONFIG

    country_code: str
    party_tax_id: TaxIdIdentityToken
    clave: str
    party_legal_name: str | None
    base_total: Decimal


class _OperatorClavePeriodAccumulator(BaseModel):
    """Mutable accumulator for operator_clave_period row aggregation."""

    model_config = _ACCUMULATOR_CONFIG

    country_code: str
    party_tax_id: TaxIdIdentityToken
    clave: str
    party_legal_name: str | None
    rectified_year: int
    rectified_period: str
    base_total: Decimal
    base_previous_total: Decimal
