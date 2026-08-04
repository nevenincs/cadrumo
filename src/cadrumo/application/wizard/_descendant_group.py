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
from typing import TYPE_CHECKING

from ...core import ART_58_2_ENTITLING_RELACIONES, DescendantRelacion
from ...core.decimal import try_parse_canonical_decimal
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
    FlowSection,
    FlowVisibility,
    ValidationVerdict,
    register_answer_validator,
    register_cross_field_validator,
)

if TYPE_CHECKING:
    from datetime import date

_FAMILIA_SECTION_ID = "familia"

#: Repeating-group id; instance answers key as ``descendientes#<index>.<page>``.
DESCENDANTS_GROUP_ID = "descendientes"

#: Count-source page id; its INTEGER answer drives the instance count.
DESCENDANTS_COUNT_PAGE_ID = "descendientes-count"

# Per-descendant page ids, in walk order. These bare tokens are the
# ``<page-id>`` half of every ``descendientes#<index>.<page-id>`` answer key.
_BIRTH_DATE_PAGE_ID = "birth-date"
_RELACION_PAGE_ID = "relacion"
_INSCRIPCION_PAGE_ID = "inscripcion-registro-civil"
_ACOGIMIENTO_PAGE_ID = "acogimiento-resolucion"
_DISCAPACIDAD_PAGE_ID = "discapacidad"
_CONVIVENCIA_PAGE_ID = "convivencia"
_DEPENDENCIA_PAGE_ID = "dependencia-economica"
_CUSTODIA_COMPARTIDA_PAGE_ID = "custodia-compartida"
_RENTAS_ANUALES_PAGE_ID = "rentas-anuales"
_DECLARACION_PROPIA_PAGE_ID = "declaracion-propia"
_PRORRATA_MINIMO_PAGE_ID = "prorrata-minimo"
_MESES_MADRE_TRABAJO_PAGE_ID = "meses-madre-trabajo"
_GASTOS_GUARDERIA_PAGE_ID = "gastos-guarderia"
_NIF_PAGE_ID = "nif"

#: Per-descendant page ids in walk order (consumed by the fact projection).
DESCENDANT_PAGE_IDS: tuple[str, ...] = (
    _BIRTH_DATE_PAGE_ID,
    _RELACION_PAGE_ID,
    _INSCRIPCION_PAGE_ID,
    _ACOGIMIENTO_PAGE_ID,
    _DISCAPACIDAD_PAGE_ID,
    _CONVIVENCIA_PAGE_ID,
    _DEPENDENCIA_PAGE_ID,
    _CUSTODIA_COMPARTIDA_PAGE_ID,
    _RENTAS_ANUALES_PAGE_ID,
    _DECLARACION_PROPIA_PAGE_ID,
    _PRORRATA_MINIMO_PAGE_ID,
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

#: Registered id of the per-answer descendant rentas-anuales sign validator.
DESCENDANT_RENTAS_VALIDATOR_ID = "descendant-rentas-nonneg"

#: Registered id of the flow-scope descendant entry-event cross-field validator.
#:
#: Covers both Art. 58.2 anchors (the Registro Civil inscription and the
#: acogimiento resolución) and their coherence against the declared relación.
#: One validator rather than two because the rules are not independent: which
#: date a record may carry is decided by the relación, so splitting them would
#: leave each half checking a condition the other half owns.
DESCENDANT_ENTRY_EVENT_VALIDATOR_ID = "descendant-entry-event-dates"

_MESES_MIN = 0
_MESES_MAX = 12

#: Relación tokens that may carry a Registro Civil inscription date.
#:
#: Derived from the core enum, never re-listed: the inscription is the adoption
#: anchor, so this is the single-member set the canonical record enforces.
_INSCRIPCION_RELACIONES: frozenset[str] = frozenset({DescendantRelacion.ADOPTADO.value})

#: Relación tokens that may carry an entitling acogimiento resolución date.
#:
#: Derived from :data:`~cadrumo.core.ART_58_2_ENTITLING_RELACIONES` so the wizard
#: gate and the model validator cannot disagree about which placements the
#: statute entitles — a temporal acogimiento is excluded from both by
#: construction rather than by two hand-maintained lists agreeing today.
_ACOGIMIENTO_RELACIONES: frozenset[str] = frozenset(member.value for member in ART_58_2_ENTITLING_RELACIONES)

# --- copy references (new wizard.setup.descendientes.* locale keys) ---------

_GROUP_TITLE_LOCALE_KEY = "wizard.setup.descendientes.title"
_COUNT_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.count.prompt"
_COUNT_HELP_LOCALE_KEY = "wizard.setup.descendientes.count.help"
_BIRTH_DATE_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.birth-date.prompt"
_RELACION_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.relacion.prompt"
_RELACION_HELP_LOCALE_KEY = "wizard.setup.descendientes.relacion.help"
_RELACION_CHOICE_DESCENDIENTE_LOCALE_KEY = "wizard.setup.descendientes.relacion.choices.descendiente.label"
_RELACION_CHOICE_ADOPTADO_LOCALE_KEY = "wizard.setup.descendientes.relacion.choices.adoptado.label"
_RELACION_CHOICE_ACOGIMIENTO_PP_LOCALE_KEY = (
    "wizard.setup.descendientes.relacion.choices.acogimiento_preadoptivo_o_permanente.label"
)
_RELACION_CHOICE_ACOGIMIENTO_TEMPORAL_LOCALE_KEY = (
    "wizard.setup.descendientes.relacion.choices.acogimiento_temporal.label"
)
_RELACION_CHOICE_TUTELA_LOCALE_KEY = "wizard.setup.descendientes.relacion.choices.tutela.label"
_INSCRIPCION_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.inscripcion-registro-civil.prompt"
_INSCRIPCION_HELP_LOCALE_KEY = "wizard.setup.descendientes.inscripcion-registro-civil.help"
_ACOGIMIENTO_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.acogimiento-resolucion.prompt"
_ACOGIMIENTO_HELP_LOCALE_KEY = "wizard.setup.descendientes.acogimiento-resolucion.help"
_DISCAPACIDAD_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.discapacidad.prompt"
_DISCAPACIDAD_CHOICE_0_LOCALE_KEY = "wizard.setup.descendientes.discapacidad.choices.0.label"
_DISCAPACIDAD_CHOICE_33_LOCALE_KEY = "wizard.setup.descendientes.discapacidad.choices.33.label"
_DISCAPACIDAD_CHOICE_65_LOCALE_KEY = "wizard.setup.descendientes.discapacidad.choices.65.label"
_CONVIVENCIA_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.convivencia.prompt"
_DEPENDENCIA_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.dependencia-economica.prompt"
_DEPENDENCIA_HELP_LOCALE_KEY = "wizard.setup.descendientes.dependencia-economica.help"
_DEPENDENCIA_CHOICE_TRUE_LOCALE_KEY = "wizard.setup.descendientes.dependencia-economica.choices.true.label"
_DEPENDENCIA_CHOICE_FALSE_LOCALE_KEY = "wizard.setup.descendientes.dependencia-economica.choices.false.label"
_CUSTODIA_COMPARTIDA_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.custodia-compartida.prompt"
_RENTAS_ANUALES_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.rentas-anuales.prompt"
_RENTAS_ANUALES_HELP_LOCALE_KEY = "wizard.setup.descendientes.rentas-anuales.help"
_DECLARACION_PROPIA_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.declaracion-propia.prompt"
_DECLARACION_PROPIA_HELP_LOCALE_KEY = "wizard.setup.descendientes.declaracion-propia.help"
_PRORRATA_MINIMO_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.prorrata-minimo.prompt"
_PRORRATA_MINIMO_HELP_LOCALE_KEY = "wizard.setup.descendientes.prorrata-minimo.help"
_PRORRATA_MINIMO_CHOICE_TRUE_LOCALE_KEY = "wizard.setup.descendientes.prorrata-minimo.choices.true.label"
_PRORRATA_MINIMO_CHOICE_FALSE_LOCALE_KEY = "wizard.setup.descendientes.prorrata-minimo.choices.false.label"
_MESES_MADRE_TRABAJO_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.meses-madre-trabajo.prompt"
_MESES_MADRE_TRABAJO_HELP_LOCALE_KEY = "wizard.setup.descendientes.meses-madre-trabajo.help"
_GASTOS_GUARDERIA_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.gastos-guarderia.prompt"
_GASTOS_GUARDERIA_HELP_LOCALE_KEY = "wizard.setup.descendientes.gastos-guarderia.help"
_NIF_PROMPT_LOCALE_KEY = "wizard.setup.descendientes.nif.prompt"

# Verdict message keys minted for the constraint guards below (the range,
# sign, and entry-event refusals). Reused generic keys were checked
# first: the closest existing leaves (cli.config.descendiente.*) carry
# CLI-flag-specific prose, so wizard-namespace keys are minted here.
_MESES_INVALID_RANGE_LOCALE_KEY = "wizard.setup.descendientes.meses-madre-trabajo.invalid_range"
_RENTAS_INVALID_NEGATIVE_LOCALE_KEY = "wizard.setup.descendientes.rentas-anuales.invalid_negative"
_GASTOS_INVALID_NEGATIVE_LOCALE_KEY = "wizard.setup.descendientes.gastos-guarderia.invalid_negative"
_ENTRY_BEFORE_BIRTH_LOCALE_KEY = "wizard.setup.descendientes.entry-event.before_birth"
_ENTRY_IN_FUTURE_LOCALE_KEY = "wizard.setup.descendientes.entry-event.in_future"
_ENTRY_RELACION_MISMATCH_LOCALE_KEY = "wizard.setup.descendientes.entry-event.relacion_mismatch"

# Format hints reuse the shared wizard.setup.format.* keys already shipped
# by the format-hint decorator; the NIF failure verdict reuses the existing
# tax-id error key, so neither mints a new locale key.
_FORMAT_DATE_LOCALE_KEY = "wizard.setup.format.date-iso"
_FORMAT_AMOUNT_LOCALE_KEY = "wizard.setup.format.amount-eur"
_FORMAT_UNITS_LOCALE_KEY = "wizard.setup.format.units-count"
_FORMAT_TAX_ID_LOCALE_KEY = "wizard.setup.format.tax-id"
_NIF_INVALID_LOCALE_KEY = "wizard.errors.invalid_tax_id"

# The rentas grammar refusal reuses the exact key the checkpoint-persistence
# path (`_persistence._descendant_from_row`) already raises for the same
# malformed-amount case on the same field, rather than minting a second one:
# the CLI `--descendiente RENTAS=` flag path carries it too
# (`domain.contribuyente._descendant_facts`). Two keys for one refusal would
# drift, and the operator would meet different words depending on which door
# they came through.
_RENTAS_NOT_A_VALID_AMOUNT_LOCALE_KEY = "application.wizard.errors.descendant_rentas_not_a_valid_amount"

#: Every net-new locale key this module references, for the scaffold gate.
DESCENDANT_LOCALE_KEYS: tuple[str, ...] = (
    _GROUP_TITLE_LOCALE_KEY,
    _COUNT_PROMPT_LOCALE_KEY,
    _COUNT_HELP_LOCALE_KEY,
    _BIRTH_DATE_PROMPT_LOCALE_KEY,
    _RELACION_PROMPT_LOCALE_KEY,
    _RELACION_HELP_LOCALE_KEY,
    _RELACION_CHOICE_DESCENDIENTE_LOCALE_KEY,
    _RELACION_CHOICE_ADOPTADO_LOCALE_KEY,
    _RELACION_CHOICE_ACOGIMIENTO_PP_LOCALE_KEY,
    _RELACION_CHOICE_ACOGIMIENTO_TEMPORAL_LOCALE_KEY,
    _RELACION_CHOICE_TUTELA_LOCALE_KEY,
    _INSCRIPCION_PROMPT_LOCALE_KEY,
    _INSCRIPCION_HELP_LOCALE_KEY,
    _ACOGIMIENTO_PROMPT_LOCALE_KEY,
    _ACOGIMIENTO_HELP_LOCALE_KEY,
    _DISCAPACIDAD_PROMPT_LOCALE_KEY,
    _DISCAPACIDAD_CHOICE_0_LOCALE_KEY,
    _DISCAPACIDAD_CHOICE_33_LOCALE_KEY,
    _DISCAPACIDAD_CHOICE_65_LOCALE_KEY,
    _CONVIVENCIA_PROMPT_LOCALE_KEY,
    _DEPENDENCIA_PROMPT_LOCALE_KEY,
    _DEPENDENCIA_HELP_LOCALE_KEY,
    _DEPENDENCIA_CHOICE_TRUE_LOCALE_KEY,
    _DEPENDENCIA_CHOICE_FALSE_LOCALE_KEY,
    _CUSTODIA_COMPARTIDA_PROMPT_LOCALE_KEY,
    _RENTAS_ANUALES_PROMPT_LOCALE_KEY,
    _RENTAS_ANUALES_HELP_LOCALE_KEY,
    _DECLARACION_PROPIA_PROMPT_LOCALE_KEY,
    _DECLARACION_PROPIA_HELP_LOCALE_KEY,
    _PRORRATA_MINIMO_PROMPT_LOCALE_KEY,
    _PRORRATA_MINIMO_HELP_LOCALE_KEY,
    _PRORRATA_MINIMO_CHOICE_TRUE_LOCALE_KEY,
    _PRORRATA_MINIMO_CHOICE_FALSE_LOCALE_KEY,
    _MESES_MADRE_TRABAJO_PROMPT_LOCALE_KEY,
    _MESES_MADRE_TRABAJO_HELP_LOCALE_KEY,
    _GASTOS_GUARDERIA_PROMPT_LOCALE_KEY,
    _GASTOS_GUARDERIA_HELP_LOCALE_KEY,
    _NIF_PROMPT_LOCALE_KEY,
    _MESES_INVALID_RANGE_LOCALE_KEY,
    _GASTOS_INVALID_NEGATIVE_LOCALE_KEY,
    _RENTAS_INVALID_NEGATIVE_LOCALE_KEY,
    _ENTRY_BEFORE_BIRTH_LOCALE_KEY,
    _ENTRY_IN_FUTURE_LOCALE_KEY,
    _ENTRY_RELACION_MISMATCH_LOCALE_KEY,
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
    """Refuse a negative guardería expense (Art. 81.2 LIRPF; euros >= 0).

    Blank (optional) passes; a parsed negative amount refuses as a verdict
    so it never reaches the ``ge=0`` model constraint at persist.
    """
    if not canonical:
        return ValidationVerdict.passed()
    if int(canonical) < 0:
        return ValidationVerdict.failed(_GASTOS_INVALID_NEGATIVE_LOCALE_KEY, page_id=page.id)
    return ValidationVerdict.passed()


def _validate_rentas_nonneg(page: FlowPage, canonical: str) -> ValidationVerdict:
    """Refuse a malformed or negative rentas figure (Art. 58.1 LIRPF; euros >= 0).

    Blank (optional) passes and leaves the figure UNDECLARED, which the
    eligibility predicate reads as non-excluding. Unlike ``gastos_guarderia``,
    this field is genuinely ``Decimal`` on the domain model
    (:class:`~cadrumo.domain.contribuyente.DescendantInfo`), and the Art. 58.1
    ceiling comparison is strict (``>``), so a cents figure genuinely at the
    boundary (e.g. ``8000.01``) is legally significant, not cosmetic
    precision. The DECIMAL widget's own shape validation already confirmed
    the canonical grammar uncapped -- it is a generic numeric channel also
    serving rates and percentages -- so this applies the money-specific
    ambiguity cap here: at most two fraction digits, since a Spanish
    thousands grouping is always exactly three and a longer fraction is
    genuinely undecidable between one euro and one thousand. A malformed
    figure refuses rather than resolving to zero or ``None``: ``None`` means
    UNDECLARED and is the CLAIMING direction (Art. 58.1 reads an absent
    figure as non-excluding), so silently mapping a typo onto it would assert
    a mínimo the taxpayer never established -- the same over-claim this cap
    guards against in the checkpoint-persistence and CLI flag paths that
    already enforce it on the same field.
    """
    if not canonical:
        return ValidationVerdict.passed()
    value = try_parse_canonical_decimal(canonical, max_fraction_digits=2)
    if value is None:
        return ValidationVerdict.failed(_RENTAS_NOT_A_VALID_AMOUNT_LOCALE_KEY, page_id=page.id)
    if value < 0:
        return ValidationVerdict.failed(_RENTAS_INVALID_NEGATIVE_LOCALE_KEY, page_id=page.id)
    return ValidationVerdict.passed()


register_answer_validator(DESCENDANT_MESES_VALIDATOR_ID, _validate_meses_range)
register_answer_validator(DESCENDANT_GASTOS_VALIDATOR_ID, _validate_gastos_nonneg)
register_answer_validator(DESCENDANT_RENTAS_VALIDATOR_ID, _validate_rentas_nonneg)


def _validate_descendant_entry_event_dates(answers: Mapping[str, str]) -> tuple[ValidationVerdict, ...]:
    """Flow-scope guard for the per-instance Art. 58.2 entry-event invariants.

    Both rules span pages inside one instance, so neither can be a per-answer
    validator: an entry date is judged against the BIRTH date on a sibling page,
    and against the RELACIÓN on another. This scans every descendant instance
    and refuses an entry event earlier than the birth or in the future, and an
    entry date the declared relación cannot carry.

    The relación gate is enforced here as well as by the page-visibility
    conditions, and that is not redundancy. Visibility stops the operator
    REACHING an incompatible page in an interactive walk, but a scripted or
    resumed answer map can carry an answer whose gate later stopped holding —
    the operator changes the relación from adoptado to tutela and the
    inscription answer is left behind. Enforcing it as a verdict is what turns
    that into a blocked submit rather than a refusal raised from deep inside the
    persist path, where it would read as a crash.

    A page id and instance index are the only context; the raw date never enters
    a diagnostic.
    """
    today = today_madrid()
    prefix_root = f"{DESCENDANTS_GROUP_ID}{REPEATING_INSTANCE_SEPARATOR}"
    verdicts = [
        verdict
        for instance in sorted(_descendant_instances(answers, prefix_root=prefix_root))
        for verdict in _entry_event_verdicts(
            answers,
            prefix=f"{prefix_root}{instance}",
            instance=instance,
            today=today,
        )
    ]
    return tuple(verdicts) if verdicts else (ValidationVerdict.passed(),)


def _descendant_instances(answers: Mapping[str, str], *, prefix_root: str) -> set[str]:
    """The instance indices present in the answer map, as bare tokens."""
    return {key[len(prefix_root) :].split(".", 1)[0] for key in answers if key.startswith(prefix_root) and "." in key}


def _entry_event_verdicts(
    answers: Mapping[str, str],
    *,
    prefix: str,
    instance: str,
    today: date,
) -> list[ValidationVerdict]:
    """Judge one instance's two entry-event dates against birth, today and relación."""
    birth = parse_iso8601_date(answers.get(f"{prefix}.{_BIRTH_DATE_PAGE_ID}") or "") or None
    relacion = (answers.get(f"{prefix}.{_RELACION_PAGE_ID}") or "").strip()
    verdicts: list[ValidationVerdict] = []
    for page_id, permitted in (
        (_INSCRIPCION_PAGE_ID, _INSCRIPCION_RELACIONES),
        (_ACOGIMIENTO_PAGE_ID, _ACOGIMIENTO_RELACIONES),
    ):
        raw = answers.get(f"{prefix}.{page_id}") or ""
        if not raw:
            continue
        entry = parse_iso8601_date(raw)
        if entry is None:
            continue
        # A future date is reported on its own; only a past one is then compared
        # against the birth, so the operator is told the one thing wrong with the
        # value rather than two overlapping refusals.
        if entry > today:
            verdicts.append(ValidationVerdict.failed(_ENTRY_IN_FUTURE_LOCALE_KEY, instance=instance, page=page_id))
        elif birth is not None and entry < birth:
            verdicts.append(ValidationVerdict.failed(_ENTRY_BEFORE_BIRTH_LOCALE_KEY, instance=instance, page=page_id))
        # An UNSTATED relación is not judged: an inscription date alone reads as
        # an adoption (the canonical record infers it), so refusing here would
        # block the shape the model accepts.
        if relacion and relacion not in permitted:
            verdicts.append(
                ValidationVerdict.failed(
                    _ENTRY_RELACION_MISMATCH_LOCALE_KEY,
                    instance=instance,
                    page=page_id,
                    accepted=", ".join(sorted(permitted)),
                ),
            )
    return verdicts


register_cross_field_validator(DESCENDANT_ENTRY_EVENT_VALIDATOR_ID, _validate_descendant_entry_event_dates)


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
    # Optional with an explicit zero default: a natural-person walk that never
    # mentions descendants declares zero (the correct tax semantics and the
    # interactive prefill), and the scripted driver fills the page from this
    # default, so existing token fixtures need no descendant token.
    default="0",
    required=False,
    visible_when=_NATURAL_PERSON_GATE,
    answer_type=int,
)


#: Art. 58.1 / 58.2 relación choices, in the order an operator recognises them.
#:
#: Every member of the closed set is offered, including the two that take the
#: tranches without the increase (temporal acogimiento, tutela). Omitting either
#: would leave that carer no honest answer, and an operator with no honest answer
#: picks the nearest entitling one -- which is the over-grant this axis exists to
#: prevent, arriving through the surface rather than through the model.
_RELACION_CHOICES: tuple[FlowChoice, ...] = (
    FlowChoice(
        value=DescendantRelacion.DESCENDIENTE.value,
        label=_locale_ref(_RELACION_CHOICE_DESCENDIENTE_LOCALE_KEY),
    ),
    FlowChoice(
        value=DescendantRelacion.ADOPTADO.value,
        label=_locale_ref(_RELACION_CHOICE_ADOPTADO_LOCALE_KEY),
    ),
    FlowChoice(
        value=DescendantRelacion.ACOGIMIENTO_PREADOPTIVO_O_PERMANENTE.value,
        label=_locale_ref(_RELACION_CHOICE_ACOGIMIENTO_PP_LOCALE_KEY),
    ),
    FlowChoice(
        value=DescendantRelacion.ACOGIMIENTO_TEMPORAL.value,
        label=_locale_ref(_RELACION_CHOICE_ACOGIMIENTO_TEMPORAL_LOCALE_KEY),
    ),
    FlowChoice(
        value=DescendantRelacion.TUTELA.value,
        label=_locale_ref(_RELACION_CHOICE_TUTELA_LOCALE_KEY),
    ),
)


#: Visibility for the acogimiento resolución page: every entitling relación.
#:
#: Built from :data:`~cadrumo.core.ART_58_2_ENTITLING_RELACIONES` and sorted so
#: the clause order is stable, rather than listing the two members here. Adding
#: an entitling relación to the statute's set therefore reaches the wizard gate
#: without a second edit that could be forgotten.
_ACOGIMIENTO_VISIBILITY: FlowVisibility = FlowVisibility(
    any_of=tuple(FlowCondition(page_id=_RELACION_PAGE_ID, equals=value) for value in sorted(_ACOGIMIENTO_RELACIONES)),
)


#: Art. 58 dependency answers. Tri-state by construction: leaving the page
#: unanswered is NOT a "no", it is an unanswered question, and only an explicit
#: yes can assimilate. An explicit no is offered so the operator can record that
#: the question was put and declined.
_DEPENDENCIA_CHOICES: tuple[FlowChoice, ...] = (
    FlowChoice(value="true", label=_locale_ref(_DEPENDENCIA_CHOICE_TRUE_LOCALE_KEY)),
    FlowChoice(value="false", label=_locale_ref(_DEPENDENCIA_CHOICE_FALSE_LOCALE_KEY)),
)


_DISCAPACIDAD_CHOICES: tuple[FlowChoice, ...] = (
    FlowChoice(value="0", label=_locale_ref(_DISCAPACIDAD_CHOICE_0_LOCALE_KEY)),
    FlowChoice(value="33", label=_locale_ref(_DISCAPACIDAD_CHOICE_33_LOCALE_KEY)),
    FlowChoice(value="65", label=_locale_ref(_DISCAPACIDAD_CHOICE_65_LOCALE_KEY)),
)


#: Art. 61 norma 1a answers. Left unanswered the engine derives the answer
#: from marital status, spouse record and declaration type, and raises a
#: visible advisory saying so; an explicit answer always wins over that.
_PRORRATA_MINIMO_CHOICES: tuple[FlowChoice, ...] = (
    FlowChoice(value="true", label=_locale_ref(_PRORRATA_MINIMO_CHOICE_TRUE_LOCALE_KEY)),
    FlowChoice(value="false", label=_locale_ref(_PRORRATA_MINIMO_CHOICE_FALSE_LOCALE_KEY)),
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
        id=_RELACION_PAGE_ID,
        widget=FlowWidgetKind.SELECT,
        prompt=_locale_ref(_RELACION_PROMPT_LOCALE_KEY),
        help=_locale_ref(_RELACION_HELP_LOCALE_KEY),
        choices=_RELACION_CHOICES,
        # Optional with no default: leaving it unanswered means an ordinary
        # descendant, which is both the record's own default and the
        # overwhelming case, so the majority of walks answer nothing here.
        required=False,
        answer_type=str,
    ),
    # Both entry-date pages are GATED on the relación answer rather than shown
    # unconditionally. The gate is per-instance -- the engine resolves a clause
    # against `<group>#<index>.<page-id>` before the bare id -- so each
    # descendant's dates follow that descendant's own relación. Gating is what
    # keeps a tutela guardian or a temporal acogimiento carer from ever seeing a
    # field the statute gives them no entitling value for; the cross-field
    # verdict and the model validator then hold the same line for a scripted or
    # resumed answer map, where visibility alone proves nothing.
    FlowPage(
        id=_INSCRIPCION_PAGE_ID,
        widget=FlowWidgetKind.DATE,
        prompt=_locale_ref(_INSCRIPCION_PROMPT_LOCALE_KEY),
        help=_locale_ref(_INSCRIPCION_HELP_LOCALE_KEY),
        format_hint=_locale_ref(_FORMAT_DATE_LOCALE_KEY),
        required=False,
        answer_type=str,
        visible_when=FlowCondition(
            page_id=_RELACION_PAGE_ID,
            equals=DescendantRelacion.ADOPTADO.value,
        ),
    ),
    FlowPage(
        id=_ACOGIMIENTO_PAGE_ID,
        widget=FlowWidgetKind.DATE,
        prompt=_locale_ref(_ACOGIMIENTO_PROMPT_LOCALE_KEY),
        help=_locale_ref(_ACOGIMIENTO_HELP_LOCALE_KEY),
        format_hint=_locale_ref(_FORMAT_DATE_LOCALE_KEY),
        required=False,
        answer_type=str,
        # Shown for an adoptado record too, and that is the cap-not-restart rule
        # made reachable: a fostered-then-adopted child's window is measured
        # from the earlier placement, so without this page the operator could
        # only record the later event and the engine would grant three fresh
        # periods on top of the ones already run.
        visible_when=_ACOGIMIENTO_VISIBILITY,
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
        # SELECT with an explicit no rather than CONFIRM, because this axis is
        # genuinely tri-state and a CONFIRM cannot express "unanswered". Unset
        # never assimilates; only an explicit yes does. Gated on a NON-cohabiting
        # answer, since the question only arises when cohabitation fails - a
        # cohabiting descendant already qualifies and asking would invite an
        # answer that changes nothing.
        id=_DEPENDENCIA_PAGE_ID,
        widget=FlowWidgetKind.SELECT,
        prompt=_locale_ref(_DEPENDENCIA_PROMPT_LOCALE_KEY),
        help=_locale_ref(_DEPENDENCIA_HELP_LOCALE_KEY),
        choices=_DEPENDENCIA_CHOICES,
        required=False,
        answer_type=str,
        visible_when=FlowCondition(page_id=_CONVIVENCIA_PAGE_ID, equals="false"),
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
        # DECIMAL, not INTEGER: the domain field is genuinely Decimal (Art.
        # 58.1's strict-`>` ceiling comparison makes cents legally
        # significant), and the CLI `--descendiente RENTAS=` flag and the
        # checkpoint-persistence re-projection already carry two-decimal
        # precision for this exact field. DECIMAL-widget pages keep
        # `answer_type=str`, per the widget's own canonicalisation contract
        # (the parsed amount rides as its `str(Decimal)` form, mirroring the
        # invoice wizard's `_validate_taxable_base`).
        id=_RENTAS_ANUALES_PAGE_ID,
        widget=FlowWidgetKind.DECIMAL,
        prompt=_locale_ref(_RENTAS_ANUALES_PROMPT_LOCALE_KEY),
        help=_locale_ref(_RENTAS_ANUALES_HELP_LOCALE_KEY),
        format_hint=_locale_ref(_FORMAT_AMOUNT_LOCALE_KEY),
        required=False,
        answer_type=str,
        answer_validator_ids=(DESCENDANT_RENTAS_VALIDATOR_ID,),
    ),
    FlowPage(
        id=_DECLARACION_PROPIA_PAGE_ID,
        widget=FlowWidgetKind.CONFIRM,
        prompt=_locale_ref(_DECLARACION_PROPIA_PROMPT_LOCALE_KEY),
        help=_locale_ref(_DECLARACION_PROPIA_HELP_LOCALE_KEY),
        default="false",
        required=False,
        answer_type=bool,
    ),
    FlowPage(
        id=_PRORRATA_MINIMO_PAGE_ID,
        widget=FlowWidgetKind.SELECT,
        prompt=_locale_ref(_PRORRATA_MINIMO_PROMPT_LOCALE_KEY),
        help=_locale_ref(_PRORRATA_MINIMO_HELP_LOCALE_KEY),
        choices=_PRORRATA_MINIMO_CHOICES,
        required=False,
        answer_type=str,
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
    flow-scope entry-event cross-field validator on the definition so a bad
    entry date -- or one the declared relación cannot carry -- blocks
    submit. Raises when the familia section is
    absent -- a silent no-op would drop the whole descendant surface.
    Idempotent on the flow validator id: re-applying does not duplicate it.
    """
    sections: list[FlowSection] = []
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
    if DESCENDANT_ENTRY_EVENT_VALIDATOR_ID not in flow_validator_ids:
        flow_validator_ids = (*flow_validator_ids, DESCENDANT_ENTRY_EVENT_VALIDATOR_ID)
    return definition.model_copy(
        update={"sections": tuple(sections), "flow_validator_ids": flow_validator_ids},
    )


__all__ = [
    "DESCENDANTS_COUNT_PAGE",
    "DESCENDANTS_COUNT_PAGE_ID",
    "DESCENDANTS_GROUP_ID",
    "DESCENDANT_ENTRY_EVENT_VALIDATOR_ID",
    "DESCENDANT_GASTOS_VALIDATOR_ID",
    "DESCENDANT_GROUP",
    "DESCENDANT_LOCALE_KEYS",
    "DESCENDANT_MESES_VALIDATOR_ID",
    "DESCENDANT_NIF_VALIDATOR_ID",
    "DESCENDANT_PAGE_IDS",
    "attach_descendant_group",
]
