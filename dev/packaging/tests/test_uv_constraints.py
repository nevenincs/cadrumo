"""Tests for the pinned runtime constraint export.

`dev.quality.module_test_reach` listed `dev/packaging/uv_constraints.py` as
unreached. It decides what the Scoop manifest and the MCPB bundle pin at user
install time: left unpinned, a user's install resolves to whatever the index
serves that day rather than the closure the release actually tested.

Every refusal in the module is therefore load-bearing in the same direction. An
export that quietly produced fewer rows, or a row without a version, would ship
an installer that pins less than it claims - and an installer that pins nothing
looks exactly like one that pinned correctly until the day a transitive
dependency changes under a user.

The export runs the real ``uv`` against this repository's own lockfile. That is
the subject: what uv emits for this lock is the closure the installers carry,
and a stand-in would prove something about the stand-in.
"""

from __future__ import annotations

import pathlib

import pytest

from ..._paths import REPO_ROOT
from ..uv_constraints import export_runtime_constraints, render_constraints_file

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def exported() -> tuple[str, ...]:
    """Export once; the subprocess is the expensive part of every case below."""
    return export_runtime_constraints(repo_root=REPO_ROOT)


def test_the_closure_is_not_empty(exported: tuple[str, ...]) -> None:
    """An empty constraints file pins nothing and reads as a successful export."""
    assert exported


def test_every_row_carries_an_exact_version(exported: tuple[str, ...]) -> None:
    """A row without ``==`` is a floating dependency wearing a constraints file."""
    assert all("==" in row for row in exported)


def test_no_row_points_at_a_local_path(exported: tuple[str, ...]) -> None:
    """A path row would pin a filesystem location that does not exist on the user's machine."""
    assert not [row for row in exported if row.startswith(("./", "../", "-e ", "-r ", "file:"))]


def test_the_product_rows_are_excluded(exported: tuple[str, ...]) -> None:
    """They install from bundle-local wheels, so pinning them would fight the installer.

    Only their transitive third-party closure needs pinning, which is what the
    module's ``--no-emit-package`` arguments are for.
    """
    named = {row.split("==", 1)[0].strip().lower() for row in exported}

    assert not named & {"cadrumo", "cadrumo-data-manuals", "cadrumo-data-official"}


def test_the_closure_covers_the_agent_transport_stack(exported: tuple[str, ...]) -> None:
    """One distribution carries both console scripts, so its closure is the whole surface.

    The module's docstring makes this claim specifically - the MCP SDK is
    cadrumo's own requirement, reached by the same export as the CLI's - and an
    export that silently narrowed to the CLI alone would leave the agent server
    unpinned while still producing a plausible file.
    """
    named = {row.split("==", 1)[0].strip().lower() for row in exported}

    assert "mcp" in named


def test_a_missing_lockfile_refuses_rather_than_exporting_nothing(
    tmp_path: pathlib.Path,
) -> None:
    """No lock means no tested closure, and an empty pin set is not the answer."""
    with pytest.raises(SystemExit, match=r"uv\.lock"):
        export_runtime_constraints(repo_root=tmp_path)


def test_the_rendered_file_says_it_is_generated() -> None:
    """A reader opening a pinned file must learn not to hand-edit the versions."""
    rendered = render_constraints_file(("alpha==1.0", "bravo==2.0"))

    assert "do not edit by hand" in rendered


def test_every_rendered_row_is_terminated() -> None:
    """A missing final newline silently joins the last pin to whatever follows it."""
    rendered = render_constraints_file(("alpha==1.0", "bravo==2.0"))

    assert rendered.endswith(chr(10))
    assert [line for line in rendered.splitlines() if not line.startswith("#")] == [
        "alpha==1.0",
        "bravo==2.0",
    ]


def test_rendering_is_deterministic_for_the_same_rows() -> None:
    """The file is committed and read as a diff, so two renders must agree."""
    rows = ("alpha==1.0", "bravo==2.0")

    assert render_constraints_file(rows) == render_constraints_file(rows)


def test_the_uv_floor_is_stated_only_when_it_is_supplied() -> None:
    """An older uv ignores these pins entirely, so the floor is the reader's warning.

    Stating it unconditionally would put a version in the file that no caller
    chose; omitting it when supplied would leave a reader believing any uv
    honours the closure.
    """
    without = render_constraints_file(("alpha==1.0",))
    with_floor = render_constraints_file(("alpha==1.0",), min_uv_version="0.5.0")

    assert "Requires uv >=" not in without
    assert "Requires uv >= 0.5.0" in with_floor
    assert with_floor.endswith("alpha==1.0" + chr(10)), "the floor note displaced a pinned row"
