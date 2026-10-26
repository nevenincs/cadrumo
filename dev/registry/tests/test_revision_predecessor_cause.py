"""The closed classification token on a grounded "no predecessor exists" root.

A root's ``reason`` prose states the grounding in full, and a census of the
corpus cannot read prose. ``cause`` is the machine-readable classification of
the same fact. The properties that must hold: a root carrying a valid cause
loads typed and serialises back into the authored spelling, a root omitting it
still loads because the field is optional and its dump is unchanged, and an
unrecognised token is refused at the typed boundary rather than carried as
free text for a later consumer to interpret.

Every test drives the real directory loader over a real on-disk TOML tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.revision_contracts import (
    DeclaredPredecessorField,
    NoPredecessor,
    NoPredecessorCause,
)

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_modelo as _shared_write_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_ID = "2025"
_LEGAL_REF = "ley-58-2003:art-29"
_SOURCE_REF = "aeat-manual"
_REASON = "Stated in full: this edition is one of several parallel scheme variants, not a step in a sequence."

_CASILLA_FRAGMENT = f"""
[[revisions."{_REVISION_ID}".casillas]]
id = "0001"
number = "1"
section = ["liquidacion"]
continuidad_id = "casilla-0001"
legal_refs = ["{_LEGAL_REF}"]
source_refs = ["{_SOURCE_REF}"]
""".lstrip()


def _none_declaration(*, cause: str | None) -> str:
    """Author the root's ``none`` table, with or without the optional classification."""
    cause_entry = "" if cause is None else f', cause = "{cause}"'
    return (
        f'predecessor = {{ none = {{ reason = "{_REASON}", '
        f'legal_refs = ["{_LEGAL_REF}"], source_refs = ["{_SOURCE_REF}"]{cause_entry} }} }}\n'
    )


def _write_root_modelo(root: Path, *, cause: str | None) -> Path:
    return _shared_write_modelo(
        root,
        casilla_fragment=_CASILLA_FRAGMENT,
        revision_id=_REVISION_ID,
        manifest_extra=_none_declaration(cause=cause),
    )


def _expected_none_payload(*, cause: str | None) -> dict[str, object]:
    payload: dict[str, object] = {
        "reason": _REASON,
        "legal_refs": [_LEGAL_REF],
        "source_refs": [_SOURCE_REF],
    }
    if cause is not None:
        payload["cause"] = cause
    return payload


@pytest.mark.parametrize("cause", sorted(NoPredecessorCause))
def test_every_declared_cause_loads_typed_and_round_trips(tmp_path: Path, cause: NoPredecessorCause) -> None:
    """Each member of the closed set survives load, dump, and rehydration unchanged.

    Parametrising over the enum itself rather than a copied list is what keeps
    a member added later from shipping untested.
    """
    modelo_dir = _write_root_modelo(tmp_path / cause.value, cause=cause.value)

    revision = load_modelo_directory(modelo_dir).revisions[_REVISION_ID]

    declaration = revision.predecessor
    assert isinstance(declaration, NoPredecessor)
    assert declaration.cause is cause
    assert declaration == NoPredecessor(
        reason=_REASON,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
        cause=cause,
    )

    dumped = revision.model_dump(mode="json")["predecessor"]
    assert dumped == {"none": _expected_none_payload(cause=cause.value)}
    assert json.loads(revision.model_dump_json())["predecessor"] == dumped

    # The serialised spelling hydrates back into the identical declaration.
    adapter = TypeAdapter(DeclaredPredecessorField)
    assert adapter.validate_python(revision.model_dump(mode="python")["predecessor"]) == declaration


def test_a_root_without_a_cause_still_loads_and_dumps_exactly_as_before(tmp_path: Path) -> None:
    """The field is optional: an unclassified root loads, and its dump carries no ``cause`` key.

    Omission is what makes the classification additive over the shipped corpus
    rather than a break that every existing root must be flipped through first.
    """
    revision = load_modelo_directory(_write_root_modelo(tmp_path, cause=None)).revisions[_REVISION_ID]

    declaration = revision.predecessor
    assert isinstance(declaration, NoPredecessor)
    assert declaration.cause is None
    assert revision.model_dump(mode="json")["predecessor"] == {"none": _expected_none_payload(cause=None)}
    assert "cause" not in revision.model_dump(mode="json")["predecessor"]["none"]


def test_an_unrecognised_cause_is_refused_and_a_declared_one_loads(tmp_path: Path) -> None:
    """Detector tooth, both directions on one tree: the bad token reds the load, a real one restores it.

    The classification is closed. A token outside the set names no grounded
    cause, so it is refused at the typed boundary instead of being carried for
    a census to discover later.
    """
    modelo_dir = _write_root_modelo(tmp_path, cause="superseded_because_i_said_so")

    with pytest.raises(RegistryLoadError, match="is not a valid NoPredecessorCause"):
        load_modelo_directory(modelo_dir)

    manifest = modelo_dir / "revisions" / _REVISION_ID / "revision.toml"
    preamble = manifest.read_text(encoding="utf-8").split("\npredecessor", 1)[0].rstrip("\n") + "\n"
    manifest.write_text(
        preamble + _none_declaration(cause=NoPredecessorCause.parallel_scheme_variants.value),
        encoding="utf-8",
        newline="\n",
    )

    restored = load_modelo_directory(modelo_dir).revisions[_REVISION_ID].predecessor
    assert isinstance(restored, NoPredecessor)
    assert restored.cause is NoPredecessorCause.parallel_scheme_variants


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("Parallel_Scheme_Variants", id="wrong-case"),
        pytest.param("parallel scheme variants", id="spaces-for-underscores"),
        pytest.param("row_order", id="retired-spelling"),
        pytest.param("", id="empty"),
    ],
)
def test_a_near_miss_cause_spelling_is_refused_rather_than_normalised(tmp_path: Path, token: str) -> None:
    """One authored spelling per cause; the boundary normalises nothing into a member."""
    with pytest.raises(RegistryLoadError, match="is not a valid NoPredecessorCause"):
        load_modelo_directory(_write_root_modelo(tmp_path, cause=token))


def test_a_cause_on_anything_but_a_none_table_is_refused(tmp_path: Path) -> None:
    """The classification belongs to the grounded root, not to a named predecessor edge."""
    modelo_dir = _shared_write_modelo(
        tmp_path,
        casilla_fragment=_CASILLA_FRAGMENT,
        revision_id=_REVISION_ID,
        manifest_extra='predecessor = { revision_id = "2024", cause = "lower_grade" }\n',
    )

    with pytest.raises(RegistryLoadError, match="predecessor must be the revision id of a sibling edition"):
        load_modelo_directory(modelo_dir)
