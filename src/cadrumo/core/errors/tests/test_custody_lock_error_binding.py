"""Custody lock contention binds identically before or after catalogue loading."""

from __future__ import annotations

import json
import sys
from typing import Literal

import pytest

from cadrumo.tests.audited_process import run_audited_process

from ...type_guards import is_object_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROBE = """
import json, sys

from cadrumo.core.errors.error_codes import declared_error_codes_by_qualname, get_registered_error_code
from cadrumo.core.errors.hierarchy import CadrumoError, InternalInvariantError

order = sys.argv[1]
catalogue = "cadrumo.core.errors.registry.declared_codes"
if order == "catalogue-first":
    declared_error_codes_by_qualname()
report = {"catalogue_loaded_before_error_import": catalogue in sys.modules}

from cadrumo.adapters.persistence.storage.custody.errors import (
    ProfileCustodyLockContendedError,
    ProfileCustodyRecordError,
)

error = ProfileCustodyLockContendedError("local custody lock remains held")
code = get_registered_error_code(error)
qualname = "cadrumo.adapters.persistence.storage.custody.errors.ProfileCustodyLockContendedError"
declared = declared_error_codes_by_qualname()
report.update({
    "class_code": ProfileCustodyLockContendedError.code.code,
    "instance_code": code.code,
    "category": code.category.value,
    "retryable": code.retryable,
    "message_key": code.message_key,
    "same_declared_code": declared[qualname] is code,
    "different_from_integrity_parent": get_registered_error_code(ProfileCustodyRecordError).category != code.category,
})

try:
    class UndeclaredCustodyProbeError(CadrumoError):
        pass
except InternalInvariantError as exc:
    report["undeclared_rejected"] = str(exc)
else:
    raise AssertionError("catalogue loading must still reject an undeclared error class")

print(json.dumps(report))
"""


@pytest.mark.parametrize("order", ["class-first", "catalogue-first"])
def test_custody_lock_contention_binds_in_either_import_order(order: Literal["class-first", "catalogue-first"]) -> None:
    completed = run_audited_process([sys.executable, "-c", _PROBE, order], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    report: object = json.loads(str(completed.stdout))
    assert is_object_mapping(report)
    assert report["catalogue_loaded_before_error_import"] is (order == "catalogue-first")
    assert report["class_code"] == report["instance_code"] == "LOCKED_STORAGE_PROFILE_CUSTODY_LOCK_CONTENDED"
    assert report["category"] == "LOCKED"
    assert report["retryable"] is True
    assert report["message_key"] == "errors.locked.locked_storage_lock_acquisition"
    assert report["same_declared_code"] is True
    assert report["different_from_integrity_parent"] is True
    rejected = report["undeclared_rejected"]
    assert isinstance(rejected, str)
    assert "UndeclaredCustodyProbeError" in rejected
    assert "missing a declared ErrorCode" in rejected
