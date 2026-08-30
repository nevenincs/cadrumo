"""Static guard: a bucket-event payload value is never a variable-length join.

A payload value is capped (:data:`BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH`) and
the cap is enforced by refusal rather than truncation, so a producer that
joins a collection into one value silently acquires a ceiling on how large
that collection may grow. Past the ceiling the producer cannot record its own
event at all: the write raises before anything is saved.

Six occurrences of that shape have been found in this codebase, each
independently and each after it shipped. This gate moves the discovery to
authoring time. It is deliberately a *shape* check rather than a length
check, because the length is not knowable statically — the defect is joining
an unbounded collection into a bounded slot, whatever today's cardinality
happens to be.

The sanctioned alternatives are a count, a digest, or a durable home of the
detail's own; they are documented on the constant.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....tests import production_ast_items, repo_relative
from ..event import BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH, payload_value_fits

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_HASHING_CALLS = frozenset({"sha256_hex", "content_hash_hex", "blake2b_hex"})

_BOUNDED_CALLS = frozenset(
    {
        # Fixed-width or width-preserving by construction.
        "str",
        "len",
        "int",
        "bool",
        "repr",
        "format",
        # Width-preserving on an already-bounded string.
        "strip",
        "lower",
        "upper",
        # Fixed-width renderings.
        "isoformat",
        "hex",
        # A rendered Decimal is a scalar amount, not a collection. The name
        # follows the canonical formatter, which absorbed the four private
        # copies this entry was originally written against.
        "format_decimal",
        # Digests: one of the sanctioned remedies.
        *_HASHING_CALLS,
        "_transaction_ids_digest",
        "_source_provenance_trace_sha256",
        # Explicitly shortens to the cap; that is its whole purpose.
        "_bounded_payload_reference",
        "_bounded_transport_label",
    }
)
"""Calls whose result cannot outgrow a payload slot.

A payload value produced by any *other* call is flagged: the gate cannot see
inside a helper, and "it returns something small" is precisely the belief
that produced six occurrences of this defect.
"""

_EXEMPT_VALUES_BY_SITE: dict[tuple[str, str], str] = {}
"""Sanctioned unbounded payload values, keyed by ``(file, payload key)``.

An entry asserts that a value the shape check flags is nonetheless
acceptable, and it must carry the reason as its value. A value merely
*believed* small does not qualify — five of the six known occurrences were
believed small. Entries are self-expiring: an exemption that outlives its
site fails :func:`test_every_exemption_names_a_live_site`.
"""


_BUCKET_EVENT_SYMBOLS = frozenset(
    {"BucketEvent", "BucketEventType", "derive_bucket_event_id", "emit_bucket_event", "append_bucket_event"}
)


def _emits_bucket_events(tree: ast.AST) -> bool:
    """Return whether a module builds bucket events at all.

    Scopes the gate to its actual subject. ``payload`` is a common name for
    Sheets rows, LLM telemetry and CLI result bodies, none of which are
    written into the capped bucket-event slot, and none of which this gate
    has any business bounding.
    """
    return any(
        (isinstance(node, ast.Name) and node.id in _BUCKET_EVENT_SYMBOLS)
        or (isinstance(node, ast.Attribute) and node.attr in _BUCKET_EVENT_SYMBOLS)
        or (isinstance(node, ast.alias) and node.name in _BUCKET_EVENT_SYMBOLS)
        for node in ast.walk(tree)
    )


def _payload_dicts(tree: ast.AST) -> list[ast.Dict]:
    """Return every dict literal that reaches a bucket-event payload.

    Two spellings both ship: passed inline as ``payload={...}``, and built
    into a local named ``*payload*`` and passed later. The second form is
    why a keyword-only matcher missed an occurrence.
    """
    if not _emits_bucket_events(tree):
        return []
    dicts: list[ast.Dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "payload" and isinstance(node.value, ast.Dict):
            dicts.append(node.value)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if any("payload" in name for name in names):
                dicts.append(node.value)
    return dicts


def _joined_value_offences(tree: ast.AST) -> list[tuple[str, int]]:
    """Return ``(payload key, line)`` for unbounded values bound to a payload key.

    A value is unbounded when it reaches a ``.join(...)`` that no digest
    wraps, or when it is produced by a call outside :data:`_BOUNDED_CALLS`.
    """
    offences: list[tuple[str, int]] = []
    for payload in _payload_dicts(tree):
        for key, value in zip(payload.keys, payload.values, strict=True):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            if _contains_bare_join(value) or _is_unbounded_call(value):
                offences.append((key.value, getattr(value, "lineno", payload.lineno)))
    return offences


def _is_unbounded_call(value: ast.expr) -> bool:
    """Return whether ``value`` is a call this gate cannot prove bounded."""
    if not isinstance(value, ast.Call):
        return False
    func = value.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
    return name not in _BOUNDED_CALLS


def _contains_bare_join(value: ast.expr) -> bool:
    """Return whether ``value`` reaches a ``.join(...)`` not wrapped in a digest."""
    for node in ast.walk(value):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "join" and not _join_is_hashed(value, node):
            return True
    return False


def _join_is_hashed(root: ast.expr, join_call: ast.Call) -> bool:
    """Return whether ``join_call`` is nested inside a hashing call under ``root``."""
    for node in ast.walk(root):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        if name not in _HASHING_CALLS:
            continue
        if any(inner is join_call for inner in ast.walk(node)):
            return True
    return False


def test_no_production_payload_value_is_unbounded() -> None:
    offences: list[str] = []
    for path, tree in production_ast_items():
        relative = repo_relative(path)
        for payload_key, line in _joined_value_offences(tree):
            if (relative, payload_key) in _EXEMPT_VALUES_BY_SITE:
                continue
            offences.append(f"{relative}:{line} payload key {payload_key!r} is not provably bounded")

    assert not offences, (
        "A bucket-event payload value is capped at "
        f"{BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH} characters and refuses rather than truncates, "
        "so a value that can grow gives its producer a ceiling it cannot record past. "
        "Emit a count, a digest, or give the detail a durable home:\n" + "\n".join(offences)
    )


def test_every_exemption_names_a_live_site() -> None:
    """A stale exemption is a hole; it must not outlive the site it excuses."""
    live_sites = {
        (repo_relative(path), payload_key)
        for path, tree in production_ast_items()
        for payload_key, _ in _joined_value_offences(tree)
    }
    stale = sorted(site for site in _EXEMPT_VALUES_BY_SITE if site not in live_sites)

    assert not stale, f"exemptions naming sites that are no longer flagged: {stale}"


def test_every_exemption_states_a_reason() -> None:
    unreasoned = sorted(site for site, reason in _EXEMPT_VALUES_BY_SITE.items() if not reason.strip())

    assert not unreasoned, f"exemptions without a stated reason: {unreasoned}"


def test_detector_flags_real_offences_and_ignores_the_sanctioned_remedies() -> None:
    """Anti-tautology proof: the detector must be able to fail.

    A shape gate that scans a tree it cannot parse, or whose matcher never
    matches, passes silently and forever. This pins the detector against each
    known offence shape and each sanctioned remedy, so a green run above is
    evidence the surface is clean rather than evidence the detector is dead.
    """

    def emitter(body: str) -> ast.AST:
        # The BucketEvent reference is what scopes the gate to its subject.
        return ast.parse(f"BucketEvent(event_type=BucketEventType.X, {body})")

    joined = emitter('payload={"child_ids": ",".join(child_ids)}')
    helper = emitter('payload={"detail": _encode_diffs(diffs)}')
    assigned = ast.parse('BucketEvent\nevent_payload = {"detail": _encode_diffs(diffs)}')
    counted = emitter('payload={"child_count": str(len(child_ids))}')
    digested = emitter('payload={"trace": sha256_hex("\\n".join(ids).encode("utf-8"))}')
    stamped = emitter('payload={"written_at": moment.isoformat()}')
    constant = emitter('payload={"modelo": "100"}')

    assert [key for key, _ in _joined_value_offences(joined)] == ["child_ids"]
    assert [key for key, _ in _joined_value_offences(helper)] == ["detail"]
    # The assigned form is the spelling a keyword-only matcher missed.
    assert [key for key, _ in _joined_value_offences(assigned)] == ["detail"]
    assert _joined_value_offences(counted) == []
    assert _joined_value_offences(digested) == []
    assert _joined_value_offences(stamped) == []
    assert _joined_value_offences(constant) == []


def test_detector_ignores_payloads_that_are_not_bucket_events() -> None:
    """Scoping proof: a Sheets or CLI ``payload`` is not this gate's subject."""
    unrelated = ast.parse('render(payload={"calendar": build_calendar(rows)})')

    assert _joined_value_offences(unrelated) == []


def test_detector_scans_a_non_empty_production_surface() -> None:
    """A gate that inspects nothing cannot fail; pin that it inspects something."""
    items = production_ast_items()

    assert len(items) > 100, f"production AST surface implausibly small: {len(items)}"
    assert any(Path(path).name == "event.py" for path, _ in items)


def test_payload_value_fits_answers_the_bound_without_building_an_event() -> None:
    assert payload_value_fits("")
    assert payload_value_fits("x" * BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH)
    assert not payload_value_fits("x" * (BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH + 1))
    assert payload_value_fits("  " + "x" * BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH + "  ")
