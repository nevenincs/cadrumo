"""A Modelo 036 tipo de actividad is STORED in exactly one place.

This gate exists because the shipped placement contradicts the accepted design
for this fact, and the contradiction is harmless today and harmful later.

The activity TYPE is a fact AEAT records per activity slot, so copying its
VALUE onto every transaction row "duplicates an upstream declaration and will
drift from it". The accepted shape puts the value on a per-activity profile row
and has the transaction carry a *reference* to the slot instead.

What shipped is the value, on the row. That was defensible — no per-activity
profile row exists in the tree yet, and waiting would have blocked the Modelo
131 agrarian aggregation behind unbuilt infrastructure. It is not defensible
indefinitely.

Today nothing is duplicated, because there is no upstream declaration to duplicate.
The moment a per-activity profile row lands carrying its own tipo de actividad,
``Transaction.tipo_actividad`` becomes a second home for one fact, and the
predicted drift starts. Nothing else would notice: both fields would be
individually correct and would diverge only for a taxpayer who edited one.

So this gate fails at exactly that moment, and tells the author what to do. It is a
tripwire on a dated hazard, not a style rule.

The check is structural rather than name-based on purpose. The future row model has
no agreed name — keying on one would be a guess that silently stops matching.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

#: The one sanctioned stored home, as ``module suffix -> (class, attribute)``.
_SANCTIONED_HOME: Final[tuple[str, str, str]] = (
    "domain/transactions/models.py",
    "Transaction",
    "tipo_actividad",
)

_REMEDY: Final[str] = (
    "A Modelo 036 tipo de actividad is now stored in more than one place. The value "
    "belongs to the per-activity profile row and the transaction should carry a "
    "REFERENCE to the activity slot, not a copy of its type. Collapse "
    "Transaction.tipo_actividad to that reference and repoint its readers "
    "(_renta_income_ledger._project_income_onto_casilla and "
    "_tipo_actividad_partitions.irpf_activity_kind_for) rather than adding this "
    "second home to the allowlist."
)


def _annotation_names(node: ast.expr | None) -> set[str]:
    """Return every bare name mentioned in an annotation expression."""
    if node is None:
        return set()
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def _stored_tipo_actividad_fields() -> list[tuple[str, str, str]]:
    """Return every ``(module, class, attribute)`` declaring a stored TipoActividad.

    A *stored* field is a class-body annotated assignment whose annotation mentions
    ``TipoActividad`` — the pydantic/dataclass field shape. Function-local variables,
    parameters and return annotations are not homes for the fact and are ignored.
    """
    found: list[tuple[str, str, str]] = []
    for path in scan_directory(_SOURCE_ROOT, pattern="*.py", recursive=True):
        relative = path.relative_to(_SOURCE_ROOT).as_posix()
        if "/tests/" in f"/{relative}" or relative.startswith("tests/"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):  # pragma: no cover - unreadable peer WIP
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue
                if "TipoActividad" in _annotation_names(statement.annotation):
                    found.append((relative, node.name, statement.target.id))
    return found


def test_the_activity_type_has_exactly_one_stored_home() -> None:
    """Exactly one persisted field carries a Modelo 036 activity code."""
    homes = _stored_tipo_actividad_fields()

    assert homes == [_SANCTIONED_HOME], f"{_REMEDY}\n\nFound: {homes!r}"


def test_the_probe_would_notice_a_second_home() -> None:
    """Anti-vacuity: the scan actually finds the field it is guarding.

    A scan that silently matched nothing — a moved source root, a renamed
    annotation, a walk that never reaches class bodies — would satisfy the
    single-home assertion perfectly while guarding nothing. This makes that
    failure loud instead.
    """
    homes = _stored_tipo_actividad_fields()

    assert _SANCTIONED_HOME in homes, (
        "the probe did not find Transaction.tipo_actividad; it is no longer "
        "measuring anything and the single-home assertion above is vacuous"
    )
