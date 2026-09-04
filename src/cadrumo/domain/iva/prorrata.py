"""Legal IVA prorrata substrate (LIVA arts. 102-106).

This module implements the Spanish Value-Added-Tax (IVA) prorrata mechanism
that governs how a taxable person who performs both deductible and
non-deductible operations may deduct input IVA. The substrate is pure
domain logic: it produces immutable result objects and never touches
persistence, the registry, or the CLI.

Legal sources (Ley 37/1992 del IVA, BOE-A-1992-28740):

* **Art. 102.Uno** ("Regla de prorrata") triggers the rule when a taxpayer
  performs, *conjuntamente*, operations that grant the right to deduction
  (taxable supplies, deemed-domestic intracomunitarias, intra-EU services,
  etc.) alongside operations of an analogous nature that do NOT grant the
  right (LIVA arts. 20 and 21 exempt supplies and similar). Art. 102.Dos
  is a separate rule about autoconsumos and carries nothing this module
  implements.

* **Art. 103.Uno** ("Clases de prorrata y criterios de aplicación") splits
  the rule into two modalities: *prorrata general* (arts. 104-105) is the
  default, and *prorrata especial* (art. 106) applies on election or, per
  art. 103.Dos.2.º, whenever the year's deductible cuotas under the general
  regime exceed those under the especial regime by the margin in force for
  that filing year.

* **Art. 104.Dos** ("La prorrata general") — general prorrata formula:
  ``deductible_percentage = operaciones_con_derecho / total_operaciones``.
  ``operaciones_con_derecho`` is the sum of the year's operations that
  grant the right to deduct input IVA (regla 1.ª, the numerator).
  ``total_operaciones`` is the sum of ``operaciones_con_derecho`` plus
  ``operaciones_sin_derecho`` (LIVA-art.-20 exempt supplies and similar;
  regla 2.ª, the denominator). Art. 104.Tres excludes subvenciones not
  linked to operations, autoconsumos, and the disposal of bienes de
  inversión from both terms; the exclusion is the caller's
  responsibility; this module only accepts already-filtered operation
  totals. Art. 104.Uno confines the percentage limitation to the cases
  where the regla de prorrata applies at all, so a taxpayer with no
  exempt-without-right operations deducts in full (arts. 92 and 94).

* **Art. 104.Dos, closing paragraph** — "La prorrata de deducción
  resultante de la aplicación de los criterios anteriores se redondeará
  en la unidad superior": the percentage is rounded **up** to the next
  whole integer (``ROUND_CEILING`` against ``Decimal("1")``). This is the
  only rounding clause in the whole of Ley 37/1992.

* **Art. 103.Dos.2.º** — prorrata especial is mandatory whenever the
  year's total deductible cuotas under the general regime exceed those
  under the especial regime by the statutory margin. The provision is NOT
  invariant across the filing years this module serves: the original
  redaction (in force to 31-12-2014) read "exceda en un 20 por 100 del que
  resultaría", while Ley 28/2014 art. 1.26 (BOE-A-2014-12329, in force from
  01-01-2015) replaced it with "exceda en un 10 por ciento o más del que
  resultaría" — lowering the margin *and* making it inclusive. See
  :func:`is_especial_mandatory`, which selects on the filing year, and
  :func:`especial_mandatory_rule`, which reports the margin that
  selection applied.

* **Art. 9.1.c** — sectoral separation (``régimen de sectores
  diferenciados``) applies when the taxpayer's activities form two or more
  distinct sectors and the difference between the highest and lowest
  general prorrata across sectors exceeds fifty percentage points. Each
  sector then runs its own prorrata (general or especial). This module
  computes the predicate; sector identification itself is a profile/
  registry concern carried in :class:`ProrrataSector`.

The substrate distinguishes *provisional* and *definitiva* prorrata
percentages explicitly (LIVA arts. 105 and 109). The provisional
percentage applies during quarterly/monthly Modelo 303 filings and is
typically the prior year's definitiva. The definitiva percentage is
computed at year-end with the year's actual operations and produces a
regularisation entry in Q4 303 (casilla 44) and Modelo 390.

Live submission is not the concern of this module. Current filing
surfaces either use registry-defined formula/manual prorrata casillas or
carry validated prorrata references on IVA ledger observations.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from ...core.external_constants import (
    PRORRATA_SECTORAL_SEPARATION_SPREAD_PP,
)
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents as _round_to_cents
from ...core.percentage import Percentage
from .errors import ProrrataInputError, ProrrataSectorError
from .prorrata_especial_parameters import ProrrataEspecialMandatoryParameters


class _ProrrataStrictFrozen(BaseModel):
    """Strict, immutable Pydantic base for the prorrata substrate."""

    model_config = STRICT_FROZEN_CONFIG


SectorId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[-._a-zA-Z0-9]+$"),
]


class ProrrataRegime(StrEnum):
    """LIVA-defined prorrata regime kinds.

    * ``GENERAL`` — single deduction percentage applied to every input IVA
      amount (art. 103.Uno LIVA for the modality, art. 104 for the
      percentage).
    * ``ESPECIAL`` — per-input classification: 100% deductible if used
      exclusively in deductible activities, 0% if used exclusively in
      non-deductible, the general percentage if used in both (common-bien
      under art. 106 LIVA).
    """

    GENERAL = "general"
    ESPECIAL = "especial"


class ProrrataKind(StrEnum):
    """Lifecycle stage of the prorrata percentage.

    * ``PROVISIONAL`` — applied during the tax year on Modelo 303 quarters
      or months, normally derived from the prior year's definitiva.
    * ``DEFINITIVA`` — computed at year-end with the year's actual
      operations; drives the regularisation entry on Q4 303 and Modelo
      390.
    """

    PROVISIONAL = "provisional"
    DEFINITIVA = "definitiva"


class InputClassification(StrEnum):
    """How a specific input IVA amount maps to deductible activity under prorrata especial.

    Governed by art. 106.Uno LIVA.

    * ``EXCLUSIVELY_DEDUCTIBLE`` — used only in operations that grant the
      right to deduct; 100% deductible.
    * ``EXCLUSIVELY_NON_DEDUCTIBLE`` — used only in operations that do
      NOT grant the right; 0% deductible.
    * ``COMMON`` — used in both kinds of operations; the general prorrata
      percentage applies.
    """

    EXCLUSIVELY_DEDUCTIBLE = "exclusively_deductible"
    EXCLUSIVELY_NON_DEDUCTIBLE = "exclusively_non_deductible"
    COMMON = "common"


class ProrrataInputs(_ProrrataStrictFrozen):
    """Aggregated operation amounts for one prorrata computation window.

    The aggregator producing these inputs is responsible for applying the
    art. 104 LIVA exclusions (subvenciones not linked to operations,
    autoconsumos, sale of bienes de inversión, non-recurring financial and
    immovable operations meeting the art. 104.Tres tests). This model
    therefore treats both fields as already-filtered annual totals
    expressed in euros.
    """

    operaciones_con_derecho_deduccion: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description=("Sum of the year's operations that grant the right to deduct input IVA. Must be non-negative."),
    )
    operaciones_sin_derecho_deduccion: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description=(
            "Sum of the year's exempt operations that do NOT grant the "
            "right to deduct (LIVA arts. 20 and 21 exempt supplies and "
            "similar). Must be non-negative."
        ),
    )


class ProrrataSector(_ProrrataStrictFrozen):
    """A single sector under the sectoral-separation regime (art. 9.1.c LIVA).

    A taxpayer with two or more economic sectors whose general prorratas
    differ by more than fifty percentage points must compute the prorrata
    independently per sector. Each sector carries its own filtered totals
    and may run under ``GENERAL`` or ``ESPECIAL`` regime.
    """

    sector_id: SectorId
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    inputs: ProrrataInputs
    regime: ProrrataRegime = ProrrataRegime.GENERAL


class ProrrataResult(_ProrrataStrictFrozen):
    """Outcome of a single prorrata computation.

    The percentage is stored as a ``Decimal`` whole-integer value between
    ``0`` and ``100`` inclusive, already rounded up per LIVA art. 104.Dos.
    Sectoral results carry their ``sector_id``; whole-entity results
    carry ``None``.
    """

    regime: ProrrataRegime
    kind: ProrrataKind
    percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description=(
            "Deductible percentage rounded up to the next whole integer per LIVA art. 104.Dos. Range 0..100 inclusive."
        ),
    )
    inputs: ProrrataInputs
    sector_id: SectorId | None = None
    year: Annotated[int, Field(ge=2000, le=2100)]
    period: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, pattern=r"^(Q[1-4]|M(0[1-9]|1[0-2])|annual)$"),
    ] = None

    @model_validator(mode="after")
    def _validate_period_matches_kind(self) -> ProrrataResult:
        # PROVISIONAL applies during the year, so a quarterly/monthly
        # period token is required. DEFINITIVA is annual.
        if self.kind is ProrrataKind.PROVISIONAL and self.period is None:
            raise ProrrataInputError("provisional prorrata result must carry a period (Qn or Mnn)")
        if self.kind is ProrrataKind.DEFINITIVA and self.period not in (None, "annual"):
            raise ProrrataInputError("definitiva prorrata result period must be 'annual' or omitted")
        return self


class ProrrataReference(_ProrrataStrictFrozen):
    """Stable identifier for a persisted IVA prorrata percentage.

    References use the canonical shape
    ``prorrata:{year}:{kind}:{regime}``, with an optional sector suffix
    ``:{sector_id}`` for sectoral-separation cases. The reference is a
    pointer to a legal IVA prorrata substrate value; it is not a
    proportional-use ratio and it is not derived from usage-ratio data.
    """

    reference_id: str = Field(min_length=1, max_length=128)
    year: Annotated[int, Field(ge=2000, le=2100)]
    kind: ProrrataKind
    regime: ProrrataRegime
    sector_id: SectorId | None = None

    @field_validator("reference_id")
    @classmethod
    def _trim_reference_id(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _reference_id_matches_fields(self) -> ProrrataReference:
        expected = _canonical_prorrata_reference_id(
            year=self.year,
            kind=self.kind,
            regime=self.regime,
            sector_id=self.sector_id,
        )
        if self.reference_id != expected:
            raise ProrrataInputError(
                f"prorrata reference {self.reference_id!r} does not match canonical value {expected!r}",
            )
        return self


class ProrrataInputDeduction(_ProrrataStrictFrozen):
    """One per-input deductibility decision under prorrata especial.

    Used to enumerate every input IVA amount classified under art. 106.Uno
    LIVA and the resulting deductible portion. The ``deductible_amount``
    field equals ``input_iva_amount * deductible_percentage / 100``,
    rounded to two decimals half-up via :func:`~cadrumo.core.money.round_to_cents`;
    the caller's modelo binding provider is responsible for further rounding if
    the registry casilla requires whole euros.

    The rounding mode is load-bearing and this docstring previously named the
    opposite one. ``core.money`` states that banker's rounding "does NOT match
    AEAT and must never be used at the euro-cent boundary for any
    operator-facing or filed value", and the implementation has always used
    half-up; only this description was wrong -- in the exact register an
    auditor reads to check a filed deduction.
    """

    classification: InputClassification
    input_iva_amount: Decimal = Field(..., ge=Decimal("0"))
    deductible_percentage: Percentage
    deductible_amount: Decimal = Field(..., ge=Decimal("0"))


class EspecialMandatoryRule(_ProrrataStrictFrozen):
    """The LIVA art. 103.Dos.2.º mandatory-especial rule in force for one filing year.

    Art. 103.Dos.2.º is not invariant across the filing years this substrate
    serves, so the rule is resolved per year by
    :func:`especial_mandatory_rule` rather than being a single constant.
    Carrying the comparison shape alongside the figure lets an
    operator-facing message state the margin AND whether reaching it is
    enough, without re-deriving either.

    Attributes:
        year: The filing year the deductions belong to.
        multiple: The factor the especial-regime deduction is scaled by to
            obtain the threshold (``1.10`` from 2015, ``1.20`` before).
        margin_percentage: The same threshold expressed as the percentage
            the provision names (``10`` from 2015, ``20`` before).
        inclusive: ``True`` when the provision reads "o más", so a general
            deduction landing exactly on the threshold already makes the
            especial regime mandatory.
    """

    year: Annotated[int, Field(ge=2000, le=2100)]
    multiple: Decimal = Field(..., gt=Decimal("1"))
    margin_percentage: Decimal = Field(..., gt=Decimal("0"))
    inclusive: bool


# ---------------------------------------------------------------------------
# Pure calculators
# ---------------------------------------------------------------------------


def _validate_year(year: int) -> int:
    if year < 2000 or year > 2100:
        raise ProrrataInputError(f"year out of supported range 2000..2100: {year}")
    return year


def _canonical_prorrata_reference_id(
    *,
    year: int,
    kind: ProrrataKind,
    regime: ProrrataRegime,
    sector_id: SectorId | None = None,
) -> str:
    base = f"prorrata:{year}:{kind.value}:{regime.value}"
    return f"{base}:{sector_id}" if sector_id is not None else base


def validate_prorrata_reference(reference_id: str) -> ProrrataReference:
    """Parse and validate a legal IVA prorrata reference id and return a :class:`ProrrataReference`.

    The accepted id shape is ``prorrata:{year}:{kind}:{regime}``, plus
    an optional ``:{sector_id}`` suffix. Values from the expense
    proportionality/usage-ratio substrate intentionally fail this
    parser; callers must keep both concepts separate.
    """
    normalized = reference_id.strip()
    parts = normalized.split(":")
    if len(parts) not in (4, 5) or parts[0] != "prorrata":
        raise ProrrataInputError(
            "prorrata_reference must use canonical shape "
            "'prorrata:{year}:{kind}:{regime}' or "
            "'prorrata:{year}:{kind}:{regime}:{sector_id}'",
        )
    try:
        year = int(parts[1])
    except ValueError as exc:
        raise ProrrataInputError(f"prorrata_reference year must be an integer: {parts[1]!r}") from exc
    _validate_year(year)
    try:
        kind = ProrrataKind(parts[2])
    except ValueError as exc:
        raise ProrrataInputError(f"unknown prorrata_reference kind: {parts[2]!r}") from exc
    try:
        regime = ProrrataRegime(parts[3])
    except ValueError as exc:
        raise ProrrataInputError(f"unknown prorrata_reference regime: {parts[3]!r}") from exc
    sector_id = parts[4] if len(parts) == 5 else None
    try:
        return ProrrataReference(
            reference_id=normalized,
            year=year,
            kind=kind,
            regime=regime,
            sector_id=sector_id,
        )
    except ValidationError as exc:
        raise ProrrataInputError(f"invalid prorrata_reference: {normalized!r}") from exc


def _compute_percentage_general(inputs: ProrrataInputs) -> Decimal:
    """Apply LIVA art. 104.Dos to produce the general prorrata percentage.

    Returns a ``Decimal`` between ``0`` and ``100`` inclusive, rounded up
    to the next whole integer. When total operations is zero the
    percentage is reported as ``100``: art. 102.Uno makes the regla de
    prorrata applicable only where deduction-granting and non-granting
    operations are performed *conjuntamente*, so with no operations the
    art. 104.Uno limitation never bites and the input tax stays deductible
    in full (arts. 92 and 94). Provisional percentages are typically
    carried over from the prior year by the application layer before this
    function is reached; this branch is a defence-in-depth.
    """
    total = inputs.operaciones_con_derecho_deduccion + inputs.operaciones_sin_derecho_deduccion
    if total == 0:
        return Decimal("100")
    ratio = inputs.operaciones_con_derecho_deduccion / total
    # LIVA art. 104.Dos, closing paragraph: "se redondeará en la unidad
    # superior" — the next whole integer up, never the nearest one.
    return (ratio * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_CEILING)


def compute_prorrata_general(
    inputs: ProrrataInputs,
    *,
    year: int,
    kind: ProrrataKind,
    period: str | None = None,
    sector_id: SectorId | None = None,
) -> ProrrataResult:
    """Compute the general prorrata percentage for one window.

    Implements LIVA art. 104.Uno + art. 104.Dos. The caller supplies the
    filtered annual totals (or annualised totals if the year is a
    fractional first/last year) and the lifecycle kind.

    Raises :class:`ProrrataInputError` when the year is out of the
    supported range or when ``kind``/``period`` combination is
    inconsistent.

    Returns:
        A :class:`ProrrataResult` with the computed percentage and inputs.
    """
    _validate_year(year)
    percentage = _compute_percentage_general(inputs)
    try:
        return ProrrataResult(
            regime=ProrrataRegime.GENERAL,
            kind=kind,
            percentage=percentage,
            inputs=inputs,
            sector_id=sector_id,
            year=year,
            period=period,
        )
    except ValidationError as exc:
        raise ProrrataInputError(f"invalid prorrata result window: year={year} period={period!r}") from exc


def deductible_percentage_for(
    classification: InputClassification,
    general_percentage: Decimal,
) -> Decimal:
    """Map an input classification to its deductible percentage under LIVA art. 106.Uno.

    The single canonical mapping of the art. 106.Uno reglas:
    ``EXCLUSIVELY_DEDUCTIBLE`` → 100 (regla 1.ª, deducted in full),
    ``EXCLUSIVELY_NON_DEDUCTIBLE`` → 0 (regla 2.ª, no deduction),
    ``COMMON`` → ``general_percentage`` (regla 3.ª, deducted at the general
    prorrata percentage). Consumed both by :func:`classify_input_deduction`
    (per-input deduction) and by the ledger IVA aggregation's regime-aware
    especial apportionment, so the reglas live in exactly one place.
    """
    if classification is InputClassification.EXCLUSIVELY_DEDUCTIBLE:
        return Decimal("100")
    if classification is InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE:
        return Decimal("0")
    # COMMON: apply the general prorrata percentage (art. 106.Uno.3.ª,
    # which routes to "el porcentaje a que se refiere el artículo 104,
    # apartados Dos y siguientes").
    return general_percentage


def classify_input_deduction(
    classification: InputClassification,
    input_iva_amount: Decimal,
    general_percentage: Decimal,
) -> ProrrataInputDeduction:
    """Compute one deductible amount and return a :class:`ProrrataInputDeduction`.

    Implements prorrata especial (art. 106). The ``general_percentage`` is the
    value produced by :func:`compute_prorrata_general` for the same window; it
    only enters the calculation when the classification is ``COMMON``.
    """
    if input_iva_amount < 0:
        raise ProrrataInputError(f"input_iva_amount must be non-negative, got {input_iva_amount}")
    if general_percentage < 0 or general_percentage > 100:
        raise ProrrataInputError(f"general_percentage out of range 0..100, got {general_percentage}")

    deductible_percentage = deductible_percentage_for(classification, general_percentage)
    deductible_amount = _round_to_cents(input_iva_amount * deductible_percentage / Decimal("100"))
    return ProrrataInputDeduction(
        classification=classification,
        input_iva_amount=input_iva_amount,
        deductible_percentage=deductible_percentage,
        deductible_amount=deductible_amount,
    )


def especial_mandatory_rule(
    year: int,
    *,
    parameters: ProrrataEspecialMandatoryParameters,
) -> EspecialMandatoryRule:
    """Return the LIVA art. 103.Dos.2 rule in force for filing ``year``.

    Both halves of the rule are registry data and neither is decided here. The
    margin and its comparison direction arrive already resolved from the
    revision the application boundary selected, because art. 103.Dos.2 has had
    two redactions differing on BOTH -- the original required an excess "en un
    20 por 100" with no "o más" and so exclusive, and Ley 28/2014 art. 1.26
    replaced it from 01-01-2015 with "en un 10 por ciento o más", lowering the
    margin and making it inclusive.

    A pre-2015 ejercicio never reaches this function: the resolver refuses it by
    name, because the repealed redaction has no citable authority in this tree
    and no revision covers such a filing year.

    Args:
        year: The filing year the deductions belong to.
        parameters: The registry-resolved margin and comparison direction.

    Raises:
        ProrrataInputError: when the year is outside the supported range.
    """
    _validate_year(year)
    margin = parameters.margin_percentage
    return EspecialMandatoryRule(
        year=year,
        multiple=parameters.multiple,
        margin_percentage=margin.quantize(Decimal("1")) if margin == margin.to_integral_value() else margin,
        inclusive=parameters.inclusive,
    )


def is_especial_mandatory(
    deduction_under_general: Decimal,
    deduction_under_especial: Decimal,
    *,
    year: int,
    parameters: ProrrataEspecialMandatoryParameters,
) -> bool:
    """Return True when LIVA art. 103.Dos.2.º forces the prorrata especial regime.

    The provision in force from filing year 2015 (Ley 28/2014 art. 1.26,
    BOE-A-2014-12329): the especial regime applies "cuando el montante
    total de las cuotas deducibles en un año natural por aplicación de la
    regla de prorrata general exceda en un 10 por ciento o más del que
    resultaría por aplicación de la regla de prorrata especial". "O más"
    reaches the margin, so a general deduction landing exactly on it
    switches the regime: the comparison is ``>=``, not ``>``.

    The original redaction (in force to filing year 2014) set the margin at
    twenty percent and carried no "o más", so for those years the margin
    must be passed rather than merely reached. ``year`` selects between the
    two through :func:`especial_mandatory_rule`; it is the filing year the
    deductions belong to, not the year the calculation is run.

    When the especial deduction is zero this function returns ``True`` if
    the general deduction is positive: a positive amount exceeds zero
    without bound, so both redactions agree the regime is mandatory.

    Raises:
        ProrrataInputError: on a negative deduction amount or a year
        outside the supported range.
    """
    if deduction_under_general < 0 or deduction_under_especial < 0:
        raise ProrrataInputError("deduction amounts must be non-negative")
    rule = especial_mandatory_rule(year, parameters=parameters)
    if deduction_under_especial == 0:
        return deduction_under_general > 0
    threshold = deduction_under_especial * rule.multiple
    return deduction_under_general >= threshold if rule.inclusive else deduction_under_general > threshold


# ---------------------------------------------------------------------------
# Annual prorrata-general regularisation (LIVA arts. 104-105)
# ---------------------------------------------------------------------------


class RegularizacionProrrataDireccion(StrEnum):
    """Direction of the annual prorrata-general regularisation (LIVA art. 105.Cuatro).

    * ``DEDUCCION`` — the year's definitive percentage exceeds the provisional
      one applied across the quarters, so a *deducción complementaria* is due:
      the taxpayer may deduct more input IVA and the Modelo 303 casilla-44 value
      is positive (it increases the total deductible cuota).
    * ``INGRESO`` — the definitive percentage is lower than the provisional one,
      so the provisional deductions were excessive and an *ingreso* is due: the
      casilla-44 value is negative (it reduces the total deductible cuota).
    * ``NINGUNA`` — the two percentages coincide; no regularisation is practised.
    """

    DEDUCCION = "deduccion"
    INGRESO = "ingreso"
    NINGUNA = "ninguna"


class RegularizacionProrrataResult(_ProrrataStrictFrozen):
    """Outcome of the annual prorrata-general regularisation (LIVA art. 105.Cuatro).

    Attributes:
        cuotas_soportadas_deducibles: The year's total deductible input IVA the
            percentages apply to (art. 105.Seis: the sum of the year's cuotas
            soportadas, excluding the arts. 95/96 non-deductibles).
        prorrata_provisional_pct: The provisional percentage applied during the
            year (art. 105.Uno: normally the prior year's definitive percentage).
        prorrata_definitiva_pct: The definitive percentage computed at year-end
            from the year's actual operations (art. 104).
        deduccion_provisional: ``cuotas × provisional% / 100`` — the deduction
            already practised across the year's provisional liquidations.
        deduccion_definitiva: ``cuotas × definitiva% / 100`` — the deduction that
            definitively applies.
        importe: ``deduccion_definitiva − deduccion_provisional``, rounded to
            cents. The signed value proposed for Modelo 303 casilla 44 / the
            Modelo 390 annual regularisation field. Positive = additional
            deduction; negative = repayment.
        direccion: :class:`RegularizacionProrrataDireccion` describing the sign.
    """

    cuotas_soportadas_deducibles: Decimal = Field(..., ge=Decimal("0"))
    prorrata_provisional_pct: Percentage
    prorrata_definitiva_pct: Percentage
    deduccion_provisional: Decimal
    deduccion_definitiva: Decimal
    importe: Decimal
    direccion: RegularizacionProrrataDireccion


def compute_prorrata_definitiva_anual(
    inputs: ProrrataInputs,
    *,
    year: int,
    sector_id: SectorId | None = None,
) -> ProrrataResult:
    """Compute the year-end DEFINITIVA general prorrata percentage (LIVA arts. 104-105).

    Thin, named wrapper over :func:`compute_prorrata_general` fixing
    ``kind = DEFINITIVA`` and ``period = "annual"``: the caller supplies the
    full-year operation volumes (con-derecho / sin-derecho) with the art-104
    exclusions already applied, and receives the definitive percentage that
    art. 105.Cuatro regularises the provisional deductions against. This is the
    definitive-percentage source the capital-goods regularización (LIVA arts.
    107-110) and the annual prorrata regularización both consume; deriving it from
    a single quarter's volume is a correctness defect (a single period computes
    neither the provisional nor the annual-regularised percentage), so the
    definitive percentage MUST come from the full-year rollup.

    Returns:
        The definitive :class:`ProrrataResult` for the year.
    """
    return compute_prorrata_general(
        inputs,
        year=year,
        kind=ProrrataKind.DEFINITIVA,
        period="annual",
        sector_id=sector_id,
    )


def compute_regularizacion_prorrata_anual(
    *,
    cuotas_soportadas_deducibles: Decimal,
    prorrata_provisional_pct: Decimal,
    prorrata_definitiva_pct: Decimal,
) -> RegularizacionProrrataResult:
    """Compute the annual prorrata-general regularisation cuota (LIVA art. 105.Cuatro).

    Implements the art-105 procedure. A taxpayer under prorrata general applies a
    PROVISIONAL deduction percentage across the year's liquidations (art. 105.Uno:
    "el porcentaje de deducción provisionalmente aplicable cada año natural será
    el fijado como definitivo para el año precedente"); then, in the last
    liquidation of the year, computes the DEFINITIVA percentage from the year's
    actual operations (art. 104) and "practicará la consiguiente regularización de
    las deducciones provisionales" (art. 105.Cuatro). The regularisation cuota is
    the difference between the deduction that definitively applies and the
    deduction already practised provisionally::

        deduccion_definitiva  = cuotas × definitiva% / 100
        deduccion_provisional = cuotas × provisional% / 100
        importe               = deduccion_definitiva − deduccion_provisional

    Unlike the capital-goods regularisation (arts. 107-110), the prorrata-general
    regularisation carries **no >10-point gate**: art. 105.Cuatro practises it in
    every year the two percentages differ. Both percentages are supplied as
    inputs; deriving the definitive percentage from the annual volumes is
    :func:`compute_prorrata_definitiva_anual`, and carrying the prior-year
    definitive as this year's provisional (art. 105.Uno) is the profile-scoped
    carry the application layer owns.

    Args:
        cuotas_soportadas_deducibles: The year's total deductible input IVA
            (art. 105.Seis), non-negative.
        prorrata_provisional_pct: Provisional deduction percentage applied during
            the year (0-100).
        prorrata_definitiva_pct: Definitive deduction percentage for the year
            (0-100).

    Returns:
        A :class:`RegularizacionProrrataResult` carrying the signed casilla-44
        importe and its :class:`RegularizacionProrrataDireccion`.

    Raises:
        ProrrataInputError: on a negative cuota or an out-of-range percentage.
    """
    if cuotas_soportadas_deducibles < 0:
        raise ProrrataInputError(
            f"cuotas_soportadas_deducibles must be non-negative, got {cuotas_soportadas_deducibles}",
        )
    for label, pct in (
        ("prorrata_provisional_pct", prorrata_provisional_pct),
        ("prorrata_definitiva_pct", prorrata_definitiva_pct),
    ):
        if pct < Decimal("0") or pct > Decimal("100"):
            raise ProrrataInputError(f"{label} out of range 0..100, got {pct}")

    deduccion_provisional = _round_to_cents(cuotas_soportadas_deducibles * prorrata_provisional_pct / Decimal("100"))
    deduccion_definitiva = _round_to_cents(cuotas_soportadas_deducibles * prorrata_definitiva_pct / Decimal("100"))
    importe = deduccion_definitiva - deduccion_provisional
    if importe > Decimal("0"):
        direccion = RegularizacionProrrataDireccion.DEDUCCION
    elif importe < Decimal("0"):
        direccion = RegularizacionProrrataDireccion.INGRESO
    else:
        direccion = RegularizacionProrrataDireccion.NINGUNA
    return RegularizacionProrrataResult(
        cuotas_soportadas_deducibles=cuotas_soportadas_deducibles,
        prorrata_provisional_pct=prorrata_provisional_pct,
        prorrata_definitiva_pct=prorrata_definitiva_pct,
        deduccion_provisional=deduccion_provisional,
        deduccion_definitiva=deduccion_definitiva,
        importe=importe,
        direccion=direccion,
    )


# ---------------------------------------------------------------------------
# Sectoral separation (art. 9.1.c LIVA)
# ---------------------------------------------------------------------------


_SECTORAL_SEPARATION_THRESHOLD_PERCENTAGE_POINTS = PRORRATA_SECTORAL_SEPARATION_SPREAD_PP


def _ensure_unique_sectors(sectors: Sequence[ProrrataSector]) -> None:
    seen: set[str] = set()
    for sector in sectors:
        if sector.sector_id in seen:
            raise ProrrataSectorError(f"duplicate sector_id in sectors list: {sector.sector_id!r}")
        seen.add(sector.sector_id)


def requires_sectoral_separation(sectors: Sequence[ProrrataSector]) -> bool:
    """Return True when LIVA art. 9.1.c mandates sectoral separation.

    The rule: a taxpayer with two or more economic sectors must compute
    prorrata independently per sector whenever the difference between the
    highest and lowest general prorrata across sectors exceeds fifty
    percentage points.

    Sectors are identified by stable ``sector_id``; the caller is
    responsible for assigning activity codes (e.g., CNAE / IAE-epígrafe)
    to sectors before invoking this function. A sectors list with fewer
    than two members returns ``False`` because the threshold cannot
    apply.
    """
    if len(sectors) < 2:
        return False
    _ensure_unique_sectors(sectors)
    percentages = [_compute_percentage_general(sector.inputs) for sector in sectors]
    spread = max(percentages) - min(percentages)
    return spread > _SECTORAL_SEPARATION_THRESHOLD_PERCENTAGE_POINTS


def compute_sectoral_prorrata(
    sectors: Sequence[ProrrataSector],
    *,
    year: int,
    kind: ProrrataKind,
    period: str | None = None,
) -> tuple[ProrrataResult, ...]:
    """Compute the general prorrata for each sector.

    Returns one :class:`ProrrataResult` per input sector, in the same
    order. This function does NOT enforce whether sectoral separation
    applies — that decision lives in
    :func:`requires_sectoral_separation`; this calculator runs once the
    caller has decided separation is required.
    """
    if not sectors:
        raise ProrrataSectorError("sectors sequence must not be empty")
    _ensure_unique_sectors(sectors)
    _validate_year(year)
    return tuple(
        compute_prorrata_general(
            sector.inputs,
            year=year,
            kind=kind,
            period=period,
            sector_id=sector.sector_id,
        )
        for sector in sectors
    )


# ---------------------------------------------------------------------------
# Helpers for caller-side rollups
# ---------------------------------------------------------------------------


def sum_deductible_amounts(
    deductions: Iterable[ProrrataInputDeduction],
) -> Decimal:
    """Sum the ``deductible_amount`` field across a collection of inputs.

    Callers use this to roll up per-input deductions after running
    :func:`classify_input_deduction` for each purchase invoice evidence
    row. Modelo casilla routing remains registry-owned.
    """
    return sum((entry.deductible_amount for entry in deductions), Decimal("0"))


__all__ = (
    "EspecialMandatoryRule",
    "InputClassification",
    "ProrrataInputDeduction",
    "ProrrataInputs",
    "ProrrataKind",
    "ProrrataReference",
    "ProrrataRegime",
    "ProrrataResult",
    "ProrrataSector",
    "RegularizacionProrrataDireccion",
    "RegularizacionProrrataResult",
    "classify_input_deduction",
    "compute_prorrata_definitiva_anual",
    "compute_prorrata_general",
    "compute_regularizacion_prorrata_anual",
    "compute_sectoral_prorrata",
    "deductible_percentage_for",
    "especial_mandatory_rule",
    "is_especial_mandatory",
    "requires_sectoral_separation",
    "sum_deductible_amounts",
    "validate_prorrata_reference",
)
