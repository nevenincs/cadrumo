"""Explicit per-user setup of the installed GNOME login observer resources.

Run this native setup entrypoint with an isolated interpreter. Publication
does not make GNOME Shell discover the extension, enable it, or grant
application access.
"""

from __future__ import annotations

import argparse
import sys

from ...adapters.local_runtime.linux_gnome_installation import (
    inspect_gnome_login_producer,
    install_gnome_login_producer,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError


def run(arguments: list[str] | None = None) -> int:
    """Inspect or install exact resources without starting a runtime or a dialog."""
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("action", choices=("inspect", "install"))
    selected = parser.parse_args(arguments)
    try:
        if sys.platform != "linux":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if selected.action == "inspect":
            result = "published" if inspect_gnome_login_producer() else "absent"
        else:
            result = "published" if install_gnome_login_producer() else "already_published"
        sys.stdout.write(result + "\n")
        return 0
    except RuntimeRefusalError as refusal:
        sys.stderr.write(refusal.reason.value + "\n")
        return 2
    except OSError:
        sys.stderr.write(RuntimeRefusalCode.UNAVAILABLE.value + "\n")
        return 2


if __name__ == "__main__":
    if not sys.flags.isolated:
        sys.stderr.write(RuntimeRefusalCode.UNAVAILABLE.value + "\n")
        raise SystemExit(2)
    raise SystemExit(run())
