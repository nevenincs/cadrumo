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
from cadrumo.entrypoints.cli.command_spec import CommandSpec
from cadrumo.entrypoints.cli.command_specs import COMMAND_SPECS
pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_SEQUENCE_HINTS: Final = ('list[', 'tuple[', 'Sequence[')
_MINIMUM_HANDLER_BINDINGS: Final = 250
_MINIMUM_DECLARED_PARAMETERS: Final = 1000

def _handler_signature(spec: CommandSpec) -> inspect.Signature | None:
    """Return the signature of the handler ``spec`` dispatches to, or ``None``.

    Every attribute is read directly rather than through a ``getattr`` default.
    A default here cannot be distinguished from the legitimate ``None`` this
    returns for a group node: both make the caller ``continue``, so renaming
    ``CommandSpec.handler`` upstream would take both gates below from 1106
    parameter comparisons to zero while they went on reporting the same green
    verdict. A direct read raises ``AttributeError`` naming the attribute.
    """
    handler = spec.handler
    if handler is None:
        return None
    target = handler.target
    if target is None:
        return None
    module = importlib.import_module(target.module)
    resolved = module
    for part in target.qualname.split('.'):
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
        if any((p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values())):
            continue
        for parameter in spec.parameters:
            if parameter.name not in accepted:
                unknown.append(f'{spec.key}: {parameter.name}')
    assert not unknown, 'spec parameters the handler cannot accept: ' + ', '.join(sorted(unknown))

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
        for parameter in spec.parameters:
            target = signature.parameters.get(parameter.name)
            if target is None or target.annotation is inspect.Parameter.empty:
                continue
            text = _annotation_text(target)
            expects_sequence = any((hint in text for hint in _SEQUENCE_HINTS))
            declared_many = bool(_dp_getattr('dev/ci/tests/test_command_spec_handler_parity.py:115:getattr', parameter, 'multiple', False))
            if declared_many is not expects_sequence and (not _dp_getattr('dev/ci/tests/test_command_spec_handler_parity.py:116:getattr', parameter, 'is_flag', False)):
                mismatched.append(f'{spec.key}: {parameter.name} multiple={declared_many} but handler types {text}')
    assert not mismatched, 'option arity disagrees with the handler: ' + '; '.join(sorted(mismatched))

def test_the_parity_gates_walk_the_corpus_they_claim_to() -> None:
    """Both gates above assert an absence; this asserts they had something to look at.

    Direct attribute access makes a RENAMED binding raise, but an EMPTIED one
    still reads as green: a corpus that bound no handlers, or specs that
    declared no parameters, would satisfy every assertion above by comparing
    nothing. The floors are the standing claim that it compared something.
    """
    bound = [spec for spec in COMMAND_SPECS if _handler_signature(spec) is not None]
    declared = sum((len(spec.parameters) for spec in COMMAND_SPECS))
    assert len(bound) >= _MINIMUM_HANDLER_BINDINGS, f'only {len(bound)} of {len(COMMAND_SPECS)} specs resolved a handler signature; the parity gates compare nothing below {_MINIMUM_HANDLER_BINDINGS}'
    assert declared >= _MINIMUM_DECLARED_PARAMETERS, f'the corpus declares only {declared} parameters; the parity gates compare nothing below {_MINIMUM_DECLARED_PARAMETERS}'