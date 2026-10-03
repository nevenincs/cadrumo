"""Observe target-interpreter identity and bind source and builder lock evidence."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any, Final

from cadrumo.core.hashing import sha256_hex
from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command
from dev.packaging.hashing import sha256_path

from .runtime_probe_contracts import _SHA256_RE, _UTF_8, CompatibilityProbeError
from .runtime_probe_environment import _isolated_environment

_RUNTIME_VERSION_RE: Final[re.Pattern[str]] = re.compile(r"^3\.(?P<minor>[0-9]+)")


_BUILDER_PIN_PATH: Final[Path] = Path("dev") / "packaging" / "release-python-version"


_DEFAULT_BUILDER_PIN: Final[Path] = REPO_ROOT / _BUILDER_PIN_PATH


def _validate_observed_runtime_minor(selector: str, observed_python: str) -> None:
    """Validate observed runtime minor."""
    selector_match = _RUNTIME_VERSION_RE.match(selector)
    observed_match = _RUNTIME_VERSION_RE.match(observed_python)
    if (
        selector_match is None
        or observed_match is None
        or selector_match.group("minor") != observed_match.group("minor")
    ):
        raise CompatibilityProbeError(
            f"selected interpreter {observed_python!r} does not satisfy selector {selector!r}",
            category="runtime-identity-mismatch",
        )


def _read_lock_digest(path: Path) -> str:
    """Hash the exact lock bytes associated with the source or sealed cohort."""
    try:
        return sha256_path(path.resolve(strict=True))
    except OSError as exc:
        raise CompatibilityProbeError(f"uv.lock is unavailable: {path}", category="lock-missing") from exc


def _cohort_lock_digest(cohort: Any) -> str:
    """Read the lock digest from the cohort's sealed wheelhouse manifest."""
    value = cohort.runtime_wheelhouse_manifest.get("lock_sha256")
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise CompatibilityProbeError("Python cohort does not carry a valid lock digest", category="cohort-invalid")
    with zipfile.ZipFile(cohort.source_archive) as archive:
        try:
            source_lock_digest = sha256_hex(archive.read("uv.lock"))
        except KeyError as exc:
            raise CompatibilityProbeError(
                "Python cohort source archive omits uv.lock",
                category="cohort-invalid",
            ) from exc
    if source_lock_digest != value:
        raise CompatibilityProbeError(
            "Python cohort wheelhouse lock digest disagrees with its source archive",
            category="cohort-invalid",
        )
    return value


def _builder_pin(repo_root: Path) -> str:
    """Return the exact release-builder interpreter identity, if declared."""
    try:
        value = (
            (_DEFAULT_BUILDER_PIN if repo_root == REPO_ROOT else repo_root / _BUILDER_PIN_PATH)
            .read_text(
                encoding=_UTF_8,
            )
            .strip()
        )
    except OSError as exc:
        raise CompatibilityProbeError(
            f"{_BUILDER_PIN_PATH.as_posix()} is unavailable", category="builder-identity-missing"
        ) from exc
    if not value:
        raise CompatibilityProbeError(f"{_BUILDER_PIN_PATH.as_posix()} is empty", category="builder-identity-missing")
    return value


def _runtime_identity(python: Path, *, runtime_id: str, selector: str, stability: str, cwd: Path) -> dict[str, str]:
    """Ask the selected interpreter for its identity, never trusting the host process."""
    code = (
        "import json,platform,sys; "
        "print(json.dumps({'python': platform.python_version(), "
        "'implementation': platform.python_implementation(), "
        "'platform': sys.platform, 'machine': platform.machine()}, sort_keys=True))"
    )
    env = _isolated_environment(cwd, python.parent)
    result = run_command((str(python), "-I", "-W", "error::DeprecationWarning", "-c", code), cwd=cwd, environment=env)
    if result.returncode != 0:
        raise CompatibilityProbeError(
            f"selected interpreter identity probe failed: {result.stderr.strip() or result.stdout.strip()}",
            category="runtime-probe-failed",
        )
    try:
        identity = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CompatibilityProbeError(
            "selected interpreter identity was not JSON",
            category="runtime-probe-failed",
        ) from exc
    if not isinstance(identity, dict):
        raise CompatibilityProbeError(
            "selected interpreter identity was not an object",
            category="runtime-probe-failed",
        )
    observed_python = identity.get("python")
    implementation = identity.get("implementation")
    if not isinstance(observed_python, str) or not isinstance(implementation, str):
        raise CompatibilityProbeError(
            "selected interpreter identity omitted Python fields",
            category="runtime-probe-failed",
        )
    if implementation != "CPython":
        raise CompatibilityProbeError(
            f"compatibility matrix requires CPython, got {implementation!r}",
            category="implementation-unsupported",
        )
    _validate_observed_runtime_minor(selector, observed_python)
    return {
        "id": runtime_id,
        "selector": selector,
        "python": observed_python,
        "implementation": implementation,
        "stability": stability,
        "platform": str(identity.get("platform", "")),
        "machine": str(identity.get("machine", "")),
    }
