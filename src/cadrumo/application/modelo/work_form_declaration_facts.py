"""The facts a work form states about the whole declaration, beyond its fields.

Where the latest calculation noticed something, whether it replayed AEAT tax
data, the last day to file, the settled result and its direction, whether the
declaration is recorded as filed, the latest exported file, and why nothing may
be edited. Each is classified from declared facts so a frontend only renders it.
Whether the filing year is carried across from another edition is read from the
pinned :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, Field, model_validator

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import InternalInvariantError, pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.result_disposition import ResultDisposition
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_references import TemporalProjectionDirection
from ...domain.deadlines.festivos import DeadlineHolidayCoverage
from ...domain.iva.refund_eligibility import RefundEligibility
from ...domain.modelos.calculation_revision_sources import CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT, CalculationNoteFact
from .work_form_findings import ModeloFormAttention


class ModeloFormBase(BaseModel):
    model_config = STRICT_FROZEN_CONFIG


class ModeloFormResolutionAnswer(StrEnum):
    """Which answer a source disagreement's line offers the operator, decided from the resolutions held."""

    ACCEPT = "accept"
    """No active acceptance covers the disagreement, so the line offers to accept the amount in use."""
    REVOKE = "revoke"
    """An active acceptance covers the disagreement, so the line offers to take that acceptance back."""


class ModeloFormCalculationNote(ModeloFormBase):
    """One thing the latest calculation noticed, on the filer's scale, with the box it names.

    ``reason`` is the calculation's own reason code, which the frontend words
    from the catalogue; ``box`` is the printed box number when the note names a
    box the form prints. ``withholds_filing`` is the application's
    calculation-note gate's own answer: the gate refuses the file and the
    recording while such a note stands, whatever its attention says, so the
    editor withholds them too (:attr:`ModeloWorkForm.blocking_calculation_notes`),
    as it does for a note at the blocking level. ``finding_id`` names the source
    disagreement the note states, the id an operator answers with a resolution;
    it is ``None`` for every other note. ``resolution_answer`` is the answer the
    note offers for that disagreement, accepting it or taking an acceptance back;
    it is ``None`` exactly when ``finding_id`` is. ``fact`` is what this note says
    about its own subject, when its reason alone does not. ``message`` is the
    calculation's own account of this note, as its resolver worded it for the
    filer and the calculate result carries it, in the form's language; ``None``
    when it wrote none in that language, or when only the note that persists
    with the calculation is known.
    """

    reason: str = Field(min_length=1, max_length=64)
    attention: ModeloFormAttention
    casilla_id: CasillaId | None = None
    box: str | None = None
    withholds_filing: bool = False
    finding_id: str | None = Field(default=None, min_length=16, max_length=16)
    resolution_answer: ModeloFormResolutionAnswer | None = None
    fact: CalculationNoteFact | None = None
    element_names: tuple[tuple[str, str], ...] = ()
    message: str | None = Field(default=None, min_length=1, max_length=CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT)


class ModeloFormAeatData(ModeloFormBase):
    """The AEAT tax data (borrador) the current calculation took values from.

    Recalculating replays the imported snapshot, so its values keep feeding the
    declaration until it is replaced. ``imported_at`` is when the data was
    imported, or ``None`` when this read could not open the snapshot's record;
    ``binding_ids`` are the bindings whose values the snapshot supplied.
    """

    snapshot_id: str = Field(min_length=1)
    imported_at: datetime | None = None
    binding_ids: tuple[BindingId, ...] = ()


class ModeloFormYearProjection(ModeloFormBase):
    """Whether the declaration's filing year is carried across from another edition, as the registry resolves it.

    ``direction`` is ``authored`` when the selected edition authors the filing
    year, otherwise ``forward`` or ``backward`` for the nearest edition carried
    across; ``authored_filing_year`` is the year that edition authors and
    ``reachable_grade`` the rung of authority the year reaches. The registry's
    temporal resolver and grade rule supply all three; a surface renders them.
    ``reachable_grade_words`` names that rung. ``words`` is the sentence
    verification refuses a filing check with, served before any check: for a
    carried year, that the declaration calculates under that edition's rules
    and cannot be checked for filing or exported; for a year its own edition
    authors below filing grade, that those rules are not yet checked against
    the official sources closely enough to file. It is ``None`` when the year
    reaches filing grade.
    """

    direction: TemporalProjectionDirection
    authored_filing_year: int
    reachable_grade: RegistryAuthorityGrade
    reachable_grade_words: str = Field(min_length=1)
    words: str | None = None


_PROJECTED_YEAR_LOCALE_KEY: Final = "application.modelo.findings.registry_filing_year_projected"
_GRADE_INSUFFICIENT_LOCALE_KEY: Final = "application.modelo.findings.registry_authority_grade_insufficient"
_REACHABLE_GRADE_LOCALE_KEYS: Final[dict[RegistryAuthorityGrade, str]] = {
    RegistryAuthorityGrade.APPLICABILITY: "application.modelo.work_form.authority_grade.applicability",
    RegistryAuthorityGrade.CALCULATION: "application.modelo.work_form.authority_grade.calculation",
    RegistryAuthorityGrade.FILING: "application.modelo.work_form.authority_grade.filing",
}
"""A literal table so the locale audit sees each rung's word reach the translator."""
if set(_REACHABLE_GRADE_LOCALE_KEYS) != set(RegistryAuthorityGrade):
    raise InternalInvariantError("every authority grade needs its word")


def year_projection(
    snapshot: RegistrySnapshot, *, modelo: str, period: str, language: OutputLanguage
) -> ModeloFormYearProjection:
    """The projection the pinned snapshot's registry resolution states for its filing year, said in ``language``.

    Args:
        snapshot: The pinned :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            whose temporal resolution and reachable grade the projection carries.
        modelo: The declaration's modelo.
        period: The declaration's registry period token.
        language: The filer's language.
    """
    direction = snapshot.revision_projection_direction
    authored = snapshot.edition_filing_year
    reachable = snapshot.effective_authority_grade
    words: str | None = None
    if direction is not TemporalProjectionDirection.AUTHORED:
        words = tr(
            _PROJECTED_YEAR_LOCALE_KEY,
            modelo=modelo,
            filing_year=snapshot.filing_year,
            period=period,
            authored_filing_year=authored,
            locale=language.value,
        )
    elif reachable is not RegistryAuthorityGrade.FILING:
        words = tr(
            _GRADE_INSUFFICIENT_LOCALE_KEY,
            modelo=modelo,
            filing_year=snapshot.filing_year,
            period=period,
            locale=language.value,
        )
    return ModeloFormYearProjection(
        direction=direction,
        authored_filing_year=authored,
        reachable_grade=reachable,
        reachable_grade_words=tr(_REACHABLE_GRADE_LOCALE_KEYS[reachable], locale=language.value),
        words=words,
    )


class ModeloFormDeadline(ModeloFormBase):
    """The last day of the voluntary filing window for this declaration.

    ``nominal_closes_on`` is the date the registry declares; ``closes_on`` is
    the date after the business-day shift, and ``holiday_coverage`` says which
    holidays that shift accounted for, so a date computed without its holiday
    calendar is never passed off as final. Exactly one of
    ``days_remaining`` and ``days_overdue`` is set, counted from
    ``reference_on``.
    """

    closes_on: date
    nominal_closes_on: date
    holiday_coverage: DeadlineHolidayCoverage
    reference_on: date
    days_remaining: int | None = Field(default=None, ge=0)
    days_overdue: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _one_posture(self) -> ModeloFormDeadline:
        if (self.days_remaining is None) == (self.days_overdue is None):
            raise ValueError("a deadline is either still open or passed, never both or neither")
        return self


class ModeloFormResultDirection(StrEnum):
    """Which way the declaration's result settles, as its official design declares it."""

    TO_PAY = "to_pay"
    TO_REFUND = "to_refund"
    TO_CARRY_FORWARD = "to_carry_forward"
    #: A negative instalment result the filer deducts from the positive results of later quarters of the same year.
    TO_DEDUCT_LATER = "to_deduct_later"
    #: A negative result that nothing carries: it is declared as negative and settles nothing.
    NEGATIVE = "negative"
    NIL = "nil"
    #: Nothing declares how this result settles, or it has no value yet.
    UNKNOWN = "unknown"


AMOUNTLESS_RESULT_DIRECTIONS: frozenset[ModeloFormResultDirection] = frozenset(
    {ModeloFormResultDirection.NEGATIVE, ModeloFormResultDirection.NIL}
)
"""The directions of a result that settles nothing, so no amount is shown beside them."""


class ModeloFormResult(ModeloFormBase):
    """The box that settles the declaration, its value and its direction.

    ``disposition`` is the official "tipo de declaración" code the result
    implies before any election the filer makes when filing; the direction is
    read from it and from nothing else, never from the sign alone. When the
    registry names the settlement box but declares no such rule, the direction
    is unknown. ``election_may_change`` says the filer's refund election can
    still turn a carried credit into a refund.

    ``refund_eligibility`` is why it can or cannot, for a carried IVA credit:
    the law admits the refund only at the year's last period or for a taxpayer
    inscribed in the Registro de devolución mensual (LIVA art. 115). It is
    ``None`` for every result with no refund election to make, and
    ``election_may_change`` is true exactly when that eligibility allows the
    refund, so the two can never disagree.
    """

    casilla_id: CasillaId
    box: str | None
    value: Decimal | None
    direction: ModeloFormResultDirection
    disposition: ResultDisposition | None = None
    election_may_change: bool = False
    refund_eligibility: RefundEligibility | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _election_agrees_with_its_eligibility(self) -> ModeloFormResult:
        allowed = self.refund_eligibility is not None and self.refund_eligibility.refund_allowed
        if self.election_may_change != allowed:
            raise ValueError("a refund election is offered exactly when its eligibility allows the refund")
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _direction_needs_a_value(self) -> ModeloFormResult:
        if self.value is None and self.direction is not ModeloFormResultDirection.UNKNOWN:
            raise ValueError("a result without a value has no direction")
        return self


class ModeloFormFiling(ModeloFormBase):
    """The declaration is recorded in Cadrumo as filed; nothing was sent to AEAT from here."""

    #: When the filing was recorded, or ``None`` when the revision does not say.
    recorded_at: datetime | None = None


class ModeloFormExport(ModeloFormBase):
    """The latest file exported for this declaration, and whether it was made from the current calculation.

    A file made from an earlier calculation no longer matches the declaration:
    changes applied or a recalculation since then created a newer one, so that
    file must not be uploaded.
    """

    exported_at: datetime
    calculation_revision_id: str = Field(min_length=1)
    current: bool


class ModeloFormEditClosure(StrEnum):
    """Why nothing on the form may be edited, whatever the edit admission says."""

    #: The declaration is recorded as filed; changing it starts a correction
    #: (a complementaria or a rectificativa), never an edit in place.
    RECORDED_AS_FILED = "recorded_as_filed"


__all__ = [
    "AMOUNTLESS_RESULT_DIRECTIONS",
    "ModeloFormAeatData",
    "ModeloFormCalculationNote",
    "ModeloFormDeadline",
    "ModeloFormEditClosure",
    "ModeloFormExport",
    "ModeloFormFiling",
    "ModeloFormResolutionAnswer",
    "ModeloFormResult",
    "ModeloFormResultDirection",
]
