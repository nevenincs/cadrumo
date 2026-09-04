"""Capital-goods IVA deduction-regularización register and annual/disposal computes.

Models the LIVA arts. 107-110 regularización de deducciones por bienes de
inversión: a durable, cross-year :class:`BienesInversionIvaRegister`, one
:class:`BienInversionIvaRecord` per capital good, the pure art-109
:class:`RegularizacionAnualResult` computed for each supplied definitive prorrata
percentage, and the pure art-110 :class:`RegularizacionTransmisionResult` computed
for a good disposed of during its regularisation window.

The register is a taxpayer-fact store (owned goods, acquisition year, cuota
soportada, initial definitive prorrata percentage), sibling to
:mod:`domain.iva_compensation`; the regulatory constants it consumes (the
4/9-year windows, the over-10-point gate, and the /5, /10 divisors) live in the
central authoring surface :mod:`core.external_constants`, grounded verbatim
in the bundled consolidated LIVA corpus.

Register-wide projection returns :class:`RegistroRegularizacionResult` for the
ordinary annual art-109 path: each art-108-eligible in-window good (not yet
disposed of) is either computed into the proposed Modelo 303 casilla 43 / Modelo
390 regularización value when the current-year definitive prorrata fact is
available, or reported as pending that separate input. A good recorded as
disposed of in the projected year routes instead through
:func:`compute_registro_transmisiones`, which folds the art-110 single ("única")
regularización for every remaining window year into the same casilla-43 total;
art-110 carries no pending state — the disposal regime and acquisition-year facts
are already on the record, so every disposed good is always computed. This domain
module does not read the secure-object store or derive prorrata; application and
persistence layers supply those facts.

See Also:
    :mod:`application.bienes_inversion`
        Profile-scoped service that declares and lists the persisted register.
    :mod:`adapters.persistence.profile.bienes_inversion`
        FINANCIAL secure-object repository that stores the register singleton.
    :mod:`application.calculations`
        Source resolver and advisory projection surfaces for the
        ``bienes_inversion_regularizacion`` calculation source.
    :mod:`domain.iva`
        Legal prorrata substrate that supplies the separate definitive
        percentage input; usage ratios are not a substitute.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.decimal.constants import HUNDRED
from ...core.errors.hierarchy import CadrumoError as _CadrumoError
from ...core.external_constants import (
    IVA_BIEN_INVERSION_INMUEBLE_DIVISOR as _IVA_BIEN_INVERSION_INMUEBLE_DIVISOR,
)
from ...core.external_constants import (
    IVA_BIEN_INVERSION_INMUEBLE_VENTANA_ANOS as _IVA_BIEN_INVERSION_INMUEBLE_VENTANA_ANOS,
)
from ...core.external_constants import (
    IVA_BIEN_INVERSION_MUEBLE_DIVISOR as _IVA_BIEN_INVERSION_MUEBLE_DIVISOR,
)
from ...core.external_constants import (
    IVA_BIEN_INVERSION_MUEBLE_VENTANA_ANOS as _IVA_BIEN_INVERSION_MUEBLE_VENTANA_ANOS,
)
from ...core.external_constants import (
    IVA_BIEN_INVERSION_REGULARIZACION_UMBRAL_PUNTOS as _IVA_BIEN_INVERSION_REGULARIZACION_UMBRAL_PUNTOS,
)
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents as _quantize
from ...core.percentage import Percentage


class BienInversionRecordError(_CadrumoError):
    """Raised when a bien-de-inversión register record is structurally invalid."""


class BienInversionValidationError(BienInversionRecordError, ValueError):
    """Raised when a bien-de-inversión record fails Pydantic validation."""


BIENES_INVERSION_SCHEMA_VERSION = "2"
"""Forward-compatible schema version stamped onto every record in this module."""

#: Lowest calendar year the register accepts; LIVA art. 107 predates it, but a
#: pre-2000 acquisition can never be in-window for any modelled filing year.
_MIN_ACQUISITION_YEAR = 2000


class BienInversionKind(StrEnum):
    """LIVA art. 107 regularisation-window taxonomy for a capital good.

    Distinct from the LIS art. 12 :class:`domain.contribuyente.assets.AssetClass`
    amortization taxonomy: this axis is the mueble-4yr / inmueble-9yr LIVA
    regularisation window (art. 107.Uno vs art. 107.Tres), not a depreciation
    coefficient family.
    """

    MUEBLE = "mueble"
    INMUEBLE = "inmueble"

    @property
    def ventana_anos(self) -> int:
        """Count of following calendar years in the art-107 regularisation window."""
        if self is BienInversionKind.INMUEBLE:
            return _IVA_BIEN_INVERSION_INMUEBLE_VENTANA_ANOS
        return _IVA_BIEN_INVERSION_MUEBLE_VENTANA_ANOS

    @property
    def divisor(self) -> Decimal:
        """Art-109 per-year regularisation divisor (5 mueble / 10 inmueble)."""
        if self is BienInversionKind.INMUEBLE:
            return _IVA_BIEN_INVERSION_INMUEBLE_DIVISOR
        return _IVA_BIEN_INVERSION_MUEBLE_DIVISOR


class BienInversionDisposalRegime(StrEnum):
    """LIVA art. 110 disposal (transmisión) regime.

    ``SUJETA_NO_EXENTA`` imputes the remaining window years at a 100% deduction
    percentage (capped at the amount originally deducted); ``EXENTA_O_NO_SUJETA``
    imputes them at 0%.
    """

    SUJETA_NO_EXENTA = "sujeta_no_exenta"
    EXENTA_O_NO_SUJETA = "exenta_o_no_sujeta"


class BienInversionDisposal(BaseModel):
    """Optional art-110 disposal event carried on a register record.

    Attributes:
        year: Calendar year the good was transmitted, within the window.
        regime: :class:`BienInversionDisposalRegime` of the transmission.
    """

    model_config = _STRICT_FROZEN_CONFIG

    year: int = Field(ge=_MIN_ACQUISITION_YEAR, le=2099)
    regime: BienInversionDisposalRegime


class BienInversionIvaRecord(BaseModel):
    """One capital good tracked for LIVA arts. 107-110 IVA regularización.

    Strict, frozen, no extra fields. Carries the taxpayer facts the art-109
    annual compute needs (acquisition year, cuota soportada, initial-year
    definitive prorrata percentage, mueble/inmueble window) plus an optional
    cross-reference to an :class:`domain.contribuyente.assets.AssetRecord`
    to avoid double data-entry, and the art-108 concept-eligibility flag.

    Attributes:
        identifier: Stable natural key chosen by the operator.
        description: Free-text human description.
        acquisition_year: Calendar year the good was acquired / put into use.
        cuota_soportada: Total input IVA (cuota repercutida) borne on the
            acquisition. Strictly positive.
        prorrata_inicial_pct: Definitive deduction percentage (0-100) that
            prevailed in the acquisition year — the baseline art-109 compares
            each later year's definitive percentage against.
        kind: :class:`BienInversionKind` — the mueble/inmueble regularisation
            window.
        art108_elegible: Whether the good qualifies as a bien de inversión under
            LIVA art. 108 (value at/above the escaso-valor threshold, normally
            used over a year as an instrument of work). ``False`` marks a good
            the operator recorded but which is excluded from regularisation.
        asset_record_ref: Optional identifier of the sibling
            :class:`domain.contribuyente.assets.AssetRecord`. Cross-reference
            only; this register — not the assets ledger — is the LIVA authority.
        disposal: Optional :class:`BienInversionDisposal` (art-110). When present,
            the good is routed through the art-110 single ("única")
            regularización (:func:`compute_registro_transmisiones`) in its
            disposal year instead of the ordinary annual art-109 comparison.
        schema_version: Forward-compatible schema version. ``"1"``.
    """

    model_config = _STRICT_FROZEN_CONFIG

    identifier: str = Field(min_length=1)
    description: str = Field(min_length=1)
    acquisition_year: int = Field(ge=_MIN_ACQUISITION_YEAR, le=2099)
    cuota_soportada: Decimal = Field(gt=Decimal("0"))
    prorrata_inicial_pct: Percentage
    kind: BienInversionKind
    art108_elegible: bool = True
    asset_record_ref: str | None = Field(default=None, min_length=1)
    acquisition_ledger_id: str = Field(min_length=1, max_length=128)
    prorrata_sector_id: str | None = Field(default=None, min_length=1, max_length=64)
    disposal: BienInversionDisposal | None = None
    schema_version: str = BIENES_INVERSION_SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than :data:`BIENES_INVERSION_SCHEMA_VERSION`."""
        if value != BIENES_INVERSION_SCHEMA_VERSION:
            raise BienInversionValidationError(f"unsupported BienInversionIvaRecord schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_disposal_window(self) -> BienInversionIvaRecord:
        """A disposal year cannot precede acquisition."""
        if self.disposal is not None and self.disposal.year < self.acquisition_year:
            raise BienInversionValidationError("disposal year cannot precede acquisition year")
        return self

    @property
    def deduccion_efectuada(self) -> Decimal:
        """Deduction actually made in the acquisition year (cuota × prorrata inicial)."""
        return _quantize(self.cuota_soportada * self.prorrata_inicial_pct / HUNDRED)

    def is_within_regularization_window(self, regularization_year: int) -> bool:
        """Whether ``regularization_year`` is one of the art-107 following window years.

        The window is the ``ventana_anos`` calendar years *following* acquisition
        (art. 107.Uno "los cuatro años naturales siguientes" / art. 107.Tres "los
        nueve años naturales siguientes"). The acquisition year itself is excluded:
        that is the year the original deduction was made, not a regularisation year.
        """
        last_year = self.acquisition_year + self.kind.ventana_anos
        return self.acquisition_year < regularization_year <= last_year

    def remaining_regularization_years(self, disposal_year: int) -> int:
        """Count of art-110 "años que resten" from ``disposal_year`` to window end.

        Art. 110.Uno: "se efectuará una regularización única por el tiempo de dicho
        período que quede por transcurrir", counting the disposal year itself and
        every later year through the last window year (inclusive). A disposal in
        the acquisition year itself counts the full window (the deduction was never
        regularised, so every following window year remains to transcur).
        """
        last_year = self.acquisition_year + self.kind.ventana_anos
        first_pending_year = max(disposal_year, self.acquisition_year + 1)
        return max(0, last_year - first_pending_year + 1)


class RegularizacionDireccion(StrEnum):
    """Direction of an art-109 annual regularisation quotient.

    ``INGRESO`` — the acquisition-year deduction exceeded what the current year's
    percentage would allow: an ingreso complementario (repay). ``DEDUCCION`` — the
    current year allows more: a deducción complementaria (claim more). ``NINGUNA`` —
    the over-10-point gate did not fire, or the good is out of window.
    """

    INGRESO = "ingreso"
    DEDUCCION = "deduccion"
    NINGUNA = "ninguna"


class RegularizacionAnualResult(BaseModel):
    """Outcome of the art-109 single-good annual regularización compute.

    Attributes:
        aplica: Whether the art-107 over-10-point gate fired (a regularisation is due).
        diferencia_puntos: Absolute percentage-point difference between the current
            year's definitive percentage and the acquisition-year one.
        divisor: Art-109 divisor applied (5 mueble / 10 inmueble).
        importe: The regularisation quotient (deducción efectuada − deducción que
            procedería) ÷ divisor, rounded to cents. Positive = ingreso
            complementario, negative = deducción complementaria; ``0.00`` when the
            gate did not fire.
        direccion: :class:`RegularizacionDireccion` describing ``importe``'s sign.
    """

    model_config = _STRICT_FROZEN_CONFIG

    aplica: bool
    diferencia_puntos: Decimal
    divisor: Decimal
    importe: Decimal
    direccion: RegularizacionDireccion


def compute_regularizacion_anual(
    *,
    cuota_soportada: Decimal,
    prorrata_inicial_pct: Decimal,
    prorrata_anio_pct: Decimal,
    kind: BienInversionKind,
) -> RegularizacionAnualResult:
    """Compute the LIVA art-109 annual regularización for one capital good.

    Implements the art-109 procedure verbatim:

    1.º the deduction that *would apply* if the cuota were borne in the year
        considered — ``cuota_soportada × prorrata_anio_pct``;
    2.º subtract it from the deduction actually made in the acquisition year —
        ``cuota_soportada × prorrata_inicial_pct``;
    3.º divide the (positive or negative) difference by 5, or by 10 for land and
        buildings; the quotient is the ingreso / deducción complementaria.

    The art-107.Uno gate applies: the regularisation is practised only when the
    absolute difference between the two definitive percentages is *strictly greater
    than* :data:`core.external_constants.IVA_BIEN_INVERSION_REGULARIZACION_UMBRAL_PUNTOS`
    (10 points). When
    the gate does not fire, ``importe`` is ``0.00`` and ``direccion`` is
    :attr:`RegularizacionDireccion.NINGUNA`.

    Both percentages are supplied as inputs; deriving the current-year definitive
    percentage (LIVA arts. 102-106) is a separate registry/materialisation concern
    and this function stays independent of it.

    Args:
        cuota_soportada: Total input IVA borne on acquisition (strictly positive).
        prorrata_inicial_pct: Definitive deduction percentage of the acquisition
            year (0-100).
        prorrata_anio_pct: Definitive deduction percentage of the regularisation
            year (0-100).
        kind: :class:`BienInversionKind` selecting the divisor.

    Returns:
        A :class:`RegularizacionAnualResult`.

    Raises:
        BienInversionValidationError: On a non-positive cuota or an out-of-range
            percentage.
    """
    if cuota_soportada <= Decimal("0"):
        raise BienInversionValidationError("cuota_soportada must be strictly positive")
    for label, pct in (("prorrata_inicial_pct", prorrata_inicial_pct), ("prorrata_anio_pct", prorrata_anio_pct)):
        if pct < Decimal("0") or pct > HUNDRED:
            raise BienInversionValidationError(f"{label} must be between 0 and 100")

    diferencia_puntos = abs(prorrata_anio_pct - prorrata_inicial_pct)
    divisor = kind.divisor
    if diferencia_puntos <= _IVA_BIEN_INVERSION_REGULARIZACION_UMBRAL_PUNTOS:
        return RegularizacionAnualResult(
            aplica=False,
            diferencia_puntos=diferencia_puntos,
            divisor=divisor,
            importe=Decimal("0.00"),
            direccion=RegularizacionDireccion.NINGUNA,
        )

    deduccion_efectuada = cuota_soportada * prorrata_inicial_pct / HUNDRED
    deduccion_procedente = cuota_soportada * prorrata_anio_pct / HUNDRED
    importe = _quantize((deduccion_efectuada - deduccion_procedente) / divisor)
    if importe > Decimal("0"):
        direccion = RegularizacionDireccion.INGRESO
    elif importe < Decimal("0"):
        direccion = RegularizacionDireccion.DEDUCCION
    else:
        direccion = RegularizacionDireccion.NINGUNA
    return RegularizacionAnualResult(
        aplica=True,
        diferencia_puntos=diferencia_puntos,
        divisor=divisor,
        importe=importe,
        direccion=direccion,
    )


class RegularizacionTransmisionResult(BaseModel):
    """Outcome of the art-110 single-final ("única") disposal regularización.

    Attributes:
        regime: :class:`BienInversionDisposalRegime` applied.
        anos_restantes: Count of window years — the disposal year plus every later
            year through window expiry — the single regularización covers
            (art. 110.Uno "el tiempo de dicho período que quede por transcurrir").
        divisor: Art-109 divisor applied (5 mueble / 10 inmueble), carried into the
            art-110 single computation per art. 110.Uno's cross-reference to the
            art-109 procedure.
        importe_sin_limite: The signed quotient before the regla-1ª cap, i.e.
            ``(deducción efectuada − deducción imputada) × años_restantes ÷ divisor``.
        importe: ``importe_sin_limite`` after applying the regla-1ª cap — a
            negative (DEDUCCION / additional-deduction) result never exceeds
            ``-cuota_devengada_entrega`` in magnitude, when supplied; equals
            ``importe_sin_limite`` unqualified for regla 2ª (no cap applies there)
            and for a non-negative regla-1ª result.
        direccion: :class:`RegularizacionDireccion` describing ``importe``'s sign.
        capped: Whether the regla-1ª cap reduced ``importe_sin_limite``'s magnitude.
    """

    model_config = _STRICT_FROZEN_CONFIG

    regime: BienInversionDisposalRegime
    anos_restantes: int
    divisor: Decimal
    importe_sin_limite: Decimal
    importe: Decimal
    direccion: RegularizacionDireccion
    capped: bool


def compute_regularizacion_transmision(
    *,
    cuota_soportada: Decimal,
    prorrata_inicial_pct: Decimal,
    anos_restantes: int,
    kind: BienInversionKind,
    regime: BienInversionDisposalRegime,
    cuota_devengada_entrega: Decimal | None = None,
) -> RegularizacionTransmisionResult:
    """Compute the LIVA art-110 single ("única") disposal regularización.

    Art. 110.Uno: on a disposal (entrega) during the regularisation window, a
    SINGLE regularización is practised for the window time remaining (the disposal
    year plus every later window year), applying the art-109 procedure once over
    that whole remaining span rather than year by year:

    Regla 1.ª (entrega sujeta y no exenta — or an exempt/non-subject entrega that
    itself originates a deduction right, e.g. exports / intra-EU supplies, per the
    art. 110.Uno final paragraph): the good is deemed used 100% in
    deduction-generating operations for every remaining year, which typically
    yields a negative (additional-deduction) quotient since the imputed 100%
    usually exceeds the acquisition-year percentage. Art. 110.Uno caps the
    MAGNITUDE of that additional deduction at the cuota devengada on the disposal
    itself ("no será deducible la diferencia ... y el importe de la cuota
    devengada por la entrega del bien") — applied via ``cuota_devengada_entrega``
    when supplied.

    Regla 2.ª (entrega exenta o no sujeta, without its own deduction right — the
    ordinary case): the good is deemed used 0% for every remaining year. No cap
    applies (the result is a repayment of previously-taken deduction, never an
    additional one).

    Both reglas apply the SAME art-109 quotient — (deducción efectuada − deducción
    imputada) ÷ divisor — but multiply the per-year difference by
    ``anos_restantes`` before dividing, since art. 110.Uno folds every remaining
    window year into one regularización rather than repeating art-109 per year.
    Unlike :func:`compute_regularizacion_anual`, art. 110 carries no
    diferencia-de-puntos gate: a disposal always triggers the single
    regularización regardless of how close the imputed percentage is to the
    acquisition-year one (the disposal itself, not a percentage drift, is what
    obliges it).

    Args:
        cuota_soportada: Total input IVA borne on acquisition (strictly positive).
        prorrata_inicial_pct: Definitive deduction percentage of the acquisition
            year (0-100).
        anos_restantes: Count of remaining window years the single regularización
            covers; see :meth:`BienInversionIvaRecord.remaining_regularization_years`.
            Must be strictly positive (a disposal outside the window has nothing
            left to regularise and is a caller-level concern, not this function's).
        kind: :class:`BienInversionKind` selecting the divisor.
        regime: :class:`BienInversionDisposalRegime` selecting regla 1ª (100%
            imputation, capped) or regla 2ª (0% imputation, uncapped).
        cuota_devengada_entrega: The cuota devengada on the disposal itself,
            applied as the regla-1ª cap. ``None`` leaves regla 1ª uncapped (the
            caller has not supplied the disposal's own cuota devengada yet).

    Returns:
        A :class:`RegularizacionTransmisionResult`.

    Raises:
        BienInversionValidationError: On a non-positive cuota, an out-of-range
            percentage, a non-positive ``anos_restantes``, or a negative
            ``cuota_devengada_entrega``.
    """
    if cuota_soportada <= Decimal("0"):
        raise BienInversionValidationError("cuota_soportada must be strictly positive")
    if prorrata_inicial_pct < Decimal("0") or prorrata_inicial_pct > HUNDRED:
        raise BienInversionValidationError("prorrata_inicial_pct must be between 0 and 100")
    if anos_restantes <= 0:
        raise BienInversionValidationError("anos_restantes must be strictly positive")
    if cuota_devengada_entrega is not None and cuota_devengada_entrega < Decimal("0"):
        raise BienInversionValidationError("cuota_devengada_entrega must not be negative")

    prorrata_imputada_pct = HUNDRED if regime is BienInversionDisposalRegime.SUJETA_NO_EXENTA else Decimal("0")
    divisor = kind.divisor
    deduccion_efectuada = cuota_soportada * prorrata_inicial_pct / HUNDRED
    deduccion_imputada = cuota_soportada * prorrata_imputada_pct / HUNDRED
    importe_sin_limite = _quantize((deduccion_efectuada - deduccion_imputada) * anos_restantes / divisor)

    # Regla 1.ª (sujeta y no exenta) imputes 100% usage, so `importe_sin_limite`
    # is typically negative (deducción complementaria — additional deduction
    # claimed). Art. 110.Uno caps that ADDITIONAL DEDUCTION at the cuota devengada
    # on the disposal itself ("no será deducible la diferencia entre la cantidad
    # que resulte ... y el importe de la cuota devengada por la entrega del bien").
    # The cap therefore bounds the MAGNITUDE of a negative (DEDUCCION) result;
    # regla 2.ª and a non-negative regla-1.ª result are never capped.
    importe = importe_sin_limite
    capped = False
    if (
        regime is BienInversionDisposalRegime.SUJETA_NO_EXENTA
        and cuota_devengada_entrega is not None
        and importe_sin_limite < Decimal("0")
        and -importe_sin_limite > cuota_devengada_entrega
    ):
        importe = -cuota_devengada_entrega
        capped = True

    if importe > Decimal("0"):
        direccion = RegularizacionDireccion.INGRESO
    elif importe < Decimal("0"):
        direccion = RegularizacionDireccion.DEDUCCION
    else:
        direccion = RegularizacionDireccion.NINGUNA

    return RegularizacionTransmisionResult(
        regime=regime,
        anos_restantes=anos_restantes,
        divisor=divisor,
        importe_sin_limite=importe_sin_limite,
        importe=importe,
        direccion=direccion,
        capped=capped,
    )


class BienesInversionIvaRegister(BaseModel):
    """Encrypted JSON document holding the per-good IVA regularización register.

    Attributes:
        schema_version: Forward-compatible schema version. ``"1"``.
        records: Tuple of :class:`BienInversionIvaRecord` rows.
    """

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = BIENES_INVERSION_SCHEMA_VERSION
    records: tuple[BienInversionIvaRecord, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than :data:`BIENES_INVERSION_SCHEMA_VERSION`."""
        if value != BIENES_INVERSION_SCHEMA_VERSION:
            raise BienInversionValidationError(f"unsupported BienesInversionIvaRegister schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _identifiers_unique(self) -> BienesInversionIvaRegister:
        """Reject a register that carries two records with the same identifier."""
        seen = [record.identifier for record in self.records]
        if len(seen) != len(set(seen)):
            raise BienInversionValidationError("register carries duplicate record identifiers")
        ledger_ids = [record.acquisition_ledger_id for record in self.records]
        if len(ledger_ids) != len(set(ledger_ids)):
            raise BienInversionValidationError("register carries duplicate acquisition_ledger_id values")
        return self

    def in_window_records(self, regularization_year: int) -> tuple[BienInversionIvaRecord, ...]:
        """Return each art-108-eligible :class:`BienInversionIvaRecord` in-window for the year.

        A good disposed of AT OR BEFORE ``regularization_year`` is excluded: art.
        110.Uno's single ("única") regularización supersedes the ordinary annual
        art-109 comparison from the disposal year onward — see
        :meth:`disposed_records` and :func:`compute_registro_transmisiones` for the
        disposal path.
        """
        return tuple(
            record
            for record in self.records
            if record.art108_elegible
            and record.is_within_regularization_window(regularization_year)
            and (record.disposal is None or record.disposal.year > regularization_year)
        )

    def disposed_records(self, disposal_year: int) -> tuple[BienInversionIvaRecord, ...]:
        """Return each art-108-eligible good whose art-110 disposal falls in ``disposal_year``.

        Only a disposal that still leaves window time to regularise is included
        (:meth:`BienInversionIvaRecord.remaining_regularization_years` strictly
        positive); a disposal recorded outside the window has nothing left to
        regularise under art. 110.
        """
        return tuple(
            record
            for record in self.records
            if record.art108_elegible
            and record.disposal is not None
            and record.disposal.year == disposal_year
            and record.remaining_regularization_years(disposal_year) > 0
        )


class RegistroRegularizacionRow(BaseModel):
    """One good's contribution to the annual register-wide regularización.

    Attributes:
        identifier: The record identifier.
        kind: :class:`BienInversionKind` of the good.
        prorrata_anio_pct: The definitive percentage supplied for the year, or
            ``None`` when the caller could not supply it (the good is reported but
            not yet computed because the prorrata-definitiva input is absent).
        result: The :class:`RegularizacionAnualResult`, or ``None`` when
            ``prorrata_anio_pct`` was absent.
    """

    model_config = _STRICT_FROZEN_CONFIG

    identifier: str
    kind: BienInversionKind
    prorrata_sector_id: str | None
    prorrata_anio_pct: Decimal | None
    result: RegularizacionAnualResult | None


class BienesInversionSectorContribution(BaseModel):
    """Immutable one-asset regularisation contribution owned by its register sector."""

    model_config = _STRICT_FROZEN_CONFIG

    asset_id: str
    prorrata_sector_id: str | None
    amount: Decimal


class InvestmentAssetAcquisitionLink(BaseModel):
    """Canonical reciprocal edge between one investment IVA fact and one asset."""

    model_config = _STRICT_FROZEN_CONFIG

    ledger_id: str = Field(min_length=1, max_length=128)
    transaction_date: date
    deduction_fact_kind: IvaDeductionFactKind
    investment_asset_id: str = Field(min_length=1, max_length=128)
    prorrata_sector_id: str | None = Field(default=None, min_length=1, max_length=64)


class _InvestmentAssetLink(Protocol):
    @property
    def ledger_id(self) -> str: ...

    @property
    def transaction_date(self) -> date: ...

    @property
    def deduction_fact_kind(self) -> IvaDeductionFactKind | None: ...

    @property
    def investment_asset_id(self) -> str | None: ...

    @property
    def prorrata_sector_id(self) -> str | None: ...


class RegistroRegularizacionResult(BaseModel):
    """Register-wide art-109 regularización projection for one year.

    Attributes:
        regularizacion_year: The year the projection covers.
        rows: Per-good :class:`RegistroRegularizacionRow` entries for every
            in-window, art-108-eligible good.
        proposed_casilla_43: The signed sum of every computed ``importe`` (art-109
            step 3), the value proposed for Modelo 303 casilla 43 / the Modelo 390
            regularización field. Positive = net ingreso, negative = net deducción
            complementaria. Rows without a supplied percentage contribute nothing.
        computed_count: Number of goods whose regularización was actually computed
            (a percentage was supplied and the gate fired).
        pending_percentage_count: Number of in-window goods for which no
            current-year definitive percentage was supplied.
    """

    model_config = _STRICT_FROZEN_CONFIG

    regularizacion_year: int
    rows: tuple[RegistroRegularizacionRow, ...]
    proposed_casilla_43: Decimal
    computed_count: int
    pending_percentage_count: int
    sector_contributions: tuple[BienesInversionSectorContribution, ...]

    @model_validator(mode="after")
    def _contributions_equal_casilla_43(self) -> RegistroRegularizacionResult:
        if sum((item.amount for item in self.sector_contributions), Decimal("0.00")) != self.proposed_casilla_43:
            raise BienInversionValidationError("per-asset sector contributions must equal proposed_casilla_43")
        return self


def compute_registro_regularizacion(
    register: BienesInversionIvaRegister,
    *,
    regularizacion_year: int,
    prorrata_definitiva_by_identifier: Mapping[str, Decimal],
) -> RegistroRegularizacionResult:
    """Project the register onto its annual art-109 regularización for a year.

    Iterates every art-108-eligible, in-window good; for each good whose
    current-year definitive percentage is supplied in
    ``prorrata_definitiva_by_identifier``, runs
    :func:`compute_regularizacion_anual` and folds the signed importe into the
    proposed casilla-43 total. Goods without a supplied percentage are reported as
    pending rather than silently dropped.

    Args:
        register: The persisted :class:`BienesInversionIvaRegister`.
        regularizacion_year: The year to regularise.
        prorrata_definitiva_by_identifier: Current-year definitive deduction
            percentage (0-100) keyed by record identifier. Absent keys mark a good
            whose percentage is not yet known.

    Returns:
        A :class:`RegistroRegularizacionResult`.
    """
    rows: list[RegistroRegularizacionRow] = []
    contributions: list[BienesInversionSectorContribution] = []
    proposed = Decimal("0.00")
    computed_count = 0
    pending = 0
    for record in register.in_window_records(regularizacion_year):
        pct = prorrata_definitiva_by_identifier.get(record.identifier)
        if pct is None:
            pending += 1
            rows.append(
                RegistroRegularizacionRow(
                    identifier=record.identifier,
                    kind=record.kind,
                    prorrata_sector_id=record.prorrata_sector_id,
                    prorrata_anio_pct=None,
                    result=None,
                )
            )
            continue
        result = compute_regularizacion_anual(
            cuota_soportada=record.cuota_soportada,
            prorrata_inicial_pct=record.prorrata_inicial_pct,
            prorrata_anio_pct=pct,
            kind=record.kind,
        )
        if result.aplica:
            computed_count += 1
            proposed += result.importe
            contributions.append(
                BienesInversionSectorContribution(
                    asset_id=record.identifier,
                    prorrata_sector_id=record.prorrata_sector_id,
                    amount=result.importe,
                )
            )
        rows.append(
            RegistroRegularizacionRow(
                identifier=record.identifier,
                kind=record.kind,
                prorrata_sector_id=record.prorrata_sector_id,
                prorrata_anio_pct=pct,
                result=result,
            )
        )
    return RegistroRegularizacionResult(
        regularizacion_year=regularizacion_year,
        rows=tuple(rows),
        proposed_casilla_43=proposed,
        computed_count=computed_count,
        pending_percentage_count=pending,
        sector_contributions=tuple(contributions),
    )


class RegistroTransmisionRow(BaseModel):
    """One disposed good's contribution to the art-110 single regularización.

    Attributes:
        identifier: The record identifier.
        kind: :class:`BienInversionKind` of the good.
        disposal_year: The recorded art-110 disposal year.
        result: The :class:`RegularizacionTransmisionResult`.
    """

    model_config = _STRICT_FROZEN_CONFIG

    identifier: str
    kind: BienInversionKind
    prorrata_sector_id: str | None
    disposal_year: int
    result: RegularizacionTransmisionResult


class RegistroTransmisionesResult(BaseModel):
    """Register-wide art-110 single-regularización projection for one disposal year.

    Attributes:
        disposal_year: The year every included disposal occurred in.
        rows: Per-good :class:`RegistroTransmisionRow` entries for every
            art-108-eligible good disposed of in ``disposal_year`` with window time
            remaining.
        proposed_casilla_43: The signed sum of every row's ``importe`` — the value
            proposed for Modelo 303 casilla 43 / the Modelo 390 regularización
            field for the disposals in this year. Positive = net ingreso, negative
            = net deducción complementaria.
        computed_count: Number of disposed goods included in the projection.
    """

    model_config = _STRICT_FROZEN_CONFIG

    disposal_year: int
    rows: tuple[RegistroTransmisionRow, ...]
    proposed_casilla_43: Decimal
    computed_count: int
    sector_contributions: tuple[BienesInversionSectorContribution, ...]

    @model_validator(mode="after")
    def _contributions_equal_casilla_43(self) -> RegistroTransmisionesResult:
        if sum((item.amount for item in self.sector_contributions), Decimal("0.00")) != self.proposed_casilla_43:
            raise BienInversionValidationError("per-asset sector contributions must equal proposed_casilla_43")
        return self


def compute_registro_transmisiones(
    register: BienesInversionIvaRegister,
    *,
    disposal_year: int,
    cuota_devengada_entrega_by_identifier: Mapping[str, Decimal] | None = None,
) -> RegistroTransmisionesResult:
    """Project the register onto its art-110 single ("única") regularización for a year.

    Iterates every art-108-eligible good recorded as disposed of in
    ``disposal_year`` with window time remaining
    (:meth:`BienesInversionIvaRegister.disposed_records`); for each, computes
    :func:`compute_regularizacion_transmision` over the remaining window years and
    folds the signed importe into the proposed casilla-43 total.

    Unlike :func:`compute_registro_regularizacion`, a disposal has no pending
    state analogous to a missing current-year prorrata-definitiva input: every
    disposal fact the register carries (acquisition-year percentage, cuota
    soportada, disposal regime) is already on the record, so every disposed good
    is always computed.

    Args:
        register: The persisted :class:`BienesInversionIvaRegister`.
        disposal_year: The year to project disposals for.
        cuota_devengada_entrega_by_identifier: Optional per-good cuota devengada on
            the disposal itself, applied as the regla-1ª cap
            (:func:`compute_regularizacion_transmision`). Absent keys leave regla 1ª
            uncapped for that good.

    Returns:
        A :class:`RegistroTransmisionesResult`.
    """
    cap_by_identifier = cuota_devengada_entrega_by_identifier or {}
    rows: list[RegistroTransmisionRow] = []
    contributions: list[BienesInversionSectorContribution] = []
    proposed = Decimal("0.00")
    for record in register.disposed_records(disposal_year):
        disposal = record.disposal
        if disposal is None:
            raise BienInversionValidationError(
                f"bien de inversion {record.identifier!r} is listed as disposed in {disposal_year} "
                "but carries no disposal record",
            )
        result = compute_regularizacion_transmision(
            cuota_soportada=record.cuota_soportada,
            prorrata_inicial_pct=record.prorrata_inicial_pct,
            anos_restantes=record.remaining_regularization_years(disposal_year),
            kind=record.kind,
            regime=disposal.regime,
            cuota_devengada_entrega=cap_by_identifier.get(record.identifier),
        )
        proposed += result.importe
        contributions.append(
            BienesInversionSectorContribution(
                asset_id=record.identifier,
                prorrata_sector_id=record.prorrata_sector_id,
                amount=result.importe,
            )
        )
        rows.append(
            RegistroTransmisionRow(
                identifier=record.identifier,
                kind=record.kind,
                prorrata_sector_id=record.prorrata_sector_id,
                disposal_year=disposal_year,
                result=result,
            )
        )
    return RegistroTransmisionesResult(
        disposal_year=disposal_year,
        rows=tuple(rows),
        proposed_casilla_43=proposed,
        computed_count=len(rows),
        sector_contributions=tuple(contributions),
    )


def validate_investment_asset_reciprocity(
    *,
    observations: Sequence[_InvestmentAssetLink],
    register: BienesInversionIvaRegister,
    ledger_profile_id: str,
    asset_profile_id: str,
    filing_year: int,
) -> None:
    """Validate the one-to-one, same-profile/year/sector acquisition contract."""
    if ledger_profile_id != asset_profile_id:
        raise BienInversionValidationError("investment ledger and asset register must share a secure profile")
    records_by_id = {record.identifier: record for record in register.records}
    applicable_asset_ids = {record.identifier for record in register.records if record.acquisition_year == filing_year}
    seen_assets: set[str] = set()
    for observation in observations:
        _validate_investment_observation(observation, records_by_id, filing_year, seen_assets)
    missing_observations = sorted(applicable_asset_ids - seen_assets)
    if missing_observations:
        raise BienInversionValidationError(
            "bienes-inversion assets acquired in the filing year have no reciprocal ledger observation: "
            + ", ".join(missing_observations)
        )


def _validate_investment_observation(
    observation: _InvestmentAssetLink,
    records_by_id: Mapping[str, BienInversionIvaRecord],
    filing_year: int,
    seen_assets: set[str],
) -> None:
    if not _is_investment_acquisition_observation(observation):
        return
    asset_id = observation.investment_asset_id
    if asset_id is None or asset_id not in records_by_id:
        raise BienInversionValidationError("investment observation has no reciprocal bienes-inversion record")
    if asset_id in seen_assets:
        raise BienInversionValidationError("multiple investment observations reference one bienes-inversion asset")
    record = records_by_id[asset_id]
    _validate_investment_record_reciprocity(observation, record, filing_year)
    seen_assets.add(asset_id)


def _is_investment_acquisition_observation(observation: _InvestmentAssetLink) -> bool:
    kind = observation.deduction_fact_kind
    asset_id = observation.investment_asset_id
    if kind is IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION:
        raise BienInversionValidationError("regularisation is not a ledger acquisition observation")
    if kind is None or not kind.is_investment_acquisition:
        if asset_id is not None:
            raise BienInversionValidationError("non-investment observation cannot carry investment_asset_id")
        return False
    return True


def _validate_investment_record_reciprocity(
    observation: _InvestmentAssetLink,
    record: BienInversionIvaRecord,
    filing_year: int,
) -> None:
    if record.acquisition_ledger_id != observation.ledger_id:
        raise BienInversionValidationError("investment asset acquisition_ledger_id is not reciprocal")
    if record.acquisition_year != filing_year or observation.transaction_date.year != filing_year:
        raise BienInversionValidationError("investment asset and observation must share the filing year")
    if record.prorrata_sector_id != observation.prorrata_sector_id:
        raise BienInversionValidationError("investment asset and observation must share the prorrata sector")
