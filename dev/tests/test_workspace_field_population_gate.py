"""Every declared Workspace field must be supplied by some production construction.

A field with a default can be omitted at every construction site and still
validate, so the payload advertises a capability it never carries and no test
fails: nothing asserted a value nobody promised. This gate asserts that no such
field exists, and proves on an isolated fixture that it can still detect one.

There is no allowed set, and adding one would be the defect this gate exists to
find. A field nothing supplies is either filled at its producer or deleted with
its consumers; recording it here as expected converts a gap into a fixture and
makes the gate green over exactly the state it was written to report.

The assertion is one-directional: filling a field, deleting it, or teaching the
scan to see a construction it was missing can never fail this gate. A gate that
goes red when a defect is FIXED trains its readers to edit the gate instead of
the code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.quality.workspace_field_population_scan import scan_unfilled_workspace_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_ROOT = _ROOT / "src" / "cadrumo"
_MODELS_MODULE = _SOURCE_ROOT / "application" / "modelo" / "workspace_models.py"


def _unfilled(source_root: Path, models_module: Path) -> set[str]:
    return {str(finding) for finding in scan_unfilled_workspace_fields(source_root, models_module)}


def test_the_scan_finds_the_declaring_module_at_all() -> None:
    """A moved or renamed models module would empty every assertion below."""
    assert _MODELS_MODULE.is_file(), (
        f"{_MODELS_MODULE} is not where this gate expects it, so the scan is walking nothing and "
        "its green means only that it found no declarations"
    )


def test_no_declared_workspace_field_is_left_unsupplied() -> None:
    """A declared field no production construction supplies fails here."""
    unfilled = sorted(_unfilled(_SOURCE_ROOT, _MODELS_MODULE))

    assert not unfilled, (
        "these Workspace fields are declared with a default and supplied by no construction site, "
        "so the payload advertises them and never carries them:\n"
        + "\n".join(f"  {entry}" for entry in unfilled)
        + "\nFill each one at its producer, or delete it with its consumers if nothing can produce it."
    )


def test_the_scan_reports_a_field_no_caller_supplies(tmp_path: Path) -> None:
    """Teeth, over a fixture tree rather than the live one.

    Driven over a temporary module so the proof does not depend on the live
    inventory happening to contain an example, and so it keeps working while
    the live tree carries none -- which is when a gate most needs to still be
    able to fail.
    """
    models = tmp_path / "workspace_models.py"
    models.write_text(
        "from typing import Literal\n"
        "class _WorkspaceModel:\n"
        "    pass\n"
        "class Thing(_WorkspaceModel):\n"
        "    kind: Literal['thing'] = 'thing'\n"
        "    supplied: str | None = None\n"
        "    never: str | None = None\n"
        "    required: str\n",
        encoding="utf-8",
    )
    caller = tmp_path / "caller.py"
    caller.write_text("Thing(required='x', supplied='y')\n", encoding="utf-8")
    assert caller.exists()

    found = _unfilled(tmp_path, models)

    assert found == {"Thing.never"}, (
        "the scan must report only the optional field nobody supplies: a supplied one is not a "
        "finding, a required one cannot be omitted, and a Literal discriminator is filled by its "
        f"own default -- got {sorted(found)}"
    )


def test_a_generic_factory_supplies_through_its_type_parameter(tmp_path: Path) -> None:
    """A model built through a ``type[...]`` parameter supplies its fields.

    The paginator every bounded facet routes through is exactly this shape, and
    a scan blind to it reports three filled pagination fields as unfilled. The
    fixture proves both directions at once: the field the factory passes is not
    a finding, and the one it omits still is -- so following the annotation has
    not simply silenced the model.
    """
    models = tmp_path / "workspace_models.py"
    models.write_text(
        "class Page:\n    supplied: str | None = None\n    never: str | None = None\n",
        encoding="utf-8",
    )
    (tmp_path / "factory.py").write_text(
        "def build(page_type: type[Page[str]], value: str) -> Page:\n    return page_type(supplied=value)\n",
        encoding="utf-8",
    )

    found = _unfilled(tmp_path, models)

    assert found == {"Page.never"}, (
        "a field supplied through a type parameter is supplied, and one the factory omits is still "
        f"a finding -- got {sorted(found)}"
    )


def test_a_file_being_rewritten_does_not_abort_the_scan(tmp_path: Path) -> None:
    """Another lane's half-written file must not decide this gate's verdict.

    The tree is edited concurrently, so a scan that raises on the first
    unparseable file reports nothing about the rest -- and reports it as a
    crash rather than as a finding.
    """
    models = tmp_path / "workspace_models.py"
    models.write_text("class Thing:\n    never: str | None = None\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def unfinished(:\n", encoding="utf-8")

    found = _unfilled(tmp_path, models)

    assert found == {"Thing.never"}


def test_a_file_the_walk_listed_but_cannot_read_does_not_abort_the_scan(tmp_path: Path) -> None:
    """A file lost between the walk and the read is the same non-evidence.

    The scan reads construction sites from across the tree, so an unreadable
    one can only make a filled field look unfilled -- an over-report the module
    accepts. Crashing instead costs every finding the run had left to make.
    """
    models = tmp_path / "workspace_models.py"
    models.write_text("class Thing:\n    never: str | None = None\n", encoding="utf-8")
    # A directory named like a module: the walk lists it and the read refuses it.
    (tmp_path / "vanished.py").mkdir()

    found = _unfilled(tmp_path, models)

    assert found == {"Thing.never"}
