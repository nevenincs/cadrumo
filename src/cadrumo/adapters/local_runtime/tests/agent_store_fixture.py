"""A stand-in for the agent's one-shot store invocations: ``version``, ``stores-state``, ``setup`` and ``migrate``.

It keeps two plain files where the agent keeps its stores, ``home/state`` under
the hosted root its environment names, each holding the revision it is at. It
answers each invocation with the agent's own output shapes and exit statuses,
and appends what it was asked and the environment it ran in to
``invocations.jsonl`` in its record directory. Every invocation writes a line of
noise to standard error, which the host must not read.

Behaviours, set per test in the stand-in's configuration: ``setup`` is ``ok`` or
``fail``; ``migrate`` is ``ok``, ``fail`` or ``hang``; ``api`` is the command-line
contract ``version`` reports; ``malformed`` names one verb whose output carries
a number where the agent writes text.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Final

PRIMARY: Final = "cadrumo-agent.db"
CHECKPOINT: Final = "checkpoints.db"
WRITE_AHEAD_LOG: Final = "cadrumo-agent.db-wal"
EXPECTED_PRIMARY: Final = "0002"
EXPECTED_CHECKPOINT: Final = "1.0.0"
STANDARD_ERROR_NOISE: Final = b"<frozen runpy>:128: RuntimeWarning: found in sys.modules\n"


def store_directory(hosted_root: Path) -> Path:
    """Where the stand-in, like the agent, keeps its stores under a hosted root."""
    return hosted_root / "home" / "state"


def seed_stores(hosted_root: Path, *, primary: str, checkpoint: str) -> None:
    """Leave stores at these revisions under a hosted root, as an earlier agent build would have."""
    stores = store_directory(hosted_root)
    stores.mkdir(parents=True, exist_ok=True)
    (stores / PRIMARY).write_text(primary, encoding="utf-8")
    (stores / CHECKPOINT).write_text(checkpoint, encoding="utf-8")
    (stores / WRITE_AHEAD_LOG).write_text(f"log of {primary}", encoding="utf-8")


def _found(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _judge(found: str | None, expected: str) -> str:
    if found is None:
        return "absent"
    if found == expected:
        return "current"
    return "older" if found < expected else "newer"


def _stores_state(stores: Path, malformed: bool) -> dict[str, object]:
    primary, checkpoint = _found(stores / PRIMARY), _found(stores / CHECKPOINT)
    states = {_judge(primary, EXPECTED_PRIMARY), _judge(checkpoint, EXPECTED_CHECKPOINT)}
    if "newer" in states:
        state = "newer"
    elif states == {"absent"}:
        state = "absent"
    elif states == {"current"}:
        state = "current"
    else:
        state = "older"
    expected: object = int(EXPECTED_PRIMARY) if malformed else EXPECTED_PRIMARY
    return {
        "state": state,
        "primary": {"state": _judge(primary, EXPECTED_PRIMARY), "found": primary, "expected": expected},
        "checkpoint": {
            "state": _judge(checkpoint, EXPECTED_CHECKPOINT),
            "found": checkpoint,
            "expected": EXPECTED_CHECKPOINT,
        },
    }


def _step(
    status: str, stores: Path, *, stage: str | None = None, changes: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "status": status,
        "target_head": EXPECTED_PRIMARY,
        "stores": changes,
        "duration_seconds": 0.25,
        "failed_stage": stage,
        "error_class": None if stage is None else "MigrationError",
        "detail": None if stage is None else f"S3CRET-DETAIL at {stores}",
        "app_home": str(stores.parent),
    }


def _answer(verb: list[str], stores: Path, config: dict[str, object]) -> tuple[dict[str, object], int]:
    malformed = config.get("malformed") == verb[0]
    if verb == ["version", "--json"]:
        return {"api_version": config.get("api", "v1"), "package_version": "0.0.0-test"}, 0
    if verb == ["stores-state"]:
        return _stores_state(stores, malformed), 0
    if verb == ["setup"]:
        if config.get("setup", "ok") == "fail":
            return _step("failed", stores, stage="primary", changes=[]), 1
        seed_stores(stores.parent.parent, primary=EXPECTED_PRIMARY, checkpoint=EXPECTED_CHECKPOINT)
        changes: list[dict[str, object]] = [
            {
                "store": "primary",
                "status": "migrated",
                "from_revision": None,
                "to_revision": EXPECTED_PRIMARY,
                "schema_version": None,
            },
            {
                "store": "checkpoint",
                "status": "initialized",
                "from_revision": None,
                "to_revision": None,
                "schema_version": EXPECTED_CHECKPOINT,
            },
        ]
        return _step("succeeded", stores, changes=changes), 0
    if verb[0] == "migrate":
        behaviour = config.get("migrate", "ok")
        found = _found(stores / PRIMARY)
        if behaviour == "hang":
            time.sleep(600)
        asserted = verb == ["migrate", "--expect-from", str(found), "--expect-head", EXPECTED_PRIMARY]
        if behaviour == "fail" or not asserted:
            # A failed migrate can leave a store half-way: the host's copy is the rollback.
            (stores / CHECKPOINT).write_text("half-migrated", encoding="utf-8")
            return _step("failed", stores, stage="checkpoint", changes=[]), 1
        seed_stores(stores.parent.parent, primary=EXPECTED_PRIMARY, checkpoint=EXPECTED_CHECKPOINT)
        change: dict[str, object] = {
            "store": "primary",
            "status": "migrated",
            "from_revision": found,
            "to_revision": EXPECTED_PRIMARY,
            "schema_version": None,
        }
        return _step("succeeded", stores, changes=[change]), 0
    return {}, 2


def main() -> None:
    """Answer the invocation named after the configuration and record directory on the command line."""
    config_path, record, verb = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
    decoded: object = json.loads(config_path.read_text(encoding="utf-8"))
    assert isinstance(decoded, dict)
    config = {str(key): value for key, value in decoded.items()}
    hosted_root = Path(os.environ[str(config["hosted_root_variable"])])
    stores = store_directory(hosted_root)
    aside = hosted_root / "stores-aside"
    with (record / "invocations.jsonl").open("a", encoding="utf-8") as log:
        entry = {
            "verb": verb,
            "pid": os.getpid(),
            "executable": sys.executable,
            "directory": os.getcwd(),
            "environment": dict(os.environ),
            "aside": sorted(path.name for path in aside.iterdir()) if aside.is_dir() else None,
        }
        log.write(json.dumps(entry) + "\n")
    sys.stderr.buffer.write(STANDARD_ERROR_NOISE)
    sys.stderr.buffer.flush()
    behaviour = config.get("stores", {})
    assert isinstance(behaviour, dict)
    document, status = _answer(verb, stores, {str(key): value for key, value in behaviour.items()})
    if document:
        sys.stdout.buffer.write(json.dumps(document, indent=2, sort_keys=True).encode("utf-8") + b"\n")
        sys.stdout.buffer.flush()
    sys.exit(status)


if __name__ == "__main__":
    main()
