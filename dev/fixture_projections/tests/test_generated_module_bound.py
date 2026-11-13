"""Every generator of committed TypeScript takes the module bound from its producer and refuses before it writes.

The bound has one definition, ``dev.quality.typescript_module_size``. A driver
that held the number itself would be a second definition free to drift, and a
driver that wrote or compared before refusing would leave an oversized module
on disk or report it merely stale.
"""

from __future__ import annotations

import re

import pytest

from dev.quality.typescript_module_size import MAX_PHYSICAL_LINES

from ...paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SCRIPTS = REPO_ROOT / "native" / "desktop" / "frontend" / "scripts"
#: Each generator of committed TypeScript, and the write or comparison its refusal must precede.
_DRIVERS = {
    "modelo-fixtures.mjs": ("if (values.check)", "rmSync(resolve(directory, name))", "console.log(`wrote ${path}`)"),
    "ledger-contract.mjs": ("if (values.check)", "writeFileSync(contract"),
    "profile-contract.mjs": ("if (values.check)", "writeFileSync(contract"),
    "calendar-contract.mjs": ("if (values.check)", "writeFileSync(contract"),
    "ledger-operation-contract.mjs": ("if (values.check)", "writeFileSync(resolve(frontend"),
}
_SOURCES = (
    *_DRIVERS,
    "generated-module-bound.mjs",
    "modelo_fixtures.py",
    "ledger_contract.py",
    "profile_contract.py",
    "calendar_contract.py",
    "ledger_operation_contract.py",
)
_REFUSAL = "refuseOversizedModules("


def _holds_the_bound(text: str) -> bool:
    """Whether ``text`` states the bound as a number of its own."""
    return re.search(rf"(?<![\w.]){MAX_PHYSICAL_LINES}(?![\w.])", text) is not None


@pytest.mark.parametrize("name", _SOURCES)
def test_no_generator_states_the_bound_itself(name: str) -> None:
    assert not _holds_the_bound((_SCRIPTS / name).read_text(encoding="utf-8"))


def test_the_literal_check_finds_a_stated_bound() -> None:
    assert _holds_the_bound(f"const MODULE_LINE_LIMIT = {MAX_PHYSICAL_LINES};")
    assert _holds_the_bound(f"if lines > {MAX_PHYSICAL_LINES}:")
    assert not _holds_the_bound(f"const timeout = {MAX_PHYSICAL_LINES}0;")
    assert not _holds_the_bound("refuseOversizedModules(modules, bound, remedy);")


@pytest.mark.parametrize("name", sorted(_DRIVERS))
def test_each_driver_refuses_before_it_compares_or_writes(name: str) -> None:
    text = (_SCRIPTS / name).read_text(encoding="utf-8")
    refusal = text.find(_REFUSAL)

    assert refusal != -1, f"{name} never calls the shared refusal"
    assert 'from "./generated-module-bound.mjs"' in text
    for later in _DRIVERS[name]:
        assert refusal < text.index(later), f"{name} reaches {later!r} before it refuses"
