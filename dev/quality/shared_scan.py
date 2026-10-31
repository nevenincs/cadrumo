"""A whole-tree scan's result, computed once per run for each distinct input and shared read-only.

A scan of the repository -- every Python file parsed for its imports, every
locale key collected, every module checked for reachability -- is a pure
function of the files it reads and of the code that reads them. A parallel
test run used to repeat each one in every worker that asked. Here the scan is
keyed on exactly those two things: the root-relative path and content digest of
each file the scan's own inclusion policy enumerates, and the source of the
modules that implement it. The first process to ask computes it and publishes it
through the run-wide artifact cache (:mod:`cadrumo.tests.run_artifact`); every
other process verifies the published bytes and reads them.

A digest over the whole worktree would be wrong in both directions: the shared
worktree churns, so an unrelated edit would recompute it, and a file outside the
walk could never matter. A digest over the scanned files alone would be wrong in
the other: a changed scanner over an unchanged tree must not serve the old
answer. The key is therefore both, and nothing else.

Results are served to many consumers in one process and must not be changed by
any of them, so a result must be built from immutable values (see
:func:`require_immutable`); a mutable one is refused before it is published.

Two forms, because a key must name the bytes the scan actually read:

- :func:`shared_snapshot_scan_result` reads every input ONCE, keys on those
  bytes and hands the same bytes to the scan as a :class:`SourceSnapshot`. A
  file edited mid-scan cannot split the key from the result, which matters in a
  worktree other sessions edit while a scan of thousands of files runs.
- :func:`shared_scan_result` is for a scanner that must read the tree itself,
  such as a third-party tool. The inputs are digested again afterwards, and a
  scan whose inputs moved is returned to its caller without being published.

A caller may also decline to share a result (``publish_if``): a timed-out tool
run says nothing about its inputs, and every later process should try again.
"""

from __future__ import annotations

import copyreg
import dataclasses
import enum
import hashlib
import io
import pickle
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path, PurePath, PurePosixPath
from types import MappingProxyType, ModuleType
from typing import Final, cast, override

from pydantic import BaseModel

from cadrumo.core.hashing import content_hash_hex, hash_file
from cadrumo.tests.run_artifact import file_inputs_digest, run_artifact

__all__ = [
    "SourceSnapshot",
    "require_immutable",
    "scanner_identity",
    "shared_scan_result",
    "shared_snapshot_scan_result",
    "take_snapshot",
]

_RESULT_NAME: Final = "result.pickle"
_DIGEST_NAME: Final = "result.sha256"
_KEY_LENGTH: Final = 32

_IMMUTABLE_ATOMS: Final = (type(None), bool, int, float, complex, str, bytes, PurePath, enum.Enum)

_TRUSTED_MODULES: Final = frozenset(
    {"builtins", "collections", "copyreg", "datetime", "decimal", "enum", "pathlib", "types"}
)
_TRUSTED_PACKAGES: Final = frozenset({"cadrumo", "dev", "pydantic", "pydantic_core"})

_memo: dict[tuple[str, str], object] = {}


class _UnpublishedResultError(Exception):
    """Carries a result that names no single input, or one its caller declined to share, back unpublished."""

    def __init__(self, result: object) -> None:
        super().__init__("the scan result was not published")
        self.result = result


@dataclasses.dataclass(frozen=True)
class SourceSnapshot:
    """The bytes of every input a scan reads, read once, in enumeration order.

    A file that could not be read is kept with the error that refused it, so the
    scan reports it as unread exactly as it would have reading the tree itself.
    """

    paths: tuple[Path, ...]
    """Every enumerated input, readable or not, in enumeration order."""
    contents: Mapping[Path, bytes]
    unreadable: Mapping[Path, str]

    def read_bytes(self, path: Path) -> bytes:
        """Return the snapshot's bytes for ``path``.

        Raises:
            OSError: When the file could not be read when the snapshot was taken.
        """
        if path in self.contents:
            return self.contents[path]
        raise OSError(self.unreadable.get(path, f"{path} is not an input of this scan"))

    def read_text(self, path: Path) -> str:
        """Return the snapshot's UTF-8 text for ``path``, as :meth:`pathlib.Path.read_text` would.

        Raises:
            OSError: When the file could not be read.
            UnicodeDecodeError: When its bytes are not UTF-8.
        """
        return self.read_bytes(path).decode("utf-8")


def take_snapshot(paths: Iterable[Path]) -> SourceSnapshot:
    """Read every one of ``paths`` once, keeping a refusal in place of the bytes it denied."""
    contents: dict[Path, bytes] = {}
    unreadable: dict[Path, str] = {}
    paths = tuple(paths)
    for path in paths:
        try:
            contents[path] = path.read_bytes()
        except OSError as error:
            unreadable[path] = f"{type(error).__name__}: {error}"
    return SourceSnapshot(
        paths=tuple(paths), contents=MappingProxyType(contents), unreadable=MappingProxyType(unreadable)
    )


def scanner_identity(*modules: ModuleType) -> str:
    """Digest the source of the modules that implement a scan, so a changed scanner is a new key."""
    entries: list[list[str]] = []
    for module in modules:
        source = module.__file__
        if source is None:
            raise ValueError(f"scanner module {module.__name__} has no source file")
        entries.append([module.__name__, hash_file(Path(source))[0]])
    return content_hash_hex({"schema": "cadrumo-scanner-identity/v1", "modules": sorted(entries)})


def _require_immutable_mapping(value: MappingProxyType[object, object], *, path: str) -> None:
    """Check each read-only mapping key before its associated value."""
    for key, item in value.items():
        require_immutable(key, path=f"{path} key {key!r}")
        require_immutable(item, path=f"{path}[{key!r}]")


def _require_immutable_model(value: BaseModel, *, path: str) -> None:
    """Check a frozen model's fields in their declaration order."""
    if not type(value).model_config.get("frozen", False):
        raise TypeError(f"{path} is a {type(value).__name__}, which is not a frozen model")
    for name in type(value).model_fields:
        require_immutable(getattr(value, name), path=f"{path}.{name}")


def require_immutable(value: object, *, path: str = "result") -> None:
    """Refuse ``value`` unless every part of it is immutable.

    Accepted: ``None``, numbers, strings, bytes, paths and enum members; tuples
    and frozensets of accepted values; read-only mappings
    (:class:`types.MappingProxyType`) whose keys and values are accepted; and
    frozen dataclasses and frozen pydantic models whose fields are accepted.

    Raises:
        TypeError: Naming the first mutable part found.
    """
    if isinstance(value, _IMMUTABLE_ATOMS):
        return
    if isinstance(value, tuple | frozenset):
        for index, item in enumerate(cast("Iterable[object]", value)):
            require_immutable(item, path=f"{path}[{index}]")
        return
    if isinstance(value, MappingProxyType):
        _require_immutable_mapping(cast("MappingProxyType[object, object]", value), path=path)
        return
    if isinstance(value, BaseModel):
        _require_immutable_model(value, path=path)
        return
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        if not getattr(getattr(type(value), "__dataclass_params__", None), "frozen", False):
            raise TypeError(f"{path} is a {type(value).__name__}, which is not a frozen dataclass")
        for field in dataclasses.fields(value):
            require_immutable(getattr(value, field.name), path=f"{path}.{field.name}")
        return
    raise TypeError(f"{path} is a mutable {type(value).__name__}; a shared scan result must be immutable")


def shared_snapshot_scan_result[T](
    kind: str,
    *,
    root: Path,
    inputs: Callable[[], Iterable[Path]],
    scanner: str,
    compute: Callable[[SourceSnapshot], T],
    cache_root: Path | None = None,
    publish_if: Callable[[T], bool] | None = None,
) -> T:
    """Return ``compute`` over one snapshot of ``inputs``, computing it only if no process in this run has.

    Args:
        kind: The scan's name, one path segment; also the artifact kind.
        root: The tree every input lies under; inputs are keyed by their path relative to it.
        inputs: Enumerates exactly the files the scan reads, by the scan's own inclusion policy.
        scanner: :func:`scanner_identity` of the modules implementing the scan.
        compute: Performs the scan over the snapshot it is given and reads no input any other way.
            Its result must satisfy :func:`require_immutable`.
        cache_root: The artifact cache root; the run's own when omitted.
        publish_if: Whether a computed result may be shared. A result it declines -- an
            environmental failure such as a timeout, which says nothing about the inputs -- is
            returned to this caller only, and the next process computes afresh.

    Returns:
        The immutable result, the same object for every caller in this process.

    Raises:
        TypeError: When the computed result is not immutable.
    """
    snapshot = take_snapshot(inputs())
    files = sorted(
        [_relative(root, path), hashlib.sha256(content).hexdigest()] for path, content in snapshot.contents.items()
    )
    refused = sorted([_relative(root, path), reason] for path, reason in snapshot.unreadable.items())
    digest = content_hash_hex(
        {
            "schema": "cadrumo-snapshot-inputs/v2",
            "paths": [_relative(root, path) for path in snapshot.paths],
            "files": files,
            "unreadable": refused,
        }
    )
    key = _key(kind, digest, scanner)

    def produce() -> object:
        return _admitted(compute(snapshot), publish_if)

    return cast("T", _shared(kind, key, produce, cache_root=cache_root))


def shared_scan_result[T](
    kind: str,
    *,
    root: Path,
    inputs: Callable[[], Iterable[Path]],
    scanner: str,
    compute: Callable[[], T],
    cache_root: Path | None = None,
    publish_if: Callable[[T], bool] | None = None,
) -> T:
    """Return the scan of ``inputs`` by ``scanner``, computing it only if no process in this run has.

    For a scanner that reads the tree itself; prefer :func:`shared_snapshot_scan_result`.

    Args:
        kind: The scan's name, one path segment; also the artifact kind.
        root: The tree every input lies under; inputs are keyed by their path relative to it.
        inputs: Enumerates exactly the files the scan reads, by the scan's own inclusion policy.
            Called before the scan and again after it.
        scanner: :func:`scanner_identity` of the modules implementing the scan.
        compute: Performs the scan. Its result must satisfy :func:`require_immutable`.
        cache_root: The artifact cache root; the run's own when omitted.
        publish_if: Whether a computed result may be shared. A result it declines -- an
            environmental failure such as a timeout, which says nothing about the inputs -- is
            returned to this caller only, and the next process computes afresh.

    Returns:
        The immutable result, the same object for every caller in this process.

    Raises:
        TypeError: When the computed result is not immutable.
    """
    key = _key(kind, file_inputs_digest(kind, root, inputs()), scanner)

    def produce() -> object:
        result = compute()
        require_immutable(result)
        if _key(kind, file_inputs_digest(kind, root, inputs()), scanner) != key:
            raise _UnpublishedResultError(result)
        return _admitted(result, publish_if)

    return cast("T", _shared(kind, key, produce, cache_root=cache_root))


def _shared(kind: str, key: str, produce: Callable[[], object], *, cache_root: Path | None) -> object:
    remembered = _memo.get((kind, key))
    if remembered is not None:
        return remembered

    def publish(destination: Path) -> None:
        result = produce()
        require_immutable(result)
        payload = _dumps(result)
        (destination / _RESULT_NAME).write_bytes(payload)
        (destination / _DIGEST_NAME).write_text(hashlib.sha256(payload).hexdigest(), encoding="ascii")

    try:
        artifact = run_artifact(kind, key, publish=publish, verify=_verified, cache_root=cache_root)
    except _UnpublishedResultError as moved:
        return moved.result
    try:
        payload = (artifact.root / _RESULT_NAME).read_bytes()
    except FileNotFoundError:
        # Retired by a newer publication between verification and this read;
        # the entry is published again rather than served from nowhere.
        return _shared(kind, key, produce, cache_root=cache_root)
    result = _ResultUnpickler(io.BytesIO(payload)).load()
    require_immutable(result)
    _memo[(kind, key)] = result
    return result


def _admitted[T](result: T, publish_if: Callable[[T], bool] | None) -> T:
    if publish_if is not None and not publish_if(result):
        raise _UnpublishedResultError(result)
    return result


def _relative(root: Path, path: Path) -> str:
    return PurePosixPath(*path.relative_to(root).parts).as_posix()


def _key(kind: str, inputs_digest: str, scanner: str) -> str:
    payload = {"schema": "cadrumo-shared-scan/v1", "kind": kind, "inputs": inputs_digest, "scanner": scanner}
    return content_hash_hex(payload)[:_KEY_LENGTH]


def _verified(entry: Path) -> bool:
    try:
        recorded = (entry / _DIGEST_NAME).read_text(encoding="ascii").strip()
        return hashlib.sha256((entry / _RESULT_NAME).read_bytes()).hexdigest() == recorded
    except OSError:
        return False


def _read_only_mapping(items: dict[object, object]) -> MappingProxyType[object, object]:
    """Rebuild a read-only mapping on unpickling; :mod:`pickle` cannot name the mappingproxy type itself."""
    return MappingProxyType(items)


def _reduce_read_only_mapping(
    mapping: MappingProxyType[object, object],
) -> tuple[Callable[[dict[object, object]], MappingProxyType[object, object]], tuple[dict[object, object]]]:
    """Pickle a read-only mapping as the mapping it wraps."""
    return _read_only_mapping, (dict(mapping),)


class _ResultUnpickler(pickle.Unpickler):
    """Reads back only first-party types and the standard immutable values a scan result is built from.

    The entry is this run's own and its digest was verified, so the restriction
    is not the integrity check; it keeps a foreign file that also forged its
    digest from naming arbitrary callables.
    """

    @override
    def find_class(self, module: str, name: str) -> object:
        # Judged by top-level package: the defining module of a stdlib class moves
        # between releases (``pathlib.Path`` pickles as ``pathlib._local`` on 3.13).
        top_level = module.split(".", 1)[0]
        if top_level in _TRUSTED_MODULES or top_level in _TRUSTED_PACKAGES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"a shared scan result may not name {module}.{name}")


def _dumps(result: object) -> bytes:
    buffer = io.BytesIO()
    pickler = pickle.Pickler(buffer, protocol=pickle.HIGHEST_PROTOCOL)
    pickler.dispatch_table = {**copyreg.dispatch_table, MappingProxyType: _reduce_read_only_mapping}
    pickler.dump(result)
    return buffer.getvalue()
