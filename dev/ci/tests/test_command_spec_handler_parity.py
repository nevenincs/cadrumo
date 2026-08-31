"""Every CLI command spec must agree with the handler it dispatches to.

A spec and its handler are written in different files and are only brought
together at dispatch time, so a drift between them is invisible until an
operator runs the verb. Three such drifts shipped at once and each one killed a
verb outright: ``ledger list`` declared a positional the handler had no
parameter for and raised ``TypeError`` on every invocation; ``modelo export``
and ``review-package build`` defaulted a selector to the literal string
``"value"``; four ``aggregate`` observation options declared ``multiple=False``
while their handler iterated the value, so a JSON payload was walked character
by character and refused at byte 1.

All three surfaced to the operator as a generic refusal that named nothing, and
none of them was caught by a test of the verb's behaviour, because the verb
never reached its body.
"""

from __future__ import annotations

import importlib
import inspect
from typing import Final

import pytest

from cadrumo.entrypoints.cli.command_specs import COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SEQUENCE_HINTS: Final = ("list[", "tuple[", "Sequence[")


def _handler_signature(spec: object) -> inspect.Signature | None:
    handler = getattr(spec, "handler", None)
    target = getattr(handler, "target", None)
    if target is None:
        return None
    module = importlib.import_module(target.module)
    resolved = module
    for part in target.qualname.split("."):
        resolved = getattr(resolved, part)
    return inspect.signature(resolved)


def _annotation_text(parameter: inspect.Parameter) -> str:
    annotation = parameter.annotation
    return annotation if isinstance(annotation, str) else str(annotation)


def test_every_spec_parameter_is_accepted_by_its_handler() -> None:
    """A spec may not declare a parameter the handler cannot receive."""
    unknown: list[str] = []
    for spec in COMMAND_SPECS:
        signature = _handler_signature(spec)
        if signature is None:
            continue
        accepted = set(signature.parameters)
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()):
            continue
        for parameter in getattr(spec, "parameters", ()) or ():
            name = getattr(parameter, "name", None)
            if name is not None and name not in accepted:
                unknown.append(f"{spec.key}: {name}")
    assert not unknown, "spec parameters the handler cannot accept: " + ", ".join(sorted(unknown))


def test_repeatable_options_match_the_arity_their_handler_expects() -> None:
    """``multiple`` must agree with whether the handler types a sequence.

    Both directions are defects. A repeatable option bound to a scalar
    parameter overwrites instead of collecting; a scalar option bound to a
    sequence parameter is iterated as a string, one character at a time.
    """
    mismatched: list[str] = []
    for spec in COMMAND_SPECS:
        signature = _handler_signature(spec)
        if signature is None:
            continue
        for parameter in getattr(spec, "parameters", ()) or ():
            name = getattr(parameter, "name", None)
            target = signature.parameters.get(name) if name else None
            if target is None or target.annotation is inspect.Parameter.empty:
                continue
            text = _annotation_text(target)
            expects_sequence = any(hint in text for hint in _SEQUENCE_HINTS)
            declared_many = bool(getattr(parameter, "multiple", False))
            if declared_many is not expects_sequence and not getattr(parameter, "is_flag", False):
                mismatched.append(f"{spec.key}: {name} multiple={declared_many} but handler types {text}")
    assert not mismatched, "option arity disagrees with the handler: " + "; ".join(sorted(mismatched))
