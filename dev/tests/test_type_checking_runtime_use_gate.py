"""Gate: no shipped module evaluates a TYPE_CHECKING-only name at runtime.

This defect is invisible to every static tool the repository runs. Under the
guard the name IS bound as far as a type checker is concerned, so ruff and mypy
both read the module as correct; the interpreter disagrees the first time the
line executes. It therefore survives precisely as long as the path goes
unexercised, which is why it reached production in an executor that no test had
ever run.

See Also:
    :mod:`dev.quality.type_checking_runtime_use_scan`
        The scanner, built on the canonical guard-detection helper.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..quality.type_checking_runtime_use_scan import (
    scan_paths_for_type_only_runtime_uses,
    scan_type_only_runtime_uses,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT = Path(__file__).resolve().parents[2]
_CADRUMO = _ROOT / "src/cadrumo"


def _shipped_modules() -> tuple[Path, ...]:
    return tuple(sorted(_CADRUMO.rglob("*.py")))


def test_the_scan_sees_a_real_corpus() -> None:
    """Anti-vacuity: the sweep below is empty over an empty module set."""
    modules = _shipped_modules()

    assert len(modules) > 1000, f"only {len(modules)} modules scanned; the gate would be vacuous"


def test_no_shipped_module_evaluates_a_guard_only_name_at_runtime() -> None:
    """A guard-only name reached at runtime raises NameError when the line runs."""
    found = scan_paths_for_type_only_runtime_uses(_shipped_modules())

    assert not found, "\n".join(f"  {use}" for use in found)


def test_the_scanner_fires_on_the_defect_shape_it_exists_for() -> None:
    """Anti-tautology: prove the scanner reports rather than reporting silence.

    The source below is the exact shape that shipped in the modelo export
    executor -- a sibling of the same module imported at runtime, the
    constructed type imported only under the guard.
    """
    source = "\n".join(
        (
            "from __future__ import annotations",
            "from typing import TYPE_CHECKING",
            "from ._export import export_modelo_revision",
            "if TYPE_CHECKING:",
            "    from ._export import ModeloExportCommand",
            "def run(payload):",
            "    return export_modelo_revision(ModeloExportCommand(path=payload))",
        )
    )

    found = scan_type_only_runtime_uses(Path("probe.py"), source=source)

    assert [use.name for use in found] == ["ModeloExportCommand"]


def test_a_guard_only_name_used_solely_in_annotations_is_not_reported() -> None:
    """The guard exists for exactly this, so flagging it would fire on correct code."""
    source = "\n".join(
        (
            "from __future__ import annotations",
            "from typing import TYPE_CHECKING",
            "if TYPE_CHECKING:",
            "    from ._report import VerificationReport",
            "def run(report: VerificationReport) -> VerificationReport:",
            "    return report",
            "value: VerificationReport | None = None",
        )
    )

    assert not scan_type_only_runtime_uses(Path("probe.py"), source=source)


def test_a_deferred_type_alias_and_type_parameter_bound_are_not_reported() -> None:
    """PEP 695 defers both, so both are legitimate homes for a guard-only name.

    Pinned because treating either as a runtime evaluation produced eleven
    false positives against this tree on the scanner's first run -- every one
    of them correct code.
    """
    source = "\n".join(
        (
            "from __future__ import annotations",
            "from typing import TYPE_CHECKING",
            "if TYPE_CHECKING:",
            "    from collections.abc import Callable",
            "    from ._ids import CasillaId",
            "    from ._cmp import SupportsAllComparisons",
            "type Resolver = Callable[[], CasillaId]",
            "def reject[Key: SupportsAllComparisons](items: dict[Key, int]) -> None:",
            "    return None",
        )
    )

    assert not scan_type_only_runtime_uses(Path("probe.py"), source=source)


def test_a_name_bound_at_runtime_as_well_as_under_the_guard_is_not_reported() -> None:
    """The runtime binding wins, so the name resolves and there is no defect."""
    source = "\n".join(
        (
            "from __future__ import annotations",
            "from typing import TYPE_CHECKING",
            "from ._export import ModeloExportCommand",
            "if TYPE_CHECKING:",
            "    from ._export import ModeloExportCommand",
            "def run():",
            "    return ModeloExportCommand()",
        )
    )

    assert not scan_type_only_runtime_uses(Path("probe.py"), source=source)
