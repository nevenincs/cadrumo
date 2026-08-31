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
"""

from __future__ import annotations

import atexit
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
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
def as_path(node: Traversable) -> Iterator[Path]:
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
