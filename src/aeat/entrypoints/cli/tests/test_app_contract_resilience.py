"""Resilience gate for the ``aeat app contract`` capability manifest.

The operator rules mandate reading ``aeat app contract`` FIRST — it is the
grounding entry point an LLM operator consults before doing anything else. A
single broken result-payload module (typically an unrelated in-flight refactor
that trips a transitive import) must therefore DEGRADE the manifest by exactly
one command and NAME the failing module in a warning notice, never crash the
whole capability surface opaquely.

These tests drive the loader with a real, deliberately-broken payload module
placed on ``sys.path`` and assert the graceful-degradation contract at the
function boundary: the loader collects the failure instead of raising, the
notice projection turns it into a ``warning``, and ``command_schema_refs()``
(the consumer that needs only the command set) stays resilient.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.json_contract import NoticeSeverity
from .. import _app_contract

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.fixture
def _broken_payload_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Materialise a temp package holding one payload module that fails to import."""
    package_name = "aeat_contract_resilience_probe"
    package_dir = tmp_path / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf8")
    # A payload-named module whose import raises — the exact shape of an
    # in-flight peer refactor that trips a transitive import.
    (package_dir / "_broken_payloads.py").write_text(
        "raise ImportError('deliberate probe: transitive symbol moved')\n",
        encoding="utf8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(
        _app_contract,
        "_PAYLOAD_PACKAGES",
        (*_app_contract._PAYLOAD_PACKAGES, package_name),
    )
    try:
        yield package_name
    finally:
        for name in list(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                del sys.modules[name]


def test_broken_payload_module_is_collected_not_raised(_broken_payload_package: str) -> None:
    failures = _app_contract._ensure_result_schemas_registered()
    broken = [f for f in failures if f.module == f"{_broken_payload_package}._broken_payloads"]
    assert len(broken) == 1, failures
    assert "ImportError" in broken[0].error
    assert "deliberate probe" in broken[0].error


def test_broken_payload_module_degrades_by_exactly_one(_broken_payload_package: str) -> None:
    # The real payload packages still load, so the surface is intact minus the
    # single broken module — projection stays non-empty and rich.
    refs = _app_contract.command_schema_refs()
    commands = {ref.command for ref in refs}
    assert "contract" in commands
    assert "modelo.work.calculate" in commands
    assert len(commands) >= 200


def test_load_failure_becomes_a_warning_notice(_broken_payload_package: str) -> None:
    failures = _app_contract._ensure_result_schemas_registered()
    notices = _app_contract._schema_load_notices(failures)
    matching = [n for n in notices if n.context.get("module") == f"{_broken_payload_package}._broken_payloads"]
    assert len(matching) == 1
    notice = matching[0]
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.code == "contract.schema_module_load_failed"
    assert _broken_payload_package in notice.message
    assert "ImportError" in notice.context["error"]


def test_clean_load_yields_no_notices() -> None:
    # Without the broken probe on the path, every real payload module imports
    # and the notice list is empty — the warning fires only on real failure.
    failures = _app_contract._ensure_result_schemas_registered()
    assert failures == ()
    assert _app_contract._schema_load_notices(failures) == []
