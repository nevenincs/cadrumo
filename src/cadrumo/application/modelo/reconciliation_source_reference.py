"""How a reconciliation's evidence reference is shown to an agent."""

from __future__ import annotations

from typing import Final

from ..operations.host_path_name import host_path_file_name

SECURE_OBJECT_REFERENCE_PREFIX: Final = "secure-object://"
"""Starts the handle of evidence held in the profile's encrypted store, which names no directory."""


def agent_source_reference(source: str) -> tuple[str, bool]:
    """Return what an agent holds of one recorded evidence reference, and whether a directory was withheld.

    A reference recorded for evidence in the profile's store names no host
    directory and is returned as it is. A path the person typed for a file on
    this machine is reduced to its file name, empty when it has none.
    """
    if source.startswith(SECURE_OBJECT_REFERENCE_PREFIX):
        return source, False
    return host_path_file_name(source) or "", True


__all__ = ["SECURE_OBJECT_REFERENCE_PREFIX", "agent_source_reference"]
