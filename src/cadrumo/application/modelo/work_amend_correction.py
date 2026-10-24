"""What correcting a declaration recorded as filed shows, and how its corrected values are read.

A correction (a complementaria, a sustitutiva or a rectificativa) restates
casillas of a filed declaration. Every frontend lists the same boxes the
command-line amendment wizard lists, those the filed calculation declares a
figure for, in box order, and reads what the filer types for each through one
grammar: the preflight's typed-entry reader with
:func:`correction_value_grammar`, whose bounds are the amendment request's own
override shape, so a value read here is a value the amendment accepts.

:func:`worded_amendment_context` words the correction in the filer's language:
the filed record, the kinds the period permits, the Modelo 303 rectificativa
motives when they apply, and each box with its filed figure.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.identifiers import canonical_decimal_string
from ...domain.modelos.calculation_revision_amendment import (
    CalculationRevisionAmendmentKind,
    M303RectificativaMotive,
)
from ...domain.modelos.filing_record import FilingDeclarationKind
from ..operations.public_scalar import PublicDecimal
from .edit_models import ModeloEditCorrectionAddressV1
from .edit_value_grammar import ModeloEditValueChannel, ModeloEditValueFamily, ModeloEditValueGrammarV1, ratio_unit
from .printed_boxes import printed_box_number
from .value_presentation import format_casilla_value
from .work_form_localization import (
    casilla_help_text,
    localized_text,
    render_box_locator_patterns,
    unnamed_casilla_label,
)
from .work_form_wording import day_text, modelo_title, period_words

if TYPE_CHECKING:
    from ...domain.calculations.registry.query_reports import ModeloCasillaRow
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
    from ...domain.modelos.filing_record import ModeloRecord
    from ...domain.modelos.work_unit import WorkUnit
    from .calculation_projection import ModeloCalculationSnapshot

#: The fraction digits and magnitude of one corrected value, as the amendment
#: request's override shape (``-?\d{1,15}(\.\d{1,6})?``) admits them.
CORRECTION_FRACTION_DIGITS: Final = 6
CORRECTION_MAGNITUDE: Final = "999999999999999.999999"

_KIND_WORDS_LOCALE_KEY: Final = "workspace.declarations.declaration_kind.{kind}"
_KIND_HELP_LOCALE_KEYS: Final[Mapping[CalculationRevisionAmendmentKind, str]] = MappingProxyType(
    {kind: f"workspace.modelo.amend.kind_help.{kind.value}" for kind in CalculationRevisionAmendmentKind}
)
_MOTIVE_LOCALE_KEYS: Final[Mapping[M303RectificativaMotive, str]] = MappingProxyType(
    {motive: f"workspace.modelo.amend.motive.{motive.value}" for motive in M303RectificativaMotive}
)
_MOTIVE_HELP_LOCALE_KEY: Final = "workspace.modelo.amend.motive_help"
_REASON_PROMPT_LOCALE_KEY: Final = "workspace.modelo.amend.reason_prompt"


def correction_value_grammar(casilla: CasillaDefinition) -> ModeloEditValueGrammarV1:
    """The grammar a corrected value of ``casilla`` is read against.

    Every figure a filed calculation declares is a decimal, whatever the box
    prints, and the amendment takes it as decimal text within the override
    shape; the box's own data type is kept so a ratio reads in its unit.
    """
    data_type = str(casilla.data_type)
    maximum = casilla.constraints.max_value if casilla.constraints is not None else None
    return ModeloEditValueGrammarV1(
        data_type=data_type,
        family=ModeloEditValueFamily.DECIMAL,
        channel=ModeloEditValueChannel.DECIMAL,
        max_fraction_digits=CORRECTION_FRACTION_DIGITS,
        minimum=f"-{CORRECTION_MAGNITUDE}",
        maximum=CORRECTION_MAGNITUDE,
        ratio_unit=ratio_unit(data_type, maximum),
    )


def correction_value_grammars(snapshot: RegistrySnapshot) -> Mapping[CasillaId, ModeloEditValueGrammarV1]:
    """The correction grammar of every casilla the revision defines, by casilla."""
    return MappingProxyType({casilla.id: correction_value_grammar(casilla) for casilla in snapshot.revision.casillas})


def filed_casilla_values(calculation: ModeloCalculationSnapshot) -> dict[str, Decimal]:
    """The exact figures the filed calculation declares, by casilla.

    Raises:
        ValueError: When a declared figure is not a decimal, which no stored
            calculation carries.
    """
    values: dict[str, Decimal] = {}
    for fact in calculation.casilla_values:
        if not isinstance(fact.value, PublicDecimal):
            raise ValueError("a filed calculation declares decimal figures only")
        values[fact.key] = Decimal(fact.value.decimal)
    return values


def amendable_casilla_rows(
    casilla_rows: tuple[ModeloCasillaRow, ...], filed_values: Mapping[str, Decimal]
) -> tuple[ModeloCasillaRow, ...]:
    """The registry rows the filed calculation declares a figure for, in casilla-number order.

    These are exactly the casillas a correction may restate, read top to bottom
    like the printed return.
    """
    return tuple(row for row in sorted(casilla_rows, key=lambda r: r.number) if row.casilla_id in filed_values)


class ModeloAmendmentFiledRecordV1(BaseModel):
    """The filed declaration the correction restates, in the filer's words."""

    model_config = STRICT_FROZEN_CONFIG

    filing_record_id: str = Field(min_length=1)
    modelo_title: str = Field(min_length=1)
    period_words: str = Field(min_length=1)
    declaration_kind: FilingDeclarationKind
    declaration_kind_words: str = Field(min_length=1)
    filed_at: datetime
    #: The day the filing was recorded, as the filer's language writes a date.
    filed_on: str = Field(min_length=1)


class ModeloAmendmentKindOptionV1(BaseModel):
    """One kind of correction the period permits, with its name and what it does."""

    model_config = STRICT_FROZEN_CONFIG

    kind: CalculationRevisionAmendmentKind
    words: str = Field(min_length=1)
    help: str = Field(min_length=1)


class ModeloAmendmentMotiveOptionV1(BaseModel):
    """One motive a Modelo 303 rectificativa states, with its name."""

    model_config = STRICT_FROZEN_CONFIG

    motive: M303RectificativaMotive
    words: str = Field(min_length=1)


class ModeloAmendmentCorrectionRowV1(BaseModel):
    """One box the correction may restate: its filed figure and how a corrected figure is typed.

    ``edit_address`` addresses the filer's entry in a preflight, whose typed
    entry reads it against ``grammar``; ``filed_value`` is the exact decimal the
    filing declares and ``filed_value_text`` the same figure as the box shows it.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    box: str | None
    label: str = Field(min_length=1)
    help: str | None
    data_type: str = Field(min_length=1)
    filed_value: str = Field(min_length=1)
    filed_value_text: str = Field(min_length=1)
    edit_address: ModeloEditCorrectionAddressV1
    grammar: ModeloEditValueGrammarV1
    legal_refs: tuple[str, ...]


class ModeloAmendmentCorrectionContextV1(BaseModel):
    """A correction of one filed declaration, worded in ``language``.

    ``motive_applies`` says whether a rectificativa of this declaration states
    a motive; ``motives`` are offered only then, and only for that kind.
    """

    model_config = STRICT_FROZEN_CONFIG

    language: OutputLanguage
    filed: ModeloAmendmentFiledRecordV1
    kinds: tuple[ModeloAmendmentKindOptionV1, ...] = Field(min_length=1)
    motive_applies: bool
    motive_kind: CalculationRevisionAmendmentKind | None
    motive_help: str | None
    motives: tuple[ModeloAmendmentMotiveOptionV1, ...]
    reason_prompt: str = Field(min_length=1)
    rows: tuple[ModeloAmendmentCorrectionRowV1, ...]


def worded_amendment_context(
    *,
    record: ModeloRecord,
    unit: WorkUnit,
    snapshot: RegistrySnapshot,
    casilla_rows: tuple[ModeloCasillaRow, ...],
    filed_values: Mapping[str, Decimal],
    permitted_kinds: tuple[CalculationRevisionAmendmentKind, ...],
    motive_applicable: bool,
    language: OutputLanguage,
) -> ModeloAmendmentCorrectionContextV1:
    """Word the correction of ``record`` for a filer reading ``language``.

    The motives are offered exactly when the command-line wizard asks them: for
    an applicable Modelo 303 rectificativa.
    """
    locale = language.value
    motive_applies = motive_applicable and CalculationRevisionAmendmentKind.RECTIFICATIVA in permitted_kinds
    return ModeloAmendmentCorrectionContextV1(
        language=language,
        filed=ModeloAmendmentFiledRecordV1(
            filing_record_id=record.filing_record_id,
            modelo_title=modelo_title(str(unit.modelo), language),
            period_words=period_words(unit.period, language),
            declaration_kind=record.declaration_kind,
            declaration_kind_words=tr(_KIND_WORDS_LOCALE_KEY.format(kind=record.declaration_kind.value), locale=locale),
            filed_at=record.filed_at,
            filed_on=day_text(record.filed_at, language),
        ),
        kinds=tuple(
            ModeloAmendmentKindOptionV1(
                kind=kind,
                words=tr(_KIND_WORDS_LOCALE_KEY.format(kind=kind.value), locale=locale),
                help=tr(_KIND_HELP_LOCALE_KEYS[kind], locale=locale),
            )
            for kind in permitted_kinds
        ),
        motive_applies=motive_applies,
        motive_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA if motive_applies else None,
        motive_help=tr(_MOTIVE_HELP_LOCALE_KEY, locale=locale) if motive_applies else None,
        motives=(
            tuple(
                ModeloAmendmentMotiveOptionV1(motive=motive, words=tr(_MOTIVE_LOCALE_KEYS[motive], locale=locale))
                for motive in M303RectificativaMotive
            )
            if motive_applies
            else ()
        ),
        reason_prompt=tr(_REASON_PROMPT_LOCALE_KEY, locale=locale),
        rows=_correction_rows(snapshot, casilla_rows, filed_values, language),
    )


def _correction_rows(
    snapshot: RegistrySnapshot,
    casilla_rows: tuple[ModeloCasillaRow, ...],
    filed_values: Mapping[str, Decimal],
    language: OutputLanguage,
) -> tuple[ModeloAmendmentCorrectionRowV1, ...]:
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    locators = render_box_locator_patterns(snapshot.modelo.id)
    rows: list[ModeloAmendmentCorrectionRowV1] = []
    for row in amendable_casilla_rows(casilla_rows, filed_values):
        casilla = casillas.get(row.casilla_id)
        if casilla is None:
            raise ValueError("the amendment lists a casilla its revision does not define")
        label = (localized_text(casilla.localization_keys, language) or unnamed_casilla_label(language)).text
        grammar = correction_value_grammar(casilla)
        filed = filed_values[row.casilla_id]
        rows.append(
            ModeloAmendmentCorrectionRowV1(
                casilla_id=row.casilla_id,
                box=printed_box_number(casilla, None),
                label=label,
                help=casilla_help_text(casilla, label, language=language, box_locators=locators),
                data_type=grammar.data_type,
                filed_value=canonical_decimal_string(filed),
                filed_value_text=format_casilla_value(
                    filed, data_type=grammar.data_type, language=language, ratio_unit=grammar.ratio_unit
                ),
                edit_address=ModeloEditCorrectionAddressV1(casilla_id=row.casilla_id),
                grammar=grammar,
                legal_refs=tuple(row.legal_refs),
            )
        )
    return tuple(rows)


__all__ = [
    "CORRECTION_FRACTION_DIGITS",
    "CORRECTION_MAGNITUDE",
    "ModeloAmendmentCorrectionContextV1",
    "ModeloAmendmentCorrectionRowV1",
    "ModeloAmendmentFiledRecordV1",
    "ModeloAmendmentKindOptionV1",
    "ModeloAmendmentMotiveOptionV1",
    "amendable_casilla_rows",
    "correction_value_grammar",
    "correction_value_grammars",
    "filed_casilla_values",
    "worded_amendment_context",
]
