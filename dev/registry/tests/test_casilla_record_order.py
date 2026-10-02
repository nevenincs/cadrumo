"""Casillas hydrate in the order their official form or record design prints them.

Storage reuse states an edition's new boxes over a baseline and places them with
positions counted against the merge. When an edition's baseline changes those
counts shift, and when new boxes are stated without positions they land at the
end, so a box can drift out of its printed place while every proof that compares
an edition with itself still passes. These checks read the order from the
casillas' own printed numbers:

- Modelo 165 numbers each record campo ``tipo<record>.<first>[-<last>]``, so its
  positional casillas follow record, then first position, as the record design
  lays them out.
- Modelo 100 numbers its boxes in the order the declaration prints them, so its
  four-digit boxes ascend in every edition.

Each check is shown biting on an isolated copy of the modelo with one box moved
out of place by an added position.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Sequence
from itertools import pairwise
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RECORD_POSITION: Final = re.compile(r"tipo(\d+)\.(\d+)(?:-\d+)?")
_FOUR_DIGIT_BOX: Final = re.compile(r"\d{4}")

type _Key = tuple[int, ...]
type _Order = Callable[[str, str], _Key | None]


def _modelo_dir(modelo_id: str) -> Path:
    return Path(bundled_path("registry", "aeat", "modelos", modelo_id))


def _record_position(casilla_id: str, number: str) -> _Key | None:
    del casilla_id
    match = _RECORD_POSITION.fullmatch(number)
    return None if match is None else (int(match.group(1)), int(match.group(2)))


def _modelo_100_box(casilla_id: str, number: str) -> _Key | None:
    del number
    return (int(casilla_id),) if _FOUR_DIGIT_BOX.fullmatch(casilla_id) else None


def _out_of_order(modelo: ModeloDefinition, key: _Order) -> list[tuple[str, str, str]]:
    """Every adjacent pair of ordered casillas whose printed order the edition reverses."""
    reversed_pairs: list[tuple[str, str, str]] = []
    for revision in ordered_revisions(modelo):
        keyed = [
            (casilla_key, str(casilla.id))
            for casilla in revision.casillas
            if (casilla_key := key(str(casilla.id), str(casilla.number))) is not None
        ]
        reversed_pairs.extend(
            (str(revision.id), earlier[1], later[1]) for earlier, later in pairwise(keyed) if earlier[0] > later[0]
        )
    return reversed_pairs


def _ordered_ids(modelo: ModeloDefinition, key: _Order, revision_id: str) -> list[str]:
    return [
        str(casilla.id)
        for casilla in modelo.revisions[revision_id].casillas
        if key(str(casilla.id), str(casilla.number)) is not None
    ]


def _with_moved_box(source: Path, destination: Path, revision_id: str, casilla_id: str, position: int) -> Path:
    """A copy of the modelo whose edition moves one box to ``position`` with an added position."""
    copy = shutil.copytree(source, destination / source.name)
    manifest = copy / "revisions" / revision_id / "revision.toml"
    text = manifest.read_text(encoding="utf-8")
    existing = re.compile(
        rf'^\[\[revisions\."{re.escape(revision_id)}"\.casilla_positions\]\]\nid = "{re.escape(casilla_id)}"\n'
        r"position = \d+\n",
        re.MULTILINE,
    )
    text = existing.sub("", text)
    manifest.write_text(
        text.rstrip("\n")
        + f'\n\n[[revisions."{revision_id}".casilla_positions]]\nid = "{casilla_id}"\nposition = {position}\n',
        encoding="utf-8",
        newline="\n",
    )
    return copy


@pytest.mark.parametrize(
    ("modelo_id", "key"),
    [("165", _record_position), ("100", _modelo_100_box)],
)
def test_casillas_hydrate_in_their_printed_order(modelo_id: str, key: _Order) -> None:
    modelo = load_modelo_directory(_modelo_dir(modelo_id))

    assert _ordered_ids(modelo, key, str(ordered_revisions(modelo)[-1].id))
    assert _out_of_order(modelo, key) == []


@pytest.mark.parametrize(
    ("modelo_id", "key", "pick"),
    [
        ("165", _record_position, lambda ids: ids[0]),
        ("100", _modelo_100_box, lambda ids: ids[len(ids) // 2]),
    ],
)
def test_a_box_moved_out_of_its_printed_place_is_detected(
    tmp_path: Path, modelo_id: str, key: _Order, pick: Callable[[Sequence[str]], str]
) -> None:
    modelo = load_modelo_directory(_modelo_dir(modelo_id))
    last = ordered_revisions(modelo)[-1]
    revision_id = str(last.id)
    box = pick(_ordered_ids(modelo, key, revision_id))

    moved = load_modelo_directory(
        _with_moved_box(_modelo_dir(modelo_id), tmp_path, revision_id, box, len(last.casillas) - 1)
    )

    assert [str(casilla.id) for casilla in moved.revisions[revision_id].casillas][-1] == box
    assert any(pair[0] == revision_id for pair in _out_of_order(moved, key))
