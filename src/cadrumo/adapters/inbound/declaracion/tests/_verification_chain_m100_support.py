"""Shared M100 verification-chain test support.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_verification_chain_m100_corpus_limited`
        Active M100 engine-verification consumer for the corpus-limited verdict.
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m100`
        Parser boundary corpus sweep that establishes the same extracted
        casilla surface before engine verification consumes it.
    :func:`~adapters.inbound.declaracion.parser.parse_declaracion`
        Public declaration-copy parser used by the shared corpus loader.
    :class:`~domain.calculations.registry.CasillaId`
        Typed casilla key carried by the expected sets and parsed-value mapping.
    :exc:`~adapters.inbound.declaracion.DeclaracionParseError`
        Parser failure converted into a corpus-specific ``PARSER-GAP`` failure.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....domain.calculations.registry.binding_value_contract import BindingValueChannel
from .....domain.calculations.registry.ids import BindingId
from .....domain.calculations.registry.schema import ModeloRevision
from .....domain.calculations.registry.schema_input_kind import InputKind
from .....tests.inventory import FIXTURES_DIR
from ..errors import DeclaracionParseError
from ..parser import parse_declaracion

_M100_INGRESOS_EXPLOTACION_CASILLA: CasillaId = validated_casilla_id("0171")
_M100_BASE_LIQUIDABLE_GENERAL_CASILLA: CasillaId = validated_casilla_id("0505")
_M100_CUOTA_ESTATAL_CASILLA: CasillaId = validated_casilla_id("0545")
_M100_CUOTA_AUTONOMICA_CASILLA: CasillaId = validated_casilla_id("0546")
_EXPECTED_CASILLAS_M100: frozenset[CasillaId] = frozenset(
    validated_casilla_id(_v)
    for _v in (
        "0171",
        "0180",
        "0218",
        "0223",
        "0224",
        "0226",
        "0231",
        "0235",
        "0432",
        "0500",
        "0505",
        "0510",
        "0545",
        "0546",
        "0585",
        "0586",
        "0587",
        "0595",
        "0604",
        "0610",
        "0670",
    )
)
_M100_CLOSURE_ASSERTION_CASILLAS: tuple[CasillaId, ...] = (
    _M100_CUOTA_ESTATAL_CASILLA,
    _M100_CUOTA_AUTONOMICA_CASILLA,
    validated_casilla_id("0585"),
    validated_casilla_id("0586"),
)


_M100_CORPUS_DIR = FIXTURES_DIR / "justificantes" / "100"
_M100_ANNUAL_PERIOD = "0A"


def _m100_corpus_years() -> tuple[int, ...]:
    """The ejercicio of every annual Modelo 100 justificante specimen on disk."""
    suffix = f"-{_M100_ANNUAL_PERIOD}"
    return tuple(
        sorted(
            int(path.stem.removesuffix(suffix))
            for path in _M100_CORPUS_DIR.glob(f"*{suffix}.pdf")
            if path.stem.removesuffix(suffix).isdigit()
        )
    )


def _m100_manual_casillas(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Casillas the edition lets a filer type; every other casilla is derived or bound."""
    return frozenset(casilla.id for casilla in revision.casillas if casilla.input_kind == InputKind.MANUAL)


def _m100_bound_extracted_values(
    revision: ModeloRevision, extracted: Mapping[CasillaId, object]
) -> dict[BindingId, Decimal]:
    """Route each extracted value of a bound casilla through the binding that fills it."""
    return {
        casilla.binding: value
        for casilla in revision.casillas
        if casilla.input_kind == InputKind.BOUND
        and casilla.binding is not None
        and isinstance(value := extracted.get(casilla.id), Decimal)
    }


@dataclass(frozen=True, slots=True)
class NeutralM100Bindings:
    """Binding values for a Cataluña individual filer with no other income, family or carry-in."""

    decimals: dict[BindingId, Decimal]
    enums: dict[BindingId, str]
    dates: dict[BindingId, date]
    booleans: dict[BindingId, bool]


_INDIVIDUAL_DECLARATION = Decimal("1")
_ADULT_BIRTH_DATE = date(1975, 6, 15)


def _neutral_m100_bindings(revision: ModeloRevision, *, ccaa: str) -> NeutralM100Bindings:
    """Neutral values for every scalar binding the edition declares.

    Relation prefills arrive through their own channel and are left out.
    """
    bindings = NeutralM100Bindings(decimals={}, enums={}, dates={}, booleans={})
    for binding in revision.bindings:
        if binding.source is BindingSourceKind.RELATION_PREFILL:
            continue
        channel = binding.value.channel
        if channel in {BindingValueChannel.DECIMAL, BindingValueChannel.INTEGER}:
            bindings.decimals[binding.id] = Decimal("0")
        elif channel is BindingValueChannel.BOOLEAN:
            bindings.booleans[binding.id] = False
        elif channel is BindingValueChannel.DATE:
            bindings.dates[binding.id] = _ADULT_BIRTH_DATE
        elif channel is BindingValueChannel.ENUM:
            bindings.enums[binding.id] = ccaa
    if any(binding.id == "renta-profile-declaration-type" for binding in revision.bindings):
        bindings.decimals["renta-profile-declaration-type"] = _INDIVIDUAL_DECLARATION
    return bindings


def _parse_m100_corpus(year: int, label: str) -> dict[CasillaId, object]:
    """Parse one M100 annual corpus specimen for verification-chain consumers.

    See Also:
        :func:`~adapters.inbound.declaracion.parser.parse_declaracion`
            Parser entry point invoked with explicit Modelo 100 annual context.
        :class:`~domain.calculations.registry.CasillaId`
            Mapping key type returned to engine-verification assertions.
    """
    pdf_path = _M100_CORPUS_DIR / f"{year}-{_M100_ANNUAL_PERIOD}.pdf"
    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="100",
            año_override=year,
            period_override=_M100_ANNUAL_PERIOD,
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [{label}]: parse_declaracion raised.\n  error: {exc}")
    return {v.casilla_id: v.printed_value for v in filing.values}
