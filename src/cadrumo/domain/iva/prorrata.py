"""Legal IVA prorrata substrate (LIVA arts. 102-106).

This module implements the Spanish Value-Added-Tax (IVA) prorrata mechanism
that governs how a taxable person who performs both deductible and
non-deductible operations may deduct input IVA. The arithmetic substrate
produces immutable result objects; its regime vocabulary is resolved through
the typed facts projection rather than defined as a Python catalogue.

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

from datetime import date
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from typing import Annotated, Final

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import core_schema

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST, FourDigitYear
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents as _round_to_cents
from ...core.percentage import Percentage
from ...core.registry_token import StrictRegistryToken
from .errors import ProrrataInputError
from .prorrata_especial_parameters import ProrrataEspecialMandatoryParameters


class _ProrrataStrictFrozen(BaseModel):
    """Strict, immutable Pydantic base for the prorrata substrate."""

    model_config = STRICT_FROZEN_CONFIG


SectorId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[-._a-zA-Z0-9]+$"),
]


class ProrrataRegime(str):
    """Opaque registry-projected LIVA prorrata regime token.

    The regime vocabulary and its legal semantics are selected from the
    dated ``renta-iva-deduction-ratio-policy`` fact.  This domain type keeps
    only the token shape; callers must use the typed registry projection when
    accepting a regime from a reference or producing a default result.
    """

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        """Expose the opaque token as a non-empty string to Pydantic."""
        return core_schema.no_info_after_validator_function(
            pydantic_validation_boundary(cls), core_schema.str_schema(min_length=1)
        )

    @property
    def value(self) -> str:
        """Return the opaque token for canonical reference serialization."""
        return str(self)


def _require_registry_prorrata_regime(
    value: object,
    *,
    effective_date: date | None = None,
) -> ProrrataRegime:
    """Resolve one regime token through the dated facts authority."""
    from ..calculations.registry.errors import RegistryValidationError
    from ..calculations.registry.prorrata_regime import require_prorrata_regime

    try:
        return require_prorrata_regime(value, effective_date=effective_date)
    except RegistryValidationError as exc:
        raise ProrrataInputError(str(exc)) from exc


def _default_registry_prorrata_regime(*, effective_date: date | None = None) -> ProrrataRegime:
    """Resolve the policy fact's declared default regime without a fallback."""
    from ..calculations.registry.errors import RegistryValidationError
    from ..calculations.registry.prorrata_regime import resolve_prorrata_regime_catalogue

    try:
        return resolve_prorrata_regime_catalogue(effective_date=effective_date).default_regime
    except RegistryValidationError as exc:
        raise ProrrataInputError(str(exc)) from exc


class _ProrrataRegistryToken(StrictRegistryToken):
    """Opaque token base whose membership is projected by the facts registry."""

    __slots__ = ()


class ProrrataKind(_ProrrataRegistryToken):
    """Opaque dated token for a provisional or definitive prorrata result."""


class InputClassification(_ProrrataRegistryToken):
    """Opaque dated token for one LIVA art. 106 input-use classification."""


def _require_registry_prorrata_kind(
    value: object,
    *,
    effective_date: date | None = None,
) -> ProrrataKind:
    """Resolve one lifecycle token through the dated 0116 facts authority."""
    from ..calculations.registry.errors import RegistryValidationError
    from ..calculations.registry.prorrata_vocabulary import require_prorrata_kind

    try:
        return require_prorrata_kind(value, effective_date=effective_date)
    except RegistryValidationError as exc:
        raise ProrrataInputError(str(exc)) from exc


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
    year: FourDigitYear
    period: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, pattern=r"^(Q[1-4]|M(0[1-9]|1[0-2])|annual)$"),
    ] = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_period_matches_kind(self) -> ProrrataResult:
        # The selected facts variant owns whether a lifecycle kind requires a
        # sub-period or is annual-only.  The period grammar itself remains a
        # structural contract of this result model.
        from ..calculations.registry.errors import RegistryValidationError
        from ..calculations.registry.prorrata_vocabulary import resolve_prorrata_kind_definition

        try:
            definition = resolve_prorrata_kind_definition(self.kind, effective_date=date(self.year, 1, 1))
        except RegistryValidationError as exc:
            raise ProrrataInputError(str(exc)) from exc
        if definition.period_required and self.period is None:
            raise ProrrataInputError("registry-declared prorrata kind requires a period (Qn or Mnn)")
        if definition.annual_only and self.period not in (None, "annual"):
            raise ProrrataInputError("registry-declared prorrata kind requires an annual or omitted period")
        return self


PRORRATA_REFERENCE_MAX_LENGTH: Final = 128
"""The longest prorrata reference, for any request that carries one."""


class ProrrataReference(_ProrrataStrictFrozen):
    """Stable identifier for a persisted IVA prorrata percentage.

    References use the canonical shape
    ``prorrata:{year}:{kind}:{regime}``, with an optional sector suffix
    ``:{sector_id}`` for sectoral-separation cases. The reference is a
    pointer to a legal IVA prorrata substrate value; it is not a
    proportional-use ratio and it is not derived from usage-ratio data.
    """

    reference_id: str = Field(min_length=1, max_length=PRORRATA_REFERENCE_MAX_LENGTH)
    year: FourDigitYear
    kind: ProrrataKind
    regime: ProrrataRegime
    sector_id: SectorId | None = None

    @field_validator("reference_id")
    @classmethod
    @pydantic_validation_boundary
    def _trim_reference_id(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    @pydantic_validation_boundary
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

    year: FourDigitYear
    multiple: Decimal = Field(..., gt=Decimal("1"))
    margin_percentage: Decimal = Field(..., gt=Decimal("0"))
    inclusive: bool


# ---------------------------------------------------------------------------
# Pure calculators
# ---------------------------------------------------------------------------


def _validate_year(year: int) -> int:
    """Refuse a year outside the one bound the filing-year axis declares.

    The ceiling here read 2100 while every other carrier of this axis read
    2099 -- the exact divergence ``cadrumo.core.filing_year`` exists to
    prevent, arrived at by restating the window locally instead of importing
    it. Nothing detected it, because a restated bound has nothing to disagree
    with until someone reads both.
    """
    if year < FOUR_DIGIT_YEAR_FIRST or year > FOUR_DIGIT_YEAR_LAST:
        raise ProrrataInputError(f"year is not written with four digits: {year}")
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
    sector_id: str | None = None
    match parts:
        case ["prorrata", _, _, _]:
            pass
        case ["prorrata", _, _, _, sector]:
            sector_id = sector
        case _:
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
        kind = _require_registry_prorrata_kind(parts[2], effective_date=date(year, 1, 1))
    except (ProrrataInputError, ValueError) as exc:
        raise ProrrataInputError(f"unknown prorrata_reference kind: {parts[2]!r}") from exc
    try:
        regime = _require_registry_prorrata_regime(parts[3], effective_date=date(year, 1, 1))
    except ValueError as exc:
        raise ProrrataInputError(f"unknown prorrata_reference regime: {parts[3]!r}") from exc
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


@pydantic_validation_boundary
def _require_canonical_prorrata_reference_text(value: str) -> str:
    """Refuse a request's non-blank prorrata reference unless the reference grammar accepts it.

    A blank value is left for the caller's own blank-means-absent normalisation;
    every other value must pass :func:`validate_prorrata_reference`, so a request
    cannot store what the IVA aggregation would later report as an invalid reference.
    """
    if not value.strip():
        return value
    return validate_prorrata_reference(value).reference_id


ProrrataReferenceText = Annotated[
    str,
    Field(max_length=PRORRATA_REFERENCE_MAX_LENGTH),
    AfterValidator(_require_canonical_prorrata_reference_text),
]
"""A prorrata reference as a write request carries it: bounded and held to the reference grammar.

Stored rows keep the plain text, so a row saved before this check still loads.
"""


def register_entry_prorrata_reference(
    *,
    ejercicio: int,
    regime: str,
    sector_id: str | None,
    settled: bool,
) -> ProrrataReference | None:
    """Name the percentage one register entry holds in force, or ``None`` where no reference can name it.

    A settled entry holds its definitive percentage, an unsettled one its
    provisional percentage. A register regime outside the reference regimes, such
    as a year under no prorrata, and a sector identifier the reference grammar
    cannot carry have no reference.
    """
    from ..calculations.registry.prorrata_vocabulary import definitive_prorrata_kind, provisional_prorrata_kind

    effective_date = date(ejercicio, 1, 1)
    kind = (definitive_prorrata_kind if settled else provisional_prorrata_kind)(effective_date=effective_date)
    try:
        reference_regime = _require_registry_prorrata_regime(regime, effective_date=effective_date)
        return ProrrataReference(
            reference_id=_canonical_prorrata_reference_id(
                year=ejercicio, kind=kind, regime=reference_regime, sector_id=sector_id
            ),
            year=ejercicio,
            kind=kind,
            regime=reference_regime,
            sector_id=sector_id,
        )
    except (ProrrataInputError, ValidationError):
        return None


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
    kind = _require_registry_prorrata_kind(kind, effective_date=date(year, 1, 1))
    percentage = _compute_percentage_general(inputs)
    try:
        return ProrrataResult(
            regime=_default_registry_prorrata_regime(effective_date=date(year, 1, 1)),
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

    The selected 0116 input-classification definition supplies either a fixed
    deductible percentage or the general percentage source.  Both the
    per-input deduction and the ledger's especial apportionment therefore
    consume one dated registry projection.
    """
    from ..calculations.registry.errors import RegistryValidationError
    from ..calculations.registry.prorrata_vocabulary import resolve_input_classification_definition

    try:
        definition = resolve_input_classification_definition(classification)
    except RegistryValidationError as exc:
        raise ProrrataInputError(str(exc)) from exc
    if definition.uses_general_percentage:
        return general_percentage
    if definition.deductible_percentage is None:
        raise ProrrataInputError("registry input classification has no deductible percentage")
    return definition.deductible_percentage


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
    # The year and the bundle are two independent legal inputs, and nothing
    # upstream forces them to agree. Without this check
    # `especial_mandatory_rule(2013, parameters=<resolved for 2025>)` would
    # return the post-2015 redaction labelled 2013 -- the resolver's own refusal
    # of a pre-2015 ejercicio is keyed on a DIFFERENT argument at a different
    # call site, so it cannot defend this one.
    if parameters.resolved_on.year != year:
        raise ProrrataInputError(
            f"art. 103.Dos.2 margin was resolved for {parameters.resolved_on.year} but is being "
            f"applied to filing year {year}; resolve the margin for the ejercicio being settled",
        )
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


class RegularizacionProrrataParticion(_ProrrataStrictFrozen):
    """One slice of the regularised cuotas that carries its own definitive percentage.

    A whole-entity general prorrata is a single partition. A taxpayer with
    differentiated sectors applies the deduction regime separately per sector
    (LIVA art. 101.Uno), and under prorrata especial only the common-use cuotas
    take the art. 104 percentage and its art. 105 procedure (art. 106.Uno
    regla 3.ª), so each such slice is its own partition.

    Attributes:
        cuotas_soportadas_deducibles: The partition's gross deductible cuotas
            in the regularised liquidations (art. 105.Seis), non-negative.
        prorrata_definitiva_pct: The partition's definitive percentage.
    """

    cuotas_soportadas_deducibles: Decimal = Field(..., ge=Decimal("0"))
    prorrata_definitiva_pct: Percentage


class RegularizacionProrrataParticionadaResult(_ProrrataStrictFrozen):
    """Outcome of an annual regularisation summed over its partitions (LIVA art. 105.Cuatro).

    Attributes:
        particiones: The partitions, in the caller's order.
        deduccion_provisional: The deductions actually practised on every
            partition's cuotas in the regularised liquidations.
        deduccion_definitiva: The sum of each partition's
            ``round(cuotas x definitiva% / 100)``.
        importe: ``deduccion_definitiva - deduccion_provisional``.
        direccion: :class:`RegularizacionProrrataDireccion` describing the sign.
    """

    particiones: tuple[RegularizacionProrrataParticion, ...]
    deduccion_provisional: Decimal
    deduccion_definitiva: Decimal
    importe: Decimal
    direccion: RegularizacionProrrataDireccion


def compute_regularizacion_prorrata_particionada(
    *,
    particiones: tuple[RegularizacionProrrataParticion, ...],
    deducciones_provisionales_practicadas: Decimal,
) -> RegularizacionProrrataParticionadaResult:
    """Compute the annual regularisation over partitions with their own definitive percentages.

    Each partition applies its own definitive percentage to its own gross cuotas
    (LIVA arts. 101.Uno, 105.Seis and 106.Uno regla 3.ª), rounded to cents per
    partition as a separately applied deduction regime is; the deductions the
    regularised liquidations actually practised on those cuotas are then
    subtracted once::

        deduccion_definitiva = sum(round(cuotas_k x definitiva_k% / 100))
        importe              = deduccion_definitiva - deducciones_practicadas

    No partition means no cuota the art. 105 procedure reaches (for example a
    prorrata especial year whose inputs are all exclusively used), so the
    definitive deduction is zero.
    """
    deduccion_definitiva = sum(
        (
            _round_to_cents(particion.cuotas_soportadas_deducibles * particion.prorrata_definitiva_pct / Decimal("100"))
            for particion in particiones
        ),
        Decimal("0"),
    )
    importe = deduccion_definitiva - deducciones_provisionales_practicadas
    return RegularizacionProrrataParticionadaResult(
        particiones=particiones,
        deduccion_provisional=deducciones_provisionales_practicadas,
        deduccion_definitiva=deduccion_definitiva,
        importe=importe,
        direccion=_regularizacion_direccion(importe),
    )


def _regularizacion_direccion(importe: Decimal) -> RegularizacionProrrataDireccion:
    if importe > Decimal("0"):
        return RegularizacionProrrataDireccion.DEDUCCION
    if importe < Decimal("0"):
        return RegularizacionProrrataDireccion.INGRESO
    return RegularizacionProrrataDireccion.NINGUNA


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
    from ..calculations.registry.errors import RegistryValidationError
    from ..calculations.registry.prorrata_vocabulary import definitive_prorrata_kind

    try:
        definitive_kind = definitive_prorrata_kind(effective_date=date(year, 1, 1))
    except RegistryValidationError as exc:
        raise ProrrataInputError(str(exc)) from exc
    return compute_prorrata_general(
        inputs,
        year=year,
        kind=definitive_kind,
        period="annual",
        sector_id=sector_id,
    )


# ---------------------------------------------------------------------------
# Helpers for caller-side rollups
# ---------------------------------------------------------------------------


__all__ = (
    "PRORRATA_REFERENCE_MAX_LENGTH",
    "EspecialMandatoryRule",
    "InputClassification",
    "ProrrataInputs",
    "ProrrataKind",
    "ProrrataReference",
    "ProrrataReferenceText",
    "ProrrataRegime",
    "ProrrataResult",
    "RegularizacionProrrataDireccion",
    "RegularizacionProrrataParticion",
    "RegularizacionProrrataParticionadaResult",
    "compute_prorrata_definitiva_anual",
    "compute_prorrata_general",
    "compute_regularizacion_prorrata_particionada",
    "deductible_percentage_for",
    "especial_mandatory_rule",
    "is_especial_mandatory",
    "register_entry_prorrata_reference",
    "validate_prorrata_reference",
)
