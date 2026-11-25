"""A failed runtime-backed job publishes its failed sandboxes' diagnostic logs, and only those.

A documented sequence that fails keeps its sandbox's ``logs`` directories under
the worktree's temporary root, and its transcript names a refusal only by its
reason; the product log names the module, function and line. A hosted runner is
discarded with its job, so each merge gate job that starts the runtime uploads
those logs when it fails. The contract is pinned here with planted defects:

- the upload runs only for a failed job, after the tests, and can find the
  hidden ``.tmp`` directory;
- its path is the product's own diagnostic log beneath the retention root and
  nothing else, because that file is the one the log filter redacts;
- it is kept for days, not months, and no job reads it back, so no run can
  hand a later run anything.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location
from dev.paths import REPO_ROOT, TEMP_ROOT

from ..lane_recipe_commands import recipes_invoked_by

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MERGE_GATE: Final = REPO_ROOT / ".github" / "workflows" / "merge-gate.yml"
_SETUP_ACTION: Final = "./.github/actions/setup"
_UPLOAD_ACTION: Final = "actions/upload-artifact@"
_DOWNLOAD_ACTION: Final = "actions/download-artifact@"
_ARTIFACT_PREFIX: Final = "cadrumo-failed-sandbox-logs-"
_ONLY_WHEN_FAILED: Final = "${{ failure() }}"
_MATRIX_ROW: Final = "${{ strategy.job-index }}"
_LONGEST_RETENTION_DAYS: Final = 7
#: The merge gate jobs whose tests start the runtime, and so can retain a sandbox.
_RUNTIME_BACKED_JOBS: Final = frozenset({"goldens", "tests", "harness"})


def _log_glob() -> str:
    """Return the one path the upload may name, built from the owners of its two halves."""
    retained = (TEMP_ROOT / "failed-sandboxes").relative_to(REPO_ROOT).as_posix()
    log_file = Path(storage_location(StorageCategory.LOG_FILE).subpath).name
    return f"{retained}/**/logs/{log_file}"


def _runtime_backed(job: Mapping[str, Any]) -> bool:
    return any(
        step.get("uses") == _SETUP_ACTION and (step.get("with") or {}).get("worker-containment") in (True, "true")
        for step in job.get("steps") or []
    )


def _uploads(job: Mapping[str, Any]) -> list[tuple[int, Mapping[str, Any]]]:
    return [
        (index, step)
        for index, step in enumerate(job.get("steps") or [])
        if str(step.get("uses", "")).startswith(_UPLOAD_ACTION)
        and str((step.get("with") or {}).get("name", "")).startswith(_ARTIFACT_PREFIX)
    ]


def _last_test_step(job: Mapping[str, Any]) -> int:
    indexes = [
        index
        for index, step in enumerate(job.get("steps") or [])
        if any(recipe.startswith("test-") for recipe in recipes_invoked_by(str(step.get("run") or "")))
    ]
    return max(indexes, default=-1)


def _upload_violations(document: Mapping[str, Any]) -> list[str]:
    """Report every way a runtime-backed job could lose, widen or keep its failed sandbox logs."""
    violations: list[str] = []
    names: list[str] = []
    for job_name, job in (document.get("jobs") or {}).items():
        uploads = _uploads(job)
        if not _runtime_backed(job):
            violations.extend(f"{job_name} uploads sandbox logs but starts no runtime" for _ in uploads)
            continue
        if len(uploads) != 1:
            violations.append(f"{job_name} holds {len(uploads)} failed sandbox log uploads, not one")
            continue
        index, step = uploads[0]
        settings = step.get("with") or {}
        names.append(str(settings.get("name")))
        if str(step.get("if", "")).strip() != _ONLY_WHEN_FAILED:
            violations.append(f"{job_name} does not upload its sandbox logs exactly when the job failed")
        if index < _last_test_step(job):
            violations.append(f"{job_name} uploads its sandbox logs before its tests have run")
        if settings.get("path") != _log_glob():
            violations.append(f"{job_name} uploads something other than the failed sandboxes' redacted logs")
        if settings.get("include-hidden-files") is not True:
            violations.append(f"{job_name} leaves the hidden temporary root out of its upload")
        if settings.get("if-no-files-found") != "ignore":
            violations.append(f"{job_name} treats a failure that retained no sandbox as an upload problem")
        retention = settings.get("retention-days")
        if type(retention) is not int or not 1 <= retention <= _LONGEST_RETENTION_DAYS:
            violations.append(f"{job_name} keeps its sandbox logs longer than {_LONGEST_RETENTION_DAYS} days")
        if (job.get("strategy") or {}).get("matrix") and _MATRIX_ROW not in str(settings.get("name")):
            violations.append(f"{job_name} gives every matrix row's sandbox logs one artifact name")
    violations.extend(f"two jobs upload sandbox logs as {name}" for name in sorted(set(names)) if names.count(name) > 1)
    for job_name, job in (document.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            if not str(step.get("uses", "")).startswith(_DOWNLOAD_ACTION):
                continue
            settings = step.get("with") or {}
            if "name" not in settings or str(settings["name"]).startswith(_ARTIFACT_PREFIX):
                violations.append(f"{job_name} reads failed sandbox logs back into a run")
    return violations


def _live() -> dict[str, Any]:
    return yaml.safe_load(_MERGE_GATE.read_text(encoding="utf-8"))


def _upload(document: dict[str, Any], job_name: str = "harness") -> dict[str, Any]:
    ((index, _),) = _uploads(document["jobs"][job_name])
    return document["jobs"][job_name]["steps"][index]


# --- the live workflow --------------------------------------------------------


def test_every_runtime_backed_job_uploads_its_failed_sandbox_logs_and_nothing_else() -> None:
    document = _live()
    assert _upload_violations(document) == []
    # Anchor: the rule judges the jobs that start the runtime, and all of them.
    assert {name for name, job in document["jobs"].items() if _runtime_backed(job)} == _RUNTIME_BACKED_JOBS
    assert {name for name, job in document["jobs"].items() if _uploads(job)} == _RUNTIME_BACKED_JOBS


def test_the_uploaded_path_is_the_product_log_beneath_the_retention_root() -> None:
    """Independent of the workflow: the glob is where the sequence runner keeps a failed sandbox's logs."""
    assert _log_glob() == ".tmp/failed-sandboxes/**/logs/cadrumo.log"


# --- teeth --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("if", "${{ always() }}", "harness does not upload its sandbox logs exactly when the job failed"),
        ("if", None, "harness does not upload its sandbox logs exactly when the job failed"),
        ("with.path", ".tmp/failed-sandboxes", "harness uploads something other than the failed sandboxes'"),
        ("with.path", ".tmp/failed-sandboxes/**/logs/*", "harness uploads something other than the failed"),
        ("with.path", ".tmp", "harness uploads something other than the failed sandboxes' redacted logs"),
        ("with.include-hidden-files", None, "harness leaves the hidden temporary root out of its upload"),
        ("with.if-no-files-found", "error", "harness treats a failure that retained no sandbox as an upload"),
        ("with.retention-days", 90, "harness keeps its sandbox logs longer than 7 days"),
        ("with.retention-days", None, "harness keeps its sandbox logs longer than 7 days"),
        ("with.name", "cadrumo-failed-sandbox-logs-goldens", "two jobs upload sandbox logs as"),
    ],
)
def test_the_upload_rule_reports_each_defect_planted_in_the_harness_job(key: str, value: object, expected: str) -> None:
    document = _live()
    step = _upload(document)
    target: dict[str, Any] = step
    if key.startswith("with."):
        target, key = step["with"], key.removeprefix("with.")
    if value is None:
        del target[key]
    else:
        target[key] = value
    violations = _upload_violations(document)
    assert len(violations) == 1, violations
    assert violations[0].startswith(expected)


def test_the_upload_rule_reports_a_missing_upload_an_early_one_and_a_shared_matrix_name() -> None:
    removed = _live()
    removed["jobs"]["goldens"]["steps"].remove(_upload(removed, "goldens"))
    assert _upload_violations(removed) == ["goldens holds 0 failed sandbox log uploads, not one"]

    early = _live()
    steps = early["jobs"]["tests"]["steps"]
    steps.insert(0, steps.pop(steps.index(_upload(early, "tests"))))
    assert _upload_violations(early) == ["tests uploads its sandbox logs before its tests have run"]

    shared = _live()
    _upload(shared, "tests")["with"]["name"] = "cadrumo-failed-sandbox-logs-tests"
    assert _upload_violations(shared) == ["tests gives every matrix row's sandbox logs one artifact name"]


def test_the_upload_rule_reports_an_upload_from_a_job_that_starts_no_runtime_and_a_read_back() -> None:
    stray = _live()
    stray["jobs"]["contracts"]["steps"].append(copy.deepcopy(_upload(stray)))
    assert "contracts uploads sandbox logs but starts no runtime" in _upload_violations(stray)

    for settings in ({"name": "cadrumo-failed-sandbox-logs-harness"}, {}):
        read_back = _live()
        read_back["jobs"]["verdict"]["steps"].append({"uses": _DOWNLOAD_ACTION + "0" * 40, "with": settings})
        assert _upload_violations(read_back) == ["verdict reads failed sandbox logs back into a run"]
