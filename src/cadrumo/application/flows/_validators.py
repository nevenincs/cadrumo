"""Validator contracts and registries for the flow substrate.

Three validator scopes exist, mirroring the three-tier validation the
substrate renders: per-answer validators run at commit time on one
page's raw token; section-exit validators run when the operator leaves a
section; flow-scope validators run at the review surface. All three are
pure functions returning :class:`ValidationVerdict` records carrying
i18n *message keys* (never prose) and redacted context — raw operator
answers never enter diagnostics.

Domain flows register their validators by id at import time and name
those ids on the :class:`FlowDefinition`; the registries reject
duplicate ids so a validator has exactly one owner. Widget-level shape
validation (blank/choice/integer/date/decimal/path canonicalisation) is
built in and runs before any registered per-answer validator.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.decimal import try_parse_canonical_decimal
from ...core.flows import DEFER_TOKEN, FlowWidgetKind
from ...core.parsing import parse_bool, parse_date
from ...core.redaction import redact_validation_context
from ._definition import FlowPage
from .errors import FlowValidatorRegistryError


class ValidationVerdict(BaseModel):
    """One typed validation outcome, renderable on the page or review surface.

    ``message_key`` is a translation key; ``context`` carries only
    redacted, non-sensitive interpolation values (counts, choice sets,
    field labels — never the raw answer).
    """

    model_config = STRICT_FROZEN_CONFIG

    ok: bool
    message_key: str | None = None
    context: dict[str, object] = Field(default_factory=dict)

    @classmethod
    def passed(cls) -> ValidationVerdict:
        return cls(ok=True)

    @classmethod
    def failed(cls, message_key: str, **context: object) -> ValidationVerdict:
        return cls(ok=False, message_key=message_key, context=redact_validation_context(dict(context)))


AnswerValidator = Callable[[FlowPage, str], ValidationVerdict]
"""Commit-time validator over one page's canonical raw token."""

CrossFieldValidator = Callable[[Mapping[str, str]], tuple[ValidationVerdict, ...]]
"""Section-exit / flow-scope validator over the canonical answer map."""

_ANSWER_VALIDATORS: dict[str, AnswerValidator] = {}
_CROSS_FIELD_VALIDATORS: dict[str, CrossFieldValidator] = {}


def register_answer_validator(validator_id: str, validator: AnswerValidator) -> None:
    """Register a per-answer validator under a unique id."""
    _register(_ANSWER_VALIDATORS, validator_id, validator)


def register_cross_field_validator(validator_id: str, validator: CrossFieldValidator) -> None:
    """Register a section-exit or flow-scope validator under a unique id."""
    _register(_CROSS_FIELD_VALIDATORS, validator_id, validator)


def resolve_answer_validator(validator_id: str) -> AnswerValidator:
    """Return the registered per-answer validator or refuse loudly."""
    return _resolve(_ANSWER_VALIDATORS, validator_id)


def resolve_cross_field_validator(validator_id: str) -> CrossFieldValidator:
    """Return the registered cross-field validator or refuse loudly."""
    return _resolve(_CROSS_FIELD_VALIDATORS, validator_id)


def _register[ValidatorT](registry: dict[str, ValidatorT], validator_id: str, validator: ValidatorT) -> None:
    if not validator_id:
        raise FlowValidatorRegistryError(
            translated_message="application.flows.errors.validator_id_blank",
        )
    if validator_id in registry:
        raise FlowValidatorRegistryError(
            translated_message="application.flows.errors.validator_id_duplicate",
            context={"validator_id": validator_id},
        )
    registry[validator_id] = validator


def _resolve[ValidatorT](registry: Mapping[str, ValidatorT], validator_id: str) -> ValidatorT:
    validator = registry.get(validator_id)
    if validator is None:
        raise FlowValidatorRegistryError(
            translated_message="application.flows.errors.validator_id_unknown",
            context={"validator_id": validator_id, "registered_count": len(registry)},
        )
    return validator


def validate_widget_shape(page: FlowPage, raw: str) -> tuple[str, ValidationVerdict]:
    """Validate and canonicalise ``raw`` against the page's widget shape.

    Returns ``(canonical_token, verdict)``. The canonical token is
    meaningful only when the verdict passes. Blank-answer policy is
    keyed on the static descriptor exactly as the one-shot wizard's
    validators were: a blank fails only for an *unconditionally*
    required page (``required`` and no ``visible_when``); a gated or
    optional page accepts blank as the undeclared state.

    A ``DATE`` page carries its canonical answer as the ISO-8601 string
    (``YYYY-MM-DD``) and a ``DECIMAL`` page as the ``str(Decimal)`` form:
    both keep ``answer_type = str`` on the page rather than widening the
    :class:`FlowPage` answer-type union to ``date`` / ``Decimal``. The
    shape validation here is the sole guarantee the stored token parses,
    so the consuming domain re-parses the canonical string with the same
    core parser it validated against.
    """
    match page.widget:
        case FlowWidgetKind.TEXT | FlowWidgetKind.SECRET:
            return _validate_text(page, raw)
        case FlowWidgetKind.CONFIRM:
            return _validate_confirm(page, raw)
        case FlowWidgetKind.SELECT:
            return _validate_select(page, raw)
        case FlowWidgetKind.COMPARE_SELECT:
            return _validate_compare_select(page, raw)
        case FlowWidgetKind.CHECKBOX:
            return _validate_checkbox(page, raw)
        case FlowWidgetKind.PATH:
            return _validate_path(page, raw)
        case FlowWidgetKind.INTEGER:
            return _validate_integer(page, raw)
        case FlowWidgetKind.DATE:
            return _validate_date(page, raw)
        case FlowWidgetKind.DECIMAL:
            return _validate_decimal(page, raw)


def _blank_allowed(page: FlowPage) -> bool:
    return not (page.required and page.visible_when is None)


def _validate_text(page: FlowPage, raw: str) -> tuple[str, ValidationVerdict]:
    value = raw if page.widget is FlowWidgetKind.SECRET else raw.strip()
    if not value and not _blank_allowed(page):
        return "", ValidationVerdict.failed("flows.errors.blank_required", page_id=page.id)
    return value, ValidationVerdict.passed()


def _validate_confirm(page: FlowPage, raw: str) -> tuple[str, ValidationVerdict]:
    token = raw.strip().lower()
    if not token:
        if _blank_allowed(page):
            return "", ValidationVerdict.passed()
        return "", ValidationVerdict.failed("flows.errors.invalid_confirm", page_id=page.id, raw=raw)
    # The refusal below names the accepted forms in the operator's own language
    # -- "Responde sí o no", "Válaszolj igennel vagy nemmel" -- so the door has
    # to accept what its own message asks for. A private token set here did not:
    # it knew no Spanish affirmative at all, so a taxpayer told to answer `sí`
    # was refused with that same sentence again, able to decline but not to
    # consent; and it knew neither Hungarian word, so `hu` could not answer
    # either way. The canonical parser is the one vocabulary every reader of an
    # operator-written boolean resolves through, and it carries the forms each
    # shipped catalogue advertises.
    answer = parse_bool(token)
    if answer is not None:
        return ("true" if answer else "false"), ValidationVerdict.passed()
    return "", ValidationVerdict.failed("flows.errors.invalid_confirm", page_id=page.id, raw=raw)


def _validate_select(page: FlowPage, raw: str) -> tuple[str, ValidationVerdict]:
    value = raw.strip()
    allowed = {choice.value for choice in page.choices}
    if not value:
        if _blank_allowed(page):
            return "", ValidationVerdict.passed()
        return "", ValidationVerdict.failed(
            "flows.errors.select_unknown",
            page_id=page.id,
            choices=sorted(allowed),
        )
    if value not in allowed:
        return "", ValidationVerdict.failed(
            "flows.errors.select_unknown",
            page_id=page.id,
            raw=raw,
            choices=sorted(allowed),
        )
    return value, ValidationVerdict.passed()


def _validate_compare_select(page: FlowPage, raw: str) -> tuple[str, ValidationVerdict]:
    value = raw.strip()
    if value == DEFER_TOKEN:
        return DEFER_TOKEN, ValidationVerdict.passed()
    return _validate_select(page, value)


def _validate_checkbox(page: FlowPage, raw: str) -> tuple[str, ValidationVerdict]:
    allowed = {choice.value for choice in page.choices}
    tokens = [item.strip() for item in raw.split(",") if item.strip()]
    if not tokens and not _blank_allowed(page):
        return "", ValidationVerdict.failed("flows.errors.checkbox_required", page_id=page.id)
    for token in tokens:
        if token not in allowed:
            return "", ValidationVerdict.failed(
                "flows.errors.checkbox_unknown",
                page_id=page.id,
                raw=token,
                choices=sorted(allowed),
            )
    return ",".join(sorted(tokens)), ValidationVerdict.passed()


def _validate_path(page: FlowPage, raw: str) -> tuple[str, ValidationVerdict]:
    value = raw.strip()
    if not value:
        if _blank_allowed(page):
            return "", ValidationVerdict.passed()
        return "", ValidationVerdict.failed("flows.errors.blank_required", page_id=page.id)
    return str(Path(value).expanduser()), ValidationVerdict.passed()


def _validate_integer(page: FlowPage, raw: str) -> tuple[str, ValidationVerdict]:
    text = raw.strip()
    if not text:
        if _blank_allowed(page):
            return "", ValidationVerdict.passed()
        return "", ValidationVerdict.failed("flows.errors.blank_required", page_id=page.id)
    try:
        parsed = int(text)
    except ValueError:
        return "", ValidationVerdict.failed("flows.errors.invalid_integer", page_id=page.id, raw=raw)
    return str(parsed), ValidationVerdict.passed()


def _validate_date(page: FlowPage, raw: str) -> tuple[str, ValidationVerdict]:
    """Validate an ISO-8601 (``YYYY-MM-DD``) date, canonicalising to the ISO string.

    The blank policy is identical to :func:`_validate_integer`. A
    non-blank token is parsed through the canonical core
    :func:`~cadrumo.core.parsing.parse_date` under the ``"none"``
    error policy, so a malformed date returns a failing *verdict* rather
    than letting a :exc:`ValueError` escape the pure validator. The
    failure context carries only ``page_id`` — never the raw answer.
    """
    text = raw.strip()
    if not text:
        if _blank_allowed(page):
            return "", ValidationVerdict.passed()
        return "", ValidationVerdict.failed("flows.errors.blank_required", page_id=page.id)
    parsed = parse_date(text, fmt="iso8601", on_error="none")
    if parsed is None:
        return "", ValidationVerdict.failed("flows.errors.invalid_date", page_id=page.id)
    return parsed.isoformat(), ValidationVerdict.passed()


def _validate_decimal(page: FlowPage, raw: str) -> tuple[str, ValidationVerdict]:
    """Validate a :class:`~decimal.Decimal` amount, canonicalising to ``str(Decimal)``.

    The blank policy is identical to :func:`_validate_integer`. A non-blank token
    must conform to the canonical decimal grammar
    (:func:`~core.decimal.try_parse_canonical_decimal`): a dot decimal separator,
    no thousands grouping, no comma decimal, no scientific notation, no leading
    ``+``, no underscore digit separator, and no ``NaN``/``Infinity``. The
    grammar subsumes the finiteness guard this previously applied on top of a
    bare :class:`~decimal.Decimal` call, and closes the forms that call admitted:
    ``1e3`` became a thousand-fold misreading of a typo, and a non-finite amount
    compares ``False`` to every threshold, so a downstream advisory keyed on
    ``> 0`` never fires for it.

    The fractional part is deliberately uncapped, because the DECIMAL widget is a
    generic numeric channel serving rates and percentages as well as euro
    amounts. Because the grammar refuses exponent input, the parsed value's
    exponent is never positive, so the ``str(Decimal)`` canonical form this
    returns is always plain digits — a token every downstream re-read parses back
    under the same grammar. The failure context carries only ``page_id`` — never
    the raw answer.
    """
    text = raw.strip()
    if not text:
        if _blank_allowed(page):
            return "", ValidationVerdict.passed()
        return "", ValidationVerdict.failed("flows.errors.blank_required", page_id=page.id)
    parsed = try_parse_canonical_decimal(text)
    if parsed is None:
        return "", ValidationVerdict.failed("flows.errors.invalid_decimal", page_id=page.id)
    return str(parsed), ValidationVerdict.passed()


def run_answer_validation(page: FlowPage, raw: str) -> tuple[str, tuple[ValidationVerdict, ...]]:
    """Run widget-shape validation then every registered per-answer validator.

    Registered validators see the canonical token only after the widget
    shape passed; a failing widget verdict short-circuits.
    """
    canonical, shape_verdict = validate_widget_shape(page, raw)
    if not shape_verdict.ok:
        return canonical, (shape_verdict,)
    verdicts = [resolve_answer_validator(validator_id)(page, canonical) for validator_id in page.answer_validator_ids]
    failures = tuple(verdict for verdict in verdicts if not verdict.ok)
    return canonical, failures if failures else (ValidationVerdict.passed(),)


__all__ = [
    "AnswerValidator",
    "CrossFieldValidator",
    "ValidationVerdict",
    "register_answer_validator",
    "register_cross_field_validator",
    "resolve_answer_validator",
    "resolve_cross_field_validator",
    "run_answer_validation",
    "validate_widget_shape",
]
