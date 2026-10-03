"""Private row materialisation for invoice-shaped registry bindings."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from ....core.identity.nif_iva import normalise_nif_iva
from ....core.identity.tax_id import TaxIdIdentityToken
from ....core.period import Period
from ...iva.establishment import SPAIN_COUNTRY_CODE
from .errors import RegistryValidationError
from .ids import BindingId
from .nif_iva_catalogue import resolve_nif_iva_catalogue

if TYPE_CHECKING:
    from .invoice_bindings import InvoiceObservation

InvoiceGrouping = Literal["operator_clave", "operator_clave_period", "contraparte_clave"]
"""How invoice rows are grouped before an M349 or M347 binding resolves them.

Public rather than underscore-private because `invoice_bindings` needs it too. It was
private here and separately restated there, byte for byte, which is this campaign's most
frequent cause: a definition that cannot be reached is a definition that gets rewritten.
"""

_M349_EXPORT_NIF_COUNTRY_BINDINGS: dict[BindingId, BindingId] = {
    "iva-349-operador-row-nif": "iva-349-operador-row-codigo-pais",
    "iva-349-rectificacion-row-nif": "iva-349-rectificacion-row-codigo-pais",
}


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


def build_invoice_rows(
    grouping: InvoiceGrouping,
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


class _InvoiceRowBucket(Protocol):
    """Shared identity and optional-name surface of every row accumulator."""

    country_code: str
    party_tax_id: TaxIdIdentityToken
    clave: str
    party_legal_name: str | None


def _materialize_grouped_invoice_rows[InvoiceRowBucketT: _InvoiceRowBucket](
    buckets: Iterable[InvoiceRowBucketT],
    *,
    values: Callable[[InvoiceRowBucketT], Mapping[str, Decimal | str]],
) -> tuple[Mapping[str, Decimal | str], ...]:
    """Build ordered export rows from already-grouped invoice accumulators.

    This owns only the repeated mapping construction and optional legal-name
    projection. Each grouping retains its own ordered buckets and explicitly
    supplies its legal row-value mapping, so M349's base and rectification
    semantics cannot be conflated with M347's annual and quarterly amounts.
    """
    rows: list[Mapping[str, Decimal | str]] = []
    for bucket in buckets:
        row: dict[str, Decimal | str] = {
            "country_code": bucket.country_code,
            "party_tax_id": bucket.party_tax_id,
            "clave": bucket.clave,
        }
        row.update(values(bucket))
        if bucket.party_legal_name is not None:
            row["party_legal_name"] = bucket.party_legal_name
        rows.append(row)
    return tuple(rows)


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
    return _materialize_grouped_invoice_rows(
        (grouped[key] for key in sorted(grouped)),
        values=lambda bucket: {"base_imponible": bucket.base_total},
    )


_M347_QUARTER_TOKENS: tuple[Literal["1T", "2T", "3T", "4T"], ...] = ("1T", "2T", "3T", "4T")
_M347_QUARTER_ROW_FIELDS: Mapping[Literal["1T", "2T", "3T", "4T"], str] = {
    "1T": "importe_q1",
    "2T": "importe_q2",
    "3T": "importe_q3",
    "4T": "importe_q4",
}


def _m347_quarter_of(value: date) -> Literal["1T", "2T", "3T", "4T"]:
    """Return the calendar quarter token ``value`` falls in.

    Routed through :meth:`~core.period.Period.contains`, the one canonical period
    boundary authority (``aeat-registry-authority-flow``'s period-boundary
    rule) -- no locally re-derived month-range arithmetic. Uses ``value``'s
    OWN calendar year, not a filing-year argument this row-producer has no
    access to: the dise�o's Q1-Q4 fields are the ordinary calendar quarter an
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
    ``transaction_date`` -- the dise�o's mandatory, unconditional "IMPORTE DE
    LAS OPERACIONES [Nth] TRIMESTRE" fields (RD 1065/2007 art. 33.1's "se
    suministrar� desglosada trimestralmente"), ungated by any "S�lo..."
    exception the way ``importe-metalico`` / ``operacion-seguro`` /
    ``arrendamiento-local-negocio`` / the transmisiones-inmuebles pair are.
    The quarterly buckets accumulate in the SAME loop that sums
    ``importe_total``, so the annual total is the sum of the four quarters by
    construction, not by a separate reconciling step.

    Applies the RD 1065/2007 art. 33 declaration floor to *this* family
    before grouping, through the ``m347_threshold_filter`` the caller passes
    (the invoice family's ``_m347_row_family_threshold_filter``), which
    delegates to the one canonical comparison,
    :func:`~.m347_threshold.m347_declarable_party_buckets`, rather than a new
    one written out here. The floor is judged per counterparty AND per
    threshold bucket of the dated clave-bucket fact: entregas and
    adquisiciones are computed separately (art. 33.1), clave C against its
    own 300,51 EUR floor (arts. 32.c, 33.4), and the floor is strictly
    exceeded, ``>``, never merely reached.
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
    return _materialize_grouped_invoice_rows(
        (grouped[key] for key in sorted(grouped)),
        values=lambda bucket: {
            "importe_total": bucket.importe_total,
            "importe_q1": bucket.importe_q1,
            "importe_q2": bucket.importe_q2,
            "importe_q3": bucket.importe_q3,
            "importe_q4": bucket.importe_q4,
            **_m347_declarado_identification(bucket.party_tax_id, bucket.country_code),
        },
    )


def _m347_declarado_identification(party_tax_id: str, country_code: str) -> dict[str, str]:
    """Project one counterparty onto the 347 declarado identification slots.

    Both 347 record designs fill the NIF DEL DECLARADO slot "solo ... con los NIF
    asignados en España" and, for "no residentes sin establecimiento permanente",
    write the país de residencia; the 2025 design adds the NIF OPERADOR
    COMUNITARIO slot, "incompatible (excluyente)" with the Spanish NIF, carrying
    the Member State prefix and number. A counterparty observed in another
    country is therefore declared by country, and by NIF-IVA only when its
    identifier has the structure the NIF-IVA catalogue publishes for that State.
    """
    if country_code == SPAIN_COUNTRY_CODE:
        return {"declarado_tax_id": party_tax_id, "residence_country_code": "", "community_vat_number": ""}
    return {
        "declarado_tax_id": "",
        "residence_country_code": country_code,
        "community_vat_number": _community_vat_number(party_tax_id, country_code),
    }


def _community_vat_number(party_tax_id: str, country_code: str) -> str:
    catalogue = resolve_nif_iva_catalogue()
    prefix = catalogue.prefix_for_country(country_code)
    if prefix is None:
        return ""
    number = normalise_nif_iva(party_tax_id)
    candidate = number if number.startswith(str(prefix)) else f"{prefix}{number}"
    return candidate if catalogue.definition(prefix).spec.pattern.fullmatch(candidate) else ""


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
                f"rectification observation {observation.invoice_id!r} declares no rectified base to compare",
            )
        bucket.base_previous_total += previous
        if bucket.party_legal_name is None and observation.party_legal_name is not None:
            bucket.party_legal_name = observation.party_legal_name
    return _materialize_grouped_invoice_rows(
        (grouped[key] for key in sorted(grouped)),
        values=lambda bucket: {
            "rectified_year": str(bucket.rectified_year),
            "rectified_period": bucket.rectified_period,
            "base_imponible": bucket.base_total,
            "rectified_base_previous": bucket.base_previous_total,
        },
    )


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
