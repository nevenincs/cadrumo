"""Every catalogue message a notice shows passes the notice's own validator in every locale.

A notice refuses a message naming a raw command, so such wording crashes the
command that raises the notice, and only when that notice fires.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.core.json_contract import Notice, NoticeSeverity
from dev._paths import REPO_ROOT

from ..chrome_projection import _catalogue_leaves

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE_ROOT = REPO_ROOT / "src"
_LOCALES_DIR = _SOURCE_ROOT / "cadrumo" / "locales"
_LOCALES = tuple(sorted(path.name for path in _LOCALES_DIR.iterdir() if path.is_dir()))


def _notice_message_keys(source: str) -> Iterator[str]:
    """Yield string constants a ``Notice(message=...)`` reads, directly or through a local name."""
    tree = ast.parse(source)
    assigned = {
        node.targets[0].id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or getattr(node.func, "id", None) != "Notice":
            continue
        for keyword in node.keywords:
            if keyword.arg != "message":
                continue
            value = (
                assigned.get(keyword.value.id, keyword.value) if isinstance(keyword.value, ast.Name) else keyword.value
            )
            for constant in ast.walk(value):
                if isinstance(constant, ast.Constant) and isinstance(constant.value, str):
                    yield constant.value


def _product_sources() -> Iterator[Path]:
    for path in _SOURCE_ROOT.rglob("*.py"):
        if "tests" not in path.parts and "__pycache__" not in path.parts:
            yield path


def test_the_scan_reads_a_direct_message_and_one_through_a_local_name() -> None:
    source = 'def f():\n    text = tr("a.named")\n    Notice(message=text)\n    Notice(message=tr("a.direct"))\n'
    assert set(_notice_message_keys(source)) == {"a.named", "a.direct"}


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_notice_message_names_a_raw_command(locale: str) -> None:
    leaves = _catalogue_leaves(_LOCALES_DIR, locale)
    keys = {
        key
        for path in _product_sources()
        if "Notice(" in (source := path.read_text(encoding="utf-8"))
        for key in _notice_message_keys(source)
        if key in leaves
    }

    assert keys
    for key in sorted(keys):
        Notice(severity=NoticeSeverity.INFO, code="catalogue.check", message=str(leaves[key]))
