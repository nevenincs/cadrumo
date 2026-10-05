"""The native contract carries the runtime exit-reason table from its Python owner."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from cadrumo.application.runtime.contracts import (
    RESERVED_RUNTIME_EXIT_CODES,
    RuntimeExitReason,
    RuntimeReservedExitCodes,
)
from dev._paths import REPO_ROOT
from dev.packaging.native import runtime_exit_reasons
from dev.packaging.native.generate import generate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REASON = re.compile(r'RuntimeExitReason \{ name: "([a-z_]+)", code: (\d+) \}')
_RESERVED = re.compile(r'RuntimeReservedExitCodes \{ owner: "([a-z_]+)", first: (\d+), last: (\d+) \}')
_CONSTANT = re.compile(r"pub const RUNTIME_EXIT_([A-Z_]+): u32 = (\d+);")


def test_generated_contract_projects_every_exit_reason_and_reservation(tmp_path: Path) -> None:
    generate(REPO_ROOT, tmp_path)
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    contract = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8"))

    reasons = [(reason.name.lower(), reason.value) for reason in RuntimeExitReason]
    reserved = [(item.owner, item.first, item.last) for item in RESERVED_RUNTIME_EXIT_CODES]
    assert [(name, int(code)) for name, code in _REASON.findall(generated)] == reasons
    assert [(owner, int(first), int(last)) for owner, first, last in _RESERVED.findall(generated)] == reserved
    assert [(name, int(code)) for name, code in _CONSTANT.findall(generated)] == [
        (reason.name, reason.value) for reason in RuntimeExitReason
    ]
    assert contract["runtime_exit"] == {
        "reasons": [{"name": name, "code": code} for name, code in reasons],
        "reserved": [{"owner": owner, "first": first, "last": last} for owner, first, last in reserved],
    }


@pytest.mark.parametrize(
    "planted",
    [
        pytest.param(RuntimeReservedExitCodes("planted_overlap", 70, 70), id="reason-inside-reserved-range"),
        pytest.param(RuntimeReservedExitCodes("planted_inverted", 9, 4), id="inverted-range"),
        pytest.param(RuntimeReservedExitCodes("Planted Owner", 5, 5), id="owner-not-a-token"),
        pytest.param(RuntimeReservedExitCodes("planted_wide", 5, 0x1_0000_0000), id="beyond-unsigned-32"),
    ],
)
def test_generator_refuses_a_table_that_breaks_the_reservation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, planted: RuntimeReservedExitCodes
) -> None:
    monkeypatch.setattr(runtime_exit_reasons, "RESERVED_RUNTIME_EXIT_CODES", (*RESERVED_RUNTIME_EXIT_CODES, planted))
    with pytest.raises(ValueError, match=r"(?i)reserved|range|token"):
        generate(REPO_ROOT, tmp_path)
    assert not (tmp_path / "contract.rs").exists()
