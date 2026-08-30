"""A field promising a UTC instant must not be fed a naive one.

``UtcInstant`` refuses a datetime without a timezone, which is the point: a
naive value reaching a field that promises UTC is a bug the type system should
catch. The failure mode this gate exists for is the mirror image -- typing a
field ``UtcInstant`` when its PRODUCER cannot supply an instant at all.

That happened. The justificante receipt carries a Europe/Madrid wall-clock time
that AEAT prints without an offset, read with ``strptime``, which yields a
naive value by construction. Typing it as an instant refused every real receipt
and broke a hundred and thirty-two tests. The same model's ``parsed_at`` is a
genuine instant, built from ``now()`` -- so the distinction is per field, not
per model, and a name ending in ``_at`` does not settle it.

The check is structural rather than a runtime probe. A function whose body
calls ``strptime`` and never attaches or converts a timezone returns a naive
datetime whatever its callers do with it, and any field ultimately fed from one
cannot honour a UTC promise. So: every such producer is enumerated, and a
producer is allowed only where a reviewer has recorded why the naive value is
correct -- which for a printed local time it is.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path(__file__).resolve().parent.parent.parent

#: Calls that attach or convert a timezone, making a parsed datetime aware.
_AWARENESS_CALLS = ("tzinfo", "astimezone", "fromisoformat", "utc_from_", "as_utc")

#: Producers that legitimately return a naive datetime, each with its reason.
#: A naive producer is only acceptable where the SOURCE carries no offset and
#: inventing one would be a guess.
NAIVE_PRODUCERS: dict[str, str] = {
    "adapters/inbound/justificante/_extract.py::_parse_datetime": (
        "AEAT prints a Europe/Madrid wall-clock time on the justificante with "
        "no offset, so the receipt states no instant; the parsed value feeds "
        "Justificante.presented_at, which is typed datetime for that reason"
    ),
}


def _returns_a_naive_datetime(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if not node.returns or "datetime" not in ast.unparse(node.returns):
        return False
    body = ast.unparse(node)
    if "strptime" not in body:
        return False
    return not any(call in body for call in _AWARENESS_CALLS)


def _naive_producers() -> dict[str, int]:
    found: dict[str, int] = {}
    for path in sorted(_SRC.rglob("*.py")):
        if "tests" in path.relative_to(_SRC).parts or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # a peer's mid-edit file is not this gate's finding
            continue
        relative = path.relative_to(_SRC).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _returns_a_naive_datetime(node):
                found[f"{relative}::{node.name}"] = node.lineno
    return found


def test_every_naive_datetime_producer_is_declared() -> None:
    """A new naive-datetime producer must state why the value has no offset."""
    undeclared = sorted(set(_naive_producers()) - set(NAIVE_PRODUCERS))
    assert not undeclared, (
        "these functions return a naive datetime. If the source genuinely "
        "carries no offset, record it in NAIVE_PRODUCERS with the reason and "
        "keep the receiving field typed datetime rather than UtcInstant; "
        f"otherwise attach the timezone at the parse boundary: {undeclared}"
    )


def test_declared_naive_producers_still_exist() -> None:
    """A producer that became timezone-aware must lose its entry."""
    found = _naive_producers()
    stale = sorted(producer for producer in NAIVE_PRODUCERS if producer not in found)
    assert not stale, (
        "these producers no longer return a naive datetime; drop them from "
        f"NAIVE_PRODUCERS and consider whether the field they feed is now an instant: {stale}"
    )


def test_every_declared_producer_states_a_reason() -> None:
    """The judgement lives in the reason, so an empty one is not an entry."""
    unreasoned = sorted(name for name, reason in NAIVE_PRODUCERS.items() if len(reason.strip()) < 20)
    assert not unreasoned, f"these naive-datetime producers carry no stated reason: {unreasoned}"
