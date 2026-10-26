"""Release the application's configure-once logging latch for the docs engine.

The documentation engine is a long-lived host that imports the application and
only AFTERWARDS pins its isolated scratch storage, then re-pins it again per
captured sequence. :func:`cadrumo.core.logging.configure_logging` is idempotent
behind a module-global latch, so the FIRST call in the process fixes both
handlers for the process lifetime: the stream handler to whatever ``sys.stderr``
then was, and the rotating file handler to whatever the storage taxonomy then
resolved. Without a reset the engine keeps writing to the pre-pin destination.

This helper lives here, at the engine that needs it, rather than in the
application: the application's own entrypoints configure logging exactly once
and never re-point either axis, so a reset seam shipped in ``src/cadrumo``
would be product surface no product path reaches.

Handlers are CLOSED, not merely detached. The rotating file handler holds an
open OS handle on its log file, and on Windows an unclosed handle keeps that
file locked against the rename its own rollover later attempts.

This is not a compatibility path: it re-derives the CURRENT configuration from
the CURRENT environment on the next
:func:`~cadrumo.core.logging.configure_logging` call. Callers that change a
logging-relevant setting must reset the settings cache first.
"""

from __future__ import annotations

import contextlib
import logging


def allow_logging_reconfiguration() -> None:
    """Detach and close the installed handlers, then release the latch."""
    from cadrumo.core import logging as cadrumo_logging

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        with contextlib.suppress(OSError, ValueError):
            handler.close()
    # The latch is the application's own private process state; the docs engine
    # is the sole host that legitimately re-points logging mid-process, and
    # clearing it here keeps that development-only need out of the product.
    cadrumo_logging._configured = False
