"""A revision refuses two continuity evolutions declared under one id.

Continuity evolutions are a chain family: they are not merged by identity like
the keyed families, and the strict-continuity validator only compares the
(continuidad_id, from, to) boundary an evolution covers. Two evolutions of
different chains could therefore share an id and load cleanly. These tests load
an isolated scratch modelo through the canonical loader to prove the revision
boundary now refuses that shape and still accepts distinct ids.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CHAINS = (("0848", "pendiente-ejercicio"), ("1965", "pendiente-ejercicio-anterior"))


def _revision_text(revision: str, *, evolution_ids: tuple[str, str] | None = None) -> str:
    year = int(revision)
    blocks = [
        f"""[revisions."{revision}"]
valid_from = {year}-01-01
period_selector = {{ years = [{year}], periods = ["0A"] }}
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""",
    ]
    for number, continuidad_id in _CHAINS:
        blocks.append(
            f"""[[revisions."{revision}".casillas]]
id = "{number}"
number = "{number}"
section = ["test"]
data_type = "money"
continuidad_id = "{continuidad_id}"
semantic_role = "{continuidad_id.replace("-", "_")}"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""",
        )
    if evolution_ids is None:
        return "\n".join(blocks)
    for evolution_id, (_number, continuidad_id) in zip(evolution_ids, _CHAINS, strict=True):
        blocks.append(
            f"""[[revisions."{revision}".casilla_continuidad_evolutions]]
id = "{evolution_id}"
continuidad_id = "{continuidad_id}"
from_revision = "{year - 1}"
to_revision = "{revision}"
evolution_kind = "label_evolved"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""",
        )
    return "\n".join(blocks)


def _write_revision(revisions_dir: Path, revision: str, text: str) -> None:
    """Write the manifest and one fragment per family, the loader's directory grammar."""
    target = revisions_dir / revision
    target.mkdir()
    manifest, *members = re.split(r"(?=\[\[revisions\.)", text)
    (target / "revision.toml").write_text(manifest, encoding="utf-8", newline="\n")
    for family in ("casillas", "casilla_continuidad_evolutions"):
        header = f'[[revisions."{revision}".{family}]]'
        body = "".join(block for block in members if block.startswith(header))
        if body:
            (target / family).mkdir()
            (target / family / "0001-declarations.toml").write_text(body, encoding="utf-8", newline="\n")


def _scratch_modelo(root: Path, *, evolution_ids: tuple[str, str]) -> Path:
    modelo = root / "999"
    revisions_dir = modelo / "revisions"
    revisions_dir.mkdir(parents=True)
    (modelo / "manifest.toml").write_text(
        """[modelo]
id = "999"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""",
        encoding="utf-8",
        newline="\n",
    )
    _write_revision(revisions_dir, "2024", _revision_text("2024"))
    _write_revision(revisions_dir, "2025", _revision_text("2025", evolution_ids=evolution_ids))
    return modelo


def test_distinct_evolution_ids_load_with_both_chains_declared(tmp_path: Path) -> None:
    """The normal path: one evolution per chain, each under its own id."""
    evolution_ids = ("m999-0848-2024-2025-label-evolved", "m999-1965-2024-2025-label-evolved")
    modelo = load_modelo_directory(_scratch_modelo(tmp_path, evolution_ids=evolution_ids))

    declared = {
        str(evolution.id): str(evolution.continuidad_id)
        for evolution in modelo.revisions["2025"].casilla_continuidad_evolutions
    }
    assert declared == {
        "m999-0848-2024-2025-label-evolved": "pendiente-ejercicio",
        "m999-1965-2024-2025-label-evolved": "pendiente-ejercicio-anterior",
    }


def test_two_chains_sharing_one_evolution_id_are_refused(tmp_path: Path) -> None:
    """The defect: different continuity chains whose evolutions carry the same id."""
    shared = "m999-1965-2024-2025-label-evolved"

    with pytest.raises(RegistryLoadError, match=rf"casilla_continuidad_evolutions declares duplicate ids: '{shared}'"):
        load_modelo_directory(_scratch_modelo(tmp_path, evolution_ids=(shared, shared)))
