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


def test_an_unparsable_module_is_announced_rather_than_read_as_clean(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An empty result reads exactly like a module with no guard-only misuse.

    What goes unreported is a name imported only under ``if TYPE_CHECKING:``
    and evaluated at runtime - a NameError waiting in shipped code. The skip
    stays, because one half-written file must not cost the sweep, but it is no
    longer silent.
    """
    broken = tmp_path / "broken.py"
    broken.write_text("def (:" + chr(10), encoding="utf-8")

    assert scan_type_only_runtime_uses(broken) == []
    assert "does not parse and was not scanned" in capsys.readouterr().err


def test_an_undecodable_module_is_not_silently_mangled(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The read was lenient, so a bad byte was dropped and the scan analysed
    text that is not what the file contains - a finding could be invented or
    lost with nothing said either way.
    """
    undecodable = tmp_path / "undecodable.py"
    undecodable.write_bytes(bytes([0xFF, 0xFE, 0x00]) + b"VALUE = 1" + bytes([10]))

    assert scan_type_only_runtime_uses(undecodable) == []
    assert "not valid UTF-8" in capsys.readouterr().err


def test_a_module_the_walk_listed_but_cannot_read_is_announced(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The third way a read fails, and the only one that used to crash.

    The scan already skips a module it cannot parse and one it cannot decode,
    announcing both, because the tree is edited while the sweep runs and one
    half-written file must not cost the thousands that were read. A file the
    walk listed and the read cannot reach is the same situation arriving
    through a third door, and it took the whole sweep down with it -- losing
    every finding from every module already scanned, which is the outcome the
    other two skips exist to prevent.

    The fixture is a DIRECTORY named ``*.py``: a walk lists it and a read
    refuses it, with no symlink privilege required.
    """
    unreadable = tmp_path / "unreadable.py"
    unreadable.mkdir()

    assert scan_type_only_runtime_uses(unreadable) == []
    assert "could not be read and was not scanned" in capsys.readouterr().err


def test_a_clean_module_announces_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A notice that fires on every run would carry no information."""
    sound = tmp_path / "sound.py"
    sound.write_text("VALUE = 1" + chr(10), encoding="utf-8")

    assert scan_type_only_runtime_uses(sound) == []
    assert capsys.readouterr().err == ""
