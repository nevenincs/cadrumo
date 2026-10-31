"""Fast distribution-boundary contract: hatchling's own file selection, without a build.

The real ``uv build`` gates (``dev/packaging/tests/test_wheel_content_boundary.py``
and ``dev/packaging/tests/test_wheel_bundles_corpus_and_registry.py``) take
minutes and run in the release lane. This module keeps the boundary in every
lane at the cost of a directory walk: it asks hatchling's real wheel and sdist
builders which files the declaration in ``pyproject.toml`` selects and checks
that selection. Build hooks do not run here, so the authority payload a hook
adds at build time stays with the release-lane gates.

The isolated-fixture cases prove the check has teeth: a project carrying this
repository's exact wheel declaration selects none of the planted test or corpus
files, and the same project with one exclude dropped selects them and fails.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest
from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder

from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CORPUS_PREFIX = "cadrumo/_data/corpus/"
_CORPUS_BINARY_SUFFIXES = (".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip")
_AUTHORED_REGISTRY_PREFIX = "cadrumo/_data/registry/aeat/"
_REQUIRED_WHEEL_MEMBERS = (
    "cadrumo/py.typed",
    "cadrumo/core/external_constants.toml",
    "cadrumo_client/contracts/navigation.toml",
)
# The registry payload is the published authority, which a build hook adds;
# the release-lane build gates own it.
_REQUIRED_DATA_ROOTS = ("corpus", "terminology")


def _wheel_declaration(root: Path) -> dict[str, object]:
    document = parse_toml((root / "pyproject.toml").read_text(encoding="utf-8"))
    declaration = document["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert isinstance(declaration, dict)
    fields: dict[str, object] = {}
    for key, value in declaration.items():
        assert isinstance(key, str)
        fields[key] = value
    return fields


def _selected(builder: WheelBuilder | SdistBuilder) -> frozenset[str]:
    return frozenset(
        PurePosixPath(*Path(item.distribution_path).parts).as_posix() for item in builder.recurse_included_files()
    )


def _wheel_selection(root: Path) -> frozenset[str]:
    return _selected(WheelBuilder(str(root)))


def _boundary_violations(members: frozenset[str], packages: tuple[str, ...]) -> list[str]:
    """Return every selected wheel member the distribution boundary forbids, with the reason."""

    roots = {Path(package).name for package in packages}
    violations: list[str] = []
    for member in sorted(members):
        parts = PurePosixPath(member).parts
        if parts[0] not in roots:
            violations.append(f"{member}: outside the declared product packages")
        if "tests" in parts or parts[-1] == "conftest.py":
            violations.append(f"{member}: test module or fixture")
        if member.startswith(_CORPUS_PREFIX) and member.lower().endswith(_CORPUS_BINARY_SUFFIXES):
            violations.append(f"{member}: corpus source binary")
        if member.startswith(_AUTHORED_REGISTRY_PREFIX):
            violations.append(f"{member}: registry authoring input")
        if member.endswith(".lock"):
            violations.append(f"{member}: lock sidecar")
    return violations


def _declared_strings(root: Path, key: str) -> list[str]:
    values = _wheel_declaration(root)[key]
    assert isinstance(values, list) and values, key
    return [str(value) for value in values]


def _declared_packages(root: Path) -> tuple[str, ...]:
    return tuple(_declared_strings(root, "packages"))


@pytest.fixture(scope="module")
def declared_wheel_members() -> frozenset[str]:
    """The live declaration's wheel selection; a read-only walk of the checkout."""

    return _wheel_selection(REPO_ROOT)


def test_the_declared_wheel_selection_holds_the_distribution_boundary(declared_wheel_members: frozenset[str]) -> None:
    members = declared_wheel_members

    assert len(members) > 1000, len(members)
    assert _boundary_violations(members, _declared_packages(REPO_ROOT)) == []


def test_the_declared_wheel_selection_keeps_the_required_payload(declared_wheel_members: frozenset[str]) -> None:
    members = declared_wheel_members

    assert [member for member in _REQUIRED_WHEEL_MEMBERS if member not in members] == []
    for data_root in _REQUIRED_DATA_ROOTS:
        assert any(member.startswith(f"cadrumo/_data/{data_root}/") for member in members), data_root
    corpus_text = [
        member for member in members if member.startswith(_CORPUS_PREFIX) and member.endswith(".extracted.md")
    ]
    assert corpus_text, "the corpus binary exclude also removed the derived extracted text"


def test_the_declared_sdist_selection_ships_no_development_tree() -> None:
    members = _selected(SdistBuilder(str(REPO_ROOT)))

    assert "pyproject.toml" in members
    assert "packaging/authority/hatch_build.py" in members
    offenders = sorted(
        member
        for member in members
        if PurePosixPath(member).parts[0] in {".vault", ".vaultspec", "native", "docs", "tests"}
        or (
            member.startswith("dev/")
            and member not in {"dev/__init__.py", "dev/packaging/__init__.py", "dev/packaging/google_oauth.py"}
        )
    )
    assert offenders == []


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _toml_strings(values: list[str]) -> str:
    return "[" + ", ".join(f'"{value}"' for value in values) + "]"


def _isolated_project(root: Path, *, dropped_excludes: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Write a project carrying this repository's wheel declaration, minus *dropped_excludes*.

    Plants one ordinary module, one owner-local test module, one conftest, one
    corpus source binary beside its extracted text, and returns the declared packages.
    """

    packages = _declared_strings(REPO_ROOT, "packages")
    declared_excludes = _declared_strings(REPO_ROOT, "exclude")
    for pattern in dropped_excludes:
        assert pattern in declared_excludes, pattern
    exclude = [pattern for pattern in declared_excludes if pattern not in dropped_excludes]
    include = _declared_strings(REPO_ROOT, "include")
    _write(
        root / "pyproject.toml",
        "[project]\n"
        'name = "cadrumo"\n'
        'version = "0.0.0"\n\n'
        "[tool.hatch.build.targets.wheel]\n"
        f"packages = {_toml_strings(packages)}\n"
        f"exclude = {_toml_strings(exclude)}\n"
        f"include = {_toml_strings(include)}\n",
    )
    for package in packages:
        _write(root / package / "__init__.py")
    _write(root / "src/cadrumo/feature/module.py", "VALUE = 1\n")
    _write(root / "src/cadrumo/feature/tests/test_module.py", "def test_value() -> None:\n    pass\n")
    _write(root / "src/cadrumo/feature/conftest.py")
    _write(root / "src/cadrumo/_data/corpus/manuals/renta/source.pdf", "%PDF-1.7\n")
    _write(root / "src/cadrumo/_data/corpus/manuals/renta/source.pdf.extracted.md", "# text\n")
    return tuple(packages)


def test_an_isolated_project_with_the_declared_excludes_selects_no_planted_violation(tmp_path: Path) -> None:
    packages = _isolated_project(tmp_path)
    members = _wheel_selection(tmp_path)

    assert "cadrumo/feature/module.py" in members
    assert "cadrumo/_data/corpus/manuals/renta/source.pdf.extracted.md" in members
    assert _boundary_violations(members, packages) == []


@pytest.mark.parametrize(
    ("dropped", "leaked"),
    [
        (
            ("src/cadrumo/**/tests", "src/cadrumo/**/tests/**"),
            "cadrumo/feature/tests/test_module.py: test module or fixture",
        ),
        (("src/cadrumo/**/conftest.py",), "cadrumo/feature/conftest.py: test module or fixture"),
        (("src/cadrumo/_data/corpus/**/*.pdf",), "cadrumo/_data/corpus/manuals/renta/source.pdf: corpus source binary"),
    ],
    ids=["tests-exclude", "conftest-exclude", "corpus-pdf-exclude"],
)
def test_dropping_one_declared_exclude_is_detected(tmp_path: Path, dropped: tuple[str, ...], leaked: str) -> None:
    packages = _isolated_project(tmp_path, dropped_excludes=dropped)

    assert _boundary_violations(_wheel_selection(tmp_path), packages) == [leaked]
