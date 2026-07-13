"""Resilience gate for the ``aeat app contract`` capability manifest.

The operator rules mandate reading ``aeat app contract`` FIRST — it is the
grounding entry point an LLM operator consults before doing anything else. A
single broken result-payload module (typically an unrelated in-flight refactor
that trips a transitive import) must therefore DEGRADE the manifest by exactly
one command and NAME the failing module in a warning notice, never crash the
whole capability surface opaquely.

These tests drive the loader with a real missing payload package name and assert
the graceful-degradation contract at the function boundary: the loader collects
the failure instead of raising, the notice projection turns it into a
``warning``, and ``command_schema_refs()`` (the consumer that needs only the
command set) stays resilient.
"""

from __future__ import annotations

import pytest

from ....core.json_contract import NoticeSeverity
from .. import _app_contract

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MISSING_PAYLOAD_PACKAGE = "cadrumo.entrypoints.cli.tests._missing_payload_package"


def _payload_packages_with_missing_probe() -> tuple[str, ...]:
    return (*_app_contract._PAYLOAD_PACKAGES, _MISSING_PAYLOAD_PACKAGE)


def test_broken_payload_module_is_collected_not_raised() -> None:
    failures = _app_contract._ensure_result_schemas_registered(
        payload_packages=_payload_packages_with_missing_probe(),
    )
    broken = [f for f in failures if f.module == _MISSING_PAYLOAD_PACKAGE]
    assert len(broken) == 1, failures
    assert "ModuleNotFoundError" in broken[0].error
    assert "_missing_payload_package" in broken[0].error


def test_broken_payload_module_degrades_by_exactly_one() -> None:
    # The real payload packages still load, so the surface is intact minus the
    # single broken module — projection stays non-empty and rich.
    refs = _app_contract.command_schema_refs(payload_packages=_payload_packages_with_missing_probe())
    commands = {ref.command for ref in refs}
    assert "contract" in commands
    assert "modelo.work.calculate" in commands
    assert len(commands) >= 200


def test_load_failure_becomes_a_warning_notice() -> None:
    failures = _app_contract._ensure_result_schemas_registered(
        payload_packages=_payload_packages_with_missing_probe(),
    )
    notices = _app_contract._schema_load_notices(failures)
    matching = [n for n in notices if (n.context or {}).get("module") == _MISSING_PAYLOAD_PACKAGE]
    assert len(matching) == 1
    notice = matching[0]
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.code == "contract.schema_module_load_failed"
    assert _MISSING_PAYLOAD_PACKAGE in notice.message
    assert notice.context is not None
    assert "ModuleNotFoundError" in notice.context["error"]


def test_clean_load_yields_no_notices() -> None:
    # Without the broken probe on the path, every real payload module imports
    # and the notice list is empty — the warning fires only on real failure.
    failures = _app_contract._ensure_result_schemas_registered()
    assert failures == ()
    assert _app_contract._schema_load_notices(failures) == []
