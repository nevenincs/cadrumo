"""Engine-shaped component records for tests of the Python consumers.

The native component engine writes a browser record once the builds verify,
under each storage root. Consumers such as the browser launch guard only read
that record, so their tests stand in for the engine by writing the record it
writes: the committed fixture the engine's own test produces, placed for a
test's browsers folder and driver.

Every test run shares one provisioned browser cache, while tests build private
storage roots of their own. The run's bootstrap registers the record the engine
would write for that shared cache (:func:`register_shared_browser`), and a test
that launches a real browser under its own storage root writes it there with
:func:`record_shared_browser`, as the engine would after adopting those builds.
"""

from __future__ import annotations

import json
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.component_records import component_records_root

if TYPE_CHECKING:
    from ..core.config import Settings

__all__ = [
    "engine_browser_record",
    "installed_driver_version",
    "record_shared_browser",
    "register_shared_browser",
    "write_engine_browser_record",
]

_ENGINE_BROWSER_RECORD = Path(__file__).parents[1] / "core" / "tests" / "_component_records" / "browser.json"
_RECORD_NAME = "browser.json"


def installed_driver_version() -> str:
    """Return the version of the Playwright driver installed in this environment."""
    spec = find_spec("playwright")
    assert spec is not None
    assert spec.origin is not None
    package = Path(spec.origin).parent / "driver" / "package" / "package.json"
    loaded: object = json.loads(package.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    version = loaded["version"]
    assert isinstance(version, str)
    return version


def _engine_record(
    *,
    browsers_root: Path,
    driver_version: str,
    paths: Mapping[str, str] | None,
    version: str | None,
) -> dict[str, Any]:
    loaded: object = json.loads(_ENGINE_BROWSER_RECORD.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    record: dict[str, Any] = loaded
    location = record["location"]
    location["root"] = str(browsers_root)
    location["facts"]["playwright_driver"] = driver_version
    if paths is not None:
        location["paths"] = dict(paths)
        # The builds are already there; a locate step never reads file digests.
        record["files"] = []
    if version is not None:
        record["version"] = version
    return record


def write_engine_browser_record(
    *,
    records_root: Path,
    browsers_root: Path,
    driver_version: str,
    executables: bool = True,
    paths: Mapping[str, str] | None = None,
    version: str | None = None,
) -> dict[str, Path]:
    """Write the engine's browser record for ``browsers_root`` and ``driver_version``.

    With ``executables`` the files the record names are created too, as the
    engine's install leaves them. ``paths`` names other executables, relative to
    ``browsers_root``, for a cache whose builds are already there; the record
    then lists no file digests. Returns each named path, resolved.
    """
    record = _engine_record(browsers_root=browsers_root, driver_version=driver_version, paths=paths, version=version)
    records_root.mkdir(parents=True, exist_ok=True)
    (records_root / _RECORD_NAME).write_text(json.dumps(record, separators=(",", ":")), encoding="utf-8")
    named: dict[str, Path] = {}
    for name, relative in record["location"]["paths"].items():
        assert isinstance(name, str)
        assert isinstance(relative, str)
        named[name] = browsers_root.joinpath(*relative.split("/"))
    if executables:
        for path in named.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"executable")
    return named


@contextmanager
def engine_browser_record(
    *, records_root: Path, browsers_root: Path, driver_version: str
) -> Generator[dict[str, Path]]:
    """Write the engine's browser record with its executables, and put back any record it replaced.

    A test whose records folder is the run's own leaves the shared browser's
    record as it found it for the tests after it.
    """
    target = records_root / _RECORD_NAME
    previous = target.read_bytes() if target.is_file() else None
    try:
        yield write_engine_browser_record(
            records_root=records_root, browsers_root=browsers_root, driver_version=driver_version
        )
    finally:
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            target.write_bytes(previous)


_shared_browser: list[bytes] = []


def register_shared_browser(*, browsers_root: Path, paths: Mapping[str, str], version: str | None) -> None:
    """Register the record the engine writes for the run's shared browser cache.

    ``paths`` names each build's executable relative to ``browsers_root``; the
    run's bootstrap passes them only when the cache holds every build the
    installed driver launches. The record is also written for the run's own
    storage root.
    """
    record = _engine_record(
        browsers_root=browsers_root, driver_version=installed_driver_version(), paths=paths, version=version
    )
    _shared_browser[:] = [json.dumps(record, separators=(",", ":")).encode("utf-8")]
    record_shared_browser()


def record_shared_browser(settings: Settings | None = None) -> None:
    """Write the shared browser cache's record under a test's storage root, as the engine would.

    The record goes to the records folder of ``settings``, or of the settings
    in force when none are given. Nothing is written when the run has no
    shared browser to record, so the consumer refuses as it would without one.
    """
    if not _shared_browser:
        return
    records_root = component_records_root(settings)
    records_root.mkdir(parents=True, exist_ok=True)
    (records_root / _RECORD_NAME).write_bytes(_shared_browser[0])
