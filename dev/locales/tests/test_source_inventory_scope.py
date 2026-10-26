"""The translation source inventory counts production modules and nothing the shared test policy excludes."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import pytest

from dev.locales.signal_source_inventory import inventory_translation_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE = "from cadrumo.core.i18n.render import tr\n\ntr('cli.app.example.title')\n"


def _literal_calls(path: Path, root: Path) -> int:
    counts: Counter[str] = Counter()
    inventory_translation_source(path, root, counts, Counter[str](), [], defaultdict(list), [])
    return counts["literal_tr_calls"]


def _write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_SOURCE, encoding="utf-8")
    return path


def test_a_production_module_is_inventoried(tmp_path: Path) -> None:
    assert _literal_calls(_write(tmp_path / "pkg" / "render_view.py"), tmp_path) == 1


@pytest.mark.parametrize(
    "relative",
    [
        "pkg/tests/render_view.py",
        "pkg/test_render_view.py",
        "pkg/_test_render_view.py",
        "pkg/conftest.py",
    ],
)
def test_every_module_the_shared_policy_calls_a_test_is_skipped(tmp_path: Path, relative: str) -> None:
    assert _literal_calls(_write(tmp_path / relative), tmp_path) == 0


def test_a_checkout_that_lives_under_a_directory_named_tests_is_still_inventoried(tmp_path: Path) -> None:
    root = tmp_path / "tests" / "checkout"

    assert _literal_calls(_write(root / "pkg" / "render_view.py"), root) == 1
