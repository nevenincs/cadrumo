"""The declared-code catalogue loads on first lookup, not on import.

Each probe runs in a fresh interpreter: the test session has long since loaded
the catalogue, and the behaviour under test is what happens before that.
"""

from __future__ import annotations

import json
import sys

import pytest

from cadrumo.tests.audited_process import run_audited_process

from ...type_guards import is_object_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROBE = """
import json, sys

from cadrumo.core.errors.hierarchy import CadrumoError, CoreValidationError, InternalInvariantError

catalogue = "cadrumo.core.errors.registry.declared_codes"
report = {"loaded_at_import": catalogue in sys.modules}


class UndeclaredProbeError(CadrumoError):
    pass


report["loaded_after_undeclared_class"] = catalogue in sys.modules
report["class_code"] = CoreValidationError.code.code
report["instance_code"] = CoreValidationError("probe").code.code
report["loaded_after_lookup"] = catalogue in sys.modules
report["root_has_code"] = hasattr(CadrumoError, "code")
try:
    UndeclaredProbeError.code
except InternalInvariantError as exc:
    report["undeclared"] = str(exc)
print(json.dumps(report))
"""


def _probe() -> dict[str, object]:
    completed = run_audited_process(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    loaded: object = json.loads(str(completed.stdout))
    assert is_object_mapping(loaded)
    return {str(key): value for key, value in loaded.items()}


def test_importing_the_hierarchy_does_not_load_the_catalogue_until_a_code_is_read() -> None:
    report = _probe()

    assert report["loaded_at_import"] is False
    assert report["loaded_after_undeclared_class"] is False
    assert report["class_code"] == "INTEGRITY_CADRUMO_CORE_VALIDATION"
    assert report["instance_code"] == "INTEGRITY_CADRUMO_CORE_VALIDATION"
    assert report["loaded_after_lookup"] is True
    assert report["root_has_code"] is False


def test_a_class_created_before_the_catalogue_loaded_is_still_refused_when_undeclared() -> None:
    report = _probe()

    undeclared = report.get("undeclared")
    assert isinstance(undeclared, str)
    assert "UndeclaredProbeError" in undeclared
