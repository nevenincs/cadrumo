"""Same-size, same-mtime schema edits must invalidate the loader cache."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from .._loader import load_modelo_file

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

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
number = "{number}"
section = ["section"]
input_kind = "manual"
continuidad_id = "cont_01"
legal_refs = ["ley-35-2006:art-1"]
source_refs = ["aeat-source"]
"""


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
    modelo_path.write_text(_MODELO_TEXT.format(number="01"), encoding="utf-8")
    loaded_a = load_modelo_file(modelo_path)
    assert loaded_a.revisions["2019-y-siguientes"].casillas[0].number == "01"

    _rewrite_pinning_stat(modelo_path, _MODELO_TEXT.format(number="02"))

    loaded_b = load_modelo_file(modelo_path)
    assert loaded_b.revisions["2019-y-siguientes"].casillas[0].number == "02"
