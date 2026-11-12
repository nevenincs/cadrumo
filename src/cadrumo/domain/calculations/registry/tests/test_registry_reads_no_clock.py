"""The calculation registry never reads the clock to decide what a fact says.

A registry read takes its date from the caller. When the caller holds none, a
vocabulary read answers from the support envelope and a fact read refuses; the
date the program runs is never a substitute, so a result cannot change with it.
This gate scans every production module of the registry package for a call to
the clock. The modules listed in the baseline still read it and belong to other
units of work; the baseline only shrinks, so an entry fails once its module
reads the clock fewer times than listed.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT: Final = Path(__file__).resolve().parents[1]

_CLOCK_FUNCTIONS: Final = frozenset({"today_madrid"})
"""Clock readers imported from the core clock module and called by bare name."""

_CLOCK_METHODS: Final = frozenset(
    {("date", "today"), ("datetime", "now"), ("datetime", "utcnow"), ("datetime", "today")}
)
"""Wall-clock constructors of the standard library called on their class."""

_CORE_CLOCK_MODULE_SUFFIX: Final = "core.time.clock"

_BASELINE: Final[dict[str, int]] = {
    "iva_regime_vocabulary.py": 2,
    "m303_schema_vocabulary.py": 2,
    "tax_id_format.py": 2,
    "tax_identity_admission.py": 1,
}
"""Clock calls each still-owning module makes, keyed by path under the registry package."""


def clock_calls(source: str) -> int:
    """Count the clock reads in one module's source.

    A read is a call to a name imported from the core clock module (its
    ``today_madrid`` or ``now``, under any alias), a call through the clock
    module itself, or a standard-library wall-clock constructor such as
    ``date.today()`` or ``datetime.now()``.
    """
    tree = ast.parse(source)
    clock_names: set[str] = set()
    clock_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(_CORE_CLOCK_MODULE_SUFFIX):
            clock_names.update(
                alias.asname or alias.name for alias in node.names if alias.name in _CLOCK_FUNCTIONS | {"now"}
            )
        elif isinstance(node, ast.ImportFrom) and (node.module or "").endswith("core.time"):
            clock_modules.update(alias.asname or alias.name for alias in node.names if alias.name == "clock")
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Name) and function.id in clock_names:
            count += 1
        elif isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            owner, attribute = function.value.id, function.attr
            if (owner, attribute) in _CLOCK_METHODS or (
                owner in clock_modules and attribute in _CLOCK_FUNCTIONS | {"now"}
            ):
                count += 1
    return count


def registry_clock_calls(root: Path) -> Counter[str]:
    """Count the clock reads of every production module under ``root``, keyed by relative path."""
    calls: Counter[str] = Counter()
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if "tests" in relative.parts:
            continue
        found = clock_calls(path.read_text(encoding="utf-8"))
        if found:
            calls[relative.as_posix()] = found
    return calls


def baseline_violations(calls: Counter[str], baseline: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    """Return the modules reading the clock beyond ``baseline`` and the entries it lists too generously."""
    exceeding = {module: count for module, count in calls.items() if count > baseline.get(module, 0)}
    stale = {module: listed for module, listed in baseline.items() if calls[module] < listed}
    return exceeding, stale


def test_no_registry_module_reads_the_clock_beyond_the_shrinking_baseline() -> None:
    exceeding, _stale = baseline_violations(registry_clock_calls(_REGISTRY_ROOT), _BASELINE)

    assert not exceeding, f"registry modules read the clock; take the date from the caller instead: {exceeding}"


def test_the_baseline_names_only_modules_that_still_read_the_clock_as_often() -> None:
    _exceeding, stale = baseline_violations(registry_clock_calls(_REGISTRY_ROOT), _BASELINE)

    assert not stale, f"lower or remove these baseline entries (listed counts): {stale}"


@pytest.mark.parametrize(
    "module",
    [
        "concepto_ingreso.py",
        "entity_type.py",
        "eu_member_state_catalogue.py",
        "irpf_regimes.py",
        "renta_codes_catalogue.py",
        "facts/string_mapping.py",
        "gasto_capital_inmobiliario.py",
    ],
)
def test_the_vocabulary_cores_are_not_baselined(module: str) -> None:
    assert module not in _BASELINE
    assert (_REGISTRY_ROOT / module).is_file()


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from ....core.time.clock import today_madrid\ndef f(d):\n    return d or today_madrid()\n", 1),
        ("from cadrumo.core.time.clock import today_madrid as t\nx = t()\n", 1),
        ("from ....core.time.clock import now\nx = now().date()\n", 1),
        ("from ....core.time import clock\nx = clock.today_madrid()\n", 1),
        ("from datetime import date, datetime\nx = date.today()\ny = datetime.now()\n", 2),
        ("from datetime import date\ndef f(d: date) -> date:\n    return d\n", 0),
        ("from ....core.time.clock import today_madrid\n", 0),
    ],
)
def test_the_scan_counts_a_representative_clock_read(source: str, expected: int) -> None:
    assert clock_calls(source) == expected


def test_the_gate_reports_an_unlisted_reader_and_a_stale_entry_in_an_isolated_tree(tmp_path: Path) -> None:
    (tmp_path / "facts").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "facts" / "offending_catalogue.py").write_text(
        "from .....core.time.clock import today_madrid\n"
        "def resolve(effective_date=None):\n"
        "    return effective_date or today_madrid()\n",
        encoding="utf-8",
    )
    (tmp_path / "listed.py").write_text("from datetime import date\nx = date.today()\n", encoding="utf-8")
    (tmp_path / "tests" / "test_reader.py").write_text(
        "from datetime import date\nx = date.today()\n", encoding="utf-8"
    )

    exceeding, stale = baseline_violations(registry_clock_calls(tmp_path), {"listed.py": 2, "retired.py": 1})

    assert exceeding == {"facts/offending_catalogue.py": 1}
    assert stale == {"listed.py": 2, "retired.py": 1}
