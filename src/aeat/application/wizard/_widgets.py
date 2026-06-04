"""Per-widget validators and the canonical dispatch entry point.

The schema-driven wizard collects answers as canonical-token strings.
Each :class:`WizardWidget` member dispatches onto one validator that
parses the raw token, enforces the closed-set or filesystem
constraints declared on the descriptor, and returns the canonical
form. Validators raise :class:`WizardValidationError` whose message
carries the failing question's translation key so renderers can map
the failure back to a localised prompt.

Tax-ID-shaped questions (any question whose id matches ``tax-id`` or
ends with ``-tax-id``) route through
:func:`aeat.core.identity.validate_identity` so the Spanish NIF / NIE
/ CIF checksum is enforced at every write surface: interactive,
``--quiet`` flag, and profile wizard mutations.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...core.errors import resolve_error_message
from ...core.i18n import tr
from ...core.identity import IdentityError, validate_identity
from ._errors import WizardValidationError
from ._models import WizardQuestion, WizardWidget

_TRUE_TOKENS = frozenset({"true", "yes", "1", "y"})
_FALSE_TOKENS = frozenset({"false", "no", "0", "n"})

_TAX_ID_QUESTION_IDS: frozenset[str] = frozenset({"tax-id", "spouse-tax-id"})

_POSTCODE_QUESTION_IDS: frozenset[str] = frozenset({"address-postcode"})
"""Question ids whose answer must be a Spanish 5-digit postcode."""

_SPANISH_POSTCODE_RE = re.compile(r"^(0[1-9]|[1-4][0-9]|5[0-2])[0-9]{3}$")
"""Spanish postcode: 5 digits whose first two are a province code 01-52.

The field is a string throughout — leading zeros are significant
(``01001`` is Vitoria-Gasteiz) and must never be int-coerced.
"""


def _fail(question: WizardQuestion, reason: str, **context: object) -> WizardValidationError:
    """Build a translated :class:`WizardValidationError` for ``question``.

    ``question.prompt`` carries a translation *key*
    (``wizard.setup.profile.tax-id.prompt``), not a resolved label.
    The operator-facing error string interpolates ``prompt_key``, so
    the key path must be resolved through :func:`tr` first — otherwise
    the internal key leaks verbatim into the refusal message
    (``Invalid NIF/NIE/CIF for wizard.setup.profile.tax-id.prompt``).
    The raw key path is intentionally not carried in the context; the
    operator-facing surface only needs the resolved field label.
    """
    message_key = f"wizard.errors.{reason}"
    field_label = tr(str(question.prompt))
    render_context: dict[str, object] = {
        "prompt_key": field_label,
        "question_id": question.id,
    }
    render_context.update(context)
    error_context = _redact_validation_context(render_context)
    translated = tr(message_key, **render_context)
    return WizardValidationError(message_key, context=error_context, translated_message=translated)


def _redact_validation_context(context: dict[str, object]) -> dict[str, object]:
    """Return structured diagnostics without raw operator answers."""
    redacted = dict(context)
    raw = redacted.pop("raw", None)
    if raw is not None:
        redacted["raw_redacted"] = True
        redacted["raw_length"] = len(str(raw))
    detail = redacted.pop("detail", None)
    if detail is not None:
        redacted["detail_redacted"] = True
    return redacted


def validate_text(raw: str, question: WizardQuestion) -> str:
    """Return the trimmed text answer; reject blank required strings.

    Tax-id-shaped questions additionally route through the Spanish
    NIF / NIE / CIF checksum validator from
    :mod:`aeat.core.identity`. Malformed values raise
    :class:`WizardValidationError` carrying
    ``wizard.errors.invalid_tax_id``. The validator's resolved,
    localised diagnostic — which names the correct check letter or
    the expected document shape — is interpolated as ``detail`` so
    the operator sees an actionable one-step fix rather than an
    opaque refusal.

    The ``address-postcode`` question additionally enforces the
    Spanish 5-digit postcode format (province code 01-52 followed by
    three digits). The answer stays a string throughout so leading
    zeros are preserved; it is never int-coerced.
    """
    value = raw.strip()
    if not value and question.required and question.visible_when is None:
        raise _fail(question, "blank_text")
    if value and question.choices:
        allowed = {choice.value for choice in question.choices}
        if value not in allowed:
            raise _fail(question, "select_unknown", raw=raw, choices=sorted(allowed))
    if value and question.id in _TAX_ID_QUESTION_IDS:
        try:
            validate_identity(value)
        except IdentityError as exc:
            raise _fail(
                question,
                "invalid_tax_id",
                raw=raw,
                detail=resolve_error_message(exc),
            ) from exc
    if value and question.id in _POSTCODE_QUESTION_IDS and not _SPANISH_POSTCODE_RE.match(value):
        raise _fail(question, "invalid_postcode", raw=raw)
    return value


def validate_secret(raw: str, question: WizardQuestion) -> str:
    """Return the raw secret answer unchanged; reject blank required strings."""
    if not raw and question.required and question.visible_when is None:
        raise _fail(question, "blank_secret")
    return raw


def validate_confirm(raw: str, question: WizardQuestion) -> str:
    """Canonicalise a boolean answer to ``"true"`` / ``"false"``.

    Blank-answer policy mirrors :func:`validate_select`: a blank token
    is accepted for an optional question or for a conditionally-gated
    question (one that declares ``visible_when``) and returns the
    empty canonical, representing the undeclared three-state. The
    persistence layer drops blank values, so an optional CONFIRM that
    the operator never positively declared persists nothing and the
    typed projection reloads as ``None`` rather than collapsing onto
    declared-``False``. A blank answer fails only for an
    unconditionally-required CONFIRM.
    """
    token = raw.strip().lower()
    if not token:
        if question.required and question.visible_when is None:
            raise _fail(question, "invalid_confirm", raw=raw)
        return ""
    if token in _TRUE_TOKENS:
        return "true"
    if token in _FALSE_TOKENS:
        return "false"
    raise _fail(question, "invalid_confirm", raw=raw)


def validate_select(raw: str, question: WizardQuestion) -> str:
    """Reject any answer that is not declared in the question's choices.

    Blank-answer policy is keyed on the *static* descriptor, because
    the validator is handed only the question and the raw answer — the
    runner's evaluated ``visible_when`` verdict is not threaded into
    this call. A blank answer fails only for an *unconditionally*
    required question (``required`` and no ``visible_when``). A blank
    answer is accepted for an optional question, and for a
    conditionally-gated question (one that declares a ``visible_when``)
    regardless of its ``required`` flag — a gated question represents
    an undeclared closed-set fact when left blank. Any non-blank answer
    must match a declared choice.
    """
    if not question.choices:
        raise _fail(question, "select_without_choices")
    value = raw.strip()
    if not value:
        if question.required and question.visible_when is None:
            raise _fail(question, "select_unknown", raw=raw, choices=sorted({c.value for c in question.choices}))
        return value
    allowed = {choice.value for choice in question.choices}
    if value not in allowed:
        raise _fail(question, "select_unknown", raw=raw, choices=sorted(allowed))
    return value


def validate_checkbox(raw: str, question: WizardQuestion) -> str:
    """Validate a comma-separated list of choice tokens against the choices.

    Blank-answer policy matches :func:`validate_select`: an empty token
    set fails only for an *unconditionally* required question
    (``required`` and no ``visible_when``). An empty set is accepted
    for an optional question, and for a conditionally-gated question
    (one that declares a ``visible_when``) regardless of its
    ``required`` flag, because the runner's evaluated visibility is not
    threaded into this validator. Every supplied token must match a
    declared choice; the canonical form is the sorted token set.
    """
    if not question.choices:
        raise _fail(question, "checkbox_without_choices")
    allowed = {choice.value for choice in question.choices}
    tokens = [item.strip() for item in raw.split(",") if item.strip()]
    if question.required and question.visible_when is None and not tokens:
        raise _fail(question, "checkbox_required")
    for token in tokens:
        if token not in allowed:
            raise _fail(question, "checkbox_unknown", raw=token, choices=sorted(allowed))
    return ",".join(sorted(tokens))


def validate_path(raw: str, question: WizardQuestion) -> str:
    """Return the canonical filesystem string; reject blank required paths."""
    value = raw.strip()
    if not value:
        if question.required and question.visible_when is None:
            raise _fail(question, "blank_path")
        return value
    path = Path(value).expanduser()
    return str(path)


def validate_integer(raw: str, question: WizardQuestion) -> str:
    """Parse the answer as an integer and re-emit the canonical decimal form."""
    text = raw.strip()
    if not text:
        if question.required and question.visible_when is None:
            raise _fail(question, "blank_integer")
        return text
    try:
        parsed = int(text)
    except ValueError as exc:
        raise _fail(question, "invalid_integer", raw=raw) from exc
    return str(parsed)


_VALIDATORS = {
    WizardWidget.TEXT: validate_text,
    WizardWidget.SECRET: validate_secret,
    WizardWidget.CONFIRM: validate_confirm,
    WizardWidget.SELECT: validate_select,
    WizardWidget.CHECKBOX: validate_checkbox,
    WizardWidget.PATH: validate_path,
    WizardWidget.INTEGER: validate_integer,
}


def validate_widget_answer(question: WizardQuestion, raw: str) -> str:
    """Dispatch ``question.widget`` onto its widget-specific validator."""
    validator = _VALIDATORS[question.widget]
    return validator(raw, question)


__all__ = [
    "WizardWidget",
    "validate_checkbox",
    "validate_confirm",
    "validate_integer",
    "validate_path",
    "validate_secret",
    "validate_select",
    "validate_text",
    "validate_widget_answer",
]
