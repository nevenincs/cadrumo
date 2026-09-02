"""Load and validate the repository's supported CPython runtime inventory.

The inventory is deliberately explicit: stable rows name every released minor
from the package floor through the current stable release, and one separate
``next`` row names the prerelease being watched.  This module owns the boundary
between that human-reviewed declaration and the GitHub Actions ``include``
matrix.  It refuses malformed, duplicated, gapped, or silently downgraded
rows before a workflow can turn them into jobs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from .._paths import REPO_ROOT, UTF_8

_INVENTORY_PATH: Final[Path] = REPO_ROOT / "dev" / "ci" / "python-runtime-matrix.json"
_SCHEMA: Final[str] = "cadrumo.python-runtime-matrix.v1"
_MINOR_RE: Final[re.Pattern[str]] = re.compile(r"^3\.(?P<minor>[0-9]+)$")
_SELECTOR_RE: Final[re.Pattern[str]] = re.compile(
    r"^3\.[0-9]+(?:\.[0-9]+)?(?:[-+][0-9A-Za-z.-]+)?$",
)
_RUNTIME_KEYS: Final[frozenset[str]] = frozenset(
    {"id", "minor", "selector", "implementation", "phase", "blocking", "classifier_eligible"},
)
_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {"schema", "minimum_minor", "current_stable_minor", "stable", "next"},
)


class RuntimePhase(StrEnum):
    """The two lifecycle states represented in the inventory."""

    STABLE = "stable"
    PRERELEASE = "prerelease"


class RuntimeMatrixError(ValueError):
    """Raised when the checked-in runtime declaration cannot be trusted."""


@dataclass(frozen=True, slots=True)
class RuntimeRecord:
    """One CPython runtime row after schema and lifecycle validation."""

    identifier: str
    minor: str
    selector: str
    implementation: str
    phase: RuntimePhase
    blocking: bool
    classifier_eligible: bool

    @property
    def minor_number(self) -> int:
        """Return the numeric minor component used for sequence checks."""
        match = _MINOR_RE.fullmatch(self.minor)
        if match is None:  # pragma: no cover - construction validates this
            raise RuntimeMatrixError(f"invalid runtime minor {self.minor!r}")
        return int(match.group("minor"))


@dataclass(frozen=True, slots=True)
class RuntimeInventory:
    """The validated stable rows and exactly one rolling prerelease row."""

    schema: str
    minimum_minor: str
    current_stable_minor: str
    stable: tuple[RuntimeRecord, ...]
    next: RuntimeRecord

    @property
    def rows(self) -> tuple[RuntimeRecord, ...]:
        """Return stable rows followed by the separately identified canary."""
        return (*self.stable, self.next)


def _require_mapping(value: object, *, context: str) -> Mapping[str, Any]:
    """Require a JSON object and provide a path-specific diagnostic."""
    if not isinstance(value, Mapping):
        raise RuntimeMatrixError(f"{context} must be a JSON object")
    return value


def _require_exact_keys(value: Mapping[str, Any], expected: frozenset[str], *, context: str) -> None:
    """Reject missing and unknown keys so schema drift cannot be ignored."""
    observed = frozenset(value)
    missing = sorted(expected - observed)
    unknown = sorted(observed - expected)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing {missing!r}")
        if unknown:
            details.append(f"unknown {unknown!r}")
        raise RuntimeMatrixError(f"{context} keys invalid ({'; '.join(details)})")


def _require_string(value: object, *, context: str) -> str:
    """Require a non-empty JSON string."""
    if not isinstance(value, str) or not value:
        raise RuntimeMatrixError(f"{context} must be a non-empty string")
    return value


def _require_bool(value: object, *, context: str) -> bool:
    """Require a JSON boolean, excluding integers accepted by Python equality."""
    if type(value) is not bool:
        raise RuntimeMatrixError(f"{context} must be a boolean")
    return value


def _parse_minor(value: object, *, context: str) -> str:
    """Validate a CPython 3.x minor identifier and return its canonical text."""
    minor = _require_string(value, context=context)
    match = _MINOR_RE.fullmatch(minor)
    if match is None or int(match.group("minor")) < 0:
        raise RuntimeMatrixError(f"{context} must use the form '3.N', got {minor!r}")
    return minor


def _parse_record(value: object, *, context: str, phase: RuntimePhase) -> RuntimeRecord:
    """Parse one row and enforce the invariant fields shared by both phases."""
    row = _require_mapping(value, context=context)
    _require_exact_keys(row, _RUNTIME_KEYS, context=context)
    identifier = _require_string(row["id"], context=f"{context}.id")
    minor = _parse_minor(row["minor"], context=f"{context}.minor")
    selector = _require_string(row["selector"], context=f"{context}.selector")
    if _SELECTOR_RE.fullmatch(selector) is None:
        raise RuntimeMatrixError(f"{context}.selector is not a Python selector: {selector!r}")
    if not selector.startswith(f"{minor}.") and selector != minor and not selector.startswith(f"{minor}-"):
        raise RuntimeMatrixError(f"{context}.selector {selector!r} does not target {minor}")
    implementation = _require_string(row["implementation"], context=f"{context}.implementation")
    if implementation != "CPython":
        raise RuntimeMatrixError(f"{context}.implementation must be 'CPython', got {implementation!r}")
    observed_phase = _require_string(row["phase"], context=f"{context}.phase")
    if observed_phase != phase.value:
        raise RuntimeMatrixError(f"{context}.phase must be {phase.value!r}, got {observed_phase!r}")
    blocking = _require_bool(row["blocking"], context=f"{context}.blocking")
    classifier_eligible = _require_bool(
        row["classifier_eligible"],
        context=f"{context}.classifier_eligible",
    )
    if phase is RuntimePhase.PRERELEASE and (blocking or classifier_eligible):
        raise RuntimeMatrixError(f"{context} prerelease rows cannot block or earn a stable classifier")
    if phase is RuntimePhase.STABLE and not blocking:
        raise RuntimeMatrixError(f"{context} stable rows must be blocking")
    return RuntimeRecord(
        identifier=identifier,
        minor=minor,
        selector=selector,
        implementation=implementation,
        phase=phase,
        blocking=blocking,
        classifier_eligible=classifier_eligible,
    )


def parse_runtime_inventory(payload: object) -> RuntimeInventory:
    """Validate a decoded inventory and return its typed representation.

    ``current_stable_minor`` is part of the declaration rather than inferred
    from the last row.  That makes a stale inventory fail when a release is
    promoted: the stable sequence must cover every minor from the floor to the
    explicitly declared current release, and the canary must be exactly the
    immediately following minor.
    """
    document = _require_mapping(payload, context="runtime inventory")
    _require_exact_keys(document, _TOP_LEVEL_KEYS, context="runtime inventory")
    schema = _require_string(document["schema"], context="runtime inventory.schema")
    if schema != _SCHEMA:
        raise RuntimeMatrixError(f"runtime inventory.schema must be {_SCHEMA!r}, got {schema!r}")
    minimum = _parse_minor(document["minimum_minor"], context="runtime inventory.minimum_minor")
    current = _parse_minor(document["current_stable_minor"], context="runtime inventory.current_stable_minor")
    minimum_number = int(minimum.split(".", maxsplit=1)[1])
    current_number = int(current.split(".", maxsplit=1)[1])
    if current_number < minimum_number:
        raise RuntimeMatrixError(
            f"current_stable_minor {current!r} precedes minimum_minor {minimum!r}",
        )

    stable_payload = document["stable"]
    if not isinstance(stable_payload, list) or not stable_payload:
        raise RuntimeMatrixError("runtime inventory.stable must be a non-empty JSON array")
    stable = tuple(
        _parse_record(value, context=f"runtime inventory.stable[{index}]", phase=RuntimePhase.STABLE)
        for index, value in enumerate(stable_payload)
    )
    expected_minors = tuple(f"3.{number}" for number in range(minimum_number, current_number + 1))
    observed_minors = tuple(row.minor for row in stable)
    if observed_minors != expected_minors:
        raise RuntimeMatrixError(
            "runtime inventory.stable must list every released minor in order: "
            f"expected {expected_minors!r}, got {observed_minors!r}",
        )
    expected_ids = tuple(f"cp3{number}" for number in range(minimum_number, current_number + 1))
    observed_ids = tuple(row.identifier for row in stable)
    if observed_ids != expected_ids:
        raise RuntimeMatrixError(
            "runtime inventory.stable ids must follow the minor sequence: "
            f"expected {expected_ids!r}, got {observed_ids!r}",
        )
    if len({row.identifier for row in stable}) != len(stable):  # defensive; sequence check catches normal duplicates
        raise RuntimeMatrixError("runtime inventory has duplicate stable ids")

    next_row = _parse_record(document["next"], context="runtime inventory.next", phase=RuntimePhase.PRERELEASE)
    expected_next_minor = f"3.{current_number + 1}"
    if next_row.minor != expected_next_minor:
        raise RuntimeMatrixError(
            f"runtime inventory.next must immediately follow {current!r}, got {next_row.minor!r}",
        )
    expected_next_id = f"cp3{current_number + 1}-next"
    if next_row.identifier != expected_next_id:
        raise RuntimeMatrixError(
            f"runtime inventory.next.id must be {expected_next_id!r}, got {next_row.identifier!r}",
        )
    if next_row.identifier in {row.identifier for row in stable}:
        raise RuntimeMatrixError(f"runtime inventory has duplicate id {next_row.identifier!r}")
    return RuntimeInventory(
        schema=schema,
        minimum_minor=minimum,
        current_stable_minor=current,
        stable=stable,
        next=next_row,
    )


def load_runtime_inventory(path: Path = _INVENTORY_PATH) -> RuntimeInventory:
    """Read and validate an inventory file from disk."""
    try:
        payload = json.loads(path.read_text(encoding=UTF_8))
    except OSError as exc:
        raise RuntimeMatrixError(f"could not read runtime inventory {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeMatrixError(f"runtime inventory {path} is not valid JSON: {exc}") from exc
    return parse_runtime_inventory(payload)


def github_matrix(inventory: RuntimeInventory) -> dict[str, list[dict[str, object]]]:
    """Project the validated rows into GitHub Actions' ``matrix.include`` shape."""
    return {
        "include": [
            {
                "runtime-id": row.identifier,
                "python-version": row.selector,
                "python-minor": row.minor,
                "implementation": row.implementation,
                "phase": row.phase.value,
                "blocking": row.blocking,
                "classifier-eligible": row.classifier_eligible,
            }
            for row in inventory.rows
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the inventory and print a compact GitHub matrix document."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=_INVENTORY_PATH)
    args = parser.parse_args(argv)
    try:
        inventory = load_runtime_inventory(args.inventory)
    except RuntimeMatrixError as exc:
        print(f"runtime inventory invalid: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(github_matrix(inventory), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI dispatch
    raise SystemExit(main())
