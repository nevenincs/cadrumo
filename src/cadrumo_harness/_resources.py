"""Single boundary for reading this package's own bundled ``_data`` tree.

Mirrors the shape of ``cadrumo.core.resources.packaged_data``, rooted at
``cadrumo_harness``. Both packages ship in the ``cadrumo`` distribution and
resolve their bundled data through their respective package roots. This is a
Python data accessor; MCP exposure is defined by the current server tools.
"""

from __future__ import annotations

# nosemgrep: python.lang.compatibility.python37.python37-compatibility-importlib2
from importlib.resources import files  # nosemgrep
from importlib.resources.abc import Traversable  # nosemgrep

_PACKAGE_DATA: Traversable = files(__package__).joinpath("_data")


def packaged_data(*parts: str) -> Traversable:
    """Return a Traversable rooted at ``cadrumo_harness/_data/<parts...>``.

    Args:
        *parts: One or more path segments joined under the bundled
            data root. Empty call returns the bundled root itself.

    Returns:
        A :class:`importlib.resources.abc.Traversable` that callers
        may read via ``read_text`` / ``read_bytes`` / ``open`` or
        iterate via ``iterdir``.
    """
    node: Traversable = _PACKAGE_DATA
    for part in parts:
        node = node.joinpath(part)
    return node
