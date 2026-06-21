"""Typed CLI row models for multi-row informational modelos.

Provides strictly-validated pydantic row shapes for operator-supplied
detail rows on modelos whose filing content is a list of repeating
records rather than a set of scalar casilla values.

Supported row types:

* ``Modelo184MemberRow`` — atribución member for modelo 184
  (``--row miembro nif=X share=Y importe=Z``)
* ``Modelo232VinculadaRow`` — operación vinculada for modelo 232
  (``--row vinculada nif=X tipo_vinculacion=Y importe=Z metodo=M pais=P``)
* ``Modelo349OperadorRow`` — operador intracomunitario for modelo 349
  (``--row operador codigo_pais=DE nif_comunitario=DE123456789 razon_social=X clave_operacion=E importe=Y``)
  Used when no collectible-invoice ledger exists; maps directly to the
  Tipo-2 operador record layout (Orden HAC/174/2020 Anexo II).
* ``Modelo347ContraparteRow`` — contraparte declarada for modelo 347
  (``--row contraparte nif=X nombre=Y importe_Q1=Z clave_operacion=A``)
  One row per counterparty. Annual importe threshold check (> €3,005.06)
  is performed by the CLI validator, not the model, so partial row sets
  accumulate correctly before final validation.

These models are the CLI boundary layer. They validate operator input
before being carried into ``detail_rows`` on the ``CalculationRevision``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.errors import AeatError
from ...core.external_constants import M347_THRESHOLD_EUR as M347_THRESHOLD_EUR  # re-export

# ---------------------------------------------------------------------------
# Shared type aliases
# ---------------------------------------------------------------------------

_NifStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
_NameStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
_IsoCountryCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=2)]


# ---------------------------------------------------------------------------
# Modelo 184 - atribucion de rentas member row
#
# Legal authority: Orden HAP/2250/2015 art. 3; Ley 35/2006 arts. 86-89.
# One row per miembro (socio / comunero / partícipe) of the entity.
# ---------------------------------------------------------------------------


class Modelo184MemberRow(BaseModel):
    """One atribución member row for Modelo 184.

    Fields mirror the per-record Tipo-2 layout declared in the M184
    ``bindings/0001-bindings.toml`` atribucion_member source block.

    Parity assertions:
    * ``nif`` → ``member_tax_id`` (binding: modelo-184-member-row-nif)
    * ``nombre`` → ``member_legal_name`` (binding: modelo-184-member-row-name)
    * ``porcentaje`` → ``share_percentage`` (binding: modelo-184-member-row-share)
    * ``importe`` → ``base_imponible_assigned`` (binding: modelo-184-member-row-base-assigned)
    * ``pais`` → ``country_code`` (ES default)
    """

    model_config = STRICT_FROZEN_CONFIG

    row_type: Literal["miembro"] = "miembro"
    nif: _NifStr
    nombre: _NameStr = Field(default="")
    pais: _IsoCountryCode = Field(default="ES")
    porcentaje: Decimal = Field(description="Share percentage in the entity [0, 100]")
    importe: Decimal = Field(description="Attributed income/base imponible in EUR")

    @field_validator("pais")
    @classmethod
    def _pais_uppercase_alpha(cls, value: str) -> str:
        if value != value.upper() or not value.replace(" ", "").isalpha():
            raise ValueError("pais must be an uppercase two-letter ISO 3166-1 country code (e.g. ES, DE, FR)")
        return value

    @field_validator("porcentaje")
    @classmethod
    def _porcentaje_within_bounds(cls, value: Decimal) -> Decimal:
        if value < Decimal("0") or value > Decimal("100"):
            raise ValueError(f"porcentaje must be within [0, 100]; got {value}")
        return value

    @field_validator("nif")
    @classmethod
    def _nif_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nif cannot be blank")
        return value.upper()


# ---------------------------------------------------------------------------
# Modelo 232 - operacion vinculada row
#
# Legal authority: Orden HFP/816/2017 art. 3; Ley 27/2014 art. 18;
# RD 634/2015 art. 13 (LIS transfer pricing).
# One row per related-party transaction group.
# ---------------------------------------------------------------------------

# Closed catalogue of válid tipo_vinculacion codes per M232 form.
_M232_TIPO_VINCULACION = Literal[
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
]

# Closed catalogue of valid tipo_operacion codes per M232 form.
_M232_TIPO_OPERACION = Literal[
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
]

# Closed catalogue of transfer-pricing method codes per M232 / LIS art. 18.
_M232_METODO = Literal["CUP", "RPM", "CPM", "PS", "TNMM", ""]


class Modelo232VinculadaRow(BaseModel):
    """One operación vinculada row for Modelo 232.

    Fields mirror the related_party_operation binding source declared in
    ``232/revisions/2018-y-siguientes/bindings/0218…0223-*.toml``.

    Parity assertions:
    * ``nif`` → ``counterparty_tax_id`` (binding: modelo-232-related-party-row-nif)
    * ``nombre`` → ``counterparty_legal_name`` (binding: modelo-232-related-party-row-name)
    * ``pais`` → ``country_code`` (binding: modelo-232-related-party-row-country)
    * ``tipo_operacion`` → ``operation_kind_code`` (binding: modelo-232-related-party-row-operation-kind)
    * ``metodo`` → ``transfer_pricing_method_code`` (binding: modelo-232-related-party-row-tpr-method)
    * ``importe`` → ``amount`` (binding: modelo-232-related-party-row-amount)
    """

    model_config = STRICT_FROZEN_CONFIG

    row_type: Literal["vinculada"] = "vinculada"
    nif: _NifStr
    nombre: _NameStr = Field(default="")
    pais: _IsoCountryCode = Field(default="ES")
    tipo_vinculacion: str = Field(default="1", min_length=1, max_length=2)
    tipo_operacion: str = Field(default="01", min_length=1, max_length=2)
    metodo: str = Field(default="", max_length=6)
    importe: Decimal

    @field_validator("pais")
    @classmethod
    def _pais_uppercase_alpha(cls, value: str) -> str:
        if value != value.upper() or not value.replace(" ", "").isalpha():
            raise ValueError("pais must be an uppercase two-letter ISO 3166-1 country code (e.g. ES, DE, FR)")
        return value

    @field_validator("nif")
    @classmethod
    def _nif_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nif cannot be blank")
        return value.upper()

    @field_validator("metodo")
    @classmethod
    def _metodo_uppercase(cls, value: str) -> str:
        return value.upper()


# ---------------------------------------------------------------------------
# Modelo 349 - operador intracomunitario row (manual-entry path)
#
# Legal authority: Orden HAC/174/2020 (Anexo II — Tipo 2 operador record);
# Orden EHA/769/2010 art. 3; Ley 58/2003 art. 93; Ley 37/1992 arts. 66-70
# (operaciones intracomunitarias).
# One row per counterparty + clave_operacion combination.
# NIF-IVA format validation enforces country-specific patterns from
# Council Directive 2006/112/EC Annex XI (the VIES registry format rules).
# ---------------------------------------------------------------------------

# Country-specific NIF-IVA format patterns.
# Pattern values are anchored regexes applied to the full NIF string
# including the two-letter country prefix.
_M349_NIF_PATTERNS: dict[str, re.Pattern[str]] = {
    "DE": re.compile(r"^DE\d{9}$"),
    "FR": re.compile(r"^FR[0-9A-Z]{2}\d{9}$"),
    "IT": re.compile(r"^IT\d{11}$"),
    "PT": re.compile(r"^PT\d{9}$"),
    "NL": re.compile(r"^NL\d{9}B\d{2}$"),
    "BE": re.compile(r"^BE0\d{9}$"),
    "AT": re.compile(r"^ATU\d{8}$"),
    "IE": re.compile(r"^IE(\d{7}[A-W]|\d[A-Z]\d{5}[A-W])$"),
    "PL": re.compile(r"^PL\d{10}$"),
    "SE": re.compile(r"^SE\d{12}$"),
    "DK": re.compile(r"^DK\d{8}$"),
    "FI": re.compile(r"^FI\d{8}$"),
    "LU": re.compile(r"^LU\d{8}$"),
    "GB": re.compile(r"^GB(\d{9}|\d{12}|GD\d{3}|HA\d{3})$"),
}
# Fallback: 2-letter country code + 2-15 alphanumeric characters.
_M349_NIF_FALLBACK: re.Pattern[str] = re.compile(r"^[A-Z]{2}[A-Z0-9]{2,15}$")

# Valid clave de operación codes per Orden HAC/174/2020 Anexo II.
_M349_CLAVE_OPERACION = Literal["E", "S", "T", "R", "A", "I", "M"]


class Modelo349OperadorRow(BaseModel):
    """One operador intracomunitario row for Modelo 349 (manual-entry path).

    Fields mirror the Tipo-2 operador record layout declared in
    ``349/revisions/2020-y-siguientes/bindings/0007-bindings.toml``.

    This row is used when the collectible-invoice ledger is absent and
    the operator declares intracom counterparties directly via the CLI.

    Parity assertions:
    * ``codigo_pais`` → ``op.codigo-pais`` (casilla 76-77)
    * ``nif_comunitario`` → ``op.nif-comunitario`` (casilla 78-92)
    * ``razon_social`` → ``op.apellidos-razon-social`` (casilla 93-132)
    * ``clave_operacion`` → ``op.clave-operacion`` (casilla 133)
    * ``importe`` → ``op.base-imponible`` (casilla 134-146)
    """

    model_config = STRICT_FROZEN_CONFIG

    row_type: Literal["operador"] = "operador"
    codigo_pais: _IsoCountryCode
    nif_comunitario: _NifStr
    razon_social: _NameStr = Field(default="")
    clave_operacion: _M349_CLAVE_OPERACION
    importe: Decimal = Field(description="Base imponible o importe de la operacion en EUR")

    @field_validator("codigo_pais")
    @classmethod
    def _codigo_pais_uppercase_alpha(cls, value: str) -> str:
        if value != value.upper() or not value.replace(" ", "").isalpha():
            raise ValueError("codigo_pais must be an uppercase two-letter ISO 3166-1 country code (e.g. DE, FR, IT)")
        return value

    @field_validator("nif_comunitario")
    @classmethod
    def _nif_comunitario_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nif_comunitario cannot be blank")
        return value.upper()

    @field_validator("importe")
    @classmethod
    def _importe_non_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise ValueError(f"importe must be non-negative per Orden HAC/174/2020 Anexo II constraint; got {value}")
        return value


def validate_m349_nif_format(nif: str, pais: str) -> bool:
    """Return True when ``nif`` matches the expected NIF-IVA format for ``pais``.

    Uses country-specific patterns where known; falls back to the generic
    EU IVA format (2-letter prefix + 2-15 alphanumerics) for other countries.
    The NIF string must already include the two-letter country prefix.
    """
    pattern = _M349_NIF_PATTERNS.get(pais.upper(), _M349_NIF_FALLBACK)
    return bool(pattern.match(nif.upper()))


# ---------------------------------------------------------------------------
# Modelo 347 - contraparte declarada row
#
# Legal authority: Orden EHA/3012/2008 art. 1; RD 1065/2007 arts. 31-35
# (reglamento de gestión e inspección tributaria, obligación de informar
# sobre operaciones con terceros); Ley 58/2003 art. 93.
# Threshold: total annual importe > €3,005.06 per counterparty (RD
# 1065/2007 art. 33.1).  The threshold check is performed at the CLI
# validator level, not here, so that partial row accumulation works.
# ---------------------------------------------------------------------------

# Valid clave de operacion codes per M347 form / Orden EHA/3012/2008.
_M347_CLAVE_OPERACION = Literal["A", "B", "C", "D", "E", "F", "G", "H", "I"]


class Modelo347ContraparteRow(BaseModel):
    """One contraparte declarada row for Modelo 347.

    Fields mirror the per-counterparty Tipo-2 record layout declared in
    ``347/revisions/2008-y-siguientes``.

    One row per counterparty. The annual total importe (sum of Q1-Q4)
    must exceed €3,005.06 per RD 1065/2007 art. 33.1.

    Parity assertions:
    * ``nif`` → ``contraparte.nif`` (counterparty tax id)
    * ``nombre`` → ``contraparte.nombre`` (legal name)
    * ``importe_Q1/Q2/Q3/Q4`` → quarterly importe slots
    * ``clave_operacion`` → operation type code
    * ``pais_codigo`` → ``contraparte.pais`` (ISO 3166-1; None = domestic)
    """

    model_config = STRICT_FROZEN_CONFIG

    row_type: Literal["contraparte"] = "contraparte"
    nif: _NifStr
    nombre: _NameStr = Field(default="")
    importe_Q1: Decimal = Field(default=Decimal("0"))
    importe_Q2: Decimal = Field(default=Decimal("0"))
    importe_Q3: Decimal = Field(default=Decimal("0"))
    importe_Q4: Decimal = Field(default=Decimal("0"))
    clave_operacion: _M347_CLAVE_OPERACION = "A"
    pais_codigo: _IsoCountryCode | None = None

    @field_validator("nif")
    @classmethod
    def _nif_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nif cannot be blank")
        return value.upper()

    @field_validator("pais_codigo")
    @classmethod
    def _pais_codigo_uppercase_alpha(cls, value: str | None) -> str | None:
        if value is None:
            return value
        v = value.strip().upper()
        if not v.isalpha() or len(v) != 2:
            raise ValueError("pais_codigo must be an uppercase two-letter ISO 3166-1 country code or None for domestic")
        return v

    @property
    def importe_total(self) -> Decimal:
        """Sum of quarterly importes — used for M347 threshold check."""
        return self.importe_Q1 + self.importe_Q2 + self.importe_Q3 + self.importe_Q4


# ---------------------------------------------------------------------------
# Discriminated union — single type accepted by the CLI --row argument
# ---------------------------------------------------------------------------

ModeloDetailRow = Modelo184MemberRow | Modelo232VinculadaRow | Modelo349OperadorRow | Modelo347ContraparteRow


# ---------------------------------------------------------------------------
# Statutory cross-row / threshold validations (domain-owned)
# ---------------------------------------------------------------------------


class Modelo347ThresholdError(AeatError, ValueError):
    """A Modelo 347 contraparte row falls at or below the declarability threshold."""

    def __init__(self, *, nif: str, total: Decimal) -> None:
        self.nif = nif
        self.total = total
        super().__init__(
            f"M347 contraparte (nif={nif!r}): importe total {total} does not exceed the "
            f"{M347_THRESHOLD_EUR} threshold required by RD 1065/2007 art. 33.1",
        )


class Modelo184ShareSumError(AeatError, ValueError):
    """Modelo 184 member share percentages do not sum to exactly 100%."""

    def __init__(self, *, total: Decimal, count: int) -> None:
        self.total = total
        self.count = count
        super().__init__(
            f"M184 miembro rows: share percentages must sum to exactly 100%; got {total} across {count} rows",
        )


def validate_m347_threshold(rows: Sequence[Modelo347ContraparteRow]) -> None:
    """Enforce the Modelo 347 per-counterparty declarability threshold.

    RD 1065/2007 art. 33.1: only counterparties whose annual operations exceed
    EUR 3,005.06 are declarable. The threshold applies to the SUM of every
    operation with the same person (same NIF), aggregated across all contraparte
    rows — not to each row in isolation. A counterparty's operations may be split
    across several rows (e.g. entregas and adquisiciones), so a per-row check would
    wrongly reject a counterparty whose individual rows are each at/below the
    threshold while their annual aggregate exceeds it (a missed declaration), and
    would never apply the "same person" threshold the regulation defines.

    Raises:
        Modelo347ThresholdError: for the first counterparty (in NIF first-appearance
            order) whose AGGREGATED annual total is at or below the threshold.
    """
    totals_by_nif: dict[str, Decimal] = {}
    for row in rows:
        totals_by_nif[row.nif] = totals_by_nif.get(row.nif, Decimal("0")) + row.importe_total
    for nif, total in totals_by_nif.items():
        if total <= M347_THRESHOLD_EUR:
            raise Modelo347ThresholdError(nif=nif, total=total)


def validate_m184_member_share_sum(rows: Sequence[Modelo184MemberRow]) -> None:
    """Enforce that Modelo 184 member share percentages sum to exactly 100%.

    Only checked when at least one miembro row is present (partial sets are skipped).

    Raises:
        Modelo184ShareSumError: when the share percentages do not total exactly 100.
    """
    if not rows:
        return
    total = sum((row.porcentaje for row in rows), Decimal("0"))
    if total != Decimal("100"):
        raise Modelo184ShareSumError(total=total, count=len(rows))


__all__ = [
    "M347_THRESHOLD_EUR",
    "Modelo184MemberRow",
    "Modelo184ShareSumError",
    "Modelo232VinculadaRow",
    "Modelo347ContraparteRow",
    "Modelo347ThresholdError",
    "Modelo349OperadorRow",
    "ModeloDetailRow",
    "validate_m184_member_share_sum",
    "validate_m347_threshold",
    "validate_m349_nif_format",
]
