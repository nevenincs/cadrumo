"""The refusals the llama-server acquisition and staging raise."""

from __future__ import annotations


class LlamaServerError(ValueError):
    """The pinned llama-server cannot be admitted into the package."""


class ArchiveMismatchError(LlamaServerError):
    """An archive, an acquired tree or a receipt differs from the pin it must match."""


class GlibcFloorError(LlamaServerError):
    """A Linux archive needs a newer glibc than the package supports."""


class UnresolvedImportError(LlamaServerError):
    """A staged Windows image imports a library that is neither the operating system's nor in the program directory."""
