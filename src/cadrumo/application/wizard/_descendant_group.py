"""The descendant repeating group for the setup flow's familia phase.

Descendant collection is a genuinely new wizard surface: the one-shot
:class:`~cadrumo.application.wizard.WizardFlow` catalogue carries no
repeating-group primitive, so the group is authored directly in the
substrate's :class:`~cadrumo.application.flows.FlowRepeatingGroup`
vocabulary and spliced into the bridged
:class:`~cadrumo.application.flows.FlowDefinition` by
:func:`attach_descendant_group` -- the same post-bridge decoration seam
as the format-hint and legal-validator attachers, so the substrate's
one-way projection stays domain-blind.

A count question (:data:`DESCENDANTS_COUNT_PAGE_ID`) gates the per-
descendant page family: the engine expands the group to that INTEGER
answer, so ``count = 0`` hides every instance page and a positive count
exposes one page set per descendant. Instance answers key the canonical
answer map as ``descendientes#<index>.<page-id>``; the commit path
projects them through
:func:`~cadrumo.application.wizard._persistence.descendant_facts_from_answers`
into the exact ``renta_family.descendiente.{n}.*`` fact shape the
``_minimo_descendientes_facts`` injector and the registry selectors
consume.

Every ``wizard.setup.descendientes.*`` copy reference is declared as a
``_LOCALE_KEY`` module constant so the locale scaffold's static usage
scanner treats it as live -- the keys are referenced only through the
frozen page literals below, never at a ``tr()`` call site.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.flows import REPEATING_INSTANCE_SEPARATOR, CopyRefKind, FlowWidgetKind
from ...core.identity import IdentityError, validate_identity
from ...core.parsing import parse_iso8601_date
from ...core.time import today_madrid
from ...domain.deadlines import EntityType
from ..flows import (
    CopyRef,
    FlowChoice,
    FlowCondition,
    FlowDefinition,
    FlowPage,
    FlowRepeatingGroup,
    ValidationVerdict,
    register_answer_validator,
    register_cross_field_validator,
)

_FAMILIA_SECTION_ID = "familia"

#: Repeating-group id; instance answers key as ``descendientes#<index>.<page>``.
DESCENDANTS_GROUP_ID = "descendientes"

#: Count-source page id; its INTEGER answer drives the instance count.
DESCENDANTS_COUNT_PAGE_ID = "descendientes-count"

# Per-descendant page ids, in walk order. These bare tokens are the
# ``<page-id>`` half of every ``descendientes#<index>.<page-id>`` answer key.
_BIRTH_DATE_PAGE_ID = "birth-date"
_ADOPTION_DATE_PAGE_ID = "adoption-date"
_DISCAPACIDAD_PAGE_ID = "discapacidad"
_CONVIVENCIA_PAGE_ID = "convivencia"
_CUSTODIA_COMPARTIDA_PAGE_ID = "custodia-compartida"
_MESES_MADRE_TRABAJO_PAGE_ID = "meses-madre-trabajo"
_GASTOS_GUARDERIA_PAGE_ID = "gastos-guarderia"
_NIF_PAGE_ID = "nif"

#: Per-descendant page ids in walk order (consumed by the fact projection).
DESCENDANT_PAGE_IDS: tuple[str, ...] = (
    _BIRTH_DATE_PAGE_ID,
    _ADOPTION_DATE_PAGE_ID,
    _DISCAPACIDAD_PAGE_ID,
    _CONVIVENCIA_PAGE_ID,
    _CUSTODIA_COMPARTIDA_PAGE_ID,
    _MESES_MADRE_TRABAJO_PAGE_ID,
    _GASTOS_GUARDERIA_PAGE_ID,
    _NIF_PAGE_ID,
)

#: Registered id of the per-answer descendant-NIF validator.
DESCENDANT_NIF_VALIDATOR_ID = "descendant-nif"

#: Registered id of the per-answer descendant meses-madre-trabajo range validator.
DESCENDANT_MESES_VALIDATOR_ID = "descendant-meses-range"

#: Registered id of the per-answer descendant gastos-guardería sign validator.
DESCENDANT_GASTOS_VALIDATOR_ID = "descendant-gastos-nonneg"

#: Registered id of the flow-scope descendant adoption-date cross-field validator.
DESCENDANT_ADOPTION_VALIDATOR_ID = "descendant-adoption-dates"

_MESES_MIN = 0
_MESES_MAX = 12

# --- copy references (new wizard.setup.descendientes.* locale keys) ---------

_GROUP_TITLE_LOCALE_KEY = "wizard.setup.descendientes.title"
_COUNT_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.count.prompt"
_COUNT_HELP_LOCALE_KEY = "wizard.setup.descendientes.count.help"
_BIRTH_DATE_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.birth-date.prompt"
_ADOPTION_DATE_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.adoption-date.prompt"
_DISCAPACIDAD_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.discapacidad.prompt"
_DISCAPACIDAD_CHOICE_0_LOCALE_KEY = "wizard.setup.descendientes.discapacidad.choices.0.label"
_DISCAPACIDAD_CHOICE_33_LOCALE_KEY = "wizard.setup.descendientes.discapacidad.choices.33.label"
_DISCAPACIDAD_CHOICE_65_LOCALE_KEY = "wizard.setup.descendientes.discapacidad.choices.65.label"
_CONVIVENCIA_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.convivencia.prompt"
_CUSTODIA_COMPARTIDA_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.custodia-compartida.prompt"
_MESES_MADRE_TRABAJO_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.meses-madre-trabajo.prompt"
_MESES_MADRE_TRABAJO_HELP_LOCALE_KEY = "wizard.setup.descendientes.meses-madre-trabajo.help"
_GASTOS_GUARDERIA_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.gastos-guarderia.prompt"
_GASTOS_GUARDERIA_HELP_LOCALE_KEY = "wizard.setup.descendientes.gastos-guarderia.help"
_NIF_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.nif.prompt"

# Verdict message keys minted for the constraint guards below (the range,
# sign, and adoption-order refusals). Reused generic keys were checked
# first: the closest existing leaves (cli.config.descendiente.*) carry
# CLI-flag-specific prose, so wizard-namespace keys are minted here.
_MESES_INVALID_RANGE_LOCALE_KEY = "wizard.setup.descendientes.meses-madre-trabajo.invalid_range"
_GASTOS_INVALID_NEGATIVE_LOCALE_KEY = "wizard.setup.descendientes.gastos-guarderia.invalid_negative"
_ADOPTION_BEFORE_BIRTH_LOCALE_KEY = "wizard.setup.descendientes.adoption-date.before_birth"
_ADOPTION_IN_FUTURE_LOCALE_KEY = "wizard.setup.descendientes.adoption-date.in_future"

# Format hints reuse the shared wizard.setup.format.* keys already shipped
# by the format-hint decorator; the NIF failure verdict reuses the existing
# tax-id error key, so neither mints a new locale key.
_FORMAT_DATE_LOCALE_KEY = "wizard.setup.format.date-iso"
_FORMAT_AMOUNT_LOCALE_KEY = "wizard.setup.format.amount-eur"
_FORMAT_UNITS_LOCALE_KEY = "wizard.setup.format.units-count"
_FORMAT_TAX_ID_LOCALE_KEY = "wizard.setup.format.tax-id"
_NIF_INVALID_LOCALE_KEY = "wizard.errors.invalid_tax_id"

#: Every net-new locale key this module references, for the scaffold gate.
DESCENDANT_LOCALE_KEYS: tuple[str, ...] = (
    _GROUP_TITLE_LOCALE_KEY,
    _COUNT_PROMPT_LOCALE_KEY,
    _COUNT_HELP_LOCALE_KEY,
    _BIRTH_DATE_PROMPT_LOCALE_KEY,
    _ADOPTION_DATE_PROMPT_LOCALE_KEY,
    _DISCAPACIDAD_PROMPT_LOCALE_KEY,
    _DISCAPACIDAD_CHOICE_0_LOCALE_KEY,
    _DISCAPACIDAD_CHOICE_33_LOCALE_KEY,
    _DISCAPACIDAD_CHOICE_65_LOCALE_KEY,
    _CONVIVENCIA_PROMPT_LOCALE_KEY,
    _CUSTODIA_COMPARTIDA_PROMPT_LOCALE_KEY,
    _MESES_MADRE_TRABAJO_PROMPT_LOCALE_KEY,
    _MESES_MADRE_TRABAJO_HELP_LOCALE_KEY,
    _GASTOS_GUARDERIA_PROMPT_LOCALE_KEY,
    _GASTOS_GUARDERIA_HELP_LOCALE_KEY,
    _NIF_PROMPT_LOCALE_KEY,
    _MESES_INVALID_RANGE_LOCALE_KEY,
    _GASTOS_INVALID_NEGATIVE_LOCALE_KEY,
    _ADOPTION_BEFORE_BIRTH_LOCALE_KEY,
    _ADOPTION_IN_FUTURE_LOCALE_KEY,
)


def _locale_ref(key: str) -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=key)


def _validate_descendant_nif(page: FlowPage, canonical: str) -> ValidationVerdict:
    """Validate a descendant NIF through the canonical identity authority.

    A descendant may legitimately lack a NIF (a minor without one), so a
    blank canonical passes; a non-blank value must satisfy the Spanish
    NIF / NIE / CIF checksum in :func:`cadrumo.core.identity.validate_identity`
    -- the same authority the identity pages bind. A malformed value
    returns the ``wizard.errors.invalid_tax_id`` verdict carrying only the
    page id; the raw answer never enters the diagnostic.
    """
    if not canonical:
        return ValidationVerdict.passed()
    try:
        validate_identity(canonical)
    except IdentityError:
        return ValidationVerdict.failed(_NIF_INVALID_LOCALE_KEY, page_id=page.id)
    return ValidationVerdict.passed()


register_answer_validator(DESCENDANT_NIF_VALIDATOR_ID, _validate_descendant_nif)


def _validate_meses_range(page: FlowPage, canonical: str) -> ValidationVerdict:
    """Refuse a months-worked answer outside the Art. 81 LIRPF 0-12 range.

    The value has already passed INTEGER shape validation, so a non-blank
    token parses; blank (optional) passes. Surfacing the range as a verdict
    keeps a value like ``15`` out of the answer map entirely, so it never
    reaches the persistence-boundary construction of
    :class:`~cadrumo.domain.contribuyente.DescendantInfo` (whose ``le=12``
    field constraint stays as defence-in-depth).
    """
    if not canonical:
        return ValidationVerdict.passed()
    if not (_MESES_MIN <= int(canonical) <= _MESES_MAX):
        return ValidationVerdict.failed(
            _MESES_INVALID_RANGE_LOCALE_KEY,
            page_id=page.id,
            minimum=_MESES_MIN,
            maximum=_MESES_MAX,
        )
    return ValidationVerdict.passed()


def _validate_gastos_nonneg(page: FlowPage, canonical: str) -> ValidationVerdict:
    """Refuse a negative guardería expense (Art. 81 bis LIRPF; euros >= 0).

    Blank (optional) passes; a parsed negative amount refuses as a verdict
    so it never reaches the ``ge=0`` model constraint at persist.
    """
    if not canonical:
        return ValidationVerdict.passed()
    if int(canonical) < 0:
        return ValidationVerdict.failed(_GASTOS_INVALID_NEGATIVE_LOCALE_KEY, page_id=page.id)
    return ValidationVerdict.passed()


register_answer_validator(DESCENDANT_MESES_VALIDATOR_ID, _validate_meses_range)
register_answer_validator(DESCENDANT_GASTOS_VALIDATOR_ID, _validate_gastos_nonneg)


def _validate_descendant_adoption_dates(answers: Mapping[str, str]) -> tuple[ValidationVerdict, ...]:
    """Flow-scope guard for the per-instance adoption-vs-birth date invariants.

    Adoption-vs-birth is a cross-field rule (two pages inside one instance),
    so it cannot be a per-answer validator: this scans every descendant
    instance in the answer map and refuses an adoption date earlier than the
    birth date or in the future. Both are enforced as review verdicts before
    persist; the same invariants stay as ``DescendantInfo`` model validators
    for defence-in-depth. Values are canonical ISO strings (DATE-shape
    validated), so parsing succeeds; a page id and instance index are the
    only context — never the raw date.
    """
    verdicts: list[ValidationVerdict] = []
    today = today_madrid()
    prefix_root = f"{DESCENDANTS_GROUP_ID}{REPEATING_INSTANCE_SEPARATOR}"
    for key, raw in answers.items():
        if not key.startswith(prefix_root) or not key.endswith(f".{_ADOPTION_DATE_PAGE_ID}") or not raw:
            continue
        instance = key[len(prefix_root) :].split(".", 1)[0]
        birth_raw = answers.get(f"{prefix_root}{instance}.{_BIRTH_DATE_PAGE_ID}", "")
        adoption = parse_iso8601_date(raw)
        if adoption is None:
            continue
        if adoption > today:
            verdicts.append(ValidationVerdict.failed(_ADOPTION_IN_FUTURE_LOCALE_KEY, instance=instance))
            continue
        birth = parse_iso8601_date(birth_raw) if birth_raw else None
        if birth is not None and adoption < birth:
            verdicts.append(ValidationVerdict.failed(_ADOPTION_BEFORE_BIRTH_LOCALE_KEY, instance=instance))
    return tuple(verdicts) if verdicts else (ValidationVerdict.passed(),)


register_cross_field_validator(DESCENDANT_ADOPTION_VALIDATOR_ID, _validate_descendant_adoption_dates)


# The count question is gated to a natural person: only an IRPF-personal
# taxpayer has descendants, and hiding it for a legal / attribution entity
# yields a zero instance count so the whole group disappears.
_NATURAL_PERSON_GATE = FlowCondition(page_id="entity-type", equals=EntityType.NATURAL_PERSON.value)


DESCENDANTS_COUNT_PAGE: FlowPage = FlowPage(
    id=DESCENDANTS_COUNT_PAGE_ID,
    widget=FlowWidgetKind.INTEGER,
    prompt=_locale_ref(_COUNT_PROMPT_LOCALE_KEY),
    help=_locale_ref(_COUNT_HELP_LOCALE_KEY),
    format_hint=_locale_ref(_FORMAT_UNITS_LOCALE_KEY),
    required=False,
    visible_when=_NATURAL_PERSON_GATE,
    answer_type=int,
)


_DISCAPACIDAD_CHOICES: tuple[FlowChoice, ...] = (
    FlowChoice(value="0", label=_locale_ref(_DISCAPACIDAD_CHOICE_0_LOCALE_KEY)),
    FlowChoice(value="33", label=_locale_ref(_DISCAPACIDAD_CHOICE_33_LOCALE_KEY)),
    FlowChoice(value="65", label=_locale_ref(_DISCAPACIDAD_CHOICE_65_LOCALE_KEY)),
)


_DESCENDANT_PAGES: tuple[FlowPage, ...] = (
    FlowPage(
        id=_BIRTH_DATE_PAGE_ID,
        widget=FlowWidgetKind.DATE,
        prompt=_locale_ref(_BIRTH_DATE_PROMPT_LOCALE_KEY),
        format_hint=_locale_ref(_FORMAT_DATE_LOCALE_KEY),
        required=True,
        answer_type=str,
    ),
    FlowPage(
        id=_ADOPTION_DATE_PAGE_ID,
        widget=FlowWidgetKind.DATE,
        prompt=_locale_ref(_ADOPTION_DATE_PROMPT_LOCALE_KEY),
        format_hint=_locale_ref(_FORMAT_DATE_LOCALE_KEY),
        required=False,
        answer_type=str,
    ),
    FlowPage(
        id=_DISCAPACIDAD_PAGE_ID,
        widget=FlowWidgetKind.SELECT,
        prompt=_locale_ref(_DISCAPACIDAD_PROMPT_LOCALE_KEY),
        choices=_DISCAPACIDAD_CHOICES,
        required=False,
        answer_type=str,
    ),
    FlowPage(
        id=_CONVIVENCIA_PAGE_ID,
        widget=FlowWidgetKind.CONFIRM,
        prompt=_locale_ref(_CONVIVENCIA_PROMPT_LOCALE_KEY),
        default="true",
        required=False,
        answer_type=bool,
    ),
    FlowPage(
        id=_CUSTODIA_COMPARTIDA_PAGE_ID,
        widget=FlowWidgetKind.CONFIRM,
        prompt=_locale_ref(_CUSTODIA_COMPARTIDA_PROMPT_LOCALE_KEY),
        default="false",
        required=False,
        answer_type=bool,
    ),
    FlowPage(
        id=_MESES_MADRE_TRABAJO_PAGE_ID,
        widget=FlowWidgetKind.INTEGER,
        prompt=_locale_ref(_MESES_MADRE_TRABAJO_PROMPT_LOCALE_KEY),
        help=_locale_ref(_MESES_MADRE_TRABAJO_HELP_LOCALE_KEY),
        format_hint=_locale_ref(_FORMAT_UNITS_LOCALE_KEY),
        required=False,
        answer_type=int,
        answer_validator_ids=(DESCENDANT_MESES_VALIDATOR_ID,),
    ),
    FlowPage(
        id=_GASTOS_GUARDERIA_PAGE_ID,
        widget=FlowWidgetKind.INTEGER,
        prompt=_locale_ref(_GASTOS_GUARDERIA_PROMPT_LOCALE_KEY),
        help=_locale_ref(_GASTOS_GUARDERIA_HELP_LOCALE_KEY),
        format_hint=_locale_ref(_FORMAT_AMOUNT_LOCALE_KEY),
        required=False,
        answer_type=int,
        answer_validator_ids=(DESCENDANT_GASTOS_VALIDATOR_ID,),
    ),
    FlowPage(
        id=_NIF_PAGE_ID,
        widget=FlowWidgetKind.TEXT,
        prompt=_locale_ref(_NIF_PROMPT_LOCALE_KEY),
        format_hint=_locale_ref(_FORMAT_TAX_ID_LOCALE_KEY),
        required=False,
        answer_type=str,
        answer_validator_ids=(DESCENDANT_NIF_VALIDATOR_ID,),
    ),
)


DESCENDANT_GROUP: FlowRepeatingGroup = FlowRepeatingGroup(
    id=DESCENDANTS_GROUP_ID,
    title=_locale_ref(_GROUP_TITLE_LOCALE_KEY),
    count_from=DESCENDANTS_COUNT_PAGE_ID,
    pages=_DESCENDANT_PAGES,
)


def attach_descendant_group(definition: FlowDefinition) -> FlowDefinition:
    """Return ``definition`` with the descendant count page and group in familia.

    Appends the count-source page and the repeating group to the familia
    section, in that order, so the substrate's count-source validator sees
    the INTEGER count page before the group that names it, and names the
    flow-scope adoption-date cross-field validator on the definition so a
    bad adoption date blocks submit. Raises when the familia section is
    absent -- a silent no-op would drop the whole descendant surface.
    Idempotent on the flow validator id: re-applying does not duplicate it.
    """
    sections = []
    attached = False
    for section in definition.sections:
        if section.id == _FAMILIA_SECTION_ID:
            sections.append(
                section.model_copy(
                    update={"items": (*section.items, DESCENDANTS_COUNT_PAGE, DESCENDANT_GROUP)},
                ),
            )
            attached = True
        else:
            sections.append(section)
    if not attached:
        raise ValueError(
            f"attach_descendant_group: definition {definition.id!r} has no {_FAMILIA_SECTION_ID!r} section",
        )
    flow_validator_ids = definition.flow_validator_ids
    if DESCENDANT_ADOPTION_VALIDATOR_ID not in flow_validator_ids:
        flow_validator_ids = (*flow_validator_ids, DESCENDANT_ADOPTION_VALIDATOR_ID)
    return definition.model_copy(
        update={"sections": tuple(sections), "flow_validator_ids": flow_validator_ids},
    )


__all__ = [
    "DESCENDANTS_COUNT_PAGE",
    "DESCENDANTS_COUNT_PAGE_ID",
    "DESCENDANTS_GROUP_ID",
    "DESCENDANT_ADOPTION_VALIDATOR_ID",
    "DESCENDANT_GASTOS_VALIDATOR_ID",
    "DESCENDANT_GROUP",
    "DESCENDANT_LOCALE_KEYS",
    "DESCENDANT_MESES_VALIDATOR_ID",
    "DESCENDANT_NIF_VALIDATOR_ID",
    "DESCENDANT_PAGE_IDS",
    "attach_descendant_group",
]
