"""Operator-safe projection of a record that failed its own validation.

A record the application built, loaded or was handed can fail its pydantic
contract. Its ``errors()`` payload holds the offending values, so it never
crosses an output boundary as it stands. This module projects it into a
bounded context that names the failing record and, per violation, the field
path and the rule that was broken -- the facts that make a defect reportable
without carrying any value that breached a constraint.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, cast, get_args

from pydantic import BaseModel, ConfigDict, ValidationError

#: Ceiling on the number of field violations named in an internal-fault context.
#: A record failing every field would otherwise turn one refusal into a wall of
#: text; the first few name the record and the constraint, which is what makes
#: the report actionable.
_INTERNAL_FAULT_VIOLATION_LIMIT: Final[int] = 5


#: Pydantic error types whose ``msg`` is prose authored by the validator that
#: raised, rather than a sentence pydantic composed from the declared constraint.
#: Their text is not under this module's control and routinely quotes the value
#: that failed -- ``ValueError(f"tax identifier {value!r} must be ...")`` is the
#: ordinary way to write a domain validator, so the leak is the NORM on this
#: shape rather than an unlucky case.
_VALIDATOR_AUTHORED_MESSAGE_TYPES: Final[frozenset[str]] = frozenset({"value_error", "assertion_error"})


#: Stands in for a path component this module cannot prove is a declared field
#: name. Fixed text, never derived from the component, so it carries nothing.
_REDACTED_PATH_COMPONENT: Final[str] = "<key>"

#: Emitted where a violation has no path at all -- a model-level validator.
_ROOT_PATH: Final[str] = "<root>"


def _declared_field_names(record: type[BaseModel] | None) -> frozenset[str]:
    """Return every field name declared anywhere in *record*'s model tree.

    A flat SET rather than a positional walk of the annotation graph, and the
    imprecision is deliberate. The question this projection has to answer is
    "could this component be taxpayer data", and a string that a programmer
    declared as a field name somewhere in the record's own tree cannot be: it is
    a source identifier either way. Resolving which model each component belongs
    to would buy precision the guarantee does not need, at the cost of walking
    unions, generics and forward references correctly -- and getting that walk
    subtly wrong fails OPEN.

    The residual imprecision is that a mapping key which happens to equal a
    declared field name elsewhere in the tree is emitted. That is a key spelling
    a programmer's identifier, not a tax identifier, an amount or a name.
    """
    if record is None:
        return frozenset[str]()
    names: set[str] = set()
    seen: set[type] = set()

    def walk(model: object) -> None:
        if not (isinstance(model, type) and issubclass(model, BaseModel)) or model in seen:
            return
        seen.add(model)
        for name, field in model.model_fields.items():
            names.add(name)
            for nested in (field.annotation, *get_args(field.annotation)):
                walk(nested)
                for deeper in get_args(nested):
                    walk(deeper)

    walk(record)
    return frozenset(names)


def _violation_path(loc: tuple[object, ...], declared: frozenset[str]) -> str:
    """Return the failing path with anything unprovable replaced, never elided.

    Integer components are list indices and are emitted verbatim: a position is
    not data. String components are emitted only when *declared* confirms them as
    field names somewhere in the record's own tree.

    **Replaced rather than dropped**, so the path keeps its DEPTH. An elided
    component would make ``rows.0.n`` and ``rows.0.<key>.n`` read alike, which
    hides the presence of a mapping exactly where an engineer needs to see one.
    """
    if not loc:
        return _ROOT_PATH
    parts = [str(part) if isinstance(part, int) or str(part) in declared else _REDACTED_PATH_COMPONENT for part in loc]
    return ".".join(parts)


def _safe_violation_field_hints(
    item: Mapping[str, object],
    declared: frozenset[str],
) -> tuple[str, ...]:
    """Return validator-supplied field names only when the model declares them.

    Model-level validators have an empty pydantic location, even when their
    registered domain error knows which fields form the invariant. The narrow
    ``fields`` metadata is carried on that domain error and survives the
    pydantic ``ValueError`` bridge as its cause. Treat it as an allowlisted
    diagnostic: every name must be a declared field of the supplied model, so
    arbitrary validator prose or input values cannot cross this boundary.
    """
    context = item.get("ctx")
    typed_context = cast(Mapping[str, object], context) if isinstance(context, Mapping) else None
    raised = typed_context.get("error") if typed_context is not None else None
    candidates = (raised, getattr(raised, "__cause__", None))
    for candidate in candidates:
        fields = _validator_field_names(getattr(candidate, "context", None))
        if fields and all(field in declared for field in fields):
            return fields
    return ()


class _ValidatorFieldHint(BaseModel):
    """The ``fields`` hint a registered domain error may carry for a model-level invariant."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    fields: str | tuple[str, ...]


def _validator_field_names(context: object) -> tuple[str, ...]:
    """Parse a domain error's ``fields`` hint into names, or nothing when it carries no well-formed one.

    A comma-separated string and a sequence of names are both accepted; any
    other shape, including a sequence holding a non-string, is no hint at all.
    """
    try:
        hint = _ValidatorFieldHint.model_validate(context)
    except ValidationError:
        return ()
    if isinstance(hint.fields, str):
        return tuple(part.strip() for part in hint.fields.split(",") if part.strip())
    return hint.fields


def _violation_location(item: Mapping[str, object], declared: frozenset[str]) -> str:
    """Render a pydantic location, or safe field hints for a model-level error."""
    raw_location = item.get("loc", ())
    location = cast(tuple[object, ...], raw_location) if isinstance(raw_location, tuple) else ()
    if location:
        return _violation_path(location, declared)
    hints = _safe_violation_field_hints(item, declared)
    return ", ".join(hints) if hints else _ROOT_PATH


def _violation_rule(item: Mapping[str, object]) -> str:
    """Return the rule an error broke, with no text the validator authored.

    Pydantic's own messages are composed from the DECLARED constraint -- "String
    should have at most 9 characters", "Input should be a valid integer" -- and
    name the rule without the value, which is exactly the projection this module
    promises. A ``value_error`` or ``assertion_error`` message is different in
    kind: it is whatever a domain validator chose to write, and this module
    cannot constrain it.

    For those, the rule is reported as the pydantic error type plus the class of
    the exception that raised. Both are identifiers from the source tree, so
    neither can carry taxpayer data, and together they say which contract failed
    -- which is what makes the fault reportable. The prose is dropped rather than
    trimmed or pattern-scrubbed: a redactor over free text is a guess about what
    is sensitive, and the whole point of this projection is that it never has to
    make one.
    """
    kind = str(item.get("type", "validation_error"))
    if kind not in _VALIDATOR_AUTHORED_MESSAGE_TYPES:
        return str(item.get("msg", "validation error"))
    context = item.get("ctx")
    typed_context = cast(Mapping[str, object], context) if isinstance(context, Mapping) else None
    raised = typed_context.get("error") if typed_context is not None else None
    named = type(raised).__name__ if raised is not None else None
    return f"{kind} ({named})" if named else kind


def internal_record_fault_context(
    error: ValidationError,
    *,
    record: type[BaseModel] | None = None,
) -> dict[str, object]:
    """Summarise ``error`` as operator-safe context naming the failing contract.

    The generic validation boundary discards the pydantic detail entirely and
    writes it only to the error log, so an operator meeting an internal fault is
    told to check arguments that are correct and has no way to discover the real
    cause. This projects the same detail into the error envelope's ``context``,
    which both the JSON and text renderers already emit.

    Carries the failing model's name and, per violation, the field path and the
    rule that was broken -- never ``input``, and never a message a domain
    validator authored. A validated record on this path holds taxpayer data, and
    the value that breached a constraint is exactly the value that must not
    cross an output boundary.

    **Withholding ``input`` alone did not achieve that**, and the docstring
    asserted it for as long as it did not. A ``value_error`` carries the value
    inside its own message text, because formatting the offending value into the
    refusal is how domain validators are normally written -- so the guarantee was
    defeated by the commonest validator shape rather than by an exotic one. The
    message is now withheld for exactly those types and the rule reported as the
    error type plus the raising exception's class.

    A withheld message is COUNTED in ``violation_messages_withheld`` rather than
    dropped silently, so an engineer reading a thin report can tell the detail
    was suppressed on purpose and go to the error log, which still holds the
    unredacted ``errors()`` payload.

    **The path is projected under the same rule as the message**, because a
    violation's ``loc`` reproduces mapping KEYS as well as field names -- a
    record holding a mapping keyed by a tax identifier puts that identifier in
    the path, and this docstring once called the path non-sensitive.

    A :exc:`~pydantic.ValidationError` carries only the failing model's NAME, so
    a component cannot be classified from the error alone; *record* is how a
    caller that knows the model supplies the missing half. Every string
    component is replaced unless that model's tree declares it as a field name.
    **Without *record* every string component is replaced**, which is a real loss
    of detail and the deliberate direction to fail in: a projection that guesses
    which strings are safe is the guess this whole helper exists to avoid, and
    ``failing_record`` plus the broken rule still identify the contract. Pattern
    matching the component against known identifier shapes was rejected for the
    same reason it was rejected for the message.
    """
    violations = error.errors()
    reported = violations[:_INTERNAL_FAULT_VIOLATION_LIMIT]
    declared = _declared_field_names(record)
    named = tuple(f"{_violation_location(item, declared)}: {_violation_rule(item)}" for item in reported)
    withheld = sum(1 for item in reported if str(item.get("type", "")) in _VALIDATOR_AUTHORED_MESSAGE_TYPES)
    context: dict[str, object] = {
        "failing_record": error.title,
        "violation_count": len(violations),
        "violations": "; ".join(named),
    }
    if withheld:
        context["violation_messages_withheld"] = withheld
    if len(violations) > _INTERNAL_FAULT_VIOLATION_LIMIT:
        context["violations_omitted"] = len(violations) - _INTERNAL_FAULT_VIOLATION_LIMIT
    return context


__all__ = ["internal_record_fault_context"]
