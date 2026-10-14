"""The file name of a host path an operation recorded, for results an automation receives."""

from __future__ import annotations

from pathlib import PureWindowsPath


def host_path_file_name(host_path: str) -> str | None:
    """Return the last component of ``host_path`` on either path convention, or ``None`` when it has none."""
    # The path was typed on whichever machine recorded it. The Windows reading
    # splits on both separators, so it finds the name in either form.
    return PureWindowsPath(host_path).name or None


__all__ = ["host_path_file_name"]
