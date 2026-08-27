"""Same-size, same-mtime schema edits must invalidate the loader cache.

The casilla number is substituted with :meth:`str.replace` on an explicit
sentinel rather than with :meth:`str.format`. TOML inline tables are written
with braces, and ``str.format`` reads ``{ year_from = 2019, ... }`` as a
replacement field: the template below raised ``KeyError`` at the first write
and the test failed during setup, so the invalidation property it guards was
never once executed. Escaping the braces would work but leaves the trap armed
for whoever adds the next inline table, and the doubled braces would no longer
be the TOML anyone reads. A sentinel has no such failure mode.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from .._loader_internals import load_modelo_file

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CASILLA_NUMBER_SENTINEL = "@@CASILLA_NUMBER@@"

_MODELO_TEXT = """
[modelo]
id = "130"
tax_domain = "irpf"
cadence = "quarterly"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-35-2006:art-1"]
source_refs = ["aeat-source"]

[revisions.2019-y-siguientes]
valid_from = 2019-01-01
period_selector = { year_from = 2019, periods = ["1T", "2T", "3T", "4T"] }
legal_refs = ["ley-35-2006:art-1"]
source_refs = ["aeat-source"]

[[revisions.2019-y-siguientes.casillas]]
id = "01"
number = "@@CASILLA_NUMBER@@"
section = ["section"]
input_kind = "manual"
continuidad_id = "cont_01"
legal_refs = ["ley-35-2006:art-1"]
source_refs = ["aeat-source"]
"""


def _modelo_text(number: str) -> str:
    """Return the modelo TOML with the casilla number substituted.

    Both call sites pass a two-character number, which is what keeps the
    rewrite the same SIZE as the original -- the collision the test needs.
    """
    if len(number) != len("01"):
        raise ValueError("the colliding rewrite requires a two-character casilla number")
    return _MODELO_TEXT.replace(_CASILLA_NUMBER_SENTINEL, number)


def _rewrite_pinning_stat(path: Path, new_text: str) -> None:
    before = path.stat()
    path.write_text(new_text, encoding="utf-8")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = path.stat()
    assert after.st_size == before.st_size
    assert after.st_mtime_ns == before.st_mtime_ns


def test_single_file_modelo_same_size_same_mtime_edit_invalidates(tmp_path: Path) -> None:
    """A colliding rewrite must serve the new language-neutral field value."""
    modelo_path = tmp_path / "130.toml"
    modelo_path.write_text(_modelo_text("01"), encoding="utf-8")
    loaded_a = load_modelo_file(modelo_path)
    assert loaded_a.revisions["2019-y-siguientes"].casillas[0].number == "01"

    _rewrite_pinning_stat(modelo_path, _modelo_text("02"))

    loaded_b = load_modelo_file(modelo_path)
    assert loaded_b.revisions["2019-y-siguientes"].casillas[0].number == "02"
