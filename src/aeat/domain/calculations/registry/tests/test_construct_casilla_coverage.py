"""Schema-independent construct→casilla legal-ref coverage gate.

This gate parses the registry TOML tree DIRECTLY (it does NOT instantiate
``ModeloRevision`` or load the binding/aggregation schema), so it keeps verifying
the construct-closure invariant even while a peer's in-flight ``BindingAggregationOp``
refactor has the full ``load_registry_tree`` path temporarily unable to load. It is the
companion to ``test_casilla_legal_refs_resolve`` (which checks resolution) and a faithful
re-implementation of the casilla-member branch of
``_validate_constructs.validate_construct_closure``:

    for every construct, for every casilla listed DIRECTLY in the construct's
    ``casillas`` member list, that casilla's ``legal_refs`` MUST be a subset of the
    construct's ``legal_refs``.

Formula / binding / parameter members carry their OWN legal_refs and are out of scope
here (they are unaffected by a casilla legal_ref edit). This gate is what makes the
legal-grounding tail correction safe without a registry load: a re-grounding that would
break a direct-member casilla's construct coverage fails this gate loudly.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_QUOTED = re.compile(r'"([^"]+)"')
_ID_RE = re.compile(r'^id = "([^"]+)"', re.M)


def _array(text: str, key: str) -> list[str]:
    """Extract the quoted string members of a ``key = [ ... ]`` TOML array (multi-line aware)."""
    m = re.search(rf"{re.escape(key)} = (\[.*?\])", text, re.S)
    return _QUOTED.findall(m.group(1)) if m else []


def _legal_refs(text: str) -> list[str]:
    m = re.search(r"^legal_refs = (\[.*?\])", text, re.M | re.S)
    return _QUOTED.findall(m.group(1)) if m else []


def _casilla_legal_refs_by_revision() -> dict[tuple[str, str], dict[str, set[str]]]:
    """Map (modelo, revision) -> {casilla_id -> set(legal_refs)} parsed from casilla TOMLs."""
    out: dict[tuple[str, str], dict[str, set[str]]] = {}
    modelos_root = bundled_path("registry", "aeat", "modelos")
    for f in modelos_root.glob("*/revisions/*/casillas/*.toml"):
        modelo = f.parents[3].name
        revision = f.parents[1].name
        text = f.read_text(encoding="utf-8", errors="replace")
        idm = _ID_RE.search(text)
        if idm is None:
            continue
        out.setdefault((modelo, revision), {})[idm.group(1)] = set(_legal_refs(text))
    return out


def _constructs_by_revision() -> dict[tuple[str, str], list[tuple[str, set[str], list[str]]]]:
    """Map (modelo, revision) -> [(construct_id, construct_legal_refs, casilla_members)]."""
    out: dict[tuple[str, str], list[tuple[str, set[str], list[str]]]] = {}
    modelos_root = bundled_path("registry", "aeat", "modelos")
    for f in modelos_root.glob("*/revisions/*/constructs/*.toml"):
        modelo = f.parents[3].name
        revision = f.parents[1].name
        text = f.read_text(encoding="utf-8", errors="replace")
        idm = _ID_RE.search(text)
        cid = idm.group(1) if idm else f.stem
        out.setdefault((modelo, revision), []).append(
            (cid, set(_legal_refs(text)), _array(text, "casillas")),
        )
    return out


def test_every_direct_member_casilla_legal_refs_covered_by_its_construct() -> None:
    """A casilla listed directly in a construct must have legal_refs ⊆ the construct's.

    Faithful schema-independent replica of the casilla branch of
    ``validate_construct_closure``: ``member.legal_refs.difference(construct.legal_refs)``
    must be empty for every casilla member.
    """
    casilla_refs = _casilla_legal_refs_by_revision()
    constructs = _constructs_by_revision()
    violations: list[str] = []
    checked = 0
    checked_m100 = 0
    for key, construct_list in constructs.items():
        cas_map = casilla_refs.get(key, {})
        for cid, c_refs, members in construct_list:
            for member_id in members:
                member_refs = cas_map.get(member_id)
                if member_refs is None:
                    # Member id this schema-independent parser cannot map to a casilla TOML
                    # (composite / row-group ids in some informativa modelos, e.g. ``moneda.saldo``).
                    # The real loader resolves those; coverage for them is out of this gate's scope.
                    continue
                checked += 1
                if key[0] == "100":
                    checked_m100 += 1
                missing = sorted(member_refs.difference(c_refs))
                if missing:
                    violations.append(
                        f"{key[0]}/{key[1]}: construct {cid!r} does not include legal refs "
                        f"{missing!r} required by casilla {member_id!r}",
                    )
    assert not violations, "construct→casilla legal-ref coverage violations:\n" + "\n".join(violations)
    # Guard against a vacuous pass: the M100 direct-member casillas (e.g. the anexo-c
    # base-liquidable-negativa box that drove the V19/V20 coherent-sweep lesson) MUST be checked.
    assert checked_m100 >= 1, f"expected to check ≥1 M100 direct construct-member casilla, checked {checked_m100}"
    assert checked >= 1, "construct-coverage gate checked zero casilla members — parser regression"
