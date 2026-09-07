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
import tomllib

import pytest

from ..._paths import REPO_ROOT
from ..uv_constraints import (
    export_runtime_constraints,
    local_product_packages,
    render_constraints_file,
)

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

    The excluded names are read from the same owner the export passes to uv
    rather than written out again here. A second hand-kept copy of the list
    agrees with the first exactly until one of them drifts, and then this case
    reports clean over the drift it exists to catch.
    """
    named = {row.split("==", 1)[0].strip().lower() for row in exported}
    local = {name.lower() for name in local_product_packages(repo_root=REPO_ROOT)}

    assert local, "no local package was excluded, so the absence below is over an empty set"
    assert not named & local, (
        f"a bundle-local product wheel was pinned as an index requirement: {sorted(named & local)}"
    )


def test_the_closure_covers_the_agent_transport_stack(exported: tuple[str, ...]) -> None:
    """One distribution carries both console scripts, so its closure is the whole surface.

    The module's docstring makes this claim specifically - the MCP SDK is
    cadrumo's own requirement, reached by the same export as the CLI's - and an
    export that silently narrowed to the CLI alone would leave the agent server
    unpinned while still producing a plausible file.
    """
    named = {row.split("==", 1)[0].strip().lower() for row in exported}

    assert "mcp" in named


def test_the_excluded_names_are_the_lockfile_s_own_non_registry_packages() -> None:
    """The exclusions must be derived, because uv accepts a wrong one in silence.

    ``uv export --no-emit-package`` does not verify that the name it is given
    exists: a nonexistent name changes nothing, and a name that IS a genuine
    third-party dependency drops precisely that row with no error and no
    cascade. Neither shape announces itself, so the only defence is to stop
    writing the names down. This asserts the derivation reads the lockfile's
    own marker rather than any list an author maintains.
    """
    document = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages = [entry for entry in document.get("package", ()) if isinstance(entry, dict)]
    expected = sorted(str(entry["name"]) for entry in packages if "registry" not in (entry.get("source") or {}))

    assert len(packages) > 50, f"only {len(packages)} locked packages; the comparison below spans almost nothing"
    assert expected, "the lockfile records no local package, so this proves nothing about the derivation"
    assert list(local_product_packages(repo_root=REPO_ROOT)) == expected


def test_a_lockfile_with_no_local_package_refuses(tmp_path: pathlib.Path) -> None:
    """Teeth: an empty exclusion set pins the product's own bundle-local wheels.

    That file installs, and it installs the wrong thing -- the wheels the
    bundle already carries, fetched from an index instead. Returning an empty
    tuple here would read as "nothing to exclude" rather than as a failure.
    """
    (tmp_path / "uv.lock").write_text(
        "[[package]]"
        + chr(10)
        + 'name = "anyio"'
        + chr(10)
        + 'source = { registry = "https://pypi.org/simple" }'
        + chr(10),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="no workspace-local package"):
        local_product_packages(repo_root=tmp_path)


def test_a_missing_lockfile_refuses_the_derivation_too(tmp_path: pathlib.Path) -> None:
    """An unreadable lockfile must not silently yield an empty exclusion set."""
    with pytest.raises(SystemExit, match=r"uv\.lock"):
        local_product_packages(repo_root=tmp_path)


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
