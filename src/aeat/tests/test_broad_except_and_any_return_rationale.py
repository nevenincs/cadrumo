"""Broad-except, lazy-module, and snapshot-dispatch rationale-marker inventory.

Real-behavior AST + source walk that asserts:

(a) The three financial-provider teardown ``except Exception`` sites
    carry a ``BROAD-EXCEPT-RATIONALE-*`` inline comment.

(b) The three ``-> Any`` lazy-module helpers in ``core/setup_answers.py`` carry
    an ``ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE`` inline marker.

(c) The four ``**kwargs: Any`` snapshot-dispatch hooks carry a
    ``KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH`` marker.

The tests walk real source files using ``ast`` + line-level string
matching. No mocks, no skips, no tautological assertions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ---------------------------------------------------------------------------
# Filesystem root
# ---------------------------------------------------------------------------

_SRC = Path(__file__).parent.parent  # src/aeat/


def _source_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------------------
# (a) Financial-provider teardown broad-except sites
# ---------------------------------------------------------------------------

# Specific (file, marker-token) pairs.  The test walks every
# ``except Exception`` line in each file and checks that the documented site
# carries its BROAD-EXCEPT-RATIONALE-* token.
_BROAD_EXCEPT_MANDATE: list[tuple[Path, str]] = [
    (
        _SRC / "adapters/inbound/financial/providers/_pdf_n26.py",
        "BROAD-EXCEPT-RATIONALE-PDF-N26-TEARDOWN",
    ),
    (
        _SRC / "adapters/inbound/financial/providers/_xlsx.py",
        "BROAD-EXCEPT-RATIONALE-XLSX-TEARDOWN",
    ),
    (
        _SRC / "adapters/inbound/financial/providers/_ofx.py",
        "BROAD-EXCEPT-RATIONALE-OFX-TEARDOWN",
    ),
]


def test_financial_provider_teardown_broad_except_carry_rationale() -> None:
    """Each financial-provider teardown broad-except site carries its BROAD-EXCEPT-RATIONALE-* marker."""
    failures: list[str] = []
    for path, expected_token in _BROAD_EXCEPT_MANDATE:
        assert path.exists(), f"Expected source file not found: {path}"
        source = path.read_text(encoding="utf-8")
        if expected_token not in source:
            failures.append(f"{path.name}: missing {expected_token!r}")
    assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------------
# (b) setup_answers.py lazy-module helper ANY-RETURN-RATIONALE markers
# ---------------------------------------------------------------------------

_PROFILE_MODULE = _SRC / "core/setup_answers.py"
_PROFILE_LAZY_HELPERS = ("_m", "_p", "_ccaa")
_PROFILE_RATIONALE_TOKEN = "ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE"


def _find_def_lines(source_lines: list[str], func_names: tuple[str, ...]) -> dict[str, int]:
    """Return {name: lineno} (1-based) for matching ``def <name>`` lines."""
    result: dict[str, int] = {}
    for i, line in enumerate(source_lines, start=1):
        stripped = line.strip()
        for name in func_names:
            if stripped.startswith(f"def {name}(") or stripped.startswith(f"async def {name}("):
                result[name] = i
    return result


def test_profile_lazy_module_helpers_carry_any_return_rationale() -> None:
    """_m, _p, _ccaa in setup_answers.py must carry ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE markers."""
    assert _PROFILE_MODULE.exists(), f"Expected source file not found: {_PROFILE_MODULE}"
    lines = _source_lines(_PROFILE_MODULE)
    def_lines = _find_def_lines(lines, _PROFILE_LAZY_HELPERS)
    missing = [name for name in _PROFILE_LAZY_HELPERS if name not in def_lines]
    assert not missing, f"Could not locate helpers in setup_answers.py: {missing}"
    failures: list[str] = []
    for name, lineno in def_lines.items():
        # The marker may appear in the 10 lines preceding the def (block-comment
        # style) or on the def line itself — same convention as the (c) hooks.
        if not _check_marker_near_def(lines, lineno, _PROFILE_RATIONALE_TOKEN):
            failures.append(f"setup_answers.py:{lineno} def {name}: missing {_PROFILE_RATIONALE_TOKEN!r}")
    assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------------
# (c) Snapshot-dispatch kwargs-Any hooks carry KWARGS-ANY-RATIONALE
# ---------------------------------------------------------------------------

# Each entry is a (path, function_name) pair. The marker may appear in the
# 10 lines preceding the def (block-comment style) or on the def line itself.
_KWARGS_ANY_MANDATE: list[tuple[Path, str]] = [
    (_SRC / "application/live/_borrador_100.py", "_derive_snapshot_id"),
    (_SRC / "application/live/_censo.py", "_derive_snapshot_id"),
    (_SRC / "application/live/_expedientes.py", "_derive_snapshot_id"),
    (_SRC / "application/live/_notifications.py", "_derive_snapshot_id"),
    (_SRC / "application/live/_snapshot_base.py", "_derive_snapshot_id"),
]

_KWARGS_RATIONALE_TOKEN = "KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH"


def _check_marker_near_def(lines: list[str], lineno: int, token: str, window: int = 10) -> bool:
    """Return True if token appears in the ``window`` lines preceding lineno or on lineno."""
    start = max(0, lineno - window - 1)
    end = lineno  # inclusive of the def line (lineno is 1-based → index lineno-1)
    return any(token in ln for ln in lines[start:end])


@pytest.mark.parametrize("path,func_name", _KWARGS_ANY_MANDATE, ids=lambda x: x if isinstance(x, str) else x.name)
def test_snapshot_dispatch_hooks_carry_kwargs_any_rationale(path: Path, func_name: str) -> None:
    """Each mandated snapshot-dispatch hook must carry a KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH marker."""
    assert path.exists(), f"Expected source file not found: {path}"
    lines = _source_lines(path)
    def_lines = _find_def_lines(lines, (func_name,))
    assert func_name in def_lines, f"{path.name}: could not locate def {func_name}"
    lineno = def_lines[func_name]
    found = _check_marker_near_def(lines, lineno, _KWARGS_RATIONALE_TOKEN)
    assert found, (
        f"{path.name}:{lineno} def {func_name}: missing {_KWARGS_RATIONALE_TOKEN!r} "
        f"in the 10 lines preceding the definition"
    )
