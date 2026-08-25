"""Persistence adapter for wizard answers.

Serialises a typed answers model back to canonical-token strings, then
persists profile facts through canonical user-profile orchestration.
The reverse projection (``project_answers``) builds the typed answers
model from a raw canonical-token dict.

``persist_answers`` distinguishes the two wizard verbs. ``create``
registers a fresh profile from the full answer set. ``edit`` is a true
patch: only the questions the operator explicitly supplied on the
command line are written, so editing one field never reverts the rest
of a populated profile to its descriptor defaults.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypedDict

from pydantic import BaseModel

if TYPE_CHECKING:
    from datetime import date

    from ...domain.contribuyente import DescendantInfo, GuarderiaMonthSpend
    from ...domain.user_profile import UserProfileRecord

from ...core import DescendantRelacion
from ...core.decimal import try_parse_canonical_decimal
from ...core.flows import REPEATING_INSTANCE_SEPARATOR
from ...core.parsing import parse_bool, parse_iso8601_date
from ...core.setup_answers import register_project_answers as _register_project_answers
from ...core.time import today_madrid
from ...domain.user_profile import UserProfileFact, UserProfileRecord
from ..workflow import WorkflowInputMismatchError, WorkflowState
from ._descendant_group import (
    DESCENDANT_PAGE_IDS,
    DESCENDANTS_COUNT_PAGE_ID,
    DESCENDANTS_GROUP_ID,
)
from ._models import WizardFlow, WizardQuestion

WizardPersistMode = Literal["create", "edit"]
"""Which wizard verb is persisting — ``create`` registers a new profile,
``edit`` upserts facts on an existing one. The verb is the authority for
the create-vs-edit branch; it is never re-derived at runtime."""


def _canonicalise(question: WizardQuestion, value: object) -> str:
    """Render ``value`` as the canonical token used by the persistence layer."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, int):
        return str(value)
    return str(value)


def _question_by_id(flow: WizardFlow) -> Mapping[str, WizardQuestion]:
    table: dict[str, WizardQuestion] = {}
    for section in flow.sections:
        for question in section.questions:
            table[question.id] = question
    return table


def _field_to_question(flow: WizardFlow) -> Mapping[str, WizardQuestion]:
    """Build ``answers_model`` field name → ``WizardQuestion`` map."""
    table: dict[str, WizardQuestion] = {}
    for section in flow.sections:
        for question in section.questions:
            field_name = question.id.replace("-", "_")
            table[field_name] = question
    return table


def serialise_answers(
    flow: WizardFlow,
    answers: BaseModel,
    *,
    only_question_ids: Collection[str] | None = None,
) -> dict[str, str]:
    """Project a typed answers model into the canonical-token dict.

    Only profile-bound questions contribute a key. When
    ``only_question_ids`` is supplied, the projection is restricted to
    those question ids — the patch behaviour the ``edit`` verb relies
    on so an unsupplied field is never written back at its default.
    """
    typed = answers.model_dump()
    mapping = _field_to_question(flow)
    result: dict[str, str] = {}
    for field_name, value in typed.items():
        question = mapping.get(field_name)
        if question is None or question.profile_key is None:
            continue
        if only_question_ids is not None and question.id not in only_question_ids:
            continue
        result[question.profile_key] = _canonicalise(question, value)
    return result


def persist_answers(
    flow: WizardFlow,
    answers: BaseModel,
    *,
    state: WorkflowState,
    profile_name: str,
    profile_id: str,
    mode: WizardPersistMode,
    supplied_question_ids: Collection[str] | None = None,
    routing_profile_id: str | None = None,
) -> WorkflowState:
    """Persist ``answers`` into the profile bucket and return updated state.

    ``profile_id`` is the immutable UUID profile identity; ``profile_name``
    is the operator-chosen display label.

    ``mode`` is the command discriminator. ``"create"`` is deliberately
    unavailable: credential registration is the only creation door.
    ``"edit"`` publishes an explicit fact replacement through the active
    session-bound record repository.

    ``supplied_question_ids`` names the questions the operator
    explicitly supplied on the command line. On the ``"edit"`` path it
    scopes the write to exactly those questions: ``edit`` is a patch,
    so a field the operator did not name is left untouched. It must be
    supplied for ``"edit"``, which is the only mode that reaches the
    write; the ``"create"`` arm refuses above it and consumes nothing.

    Returns the updated :class:`WorkflowState` after persisting the answers.
    """
    from ..user_profile import ProfileFactWriteDoor, apply_profile_fact_changes

    if mode == "create":
        del flow, answers, profile_name, routing_profile_id
        from ..user_profile import ProfileRegistrationError

        raise ProfileRegistrationError(
            "wizard profile creation is unavailable; register with credentials before setup",
        )

    if supplied_question_ids is None:
        raise WorkflowInputMismatchError(
            translated_message="application.wizard.errors.persist_answers_edit_requires_supplied_question_ids",
        )
    canonical = serialise_answers(flow, answers, only_question_ids=supplied_question_ids)
    facts = tuple(UserProfileFact(path=path, value=value) for path, value in canonical.items() if value)
    apply_profile_fact_changes(
        profile_id=profile_id,
        changes=facts,
        door=ProfileFactWriteDoor.ANSWERS,
    )
    return state


def profile_values_from_patch(flow: WizardFlow, supplied: Mapping[str, str]) -> dict[str, str]:
    """Project a non-interactive edit patch to schema-path keyed values."""
    from ._widgets import validate_widget_answer

    questions = _question_by_id(flow)
    values: dict[str, str] = {}
    for question_id, raw in supplied.items():
        question = questions.get(question_id)
        if question is None:
            raise WorkflowInputMismatchError(
                translated_message="application.wizard.errors.persist_patch_unknown_question_id",
                context={"question_id": question_id},
            )
        if question.profile_key is None:
            continue
        validated = validate_widget_answer(question, raw)
        if not validated:
            continue
        values[question.profile_key] = validated
    return values


def persist_patch(
    flow: WizardFlow,
    supplied: Mapping[str, str],
    *,
    state: WorkflowState,
) -> WorkflowState:
    """Patch the active profile with only the explicitly supplied flags and return the updated :class:`WorkflowState`.

    ``supplied`` is the canonical-token dict keyed by *question id*,
    carrying exactly the flags the operator named on a non-interactive
    ``edit`` (``--quiet`` / ``--accept-defaults``). This is the true
    patch path: it never constructs the full :class:`SetupAnswers`
    model — which would demand every required field — and never seeds a
    descriptor default for an unsupplied question. Each supplied value
    is re-validated through its widget validator, mapped to its
    ``profile_key``, and CAS-published as one authenticated command. A
    question with no ``profile_key`` is not a profile fact and is
    skipped.
    """
    from ..user_profile import ProfileFactWriteDoor, apply_profile_fact_changes

    facts = tuple(
        UserProfileFact(path=path, value=value) for path, value in profile_values_from_patch(flow, supplied).items()
    )
    from ...core.bucket_pointer import require_active_bucket_id

    apply_profile_fact_changes(
        profile_id=require_active_bucket_id(),
        changes=facts,
        door=ProfileFactWriteDoor.PATCH,
    )
    return state


def project_answers(flow: WizardFlow, values: Mapping[str, str]) -> BaseModel:
    """Reverse projection: build the typed answers model from canonical tokens.

    Values absent from ``values`` fall back to the descriptor's default
    or the answers model's own field default; the answers model then
    runs its strict validation.
    """
    questions = _question_by_id(flow)
    typed: dict[str, object] = {}
    for question in questions.values():
        canonical = _resolve_canonical(question, values)
        if canonical is None:
            continue
        field_name = question.id.replace("-", "_")
        typed[field_name] = parse_canonical(question, canonical)
    return flow.answers_model.model_validate(typed)


def _resolve_canonical(question: WizardQuestion, values: Mapping[str, str]) -> str | None:
    """Resolve the canonical token to project for ``question``."""
    if question.profile_key is not None:
        candidate = values.get(question.profile_key)
        if candidate is not None:
            return candidate
    return question.default


def parse_canonical(question: WizardQuestion, raw: str) -> object:
    """Parse a canonical token into the question's declared answer type.

    For an optional CONFIRM, a blank canonical projects to the empty
    string (the undeclared three-state arm of the answers-model union),
    never to ``False``. Collapsing blank onto ``False`` here would
    erase the distinction between "the operator did not declare this
    fact" and "the operator positively declined", and would defeat the
    persistence-layer's drop-blank filter — the projected ``False``
    would round-trip to a stored ``"false"`` token and reload as a
    declared decline.
    """
    answer_type = question.answer_type
    if answer_type is bool:
        if raw == "" and not (question.required and question.visible_when is None):
            return ""
        # Deliberately NOT the canonical vocabulary. This reads a token the
        # application itself wrote, and its strictness is a guard: accepting
        # 'True' or 'TRUE' would silently admit an unlowercased str(bool)
        # that leaked past _render_fact_value, corrupting the round-trip
        # rather than failing it. Widening it here is what that guard exists
        # to prevent -- the operator-facing vocabulary belongs at
        # validate_confirm, which is where a person actually types.
        return raw == "true"
    if answer_type is int:
        return int(raw) if raw else 0
    if answer_type is Path:
        return Path(raw) if raw else Path()
    return raw


def _instance_count(raw: str) -> int:
    """Parse the descendant count answer, clamping malformed input to zero."""
    try:
        return max(0, int(raw)) if raw else 0
    except ValueError:
        return 0


def _discapacidad_grade(raw: str) -> Literal[0, 33, 65] | None:
    """Narrow a discapacidad answer token to the closed grade set."""
    match raw:
        case "0":
            return 0
        case "33":
            return 33
        case "65":
            return 65
        case _:
            return None


def _safe_entry_date(birth_raw: str, entry_raw: str | None) -> date | None:
    """Return the entry-event date only when it is a valid pair with birth.

    The cross-field entry-event invariants (entry >= birth, entry <= today) are
    surfaced as review verdicts before submit, but a persistence projection can
    still receive an out-of-order date. Dropping the invalid optional token
    here keeps the projection from raising a raw ``DescendantInfo`` model error;
    the review verdict still blocks final submission until the operator corrects
    it.
    """
    if not entry_raw:
        return None
    birth = parse_iso8601_date(birth_raw) if birth_raw else None
    entry = parse_iso8601_date(entry_raw)
    if birth is None or entry is None or entry < birth or entry > today_madrid():
        return None
    return entry


def _safe_relacion_and_entry_dates(
    row: Mapping[str, str],
) -> tuple[DescendantRelacion | None, date | None, date | None]:
    """Read one instance's relación and the two entry dates it may legitimately carry.

    Drops an entry date the declared relación cannot carry, for the same reason
    :func:`_safe_entry_date` drops an out-of-order one: a stale answer left
    behind when the operator changed the relación must not raise a raw model
    error during persistence projection.

    Dropping is the safe direction here specifically. The dropped value is an
    Art. 58.2 window anchor, so losing it can only WITHHOLD the increase, never
    grant it — while keeping it on an excluded record is exactly the over-grant
    the relación axis exists to prevent. The review verdict still blocks the
    final submit, so the operator is told rather than silently trimmed.
    """
    from ...core import ART_58_2_ENTITLING_RELACIONES

    raw_relacion = (row.get("relacion") or "").strip()
    try:
        relacion = DescendantRelacion(raw_relacion) if raw_relacion else None
    except ValueError:
        relacion = None
    birth_raw = row["birth-date"]
    inscripcion = _safe_entry_date(birth_raw, row.get("inscripcion-registro-civil"))
    acogimiento = _safe_entry_date(birth_raw, row.get("acogimiento-resolucion"))
    if relacion is not None and relacion is not DescendantRelacion.ADOPTADO:
        inscripcion = None
    if relacion is not None and relacion not in ART_58_2_ENTITLING_RELACIONES:
        acogimiento = None
    elif relacion is None and acogimiento is not None:
        # An unstated relación cannot carry an acogimiento date: the canonical
        # record refuses it because the token is compatible with two members the
        # statute treats oppositely, and guessing between them is the one thing
        # this axis must not do.
        acogimiento = None
    return relacion, inscripcion, acogimiento


def _descendant_from_row(row: Mapping[str, str]) -> DescendantInfo:
    """Reconstruct one ``DescendantInfo`` from an instance's canonical answers.

    Blank optional answers fall back to the record's own defaults
    (convivencia defaults to cohabiting, custodia to sole custody, the
    integer supplements to zero); the ISO date strings are coerced by the
    record's own field validators. An out-of-order or relación-incompatible
    entry date is dropped (see :func:`_safe_relacion_and_entry_dates`) so
    persistence projection never raw-raises.
    """
    from ...domain.contribuyente import DescendantInfo, parse_meses_trabajo, relacion_kwarg

    meses = row.get("meses-madre-trabajo") or ""
    birth_date = parse_iso8601_date(row["birth-date"])
    assert birth_date is not None
    rentas = row.get("rentas-anuales", "").strip()
    prorrata = row.get("prorrata-minimo", "").strip()
    dependencia_raw = row.get("dependencia-economica", "").strip()
    # Tri-state: a blank answer stays UNSET rather than collapsing to a no,
    # because only an explicit yes assimilates and only an unset value may
    # later be answered.
    dependencia = parse_bool(dependencia_raw) if dependencia_raw else None
    relacion, inscripcion_date, acogimiento_date = _safe_relacion_and_entry_dates(row)
    # Operator-typed euros, so the strict grammar with the money cap: a bare
    # Decimal() admitted '1e3', '+100', 'NaN' and 'Infinity', and read the
    # Spanish thousands shape '1.000' as one euro. The cap refuses that shape
    # because it is genuinely undecidable, not because three decimals are too
    # precise.
    #
    # A malformed figure REFUSES rather than resolving to None. None here means
    # UNDECLARED, and Art. 58.1 reads an absent figure as non-excluding -- so
    # None is the claiming direction, and quietly mapping a typo onto it would
    # assert a mínimo the taxpayer never established. That is the same
    # over-claim the sibling flags resolve away from.
    #
    # `signed` stays at its permissive default: a negative figure has its own
    # upstream verdict and the record's own ge=0 constraint, both of which say
    # "cannot be negative" far more usefully than this refusal would.
    rentas_anuales_euros = try_parse_canonical_decimal(rentas, max_fraction_digits=2) if rentas else None
    if rentas and rentas_anuales_euros is None:
        raise WorkflowInputMismatchError(
            translated_message="application.wizard.errors.descendant_rentas_not_a_valid_amount",
        )
    # Read as a named pair rather than a second ** unpack: the call already
    # carries one (relacion_kwarg, whose whole purpose is to render zero or
    # one keyword), and two unpacks in one constructor leave a checker unable
    # to tell which of them supplies what.
    guarderia = _safe_guarderia_spend(row)
    return DescendantInfo(
        birth_date=birth_date,
        **relacion_kwarg(relacion),
        dependencia_economica=dependencia,
        inscripcion_registro_civil_date=inscripcion_date,
        acogimiento_resolucion_date=acogimiento_date,
        death_date=parse_iso8601_date(row.get("fallecimiento", "")),
        discapacidad_grado=_discapacidad_grade(row.get("discapacidad", "")),
        # Both read through the canonical vocabulary, and both resolve an
        # unreadable or unanswered value to the NON-CLAIMING direction.
        #
        # convivencia gates the Art. 58.1 and 58.2 mínimo outright
        # (DescendantInfo.is_eligible_ordinary refuses when it is false), so
        # True is the claiming answer. The negative list this replaces --
        # `!= "false"` -- resolved everything except one spelling to True,
        # which made an unanswered question assert cohabitation and claim a
        # mínimo the taxpayer never stated. Over-declaring is the worse
        # direction: under-declaring short-changes them and is visible to
        # them, while a false claim to AEAT is what gets them penalised.
        #
        # Do not flip either of these back for symmetry with the page
        # defaults. The flow declares `default="true"` for convivencia, which
        # is the value the widget PRE-FILLS for an operator who is present to
        # accept or change it; it is not a licence to assert the same answer
        # for one who never saw the question.
        convive_con_contribuyente=parse_bool(row.get("convivencia", "")) is True,
        custodia_compartida=parse_bool(row.get("custodia-compartida", "")) is True,
        # An unanswered rentas figure stays UNDECLARED (None) rather than
        # collapsing to zero. Zero is a positive claim that the descendant
        # earned nothing, and asserting it for an operator who skipped the
        # page would re-create the silent over-claim the Art. 58.1 ceiling
        # exists to prevent; None instead records that nobody answered.
        rentas_anuales_euros=rentas_anuales_euros,
        # Both remaining flags resolve an unanswered question to the
        # non-claiming direction, as convivencia and custodia above do.
        presenta_declaracion_propia=parse_bool(row.get("declaracion-propia", "")) is True,
        prorrata_minimo=parse_bool(prorrata) if prorrata else None,
        meses_madre_trabajo=parse_meses_trabajo(meses, field="meses-madre-trabajo") if meses else (),
        alta_posterior_nacimiento_mes=(
            int(row["alta-posterior-nacimiento-mes"]) if row.get("alta-posterior-nacimiento-mes") else None
        ),
        gastos_guarderia_euros=guarderia["gastos_guarderia_euros"],
        gastos_guarderia_mensuales=guarderia["gastos_guarderia_mensuales"],
        nif=row.get("nif") or None,
    )


class _GuarderiaSpend(TypedDict):
    """The two guardería fields ``_safe_guarderia_spend`` resolves as a pair.

    Declared rather than returned as a bare mapping so the ``**`` unpack into
    :class:`~cadrumo.domain.contribuyente.DescendantInfo` stays checkable: a
    ``dict[str, object]`` makes both values ``object`` at the call site, which
    reads as a type error against every field on the record.
    """

    gastos_guarderia_euros: int
    gastos_guarderia_mensuales: tuple[GuarderiaMonthSpend, ...]


def _safe_guarderia_spend(row: Mapping[str, str]) -> _GuarderiaSpend:
    """Read one instance's two guardería answers into a pair the record accepts.

    A persistence projection can receive both an annual total and a monthly
    map, or a monthly map whose grammar broke. The canonical record refuses
    both states, and a raw error would read as a crash rather than a correction
    — the same reason :func:`_safe_relacion_and_entry_dates` drops rather than
    raises. The review verdict still blocks final submission, so the operator
    is told.

    Both resolutions follow the record's own ranking, not convenience:

    * Both declared -> keep the MONTHLY map, drop the annual. The record
      documents the monthly breakdown as the authority where it exists, and it
      is the only shape that can express the period the child turns three.
    * Monthly map unreadable -> drop it and keep whatever annual figure was
      given. Dropping an unreadable map can only WITHHOLD spend, never invent
      it, which is the safe direction while the verdict brings the operator back
      to fix the text.
    """
    from ...core.errors import ProfileAnswerTypeError
    from ...domain.contribuyente import parse_guarderia_mensual

    annual_raw = row.get("gastos-guarderia") or ""
    annual = int(annual_raw) if annual_raw else 0
    try:
        mensuales = parse_guarderia_mensual(row.get("gastos-guarderia-mensuales") or "", field="gastos-guarderia")
    except ProfileAnswerTypeError:
        return {"gastos_guarderia_euros": annual, "gastos_guarderia_mensuales": ()}
    if mensuales:
        return {"gastos_guarderia_euros": 0, "gastos_guarderia_mensuales": mensuales}
    return {"gastos_guarderia_euros": annual, "gastos_guarderia_mensuales": ()}


def descendant_facts_from_answers(answers: Mapping[str, str]) -> list[tuple[str, str]]:
    """Project the descendant repeating-group answers into profile facts.

    The setup flow's descendant repeating group keys each instance answer
    as ``descendientes#<index>.<page-id>``. This reads the live instance
    count from the count page, reconstructs one
    :class:`~cadrumo.domain.contribuyente.DescendantInfo` per index, and
    delegates to
    :func:`~cadrumo.domain.contribuyente.descendant_facts_from_list` so the
    emitted ``renta_family.descendiente.{n}.*`` paths and the derived
    aggregates are the single canonical projection the
    ``_minimo_descendientes_facts`` injector and the registry selectors
    consume. Returns an empty list when the group was never reached (the
    count page carries no answer), so a descendant-free profile writes no
    descendant fact.
    """
    if DESCENDANTS_COUNT_PAGE_ID not in answers:
        return []
    from ...domain.contribuyente import descendant_facts_from_list

    count = _instance_count(answers.get(DESCENDANTS_COUNT_PAGE_ID, ""))
    descendientes: list[DescendantInfo] = []
    for index in range(count):
        prefix = f"{DESCENDANTS_GROUP_ID}{REPEATING_INSTANCE_SEPARATOR}{index}"
        row = {page_id: answers.get(f"{prefix}.{page_id}", "") for page_id in DESCENDANT_PAGE_IDS}
        if not row["birth-date"]:
            continue
        descendientes.append(_descendant_from_row(row))
    return descendant_facts_from_list(descendientes)


def descendant_answers_from_record(record: UserProfileRecord | None) -> dict[str, str]:
    """Re-project a record's descendant facts into repeating-group answers.

    The inverse of :func:`descendant_facts_from_answers`: reads the
    ``renta_family.descendiente.{n}.*`` facts a record carries, reconstructs
    each :class:`~cadrumo.domain.contribuyente.DescendantInfo` through the
    canonical :func:`~cadrumo.domain.contribuyente.descendant_list_from_facts`,
    and emits the ``descendientes-count`` answer plus one
    ``descendientes#<index>.<page-id>`` answer per populated field. This is the
    exact page-keyed shape :func:`~cadrumo.application.flows.resume.resume_flow`
    re-walks to re-instantiate the group: the count answer commits first (the
    familia section orders the count page before the group), revealing the
    instance pages the remaining answers then seed against the current
    definition. Returns an empty map when the record declares no descendants,
    so a childless profile seeds no group.

    The per-field emission mirrors :func:`_descendant_from_row` exactly, so a
    facts-to-answers re-projection preserves an identical fact set: an absent
    optional field stays absent on both legs, never coerced to a stored default.

    Args:
        record: The :class:`UserProfileRecord` whose descendant facts are
            re-projected into repeating-group answers, or ``None``.
    """
    if record is None:
        return {}
    from ...domain.contribuyente import descendant_list_from_facts
    from ..user_profile import record_to_path_values

    descendientes = descendant_list_from_facts(record_to_path_values(record))
    if not descendientes:
        return {}
    answers: dict[str, str] = {DESCENDANTS_COUNT_PAGE_ID: str(len(descendientes))}
    for index, descendant in enumerate(descendientes):
        prefix = f"{DESCENDANTS_GROUP_ID}{REPEATING_INSTANCE_SEPARATOR}{index}"
        answers.update(_descendant_instance_answers(descendant, prefix=prefix))
    return answers


def _descendant_instance_answers(descendant: DescendantInfo, *, prefix: str) -> dict[str, str]:
    """Emit one descendant's page-keyed answers under its instance prefix.

    An absent optional field emits NO answer rather than a stored default,
    which keeps a facts-to-answers re-projection identical on both legs.
    """
    from ...domain.contribuyente import serialise_guarderia_mensual, serialise_meses_trabajo

    answers = {
        f"{prefix}.birth-date": descendant.birth_date.isoformat(),
        f"{prefix}.convivencia": "true" if descendant.convive_con_contribuyente else "false",
        f"{prefix}.custodia-compartida": "true" if descendant.custodia_compartida else "false",
        f"{prefix}.declaracion-propia": "true" if descendant.presenta_declaracion_propia else "false",
    }
    optional: tuple[tuple[str, object | None], ...] = (
        # The ordinary relación emits no answer: it is the record's own default,
        # so re-emitting it would commit an answer on a resume walk that the
        # original walk never gave, and the two legs would stop matching.
        (
            "relacion",
            descendant.relacion.value if descendant.relacion is not DescendantRelacion.DESCENDIENTE else None,
        ),
        (
            "inscripcion-registro-civil",
            descendant.inscripcion_registro_civil_date.isoformat()
            if descendant.inscripcion_registro_civil_date is not None
            else None,
        ),
        (
            "acogimiento-resolucion",
            descendant.acogimiento_resolucion_date.isoformat()
            if descendant.acogimiento_resolucion_date is not None
            else None,
        ),
        ("fallecimiento", descendant.death_date.isoformat() if descendant.death_date is not None else None),
        ("discapacidad", descendant.discapacidad_grado),
        # An empty set means "none recorded", so it emits no answer at all
        # rather than a literal empty string the resume walk would commit.
        # Re-emitted in the CANONICAL expanded form for the same reason the
        # guarderia map below is: a set typed as a range was stored expanded.
        (
            "meses-madre-trabajo",
            serialise_meses_trabajo(descendant.meses_madre_trabajo) if descendant.meses_madre_trabajo else None,
        ),
        ("alta-posterior-nacimiento-mes", descendant.alta_posterior_nacimiento_mes),
        ("gastos-guarderia", descendant.gastos_guarderia_euros if descendant.gastos_guarderia_euros > 0 else None),
        # Re-emitted in the CANONICAL expanded form, which is what the resume
        # walk must see: a map the operator originally typed as a range was
        # stored expanded, so seeding the range back would make the resumed
        # answer differ from the saved one and the two legs would stop matching.
        # An empty map emits nothing, like every other absent optional.
        (
            "gastos-guarderia-mensuales",
            serialise_guarderia_mensual(descendant.gastos_guarderia_mensuales) or None,
        ),
        # Unlike the counts above, zero rentas is a MEANINGFUL declaration
        # ("this child earned nothing"), distinct from never having been
        # asked, so a zero emits its answer rather than being dropped.
        ("rentas-anuales", descendant.rentas_anuales_euros),
        ("prorrata-minimo", None if descendant.prorrata_minimo is None else str(descendant.prorrata_minimo).lower()),
        (
            "dependencia-economica",
            None if descendant.dependencia_economica is None else str(descendant.dependencia_economica).lower(),
        ),
        ("nif", descendant.nif),
    )
    answers.update({f"{prefix}.{page_id}": str(value) for page_id, value in optional if value is not None})
    return answers


_register_project_answers(project_answers)

__all__ = [
    "WizardPersistMode",
    "descendant_answers_from_record",
    "descendant_facts_from_answers",
    "parse_canonical",
    "persist_answers",
    "persist_patch",
    "profile_values_from_patch",
    "project_answers",
    "serialise_answers",
]
