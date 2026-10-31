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

A file edited while the scan reads it would publish a result under a key it no
longer matches. The inputs are digested again afterwards, and a scan whose
inputs moved is returned to its caller without being published.
"""

from __future__ import annotations

import copyreg
import dataclasses
import enum
import hashlib
import io
import pickle
from collections.abc import Callable, Iterable
from pathlib import Path, PurePath
from types import MappingProxyType, ModuleType
from typing import Final, cast, override

from cadrumo.core.hashing import content_hash_hex, hash_file
from cadrumo.tests.run_artifact import file_inputs_digest, run_artifact

__all__ = ["ScanInputsChangedError", "require_immutable", "scanner_identity", "shared_scan_result"]

_RESULT_NAME: Final = "result.pickle"
_DIGEST_NAME: Final = "result.sha256"
_KEY_LENGTH: Final = 32

_IMMUTABLE_ATOMS: Final = (type(None), bool, int, float, complex, str, bytes, PurePath, enum.Enum)

_TRUSTED_MODULES: Final = frozenset({"builtins", "pathlib", "types", "collections", "enum", "decimal"})
_TRUSTED_PACKAGES: Final = frozenset({"cadrumo", "dev"})

_memo: dict[tuple[str, str], object] = {}


class ScanInputsChangedError(RuntimeError):
    """The scanned files changed while the scan read them, so its result names no single input."""

    def __init__(self, result: object) -> None:
        """Carry the scan's result back to the caller, which uses it without publishing it."""
        super().__init__("the scanned files changed while they were read")
        self.result = result


def scanner_identity(*modules: ModuleType) -> str:
    """Digest the source of the modules that implement a scan, so a changed scanner is a new key."""
    entries: list[list[str]] = []
    for module in modules:
        source = module.__file__
        if source is None:
            raise ValueError(f"scanner module {module.__name__} has no source file")
        entries.append([module.__name__, hash_file(Path(source))[0]])
    return content_hash_hex({"schema": "cadrumo-scanner-identity/v1", "modules": sorted(entries)})


def require_immutable(value: object, *, path: str = "result") -> None:
    """Refuse ``value`` unless every part of it is immutable.

    Accepted: ``None``, numbers, strings, bytes, paths and enum members; tuples
    and frozensets of accepted values; read-only mappings
    (:class:`types.MappingProxyType`) whose keys and values are accepted; and
    frozen dataclasses whose fields are accepted.

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
        for key, item in cast("MappingProxyType[object, object]", value).items():
            require_immutable(key, path=f"{path} key {key!r}")
            require_immutable(item, path=f"{path}[{key!r}]")
        return
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        if not getattr(getattr(type(value), "__dataclass_params__", None), "frozen", False):
            raise TypeError(f"{path} is a {type(value).__name__}, which is not a frozen dataclass")
        for field in dataclasses.fields(value):
            require_immutable(getattr(value, field.name), path=f"{path}.{field.name}")
        return
    raise TypeError(f"{path} is a mutable {type(value).__name__}; a shared scan result must be immutable")


def shared_scan_result[T](
    kind: str,
    *,
    root: Path,
    inputs: Callable[[], Iterable[Path]],
    scanner: str,
    compute: Callable[[], T],
    cache_root: Path | None = None,
) -> T:
    """Return the scan of ``inputs`` by ``scanner``, computing it only if no process in this run has.

    Args:
        kind: The scan's name, one path segment; also the artifact kind.
        root: The tree every input lies under; inputs are keyed by their path relative to it.
        inputs: Enumerates exactly the files the scan reads, by the scan's own inclusion policy.
            Called before the scan and again after it.
        scanner: :func:`scanner_identity` of the modules implementing the scan.
        compute: Performs the scan. Its result must satisfy :func:`require_immutable`.
        cache_root: The artifact cache root; the run's own when omitted.

    Returns:
        The immutable result, the same object for every caller in this process.

    Raises:
        TypeError: When the computed result is not immutable.
    """
    key = _key(kind, root, inputs, scanner)
    remembered = _memo.get((kind, key))
    if remembered is not None:
        return cast("T", remembered)

    def publish(destination: Path) -> None:
        result = compute()
        require_immutable(result)
        if _key(kind, root, inputs, scanner) != key:
            raise ScanInputsChangedError(result)
        payload = _dumps(result)
        (destination / _RESULT_NAME).write_bytes(payload)
        (destination / _DIGEST_NAME).write_text(hashlib.sha256(payload).hexdigest(), encoding="ascii")

    try:
        artifact = run_artifact(kind, key, publish=publish, verify=_verified, cache_root=cache_root)
    except ScanInputsChangedError as moved:
        return cast("T", moved.result)
    result = _ResultUnpickler(io.BytesIO((artifact.root / _RESULT_NAME).read_bytes())).load()
    require_immutable(result)
    _memo[(kind, key)] = result
    return cast("T", result)


def _key(kind: str, root: Path, inputs: Callable[[], Iterable[Path]], scanner: str) -> str:
    files = file_inputs_digest(kind, root, inputs())
    return content_hash_hex({"schema": "cadrumo-shared-scan/v1", "files": files, "scanner": scanner})[:_KEY_LENGTH]


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
        if module in _TRUSTED_MODULES or module.split(".", 1)[0] in _TRUSTED_PACKAGES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"a shared scan result may not name {module}.{name}")


def _dumps(result: object) -> bytes:
    buffer = io.BytesIO()
    pickler = pickle.Pickler(buffer, protocol=pickle.HIGHEST_PROTOCOL)
    pickler.dispatch_table = {**copyreg.dispatch_table, MappingProxyType: _reduce_read_only_mapping}
    pickler.dump(result)
    return buffer.getvalue()
