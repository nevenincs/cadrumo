"""Single boundary for reading bundled corpus and registry data.

Bundled trees live at ``cadrumo/_data/corpus/...`` and
``cadrumo/_data/registry/...`` inside the installed wheel via the
hatchling ``force-include`` configuration in ``pyproject.toml``. The
same prefix resolves to the in-tree top-level ``corpus/`` and
``registry/`` directories under an editable install because hatchling
honours the force-include mapping for both targets.

Callers MUST go through :func:`packaged_data` rather than computing the location
from ``__file__`` or a repo-root walk. Use :func:`bundled_path` when a
process-lifetime :class:`~pathlib.Path` is required, and :func:`as_path` for a
scoped materialised path. The data-root anchor is reserved for ``var/``
operator outputs in :mod:`cadrumo.core.config` and is not a valid resolution path
for read-only bundled data.

The corpus source binaries (``_data/corpus/**/*.{pdf,xls,xlsx}``) are excluded
from the command-bearing ``cadrumo`` wheel and shipped in two mandatory
``cadrumo_data`` companion distributions whose joined layout mirrors
``cadrumo/_data``. :func:`resolve_corpus_binary` is the single
``importlib.resources`` seam that resolves such a binary from the ``cadrumo``
tree first and then the companion namespace, so a full checkout and an installed
three-wheel cohort read a corpus binary uniformly. A missing companion remains
a not-present signal (``None``) at this low-level resource boundary; the
catalogue integrity boundary turns that signal into a hard failure.

Because the split is by file SUFFIX rather than by directory, a corpus
directory is a single logical tree whose members can materialise under
different installed roots: a design workbook resolves under ``cadrumo_data``
while the hand-authored declarations that annotate it stay under ``cadrumo``.
A reader that reaches a neighbouring file with :meth:`pathlib.Path.with_name`
therefore sees only the root its starting file happened to come from.
:func:`bundled_data_roots` and :func:`resolve_data_root_copies` are the seam
that spans them, so a neighbour is located by its position in the logical tree
rather than by which distribution happens to carry the file next to it.
"""

from __future__ import annotations

import atexit
import importlib
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from functools import cache
from importlib.resources import as_file, files  # nosemgrep
from importlib.resources.abc import Traversable  # nosemgrep
from pathlib import Path

from ..product_identity import PRODUCT_IDENTITY

_PACKAGE_DATA: Traversable = files(PRODUCT_IDENTITY.python_package).joinpath("_data")
_RESOURCE_STACK: ExitStack = ExitStack()
atexit.register(_RESOURCE_STACK.close)

_COMPANION_PACKAGE = PRODUCT_IDENTITY.companion_namespace


def packaged_data(*parts: str) -> Traversable:
    """Return a Traversable rooted at ``cadrumo/_data/<parts...>``.

    Args:
        *parts: One or more path segments joined under the bundled
            data root. Empty call returns the bundled root itself.

    Returns:
        A :class:`importlib.resources.abc.Traversable` that callers
        may read via ``read_text`` / ``read_bytes`` / ``open`` or
        iterate via ``iterdir``. Use :func:`as_path` when a real
        on-disk :class:`pathlib.Path` is required.
    """
    node: Traversable = _PACKAGE_DATA
    for part in parts:
        node = node.joinpath(part)
    return node


def bundled_path(*parts: str) -> Path:
    """Return a process-lifetime :class:`pathlib.Path` for a bundled subtree.

    Suitable for module-level Settings field defaults that need a real
    on-disk path at import time. The underlying ``as_file`` context is
    entered into a module-level :class:`contextlib.ExitStack` that is
    closed at interpreter exit. Under the supported install modes
    (editable hatchling, built wheel) the materialisation is a no-op:
    ``importlib.resources.files("cadrumo")`` resolves to a real on-disk
    directory and ``as_file`` returns the path unchanged.

    Args:
        *parts: Path segments joined under the bundled data root.

    Returns:
        A :class:`pathlib.Path` whose lifetime spans the running
        process. Callers MUST treat the path as read-only.
    """
    return _RESOURCE_STACK.enter_context(as_file(packaged_data(*parts)))


@contextmanager
def as_path(node: Traversable) -> Generator[Path]:
    """Materialise ``node`` as a real on-disk path for the lifetime of the context.

    ``importlib.resources.as_file`` extracts the resource to a
    temporary location when the underlying loader does not already
    expose a filesystem path. Under an editable install (hatchling
    force-include against the source tree) the materialised path is
    the in-tree location with no copy.

    Args:
        node: A Traversable returned by :func:`packaged_data` (or a
            descendant obtained via ``joinpath``).

    Yields:
        A :class:`pathlib.Path` that is valid only inside the
        ``with`` block. Callers MUST NOT retain the path beyond the
        context manager's exit.
    """
    with as_file(node) as path:
        yield path


def _traversable_is_file(node: Traversable) -> bool:
    """Return whether ``node`` resolves to a readable file, swallowing loader errors."""
    try:
        return node.is_file()
    except (OSError, ValueError):
        return False


def _companion_root() -> Traversable | None:
    """Return the ``cadrumo_data`` companion package root, or ``None`` when it is absent.

    The companion namespace is supplied by two mandatory distributions. A
    broken or deliberately dependency-pruned installation may still omit it;
    this low-level helper maps that import-family error to ``None`` so the
    catalogue integrity boundary can report the missing source precisely.
    """
    try:
        return files(_COMPANION_PACKAGE)
    except (ImportError, TypeError):
        return None


def resolve_companion_binary(*parts: str) -> Path | None:
    """Resolve a corpus binary from the mandatory ``cadrumo_data`` namespace.

    Args:
        *parts: Segments under the companion's mirrored ``_data`` root
            (e.g. ``"corpus", "manuals", "renta", "2024", "source.pdf"``).

    Returns:
        A read-only :class:`pathlib.Path` valid for the process lifetime when
        the joined companion namespace carries the binary, else ``None``. The
        namespace mirrors ``cadrumo/_data``, so the segments are identical to
        the ones :func:`packaged_data` takes.
    """
    root = _companion_root()
    if root is None:
        return None
    node: Traversable = root.joinpath("_data")
    for part in parts:
        node = node.joinpath(part)
    if not _traversable_is_file(node):
        return None
    return _RESOURCE_STACK.enter_context(as_file(node))


def resolve_corpus_binary(*parts: str) -> Path | None:
    """Resolve a bundled corpus binary, the ``cadrumo`` tree first then the ``cadrumo_data`` companion.

    ``parts`` are the segments under ``_data`` (e.g. ``"corpus",
    "aeat_official", "disenos_registro", "modelo_100", "files", "dr.xlsx"``).
    The command-bearing Cadrumo wheel excludes
    ``_data/corpus/**/*.{pdf,xls,xlsx}``; the mandatory ``cadrumo_data``
    namespace carries exactly those binaries under mirrored paths. This is the
    single ``importlib.resources`` seam that unifies the full-checkout read
    (binary in the ``cadrumo`` tree) and the installed-cohort read (binary in a
    companion distribution).

    Returns:
        A read-only :class:`pathlib.Path` valid for the process lifetime when
        the binary is present under either root, else ``None`` when it resolves
        under neither.
    """
    primary = packaged_data(*parts)
    if _traversable_is_file(primary):
        return _RESOURCE_STACK.enter_context(as_file(primary))
    return resolve_companion_binary(*parts)


def _companion_data_roots() -> tuple[Path, ...]:
    """Return the mirrored ``_data`` directory of every installed companion portion.

    Read from the namespace package's ``__path__`` rather than from the
    ``MultiplexedPath`` :func:`files` returns, because the portions must stay
    distinguishable: a file present under two portions with different content is
    a defect a caller has to be able to see, and a multiplexed join answers with
    the first hit and hides the second.

    Returns:
        One :class:`pathlib.Path` per installed portion that carries a ``_data``
        directory, in ``__path__`` order. Empty when the companion namespace is
        absent, which is the same not-present signal :func:`resolve_companion_binary`
        reports.
    """
    try:
        module = importlib.import_module(_COMPANION_PACKAGE)
    except (ImportError, TypeError):
        return ()
    spec = module.__spec__
    if spec is None or spec.submodule_search_locations is None:
        return ()
    # The search locations of a namespace package recompute from ``sys.path``,
    # so an installation that gains or loses a portion is seen without a restart.
    roots = [Path(portion) / "_data" for portion in spec.submodule_search_locations]
    return tuple(root for root in roots if root.is_dir())


@cache
def _primary_data_root() -> Path:
    """Return the ``cadrumo`` tree's ``_data`` root, materialised once per process.

    Cached because :func:`bundled_path` enters an ``as_file`` context on the
    module-level :class:`~contextlib.ExitStack` on every call, and this root is
    consulted once per annotation lookup. The underlying Traversable is fixed at
    import, so one materialisation is the whole answer.
    """
    return bundled_path()


def bundled_data_roots() -> tuple[Path, ...]:
    """Return every installed root the bundled ``_data`` tree materialises under.

    The ``cadrumo`` tree comes first and is always present; each installed
    ``cadrumo_data`` portion follows. Together they are the roots a single
    logical ``_data``-relative path may resolve under, which is what makes the
    suffix-partitioned corpus one tree rather than three.

    Returns:
        The ordered roots, ``cadrumo`` first.
    """
    return (_primary_data_root(), *_companion_data_roots())


def resolve_data_root_copies(path: Path) -> tuple[Path, ...]:
    """Return every existing copy of ``path`` across the bundled ``_data`` roots.

    ``path`` is an ordinary filesystem path a caller computed by navigating from
    some other bundled file -- a sibling annotation, a per-directory declaration.
    Whichever root ``path`` currently sits under, the same ``_data``-relative
    position is checked under every other root, so a file and its neighbour are
    found together even when the distribution split placed them apart.

    A ``path`` under no bundled root is left alone and answered from the
    filesystem: a temporary fixture or an operator-supplied file has no position
    in the logical tree, and inventing one for it would be a claim this seam
    cannot support.

    Args:
        path: The location to resolve, expressed in any one root's coordinates.

    Returns:
        Every existing copy, in :func:`bundled_data_roots` order, so the first
        entry is the ``cadrumo`` tree's copy whenever it has one. Empty when the
        file exists under no root. More than one entry means the same logical
        file is published by more than one distribution, which callers that
        cannot tolerate a silent winner must adjudicate.
    """
    roots = bundled_data_roots()
    relative: Path | None = None
    for root in roots:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        break
    if relative is None:
        return (path,) if path.is_file() else ()
    return tuple(candidate for root in roots if (candidate := root / relative).is_file())
