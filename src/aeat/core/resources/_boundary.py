"""Single boundary for reading bundled corpus and registry data.

Bundled trees live at ``aeat/_data/corpus/...`` and
``aeat/_data/registry/...`` inside the installed wheel via the
hatchling ``force-include`` configuration in ``pyproject.toml``. The
same prefix resolves to the in-tree top-level ``corpus/`` and
``registry/`` directories under an editable install because hatchling
honours the force-include mapping for both targets.

Callers MUST go through :func:`packaged_data` rather than computing the location
from ``__file__`` or a ``PROJECT_ROOT`` walk. Use :func:`bundled_path` when a
process-lifetime :class:`~pathlib.Path` is required, and :func:`as_path` for a
scoped materialised path. The ``PROJECT_ROOT`` walk is reserved for ``var/``
operator outputs in :mod:`aeat.core.config` and is not a valid resolution path
for read-only bundled data.
"""

from __future__ import annotations

import atexit
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from importlib.resources import as_file, files  # nosemgrep
from importlib.resources.abc import Traversable  # nosemgrep
from pathlib import Path

_PACKAGE_DATA: Traversable = files("aeat").joinpath("_data")
_RESOURCE_STACK: ExitStack = ExitStack()
atexit.register(_RESOURCE_STACK.close)


def packaged_data(*parts: str) -> Traversable:
    """Return a Traversable rooted at ``aeat/_data/<parts...>``.

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
    ``importlib.resources.files("aeat")`` resolves to a real on-disk
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
