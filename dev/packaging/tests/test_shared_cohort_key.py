"""The shared cohort is keyed on what its distributions are built from, and nothing else.

The cohort is reused across processes and runs only while its key holds, and
in a shared worktree a key over the whole checkout never held: every peer edit
to the vault, the documentation or a test moved it and forced a rebuild. The
key now comes from each distribution's own build selection, so these proofs
pin both directions: a selected file moves it, an unselected one does not.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.product_identity import PRODUCT_IDENTITY

from ..shared_cohort import cohort_inputs_digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]

_PYPROJECT = """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cadrumo"
version = "0.0.1"

[tool.hatch.build.targets.sdist]
only-include = ["src/cadrumo", "pyproject.toml"]
exclude = ["src/cadrumo/**/tests", "src/cadrumo/**/tests/**"]

[tool.hatch.build.targets.wheel]
packages = ["src/cadrumo"]
exclude = ["src/cadrumo/**/tests", "src/cadrumo/**/tests/**"]

[tool.uv.sources]
"""


def _checkout(root: Path) -> dict[str, Path]:
    """Write a small checkout with the real data companion projects and their corpus."""
    sources = "".join(
        f'{name} = {{ path = "packaging/{name.replace("-", "_")}" }}\n'
        for name in PRODUCT_IDENTITY.companion_distributions
    )
    (root / "pyproject.toml").write_text(_PYPROJECT + sources, encoding="utf-8", newline="\n")
    (root / ".gitignore").write_text("*.scratch\n", encoding="utf-8", newline="\n")
    for name in PRODUCT_IDENTITY.companion_distributions:
        project = f"packaging/{name.replace('-', '_')}"
        shutil.copytree(_REPO_ROOT / project, root / project, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    files = {
        "module": root / "src/cadrumo/module.py",
        "test": root / "src/cadrumo/feature/tests/test_module.py",
        "corpus": root / "src/cadrumo/_data/corpus/aeat_official/document.pdf",
        "vault": root / ".vault/adr/decision.md",
        "docs": root / "docs/index.md",
        "ignored": root / "src/cadrumo/notes.scratch",
    }
    (root / "src/cadrumo/__init__.py").parent.mkdir(parents=True)
    (root / "src/cadrumo/__init__.py").write_text("", encoding="utf-8")
    for path in files.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"original\n")
    return files


@pytest.fixture
def checkout(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    root = tmp_path / "checkout"
    root.mkdir()
    return root, _checkout(root)


@pytest.mark.parametrize("member", ["module", "corpus"])
def test_a_selected_file_moves_the_key(checkout: tuple[Path, dict[str, Path]], member: str) -> None:
    root, files = checkout
    before = cohort_inputs_digest(root)

    files[member].write_bytes(b"revised\n")

    assert cohort_inputs_digest(root) != before


def test_a_new_selected_file_moves_the_key(checkout: tuple[Path, dict[str, Path]]) -> None:
    root, _ = checkout
    before = cohort_inputs_digest(root)

    (root / "src/cadrumo/added.py").write_bytes(b"added\n")

    assert cohort_inputs_digest(root) != before


@pytest.mark.parametrize("member", ["vault", "docs", "test", "ignored"])
def test_an_unselected_file_leaves_the_key(checkout: tuple[Path, dict[str, Path]], member: str) -> None:
    root, files = checkout
    before = cohort_inputs_digest(root)

    files[member].write_bytes(b"revised\n")
    files[member].with_name(f"another{files[member].suffix}").write_bytes(b"added\n")

    assert cohort_inputs_digest(root) == before
