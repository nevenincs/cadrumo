"""Guard the temporary homes of the Modelo 036 activity type.

The intended owner is a per-activity profile slot; transactions and assets should
then refer to that slot. Until that model exists, a transaction declares the type
on its row. An asset with no acquisition row must declare it on the asset instead;
a linked purchase must not do so and reads the transaction. Both are temporary
copies of an activity declaration and must migrate when the profile slot lands.

This census also records transport and provider annotations: neither is a
persisted authority, but silently excluding arbitrary classes would let a new
profile row evade the tripwire.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

# Each entry has a distinct role. New occurrences require an ownership review;
# they must not simply be added here to make the test pass.
_EXPECTED_ANNOTATIONS: Final[frozenset[tuple[str, str, str]]] = frozenset(
    {
        ("domain/transactions/models.py", "Transaction", "tipo_actividad"),
        ("domain/renta/actividad_asset/lifecycle.py", "ActivityAssetRevision", "declared_activity"),
        (
            "application/actividad_asset/activity_asset_read_models.py",
            "ActivityAssetFormOptionsView",
            "declared_activities",
        ),
        ("application/actividad_asset/operation_dtos.py", "ActivityAssetRevisionSnapshot", "declared_activity"),
        ("application/actividad_asset/operations.py", "ActivityAssetRegisterAuthority", "agrarian_activities"),
    }
)

_REMEDY: Final[str] = (
    "Review the activity type's ownership. Once a per-activity profile slot stores "
    "the value, transactions and off-ledger assets must refer to that slot instead "
    "of copying its type. Repoint their readers and remove their temporary declarations; "
    "do not add another persisted authority to this census."
)


def _activity_annotations(tree: ast.Module, module: str) -> set[tuple[str, str, str]]:
    """Find class fields mentioning the type, including imported aliases and qualified names."""
    aliases = {"TipoActividad"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            aliases.update(alias.asname or alias.name for alias in node.names if alias.name == "TipoActividad")

    found: set[tuple[str, str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                continue
            if any(
                (isinstance(part, ast.Name) and part.id in aliases)
                or (isinstance(part, ast.Attribute) and part.attr == "TipoActividad")
                for part in ast.walk(statement.annotation)
            ):
                found.add((module, node.name, statement.target.id))
    return found


def _all_activity_annotations() -> set[tuple[str, str, str]]:
    found: set[tuple[str, str, str]] = set()
    for path in scan_directory(_SOURCE_ROOT, pattern="*.py", recursive=True):
        relative = path.relative_to(_SOURCE_ROOT).as_posix()
        if "/tests/" in f"/{relative}" or relative.startswith("tests/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found.update(_activity_annotations(tree, relative))
    return found


def test_activity_type_annotations_have_reviewed_ownership() -> None:
    annotations = _all_activity_annotations()

    assert annotations == _EXPECTED_ANNOTATIONS, f"{_REMEDY}\n\nFound: {sorted(annotations)!r}"


@pytest.mark.parametrize(
    "source",
    [
        "class ActivitySlot:\n    activity: TipoActividad\n",
        "from somewhere import TipoActividad as ActivityType\nclass ActivitySlot:\n    activity: ActivityType\n",
        "class ActivitySlot:\n    activity: vocabulary.TipoActividad\n",
    ],
)
def test_the_probe_detects_a_new_profile_home(source: str) -> None:
    assert _activity_annotations(ast.parse(source), "profile.py") == {("profile.py", "ActivitySlot", "activity")}
