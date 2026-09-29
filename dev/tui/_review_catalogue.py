"""What each review run on disk holds right now, read while a render writes it.

A full render takes well over an hour and writes its manifest only after the
last frame, so a reviewer following a live run cannot wait for the manifest to
learn which frames exist. The catalogue reads each run's ``png/`` directory
instead, and consults the manifest only for what the directory cannot say --
the harness's geometry findings and the glyphs the raster font lacked -- and
only where the manifest's recorded digest proves it describes the image on
disk rather than an earlier render of the same frame.

The rasteriser writes a PNG in place, so a scan can meet a file half written.
A frame is published only once its file has gone :data:`SETTLE_SECONDS`
without changing; until then the previous settled version, if any, stands.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Final

from ._artifacts import (
    MANIFEST_NAME,
    Manifest,
    ManifestVersionError,
    RenderedFrame,
    ThemeName,
    read_manifest,
)
from ._viewports import VIEWPORTS, ViewportName

SETTLE_SECONDS: Final[float] = 1.5
"""How long a file must go unmodified before it counts as fully written."""

_PNG_SUFFIX: Final[str] = ".png"
_TEXT_SUFFIX: Final[str] = ".txt"
_STEM_SEPARATOR: Final[str] = "__"
_PNG_SIGNATURE: Final[bytes] = b"\x89PNG\r\n\x1a\n"
_VIEWPORT_ORDER: Final[dict[ViewportName, int]] = {name: index for index, name in enumerate(ViewportName)}
_THEME_ORDER: Final[dict[ThemeName, int]] = {name: index for index, name in enumerate(ThemeName)}


@dataclass(frozen=True)
class FrameIdentity:
    """Which surface, grid and appearance a file name describes."""

    surface: str
    viewport: ViewportName
    theme: ThemeName

    @property
    def key(self) -> str:
        """The identity a rendered frame carries in the manifest, and a note is filed under."""
        return f"{self.surface}/{self.viewport}/{self.theme}"


def parse_stem(stem: str) -> FrameIdentity | None:
    """Read ``surface__viewport__theme`` back out of a frame file name.

    Split from the right: a surface name may itself contain the separator,
    while the viewport and theme vocabularies never do.
    """
    parts = stem.rsplit(_STEM_SEPARATOR, 2)
    if len(parts) != 3 or not parts[0]:
        return None
    try:
        return FrameIdentity(surface=parts[0], viewport=ViewportName(parts[1]), theme=ThemeName(parts[2]))
    except ValueError:
        return None


@dataclass(frozen=True)
class CatalogueFrame:
    """One settled PNG in one run."""

    run: str
    stem: str
    identity: FrameIdentity
    png: Path
    size: int
    modified_ns: int
    png_sha256: str
    width: int
    height: int

    @property
    def key(self) -> str:
        """The frame identity, stable across re-renders."""
        return self.identity.key


@dataclass(frozen=True)
class RunView:
    """Everything one run directory holds at the last scan."""

    name: str
    directory: Path
    frames: tuple[CatalogueFrame, ...]
    texts: frozenset[str]
    """Stems whose harness text reading is on disk."""
    unrecognised: tuple[str, ...]
    """PNG names that do not parse as a frame; reported, never served."""
    manifest: Manifest | None
    manifest_error: str | None
    by_stem: Mapping[str, CatalogueFrame] = field(repr=False)
    records: Mapping[str, RenderedFrame] = field(repr=False)
    """Manifest records by frame key, kept only where the recorded digest is
    the digest of the image on disk now."""

    def frame(self, stem: str) -> CatalogueFrame | None:
        """The settled frame with this file stem, if the run holds one."""
        return self.by_stem.get(stem)

    def recorded(self, frame: CatalogueFrame) -> RenderedFrame | None:
        """The manifest's record of this frame, only when it describes these exact pixels."""
        return self.records.get(frame.key)

    def text_path(self, stem: str) -> Path | None:
        """The harness text reading for a frame, if one was written."""
        if stem not in self.texts:
            return None
        return self.directory / "text" / f"{stem}{_TEXT_SUFFIX}"


@dataclass(frozen=True)
class _RunScan:
    view: RunView
    manifest_modified_ns: int | None


class ReviewCatalogue:
    """The live contents of every run under one runs directory.

    :meth:`refresh` rescans and reports whether anything changed; readers get
    immutable :class:`RunView` values, so a request thread never observes a
    scan half applied.
    """

    def __init__(
        self,
        runs_dir: Path,
        *,
        only: str | None = None,
        settle_seconds: float = SETTLE_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Watch ``runs_dir``, or only the run named ``only`` inside it.

        ``clock`` is injectable so settling can be tested without sleeping.
        """
        self.runs_dir = runs_dir
        self._only = only
        self._settle_seconds = settle_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._scans: dict[str, _RunScan] = {}

    def runs(self) -> tuple[RunView, ...]:
        """Every run the last scan found, by name."""
        with self._lock:
            return tuple(self._scans[name].view for name in sorted(self._scans))

    def run(self, name: str) -> RunView | None:
        """The last scan of one run."""
        with self._lock:
            scan = self._scans.get(name)
        return None if scan is None else scan.view

    def refresh(self) -> bool:
        """Rescan every run; return whether any run's contents changed."""
        with self._lock:
            previous = dict(self._scans)
        scans: dict[str, _RunScan] = {}
        for directory in _run_directories(self.runs_dir):
            if self._only is not None and directory.name != self._only:
                continue
            scans[directory.name] = self._scan_run(directory, previous.get(directory.name))
        changed = _signature(scans) != _signature(previous)
        with self._lock:
            self._scans = scans
        return changed

    def _settled(self, modified_ns: int) -> bool:
        return self._clock() - modified_ns / 1e9 >= self._settle_seconds

    def _scan_run(self, directory: Path, previous: _RunScan | None) -> _RunScan:
        known = {frame.stem: frame for frame in previous.view.frames} if previous else {}
        frames: list[CatalogueFrame] = []
        unrecognised: list[str] = []
        for entry in _files(directory / "png", _PNG_SUFFIX):
            stem = entry.name.removesuffix(_PNG_SUFFIX)
            identity = parse_stem(stem)
            if identity is None:
                unrecognised.append(entry.name)
                continue
            frame = self._frame(directory.name, stem, identity, entry, known.get(stem))
            if frame is not None:
                frames.append(frame)
        frames.sort(key=_frame_order)
        texts = frozenset(entry.name.removesuffix(_TEXT_SUFFIX) for entry in _files(directory / "text", _TEXT_SUFFIX))

        manifest, manifest_error, manifest_modified_ns = self._manifest(directory, previous)
        digests = {frame.key: frame.png_sha256 for frame in frames}
        records = (
            {}
            if manifest is None
            else {record.key: record for record in manifest.frames if digests.get(record.key) == record.png_sha256}
        )
        view = RunView(
            name=directory.name,
            directory=directory,
            frames=tuple(frames),
            texts=texts,
            unrecognised=tuple(sorted(unrecognised)),
            manifest=manifest,
            manifest_error=manifest_error,
            by_stem={frame.stem: frame for frame in frames},
            records=records,
        )
        return _RunScan(view=view, manifest_modified_ns=manifest_modified_ns)

    def _frame(
        self,
        run: str,
        stem: str,
        identity: FrameIdentity,
        entry: os.DirEntry[str],
        previous: CatalogueFrame | None,
    ) -> CatalogueFrame | None:
        try:
            stat = entry.stat()
        except OSError:
            return previous
        if previous is not None and (previous.size, previous.modified_ns) == (stat.st_size, stat.st_mtime_ns):
            return previous
        if not self._settled(stat.st_mtime_ns):
            return previous
        try:
            payload = Path(entry.path).read_bytes()
        except OSError:
            return previous
        dimensions = _png_dimensions(payload)
        if dimensions is None:
            return previous
        return CatalogueFrame(
            run=run,
            stem=stem,
            identity=identity,
            png=Path(entry.path),
            size=stat.st_size,
            modified_ns=stat.st_mtime_ns,
            png_sha256=sha256(payload).hexdigest(),
            width=dimensions[0],
            height=dimensions[1],
        )

    def _manifest(
        self,
        directory: Path,
        previous: _RunScan | None,
    ) -> tuple[Manifest | None, str | None, int | None]:
        try:
            modified_ns = (directory / MANIFEST_NAME).stat().st_mtime_ns
        except OSError:
            return None, None, None
        if previous is not None and previous.manifest_modified_ns == modified_ns:
            return previous.view.manifest, previous.view.manifest_error, modified_ns
        if not self._settled(modified_ns):
            if previous is None:
                return None, None, None
            return previous.view.manifest, previous.view.manifest_error, previous.manifest_modified_ns
        try:
            return read_manifest(directory), None, modified_ns
        except (ManifestVersionError, ValueError, OSError) as refusal:
            return None, str(refusal).splitlines()[0], modified_ns


def _run_directories(runs_dir: Path) -> tuple[Path, ...]:
    """Run directories that hold frames or a manifest; a bare directory is not a run yet."""
    try:
        candidates = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    except OSError:
        return ()
    return tuple(path for path in candidates if (path / "png").is_dir() or (path / MANIFEST_NAME).is_file())


def _files(directory: Path, suffix: str) -> tuple[os.DirEntry[str], ...]:
    try:
        with os.scandir(directory) as entries:
            return tuple(entry for entry in entries if entry.name.endswith(suffix) and entry.is_file())
    except OSError:
        return ()


def _png_dimensions(payload: bytes) -> tuple[int, int] | None:
    """Width and height from the IHDR chunk, which the PNG format fixes at bytes 16-24."""
    if len(payload) < 24 or not payload.startswith(_PNG_SIGNATURE) or payload[12:16] != b"IHDR":
        return None
    return int.from_bytes(payload[16:20], "big"), int.from_bytes(payload[20:24], "big")


def _frame_order(frame: CatalogueFrame) -> tuple[str, int, int]:
    identity = frame.identity
    return identity.surface, _VIEWPORT_ORDER[identity.viewport], _THEME_ORDER[identity.theme]


def _signature(scans: Mapping[str, _RunScan]) -> tuple[object, ...]:
    return tuple(
        (
            name,
            tuple((frame.stem, frame.png_sha256) for frame in scan.view.frames),
            scan.view.texts,
            scan.view.unrecognised,
            scan.manifest_modified_ns,
            scan.view.manifest_error,
        )
        for name, scan in sorted(scans.items())
    )


def viewport_grid(viewport: ViewportName) -> tuple[int, int, str]:
    """Columns, rows and orientation of a viewport, from the one table that owns them."""
    shape = VIEWPORTS[viewport]
    return shape.columns, shape.rows, str(shape.orientation)


__all__ = [
    "SETTLE_SECONDS",
    "CatalogueFrame",
    "FrameIdentity",
    "ReviewCatalogue",
    "RunView",
    "parse_stem",
    "viewport_grid",
]
