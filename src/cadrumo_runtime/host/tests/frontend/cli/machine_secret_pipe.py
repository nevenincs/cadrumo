"""Hand a command its machine-secret payload through an in-process descriptor.

The profile passphrase already uses standard input in these invocations, so the
command's own payload travels on the descriptor channel. The command reads and closes
the read end; the write end is closed here once the payload is in the pipe.
"""

from __future__ import annotations

import json
import os


def machine_secret_descriptor_option(payload: dict[str, str]) -> tuple[str, str]:
    """Return ``("--secrets-fd", "<n>")`` for a pipe already holding ``payload`` as one JSON object."""
    read_end, write_end = os.pipe()
    try:
        os.write(write_end, json.dumps(payload).encode("utf-8"))
    finally:
        os.close(write_end)
    return "--secrets-fd", str(read_end)


__all__ = ["machine_secret_descriptor_option"]
