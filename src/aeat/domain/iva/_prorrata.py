"""Legal IVA prorrata substrate (LIVA arts. 101-103).

This module implements the Spanish Value-Added-Tax (IVA) prorrata mechanism
that governs how a taxable person who performs both deductible and
non-deductible operations may deduct input IVA. The substrate is pure
domain logic: it produces immutable result objects and never touches
persistence, the registry, or the CLI.

Legal sources (Ley 37/1992 del IVA, BOE-A-1992-28740):

* **Art. 101** triggers the rule when a taxpayer performs operations that
  grant the right to deduction (taxable supplies, deemed-domestic
  intracomunitarias, intra-EU services, etc.) alongside operations that do
  NOT grant the right (LIVA arts. 20 and 21 exempt supplies and similar).
  The default form is *prorrata general* (art. 102); *prorrata especial*
  (art. 103) applies on election or as a mandatory fallback when the
  general regime overstates the deduction by more than ten percent.

* **Art. 102.Uno** — general prorrata formula:
  ``deductible_percentage = operaciones_con_derecho / total_operaciones``.
  ``operaciones_con_derecho`` is the sum of the year's operations that
  grant the right to deduct input IVA. ``total_operaciones`` is the sum of
  ``operaciones_con_derecho`` plus ``operaciones_sin_derecho``
  (LIVA-art.-20 exempt supplies and similar). Subvenciones not linked to
  operations, autoconsumos, and the disposal of bienes de inversión are
  excluded from both numerator and denominator per art. 104 LIVA; the
  exclusion is the caller's responsibility — this module operates on the
  amounts the application aggregator already filtered.

* **Art. 102.Dos** — the resulting percentage is rounded **up** to the
  next whole integer (``ROUND_CEILING`` against ``Decimal("1")``).

* **Art. 103.Dos** — prorrata especial is mandatory whenever the
  deduction computed under the general regime exceeds the deduction
  computed under the especial regime by more than ten percent (i.e.
  ``deduction_general > deduction_especial * Decimal("1.10")``).

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

Live submission is not the concern of this module: the substrate emits
calculation results consumed by Modelo 303 and 390 binding providers in
the application aggregation layer.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from ...core.external_constants import (
    PRORRATA_ESPECIAL_MANDATORY_MULTIPLE,
    PRORRATA_SECTORAL_SEPARATION_SPREAD_PP,
)
from ...core.money import round_to_cents as _round_to_cents
from ._errors import ProrrataInputError, ProrrataSectorError


class _ProrrataStrictFrozen(BaseModel):
    """Strict, immutable Pydantic base for the prorrata substrate."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )


SectorId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[-._a-zA-Z0-9]+$"),
]


class ProrrataRegime(StrEnum):
    """LIVA-defined prorrata regime kinds.

    * ``GENERAL`` — single deduction percentage applied to every input IVA
      amount (art. 102 LIVA).
    * ``ESPECIAL`` — per-input classification: 100% deductible if used
      exclusively in deductible activities, 0% if used exclusively in
      non-deductible, the general percentage if used in both (common-bien
      under art. 103 LIVA).
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

    Governed by art. 103 LIVA.

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
    ``0`` and ``100`` inclusive, already rounded up per LIVA art. 102.Dos.
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
            "Deductible percentage rounded up to the next whole integer per LIVA art. 102.Dos. Range 0..100 inclusive."
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

    Used to enumerate every input IVA amount classified under art. 103
    LIVA and the resulting deductible portion. The ``deductible_amount``
    field equals ``input_iva_amount * deductible_percentage / 100``,
    rounded to two decimals using banker's rounding (the default Decimal
    quantizer); the caller's modelo binding provider is responsible for
    further rounding if the registry casilla requires whole euros.
    """

    classification: InputClassification
    input_iva_amount: Decimal = Field(..., ge=Decimal("0"))
    deductible_percentage: Decimal = Field(..., ge=Decimal("0"), le=Decimal("100"))
    deductible_amount: Decimal = Field(..., ge=Decimal("0"))


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
    """Apply LIVA art. 102.Uno and art. 102.Dos to produce the general prorrata percentage.

    Returns a ``Decimal`` between ``0`` and ``100`` inclusive, rounded up
    to the next whole integer. When total operations is zero the
    percentage is reported as ``100`` per the long-standing AEAT
    administrative criterion that a taxpayer with no operations in the
    year may not lose the right to deduct (provisional percentages are
    typically carried over from the prior year by the application layer
    before this function is reached; this branch is a defence-in-depth).
    """
    total = inputs.operaciones_con_derecho_deduccion + inputs.operaciones_sin_derecho_deduccion
    if total == 0:
        return Decimal("100")
    ratio = inputs.operaciones_con_derecho_deduccion / total
    # LIVA art. 102.Dos: round up to the next whole integer percentage.
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

    Implements LIVA art. 102.Uno + art. 102.Dos. The caller supplies the
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


def _deductible_percentage_for(
    classification: InputClassification,
    general_percentage: Decimal,
) -> Decimal:
    """Map an input classification to its deductible percentage under LIVA art. 103."""
    if classification is InputClassification.EXCLUSIVELY_DEDUCTIBLE:
        return Decimal("100")
    if classification is InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE:
        return Decimal("0")
    # COMMON: apply the general prorrata percentage (art. 103.Uno.3.º).
    return general_percentage


def classify_input_deduction(
    classification: InputClassification,
    input_iva_amount: Decimal,
    general_percentage: Decimal,
) -> ProrrataInputDeduction:
    """Compute one deductible amount and return a :class:`ProrrataInputDeduction`.

    Implements prorrata especial (art. 103). The ``general_percentage`` is the
    value produced by :func:`compute_prorrata_general` for the same window; it
    only enters the calculation when the classification is ``COMMON``.
    """
    if input_iva_amount < 0:
        raise ProrrataInputError(f"input_iva_amount must be non-negative, got {input_iva_amount}")
    if general_percentage < 0 or general_percentage > 100:
        raise ProrrataInputError(f"general_percentage out of range 0..100, got {general_percentage}")

    deductible_percentage = _deductible_percentage_for(classification, general_percentage)
    deductible_amount = _round_to_cents(input_iva_amount * deductible_percentage / Decimal("100"))
    return ProrrataInputDeduction(
        classification=classification,
        input_iva_amount=input_iva_amount,
        deductible_percentage=deductible_percentage,
        deductible_amount=deductible_amount,
    )


def is_especial_mandatory(
    deduction_under_general: Decimal,
    deduction_under_especial: Decimal,
) -> bool:
    """Return True when LIVA art. 103.Dos forces the prorrata especial regime.

    The rule: the prorrata especial regime is mandatory whenever the
    deduction computed under the general regime would exceed the
    deduction computed under the especial regime by more than ten
    percent, i.e. ``deduction_general > deduction_especial * 1.10``.
    When the especial deduction is zero this function returns ``True``
    if the general deduction is positive (the general regime would over-
    deduct without bound).
    """
    if deduction_under_general < 0 or deduction_under_especial < 0:
        raise ProrrataInputError("deduction amounts must be non-negative")
    if deduction_under_especial == 0:
        return deduction_under_general > 0
    threshold = deduction_under_especial * PRORRATA_ESPECIAL_MANDATORY_MULTIPLE
    return deduction_under_general > threshold


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
# Helpers for the application layer
# ---------------------------------------------------------------------------


def sum_deductible_amounts(
    deductions: Iterable[ProrrataInputDeduction],
) -> Decimal:
    """Sum the ``deductible_amount`` field across a collection of inputs.

    The application aggregation layer uses this to roll up per-input
    deductions into the casilla 28 (Modelo 303) or casilla 33 (Modelo
    390) totals after running :func:`classify_input_deduction` for each
    purchase invoice evidence row.
    """
    return sum((entry.deductible_amount for entry in deductions), Decimal("0"))


__all__ = (
    "InputClassification",
    "ProrrataInputDeduction",
    "ProrrataInputs",
    "ProrrataKind",
    "ProrrataReference",
    "ProrrataRegime",
    "ProrrataResult",
    "ProrrataSector",
    "classify_input_deduction",
    "compute_prorrata_general",
    "compute_sectoral_prorrata",
    "is_especial_mandatory",
    "requires_sectoral_separation",
    "sum_deductible_amounts",
    "validate_prorrata_reference",
)
