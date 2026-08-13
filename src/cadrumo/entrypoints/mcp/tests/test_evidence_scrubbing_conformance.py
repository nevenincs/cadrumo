"""Conformance gate: no operator-facing result schema emits raw bytes.

Taxpayer source documents (invoice/statement bytes, decrypted evidence) must not
leave the host: they live only in the encrypted secure-storage backend
(``sensitive-financial-data-secure-storage-only``), and the MCP serving path
relays the CLI's ``--json`` envelope verbatim. That guarantee therefore rests on
a single structural fact: the CLI contract never renders evidence bytes into an
envelope; the amount-bearing and evidence-referencing verbs emit attachment
IDs, content hashes, and amounts, not the bytes themselves.

This gate makes that fact enforceable rather than incidental. It walks every
registered ``--json`` result schema (the exact set the serving path can relay)
and asserts no field, however deeply nested, is typed ``bytes`` / ``bytearray``.
A future verb that added a raw-bytes field to its result payload — the one way
evidence bytes could ride an envelope off-host — fails here loudly.

The walk is over the type CONTRACT (pydantic field annotations), so it is
deterministic and needs no live CLI run or profile state.
"""

from __future__ import annotations

import typing
from collections.abc import Iterator
from types import UnionType
from typing import Union, get_args, get_origin

import pytest
from pydantic import BaseModel

from ....core.json_contract import SCHEMA_REGISTRY
from ...cli import command_schema_refs

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FORBIDDEN_LEAF_TYPES: frozenset[type] = frozenset({bytes, bytearray, memoryview})


def _iter_field_annotations(model: type[BaseModel]) -> Iterator[tuple[str, object]]:
    """Yield ``(field_name, annotation)`` for every field of ``model``.

    Works for both ``OutputSchema`` (mapping models) and ``OutputRootSchema``
    (``RootModel`` subclasses): pydantic exposes the root type as the synthetic
    ``root`` field in ``model_fields``, so one path covers both.
    """
    for name, info in model.model_fields.items():
        if not isinstance(name, str):
            raise TypeError("pydantic field names must be strings")
        annotation = info.annotation
        if not isinstance(annotation, object):
            raise TypeError("pydantic field annotations must be objects")
        yield name, annotation


def _walk(annotation: object, seen: set[object], trail: str, findings: list[str]) -> None:
    """Recurse through an annotation, recording any forbidden leaf type it reaches."""
    if annotation in _FORBIDDEN_LEAF_TYPES:
        findings.append(f"{trail} -> {annotation!r}")
        return
    origin = get_origin(annotation)
    if origin in (Union, UnionType) or origin is not None:
        for arg in get_args(annotation):
            if arg is type(None) or arg is Ellipsis:
                continue
            _walk(arg, seen, trail, findings)
        return
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if annotation in seen:
            return
        seen.add(annotation)
        # Resolve any string/forward-ref annotations against the model's module.
        hints = _resolved_hints(annotation)
        for name, hint in hints.items():
            _walk(hint, seen, f"{trail}.{name}", findings)


def _resolved_hints(model: type[BaseModel]) -> dict[str, object]:
    try:
        return dict(typing.get_type_hints(model))
    except Exception:
        # Fall back to the raw pydantic annotations if a forward ref cannot be
        # resolved in this context; still catches concrete bytes annotations.
        return {name: info.annotation for name, info in model.model_fields.items()}


def _all_registered_schemas() -> dict[str, type[BaseModel]]:
    command_schema_refs()
    return dict(SCHEMA_REGISTRY)


def test_registry_is_populated() -> None:
    # Guard against a vacuously-green gate: the walk must see the real surface.
    assert len(_all_registered_schemas()) >= 200


def test_no_result_schema_field_is_raw_bytes() -> None:
    findings: list[str] = []
    for command, schema in sorted(_all_registered_schemas().items()):
        seen: set[object] = set()
        for name, annotation in _iter_field_annotations(schema):
            _walk(annotation, seen, f"{command}::{schema.__name__}.{name}", findings)
    assert not findings, (
        "A result schema declares a raw-bytes field, so evidence bytes could ride a "
        "relayed envelope off-host (R9 breach). Emit an attachment id / content hash "
        "instead:\n" + "\n".join(findings)
    )


def test_walker_detects_a_planted_bytes_field() -> None:
    # Anti-tautology proof: the walk must actually catch a nested bytes field,
    # not pass vacuously because the traversal is broken.
    class _Inner(BaseModel):
        blob: bytes

    class _Outer(BaseModel):
        nested: _Inner
        maybe: _Inner | None
        rows: list[_Inner]

    findings: list[str] = []
    seen: set[object] = set()
    for name, annotation in _iter_field_annotations(_Outer):
        _walk(annotation, seen, f"probe::_Outer.{name}", findings)
    # The bytes leaf is reached (through the nested model, the optional, and the
    # list). The offending model type is reported once — deduped by type so the
    # human fixes `_Inner.blob` in one place rather than chasing every field.
    assert findings, findings
    assert all("blob" in f for f in findings)


def test_walker_accepts_str_and_decimal_evidence_shapes() -> None:
    # The legitimate evidence/amount shape — ids, hashes, amounts as str/Decimal —
    # must NOT be flagged, or the gate would be uselessly noisy.
    from decimal import Decimal

    class _EvidenceRow(BaseModel):
        attachment_id: str
        content_sha256: str
        amount: Decimal
        note: str | None

    findings: list[str] = []
    seen: set[object] = set()
    for name, annotation in _iter_field_annotations(_EvidenceRow):
        _walk(annotation, seen, f"probe::_EvidenceRow.{name}", findings)
    assert findings == []
