"""Shared test support for the outbound AEAT adapter packages.

Holds helpers used by more than one of the sibling test packages beneath
``adapters/outbound/aeat`` (``auth/tests``, ``browser/tests``, ``sede/tests``).
A helper needed by only one of them belongs in that package's own
``tests/_*_support.py``, not here.

Shared helpers are re-exported here so a sibling imports the package rather
than dotting into ``_process_support``: a cross-package reach into a private
module is what ``service-imports-via-top-level-reexports`` forbids, and the
import-hygiene gate counts every occurrence.
"""

from ._process_support import DEFAULT_PROCESS_EXIT_TIMEOUT_SECONDS, wait_for_process_exit

__all__ = ["DEFAULT_PROCESS_EXIT_TIMEOUT_SECONDS", "wait_for_process_exit"]
