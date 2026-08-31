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
* ``Modelo349RectificacionRow`` — rectificación intracomunitaria for modelo 349
  (``--row rectificacion codigo_pais=DE nif_comunitario=DE123456789 razon_social=X``
  ``clave_operacion=E ejercicio=2025 periodo=2T base_rectificada=Y base_anterior=Z``)
  Used when the operator declares Tipo-2 rectification records directly.
* ``Modelo347ContraparteRow`` — contraparte declarada for modelo 347
  (``--row contraparte nif=X nombre=Y importe_Q1=Z clave_operacion=A``)
  One row per counterparty. Annual importe threshold check (> €3,005.06)
  is performed by the CLI validator, not the model, so partial row sets
  accumulate correctly before final validation.
* ``Modelo210AgrupacionRentaRow`` — one component renta in an annual
  Modelo 210 agrupación (period ``0A``). The row retains the official
  two-digit renta code and the statutory grouping keys; it is evidence
  only and never an alternate arithmetic input.

These models are the CLI boundary layer. They validate operator input
before being carried into ``detail_rows`` on the ``CalculationRevision``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, field_validator, model_validator

from ...core import MetodoValoracion, TipoOperacionVinculada, TipoVinculacion
from ...core.irnr import M210PayerMode, M210_TIPO_RENTA_CODE_PROJECTION
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.external_constants import M347_THRESHOLD_EUR
from ...core.errors.hierarchy import CadrumoError
from ...core.identity import nif_iva_format_for_country
from ...core.unit_proportion import UnitProportion

# ---------------------------------------------------------------------------
# Shared type aliases
# ---------------------------------------------------------------------------

_NifStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
_NameStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
_RequiredNameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
_IsoCountryCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=2)]
_M210OfficialTipoRentaCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=2)]


# ---------------------------------------------------------------------------
# Modelo 184 - atribucion de rentas member row
#
# Legal authority: Orden HAP/2250/2015 art. 3; Ley 35/2006 arts. 86-89.
# One row per miembro (socio / comunero / partícipe) of the entity.
# ---------------------------------------------------------------------------


type M184Clave = Literal["A", "C", "D", "E", "F", "G", "I", "J", "K"]
type M184Subclave = Literal["01", "02", "03", "04", "05", "06"]
type M184NaturalezaInmueble = Literal["1", "2"]
type M184SituacionInmueble = Literal["1", "2", "3", "4", "5"]
type M184ClaveDeclarado = Literal["N", "T", "U", "O"]


class Modelo184MemberRow(BaseModel):
    """One (member, clave, subclave) atribución row for Modelo 184.

    The socio record's own diseño repeats per clave or subclave with an
    importe declared, not per member alone (see the accepted row-shape ADR),
    so this row's identity is ``(nif, clave, subclave)`` rather than ``nif``
    alone -- the same shape 349's ``operador`` row already carries via its
    ``clave_operacion`` axis.

    Fields mirror the per-record Tipo-2 layout declared in the M184
    ``bindings/0001-bindings.toml`` atribucion_member source block.

    Parity assertions:
    * ``nif`` → ``member_tax_id`` (binding: modelo-184-member-row-nif)
    * ``nombre`` → ``member_legal_name`` (binding: modelo-184-member-row-name)
    * ``porcentaje`` → ``share_percentage`` (binding: modelo-184-member-row-share)
    * ``importe`` → ``base_imponible_assigned`` (binding: modelo-184-member-row-base-assigned)
    * ``pais`` → ``country_code`` (required; never inferred)
    * ``clave`` → ``clave`` (binding: modelo-184-member-row-clave)
    * ``subclave`` → ``subclave`` (binding: modelo-184-member-row-subclave)
    * every clave/subclave-conditional field below mirrors its own
      ``modelo-184-member-row-<field>`` binding.

    Deliberately excluded (see the accepted row-shape ADR): the clave-A
    reducción (its governing article is unresolved), provisiones-gastos-
    dificil-justificacion (computed from the entity's own régimen fact, not
    an operator-declared value), and any clave-E eligibility fact (a tracked
    gap, no representation in this tree yet).
    """

    model_config = STRICT_FROZEN_CONFIG

    row_type: Literal["miembro"] = "miembro"
    nif: _NifStr
    nombre: _NameStr = Field(default="")
    # Optional, and deliberately not defaulted to Spain. A default is an
    # INFERENCE about a fact nobody stated, and it inferred the one value that
    # makes the member domestic -- a foreign member silently declared as
    # Spanish is the direction AEAT reconciles against what that member itself
    # declared.
    #
    # Absent rather than required because the profile-driven producer has no
    # country to supply: the atribucion socio facts carry nif, name, share and
    # base and no territory at all. Demanding one here would refuse every
    # profile-resolved row while naming a fact no surface records, which is a
    # refusal nobody can answer. Recording the socio's country on the profile
    # is the fix that would let this be required.
    pais: _IsoCountryCode | None = None
    porcentaje: Decimal = Field(description="Share percentage in the entity [0, 100]")
    importe: Decimal = Field(description="Attributed income/base imponible in EUR")

    # (member, clave, subclave) repetition axis. clave is required -- the
    # socio record's own diseño has no row without one; subclave is optional
    # because claves C and E carry no subclave table at all.
    clave: M184Clave
    subclave: M184Subclave | None = None

    # Always-present-per-row facts, independent of clave.
    codigo_provincia: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2)] | None = None
    miembro_a_31_diciembre: bool | None = None
    dias_miembro: int | None = Field(default=None, ge=0, le=366)
    domicilio_fiscal: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None

    # Clave-C inmueble sub-block.
    naturaleza_inmueble: M184NaturalezaInmueble | None = None
    situacion_inmueble: M184SituacionInmueble | None = None
    referencia_catastral: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    clave_declarado: M184ClaveDeclarado | None = None
    porcentaje_titularidad_inmueble: Decimal | None = None
    dias_arrendamiento: int | None = Field(default=None, ge=0, le=366)

    # Shared clave-C/clave-D reducción field (diseño positions 109-119); the
    # clave-A branch of this same physical field is deliberately excluded.
    reduccion: Decimal | None = None

    # Clave-D subclave 03/04 rendimiento-neto fields (estimación objetiva).
    rendimiento_neto_previo_eo: Decimal | None = None
    rendimiento_neto_minorado_agricola_eo: Decimal | None = None

    @field_validator("pais")
    @classmethod
    def _pais_uppercase_alpha(cls, value: str | None) -> str | None:
        # ``pais`` is optional on THIS row for the reason recorded on the field
        # above: the profile-driven producer has no country to supply, so a
        # missing one is a declared state rather than a malformed value. The
        # shape check therefore applies to a present value only -- calling
        # ``.upper()`` on the absent case raised AttributeError instead of
        # validating anything, which is a crash rather than a refusal.
        if value is None:
            return value
        if value != value.upper() or not value.replace(" ", "").isalpha():
            raise ValueError("pais must be an uppercase two-letter ISO 3166-1 country code (e.g. ES, DE, FR)")
        return value

    @field_validator("porcentaje")
    @classmethod
    def _porcentaje_within_bounds(cls, value: Decimal) -> Decimal:
        if value < Decimal("0") or value > Decimal("100"):
            raise ValueError(f"porcentaje must be within [0, 100]; got {value}")
        return value

    @field_validator("porcentaje_titularidad_inmueble")
    @classmethod
    def _porcentaje_titularidad_within_bounds(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (value < Decimal("0") or value > Decimal("100")):
            raise ValueError(f"porcentaje_titularidad_inmueble must be within [0, 100]; got {value}")
        return value

    @field_validator("nif")
    @classmethod
    def _nif_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nif cannot be blank")
        return value.upper()

    @model_validator(mode="after")
    def _subclave_only_where_the_diseno_declares_one(self) -> Modelo184MemberRow:
        if self.subclave is not None and self.clave not in {"A", "D", "F", "G", "I", "J", "K"}:
            raise ValueError(f"clave {self.clave!r} carries no subclave table; leave subclave unset")
        return self

    @model_validator(mode="after")
    def _clave_a_reduccion_stays_blocked(self) -> Modelo184MemberRow:
        """Refuse a populated reducción on a clave-A row.

        The shared diseño field (positions 109-119) also serves claves C and
        D, whose reductions are grounded (LIRPF arts. 23 and 32.1). The
        clave-A branch is explicitly BLOCKED by the accepted row-shape ADR:
        the diseño's own citation (LIRPF art. 24.2) does not exist as such,
        and art. 26.2 is only a strong, unconfirmed candidate. Modelling
        reducción as one field (matching the diseño's own physical layout)
        makes it reachable under clave A unless refused here explicitly, so
        the block lives on the row rather than only in prose.
        """
        if self.clave == "A" and self.reduccion is not None:
            raise ValueError(
                "clave A reducción is blocked pending confirmation of its governing provision "
                "(the diseño's own LIRPF art. 24.2 citation does not exist; see the accepted "
                "row-shape ADR) -- leave reduccion unset for a clave-A row",
            )
        return self


# ---------------------------------------------------------------------------
# Modelo 232 - operacion vinculada row
#
# Legal authority: Orden HFP/816/2017 art. 3; Ley 27/2014 art. 18;
# RD 634/2015 art. 13 (LIS transfer pricing).
# One row per related-party transaction group.
# ---------------------------------------------------------------------------

# The three coded fields' value sets are AEAT's published Tablas A, C and B
# of the diseño de registro DR23200. They are declared once in ``core`` --
# see :class:`~core.TipoVinculacion`, :class:`~core.TipoOperacionVinculada`
# and :class:`~core.MetodoValoracion` -- because the registry's own
# related-party observation is typed with the same sets.


def _hydrate_m232_codigo[EnumT: StrEnum](*, field_name: str, value: object, code_set: type[EnumT]) -> EnumT | object:
    """Hydrate the operator's text into its typed DR23200 code set.

    The CLI delivers `--row vinculada k=v` as plain strings and the model is
    strict, so this is the boundary that turns a token into a member. An
    off-catalogue token is refused here rather than by the strict-instance
    check, so the message can name the codes AEAT actually publishes instead
    of only reporting the wrong type.
    """
    if not isinstance(value, str):
        return value
    try:
        return code_set(value.upper())
    except ValueError:
        accepted = ", ".join(repr(str(member)) for member in code_set)
        raise ValueError(f"{field_name} must be one of {accepted}; got {value!r}") from None


class Modelo232VinculadaRow(BaseModel):
    """One operación vinculada row for Modelo 232.

    Fields mirror the related_party_operation binding source declared in
    ``232/revisions/2018-y-siguientes/bindings/0218…0223-*.toml``.

    The three coded fields carry the closed catalogues AEAT's diseño de
    registro DR23200 publishes as Tablas A, C and B — off-catalogue codes are
    refused here rather than travelling into a fichero field that cannot hold
    them.

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
    # Required, and deliberately not defaulted to Spain. The row is built from
    # operator-supplied key-value pairs, so a default is an INFERENCE about a
    # fact the operator did not state -- and it inferred the one value that
    # makes the row domestic. A foreign member or a cross-border related-party
    # operation silently declared as Spanish is the direction AEAT reconciles
    # against what the counterparty itself declared.
    pais: _IsoCountryCode
    tipo_vinculacion: Annotated[
        TipoVinculacion | str,
        BeforeValidator(
            lambda v: _hydrate_m232_codigo(field_name="tipo_vinculacion", value=v, code_set=TipoVinculacion),
        ),
    ] = TipoVinculacion.NO_DECLARADO
    tipo_operacion: Annotated[
        TipoOperacionVinculada | str,
        BeforeValidator(
            lambda v: _hydrate_m232_codigo(field_name="tipo_operacion", value=v, code_set=TipoOperacionVinculada),
        ),
    ] = TipoOperacionVinculada.NO_DECLARADO
    metodo: Annotated[
        MetodoValoracion | str,
        BeforeValidator(lambda v: _hydrate_m232_codigo(field_name="metodo", value=v, code_set=MetodoValoracion)),
    ] = MetodoValoracion.NO_DECLARADO
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

# Country-specific NIF-IVA format patterns for Modelo 349. Every current EU
# Member State (plus post-Brexit Northern Ireland ``XI``) routes through the
# canonical :data:`cadrumo.core.identity.NIF_IVA_FORMATS` authority so the
# structural pattern lives in exactly one place (per the
# aeat-registry-bindings discipline: a per-family collection is
# derived from the core table, never hand-maintained as a parallel literal
# set). ``GB`` is the sole deliberate exception: post-Brexit UK is not an EU
# Member State, so the general IVA/invoice counterparty boundary
# (:mod:`cadrumo.domain.invoices`) correctly carries no GB structural pattern and
# falls back to its generic non-EU shape check. Modelo 349's Brexit-transition
# filing rules (:func:`validate_m349_country_prefix_context`) still permit a
# historical ``GB`` prefix for pre-2021 rectifications and the 2021 1M/1T
# transition period, so the exact GB IVA structural shape (9 or 12 digits, or
# the ``GD``/``HA`` government/health-authority forms) is retained here only,
# scoped to Modelo 349's own transition-period need.
_M349_GB_NIF_PATTERN: re.Pattern[str] = re.compile(r"^GB(\d{9}|\d{12}|GD\d{3}|HA\d{3})$")

# Valid clave de operación codes per Orden HAC/174/2020 Anexo II.
_M349_CLAVE_OPERACION = Literal["E", "M", "H", "A", "T", "S", "I", "R", "D", "C"]
_M349_RECTIFICACION_PERIODO = Literal[
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
    "1M",
    "1T",
    "2T",
    "3T",
    "4T",
]
_M349_NI_PREFIX = "XI"
_M349_GB_PREFIX = "GB"
_M349_SERVICE_CLAVES = frozenset({"S", "I"})
_M349_2021_FIRST_PERIODS = frozenset({"01", "1M", "1T"})


class Modelo349CountryPrefixContextError(CadrumoError, ValueError):
    """A Modelo 349 country prefix is invalid for the filing context."""

    def __init__(
        self,
        *,
        country_code: str,
        clave_operacion: str,
        filing_year: int,
        period: str,
        reason: str,
    ) -> None:
        """Record the prefix, the operation and the period that made it invalid."""
        self.country_code = country_code
        self.clave_operacion = clave_operacion
        self.filing_year = filing_year
        self.period = period
        self.reason = reason
        super().__init__(
            translated_message="errors.refused.modelo_349_country_prefix_context",
            context={
                "country_code": country_code,
                "clave_operacion": clave_operacion,
                "filing_year": filing_year,
                "period": period,
                "reason": reason,
            },
        )


def _validate_m349_codigo_pais(value: str) -> str:
    """Require an uppercase two-letter ISO 3166-1 country code for an M349 row."""
    if value != value.upper() or not value.replace(" ", "").isalpha():
        raise ValueError("codigo_pais must be an uppercase two-letter ISO 3166-1 country code (e.g. DE, FR, IT)")
    return value


def _validate_m349_nif_comunitario(value: str) -> str:
    """Require a non-blank comunitario NIF for an M349 row, normalised to upper case."""
    if not value.strip():
        raise ValueError("nif_comunitario cannot be blank")
    return value.upper()


class Modelo349OperadorRow(BaseModel):
    """One operador intracomunitario row for Modelo 349 (manual-entry path).

    Fields mirror the Tipo-2 operador record layout declared in
    ``349/revisions/2020-y-siguientes/bindings/0007-bindings.toml``.

    This row is used when the collectible-invoice ledger is absent and
    the operator declares intracom counterparties directly via the CLI.

    Parity assertions:
    * ``codigo_pais`` -> ``op.codigo-pais`` (record positions 76-77)
    * ``nif_comunitario`` -> ``op.nif-comunitario`` (record positions 78-92)
    * ``razon_social`` -> ``op.apellidos-razon-social`` (record positions 93-132)
    * ``clave_operacion`` -> ``op.clave-operacion`` (record position 133)
    * ``importe`` -> ``op.base-imponible`` (record positions 134-146)
    """

    model_config = STRICT_FROZEN_CONFIG

    row_type: Literal["operador"] = "operador"
    codigo_pais: _IsoCountryCode
    nif_comunitario: _NifStr
    razon_social: _RequiredNameStr
    clave_operacion: _M349_CLAVE_OPERACION
    importe: Decimal = Field(description="Base imponible o importe de la operacion en EUR")

    @field_validator("codigo_pais")
    @classmethod
    def _codigo_pais_uppercase_alpha(cls, value: str) -> str:
        return _validate_m349_codigo_pais(value)

    @field_validator("nif_comunitario")
    @classmethod
    def _nif_comunitario_not_blank(cls, value: str) -> str:
        return _validate_m349_nif_comunitario(value)

    @field_validator("importe")
    @classmethod
    def _importe_non_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise ValueError(f"importe must be non-negative per Orden HAC/174/2020 Anexo II constraint; got {value}")
        return value


class Modelo349RectificacionRow(BaseModel):
    """One rectificación row for Modelo 349 (manual-entry path).

    Fields mirror the Tipo-2 rectificación record layout declared in
    ``349/revisions/2020-y-siguientes/bindings/0007-bindings.toml``.

    Parity assertions:
    * ``codigo_pais`` -> ``op.codigo-pais`` (record positions 76-77)
    * ``nif_comunitario`` -> ``op.nif-comunitario`` (record positions 78-92)
    * ``razon_social`` -> ``op.apellidos-razon-social`` (record positions 93-132)
    * ``clave_operacion`` -> ``op.clave-operacion`` (record position 133)
    * ``ejercicio`` -> ``rect.ejercicio-rectificado`` (record positions 147-150)
    * ``periodo`` -> ``rect.periodo-rectificado`` (record positions 151-152)
    * ``base_rectificada`` -> ``rect.base-rectificada`` (record positions 153-165)
    * ``base_anterior`` -> ``rect.base-anterior`` (record positions 166-178)
    """

    model_config = STRICT_FROZEN_CONFIG

    row_type: Literal["rectificacion"] = "rectificacion"
    codigo_pais: _IsoCountryCode
    nif_comunitario: _NifStr
    razon_social: _RequiredNameStr
    clave_operacion: _M349_CLAVE_OPERACION
    ejercicio: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=4)]
    periodo: _M349_RECTIFICACION_PERIODO | str
    base_rectificada: Decimal = Field(description="Base imponible o importe rectificado en EUR")
    base_anterior: Decimal = Field(description="Base imponible declarada anteriormente en EUR")

    @field_validator("codigo_pais")
    @classmethod
    def _codigo_pais_uppercase_alpha(cls, value: str) -> str:
        return _validate_m349_codigo_pais(value)

    @field_validator("nif_comunitario")
    @classmethod
    def _nif_comunitario_not_blank(cls, value: str) -> str:
        return _validate_m349_nif_comunitario(value)

    @field_validator("periodo", mode="before")
    @classmethod
    def _periodo_uppercase(cls, value: object) -> object:
        if isinstance(value, str):
            normalised = value.strip().upper()
            if normalised not in get_args(_M349_RECTIFICACION_PERIODO):
                accepted = ", ".join(repr(member) for member in get_args(_M349_RECTIFICACION_PERIODO))
                raise ValueError(f"periodo must be one of {accepted}; got {value!r}")
            return normalised
        return value

    @field_validator("ejercicio")
    @classmethod
    def _ejercicio_four_digit_year(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("ejercicio must be a four-digit year")
        return value

    @field_validator("base_rectificada", "base_anterior")
    @classmethod
    def _bases_non_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise ValueError("rectification bases must be non-negative per Orden HAC/174/2020 Anexo II constraint")
        return value


def validate_m349_nif_format(nif: str, pais: str) -> bool:
    """Return True when ``nif`` matches the expected NIF-IVA format for ``pais``.

    Every current EU Member State (plus ``XI``) resolves its structural
    pattern from the canonical :func:`cadrumo.core.identity.nif_iva_format_for_country`
    authority. ``GB`` is validated against Modelo 349's own Brexit-transition
    pattern (see :data:`_M349_GB_NIF_PATTERN`), since post-Brexit UK carries no
    entry in the general EU NIF-IVA authority. Unsupported country prefixes
    fail closed. The NIF string must include the same two-letter country
    prefix.
    """
    normalized_pais = pais.upper()
    normalized_nif = nif.upper()
    if not normalized_nif.startswith(normalized_pais):
        return False
    if normalized_pais == "GB":
        return bool(_M349_GB_NIF_PATTERN.match(normalized_nif))
    spec = nif_iva_format_for_country(normalized_pais)
    if spec is None:
        return False
    return bool(spec.pattern.match(normalized_nif))


def validate_m349_country_prefix_context(
    *,
    country_code: str,
    clave_operacion: str,
    filing_year: int,
    period: str,
    is_rectification: bool = False,
    rectified_year: int | None = None,
    rectified_period: str | None = None,
) -> None:
    """Validate post-Brexit ``GB`` / ``XI`` rules for Modelo 349.

    AEAT's Brexit IVA instructions keep ``XI`` for Northern Ireland goods
    operations after 2021 and exclude ``S`` / ``I`` service keys from ``XI``.
    Ordinary ``GB`` rows are not valid for post-transition periods, except for
    the limited 2021 first-period and pre-2021 rectification cases named by
    the official instructions.
    """
    country = country_code.strip().upper()
    clave = clave_operacion.strip().upper()
    period_code = _normalise_m349_period(period)
    rectified_period_code = _normalise_m349_period(rectified_period) if rectified_period is not None else None

    if country == _M349_NI_PREFIX:
        if clave in _M349_SERVICE_CLAVES:
            _raise_m349_country_context_error(
                country_code=country,
                clave_operacion=clave,
                filing_year=filing_year,
                period=period_code,
                reason="Northern Ireland prefix XI is not accepted for service keys S or I",
            )
        if is_rectification and rectified_year is not None and rectified_year < 2021:
            _raise_m349_country_context_error(
                country_code=country,
                clave_operacion=clave,
                filing_year=filing_year,
                period=period_code,
                reason="pre-2021 rectifications use GB, not XI",
            )
        if not is_rectification and filing_year < 2021:
            _raise_m349_country_context_error(
                country_code=country,
                clave_operacion=clave,
                filing_year=filing_year,
                period=period_code,
                reason="XI applies only from 2021 onward",
            )
        return

    if country != _M349_GB_PREFIX:
        return

    if is_rectification:
        if rectified_year is not None and rectified_year < 2021:
            return
        if (
            rectified_year == 2021
            and rectified_period_code in _M349_2021_FIRST_PERIODS
            and clave not in _M349_SERVICE_CLAVES
        ):
            return
        _raise_m349_country_context_error(
            country_code=country,
            clave_operacion=clave,
            filing_year=filing_year,
            period=period_code,
            reason="GB is limited to pre-2021 rectifications and the 2021 1M/1T transition case",
        )

    if filing_year < 2021:
        return
    if filing_year == 2021 and period_code in _M349_2021_FIRST_PERIODS and clave not in _M349_SERVICE_CLAVES:
        return
    _raise_m349_country_context_error(
        country_code=country,
        clave_operacion=clave,
        filing_year=filing_year,
        period=period_code,
        reason="ordinary post-transition Modelo 349 rows use XI for Northern Ireland goods and exclude GB",
    )


def _normalise_m349_period(period: str | None) -> str:
    if period is None:
        return ""
    token = str(period).strip().upper()
    if len(token) == 1 and token.isdigit():
        return f"0{token}"
    return token


def _raise_m349_country_context_error(
    *,
    country_code: str,
    clave_operacion: str,
    filing_year: int,
    period: str,
    reason: str,
) -> None:
    raise Modelo349CountryPrefixContextError(
        country_code=country_code,
        clave_operacion=clave_operacion,
        filing_year=filing_year,
        period=period,
        reason=reason,
    )


def m349_nif_number_for_export(nif: str, pais: str) -> str:
    """Return the BOE NIF subfield without the separate country-code prefix.

    Modelo 349 operator records split the IVA identifier into ``codigo_pais``
    and ``nif_comunitario`` fields. The CLI accepts and validates the full
    prefixed IVA identifier for operator ergonomics, but the fixed-width export
    must write only the number part into positions 78-92.
    """
    normalized_pais = pais.upper()
    normalized_nif = nif.upper()
    if not validate_m349_nif_format(normalized_nif, normalized_pais):
        raise ValueError(
            f"nif_comunitario {nif} does not match the expected NIF-IVA format for country {pais}",
        )
    return normalized_nif[len(normalized_pais) :]


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
_M347_CLAVE_OPERACION = Literal["A", "B", "C", "D", "E", "F", "G"]


class Modelo347ContraparteRow(BaseModel):
    """One contraparte declarada row for Modelo 347.

    Fields mirror the per-counterparty Tipo-2 record layout declared in
    ``347/revisions/2011-2024``.

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
# Modelo 210 - annual grouped-renta rows
#
# Orden HAC/56/2024 art. 4.1 substitutes the M210 grouping rule in Orden
# EHA/3316/2010 art. 2: grouped rents share one official renta code, rate and
# (where applicable) property/right; one payer is required except for code 35;
# components must not offset one another. Annual 0A is the lease/sublease
# grouping period, represented by official codes 01 and 35.
# ---------------------------------------------------------------------------

_M210_ANNUAL_AGRUPACION_CODES = frozenset({"01", "35"})


class Modelo210AgrupacionRentaRow(BaseModel):
    """One non-offsetting component renta in an annual Modelo 210 grouping.

    The record deliberately carries the official M210 code rather than the
    rate-concept token used by the formula engine. Several official codes map to
    the same conceptual rate, but Article 2's grouping test is on the official
    code itself. ``source_id`` remains stable across persistence and can name a
    manual supporting record now or a classified ledger transaction later.

    Rows evidence the legality of a grouped declaration. They do not sum into a
    casilla: the registry-owned manual M210 formula remains the sole arithmetic
    path.
    """

    model_config = STRICT_FROZEN_CONFIG

    row_type: Literal["agrupacion_renta"] = "agrupacion_renta"
    source_id: _RequiredNameStr
    tipo_renta_code: _M210OfficialTipoRentaCode
    importe: Decimal = Field(ge=Decimal("0"), description="Non-negative individual renta amount in EUR")
    tipo_gravamen: UnitProportion = Field(
        description="Applicable tax-rate fraction (for example, 0.24 for 24%)",
    )
    pagador_mode: M210PayerMode
    pagador_id: _RequiredNameStr | None = None
    deriva_de_bien_derecho: bool
    bien_derecho_id: _RequiredNameStr | None = None

    @field_validator("tipo_renta_code")
    @classmethod
    def _tipo_renta_code_is_registry_declared(cls, value: str) -> str:
        if value not in M210_TIPO_RENTA_CODE_PROJECTION:
            accepted = ", ".join(sorted(M210_TIPO_RENTA_CODE_PROJECTION))
            raise ValueError(
                f"tipo_renta_code must be a registry-declared Modelo 210 official code; "
                f"got {value!r}; accepted codes: {accepted}"
            )
        return value

    @model_validator(mode="after")
    def _statutory_identity_contract(self) -> Modelo210AgrupacionRentaRow:
        if self.tipo_renta_code == "35":
            if self.pagador_mode is not M210PayerMode.MULTIPLE_PAYERS_CODE_35:
                raise ValueError("tipo_renta_code '35' requires the explicit multiple-payers code-35 mode")
        elif self.pagador_mode is not M210PayerMode.SINGLE_PAYER:
            raise ValueError("only tipo_renta_code '35' may use the multiple-payers code-35 mode")
        elif self.pagador_id is None:
            raise ValueError("single-payer grouped renta rows require a non-blank pagador_id")

        if self.deriva_de_bien_derecho:
            if self.bien_derecho_id is None:
                raise ValueError("a renta derived from a bien or derecho requires bien_derecho_id")
        elif self.bien_derecho_id is not None:
            raise ValueError("bien_derecho_id is only valid when deriva_de_bien_derecho is true")
        return self


class Modelo210AgrupacionRentaRowsError(CadrumoError, ValueError):
    """A Modelo 210 annual grouped-renta set violates Article 2 compatibility."""

    def __init__(self, *, reason: str, detail: str) -> None:
        """Record which Article 2 compatibility rule the row set broke."""
        self.reason = reason
        self.detail = detail
        super().__init__(f"Modelo 210 annual agrupación rows are invalid ({reason}): {detail}")


def _require_nonempty_agrupacion(rows: Sequence[Modelo210AgrupacionRentaRow]) -> None:
    if not rows:
        raise Modelo210AgrupacionRentaRowsError(
            reason="empty_group",
            detail="period 0A requires at least one grouped-renta component",
        )


def _require_unique_agrupacion_source_ids(rows: Sequence[Modelo210AgrupacionRentaRow]) -> None:
    source_ids = tuple(row.source_id for row in rows)
    if len(set(source_ids)) != len(source_ids):
        raise Modelo210AgrupacionRentaRowsError(
            reason="duplicate_source_id",
            detail="each grouped-renta component must carry a unique stable source_id",
        )


def _resolve_single_agrupacion_tipo_renta_code(rows: Sequence[Modelo210AgrupacionRentaRow]) -> str:
    codes = {row.tipo_renta_code for row in rows}
    if len(codes) != 1:
        raise Modelo210AgrupacionRentaRowsError(
            reason="mixed_tipo_renta_code",
            detail=f"components use more than one official code: {', '.join(sorted(codes))}",
        )
    return next(iter(codes))


def _require_annual_agrupacion_code(code: str) -> None:
    if code not in _M210_ANNUAL_AGRUPACION_CODES:
        raise Modelo210AgrupacionRentaRowsError(
            reason="annual_code_not_lease_or_sublease",
            detail=f"period 0A is limited to lease/sublease grouped rentas (01 or 35), got {code}",
        )


def _require_single_agrupacion_tipo_gravamen(rows: Sequence[Modelo210AgrupacionRentaRow]) -> None:
    rates = {row.tipo_gravamen for row in rows}
    if len(rates) != 1:
        raise Modelo210AgrupacionRentaRowsError(
            reason="mixed_tipo_gravamen",
            detail=f"components use more than one tax rate: {', '.join(str(rate) for rate in sorted(rates))}",
        )


def _require_shared_agrupacion_bien_derecho(rows: Sequence[Modelo210AgrupacionRentaRow]) -> None:
    if not all(row.deriva_de_bien_derecho and row.bien_derecho_id is not None for row in rows):
        raise Modelo210AgrupacionRentaRowsError(
            reason="missing_bien_derecho",
            detail="annual lease/sublease grouping requires an identified shared bien or derecho",
        )
    bienes_derechos = {row.bien_derecho_id for row in rows}
    if len(bienes_derechos) != 1:
        raise Modelo210AgrupacionRentaRowsError(
            reason="mixed_bien_derecho",
            detail="components derive from more than one bien or derecho",
        )


def _validate_agrupacion_payer_grouping(rows: Sequence[Modelo210AgrupacionRentaRow], code: str) -> None:
    if code == "35":
        if any(row.pagador_mode is not M210PayerMode.MULTIPLE_PAYERS_CODE_35 for row in rows):
            raise Modelo210AgrupacionRentaRowsError(
                reason="code_35_payer_mode",
                detail="code 35 requires the explicit multiple-payers mode on every component",
            )
        return

    payer_ids = {row.pagador_id for row in rows}
    if None in payer_ids or len(payer_ids) != 1:
        raise Modelo210AgrupacionRentaRowsError(
            reason="mixed_pagador",
            detail="non-35 grouped rentas must proceed from one identified payer",
        )


def validate_m210_agrupacion_renta_rows(rows: Sequence[Modelo210AgrupacionRentaRow]) -> None:
    """Validate the complete M210 annual ``0A`` grouped-renta row set.

    The validator makes the statutory grouping facts explicit: at least one
    component; one official renta code, rate, and identified property/right;
    and one payer unless the set declares the explicit code-35 multi-payer
    exception. Individual row validation forbids negative components, so no
    component can offset another in the group.

    Raises:
        Modelo210AgrupacionRentaRowsError: if the supplied row set cannot be a
            lawful annual grouping.
    """
    _require_nonempty_agrupacion(rows)
    _require_unique_agrupacion_source_ids(rows)
    code = _resolve_single_agrupacion_tipo_renta_code(rows)
    _require_annual_agrupacion_code(code)
    _require_single_agrupacion_tipo_gravamen(rows)
    _require_shared_agrupacion_bien_derecho(rows)
    _validate_agrupacion_payer_grouping(rows, code)


# ---------------------------------------------------------------------------
# Discriminated union — single type accepted by the CLI --row argument
# ---------------------------------------------------------------------------

ModeloDetailRow = (
    Modelo184MemberRow
    | Modelo232VinculadaRow
    | Modelo349OperadorRow
    | Modelo349RectificacionRow
    | Modelo347ContraparteRow
    | Modelo210AgrupacionRentaRow
)


# ---------------------------------------------------------------------------
# Statutory cross-row / threshold validations (domain-owned)
# ---------------------------------------------------------------------------


class Modelo347ThresholdError(CadrumoError, ValueError):
    """A Modelo 347 contraparte row falls at or below the declarability threshold."""

    def __init__(self, *, nif: str, total: Decimal) -> None:
        """Record the counterparty and the total that fell short of the threshold."""
        self.nif = nif
        self.total = total
        super().__init__(
            f"M347 contraparte (nif={nif!r}): importe total {total} does not exceed the "
            f"{M347_THRESHOLD_EUR} threshold required by RD 1065/2007 art. 33.1",
        )


class Modelo184ShareSumError(CadrumoError, ValueError):
    """Modelo 184 member share percentages do not sum to exactly 100%."""

    def __init__(self, *, total: Decimal, count: int) -> None:
        """Record the share total the miembro rows reached, and over how many rows."""
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
    "M184Clave",
    "M184ClaveDeclarado",
    "M184NaturalezaInmueble",
    "M184SituacionInmueble",
    "M184Subclave",
    "Modelo184MemberRow",
    "Modelo184ShareSumError",
    "Modelo210AgrupacionRentaRow",
    "Modelo210AgrupacionRentaRowsError",
    "Modelo232VinculadaRow",
    "Modelo347ContraparteRow",
    "Modelo347ThresholdError",
    "Modelo349CountryPrefixContextError",
    "Modelo349OperadorRow",
    "Modelo349RectificacionRow",
    "ModeloDetailRow",
    "m349_nif_number_for_export",
    "validate_m184_member_share_sum",
    "validate_m210_agrupacion_renta_rows",
    "validate_m347_threshold",
    "validate_m349_country_prefix_context",
    "validate_m349_nif_format",
]
