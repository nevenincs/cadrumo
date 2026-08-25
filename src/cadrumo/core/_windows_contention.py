"""The Windows error codes a peer's open handle produces, declared once.

Windows refuses to remove or replace a file while another process holds a
handle to it. Two codes carry that refusal, and CPython surfaces both as
:class:`PermissionError`: ``ERROR_SHARING_VIOLATION`` (32) while a peer holds
the file open, and ``ERROR_ACCESS_DENIED`` (5) once a delete against it is
already pending. Both clear when the last handle closes.

Windows does not distinguish either from a denying ACL or a read-only attribute
at the operation boundary, so the code alone never proves contention -- a retry
budget is what separates them: a transient block clears inside the window, and a
permanent one outlasts it. Each caller owns that budget, because the right
answer depends on what losing the race costs it.

Declared here rather than in either consumer because the two that need it
cannot share a module: :mod:`core._lockfile_unlink` imports
:mod:`core.logging`, and :mod:`core.bucket_pointer` is read during
``Settings()`` bootstrap and must not (its own comments record the circular
bootstrap that import recreates). This module imports nothing, so it is safe
from both.

Nothing is absorbed off Windows: ``winerror`` is absent there, so
:func:`is_windows_contention` is ``False`` for every POSIX ``EACCES``, which is
genuine and must propagate.
"""

from __future__ import annotations

WINDOWS_CONTENDED_ACCESS_ERRORS = frozenset({5, 32})
"""``ERROR_ACCESS_DENIED`` and ``ERROR_SHARING_VIOLATION``."""


def is_windows_contention(exc: OSError) -> bool:
    """Report whether ``exc`` is Windows refusing an operation a handle blocks.

    Args:
        exc: The raised OS error to classify.

    Returns:
        ``True`` when the error carries a Windows contention code. ``False``
        everywhere else, including every POSIX error, where no
        sharing-violation class exists to confuse with a genuine refusal.
    """
    return getattr(exc, "winerror", None) in WINDOWS_CONTENDED_ACCESS_ERRORS


__all__ = ["WINDOWS_CONTENDED_ACCESS_ERRORS", "is_windows_contention"]
