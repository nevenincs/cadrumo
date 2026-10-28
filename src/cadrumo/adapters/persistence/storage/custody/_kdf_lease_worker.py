"""Secret-free POSIX helper for one cancellable inherited-description flock."""

from __future__ import annotations

import os
import sys
import threading

KDF_LEASE_WAITING = b"W"
KDF_LEASE_ACQUIRED = b"L"


def main() -> int:
    """Block in the kernel until capacity or owner death; hand off no authority."""
    if sys.platform == "win32":
        return 1
    import fcntl

    names = {"--lease-fd", "--owner-fd", "--result-fd", "--descriptor-bound"}
    arguments = sys.argv[1:]
    if len(arguments) != 8:
        return 1
    options: dict[str, int] = {}
    for name, value in zip(arguments[::2], arguments[1::2], strict=True):
        if name not in names or name in options or not value.isdecimal():
            return 1
        options[name] = int(value)
    lease, owner, result = (options[name] for name in ("--lease-fd", "--owner-fd", "--result-fd"))
    bound = options["--descriptor-bound"]
    if len({lease, owner, result}) != 3 or min(lease, owner, result) < 3 or max(lease, owner, result) >= bound:
        return 1
    start = 3
    for descriptor in sorted((lease, owner, result)):
        os.closerange(start, descriptor)
        start = descriptor + 1
    os.closerange(start, bound)

    def owner_closed() -> None:
        # The retained parent is the only writer. EOF or unexpected data ends
        # this process, including its blocked flock syscall; no thread survives.
        try:
            os.read(owner, 1)
        finally:
            os._exit(1)

    threading.Thread(target=owner_closed, name="kdf-lease-owner", daemon=True).start()
    try:
        os.write(result, KDF_LEASE_WAITING)
        fcntl.flock(lease, fcntl.LOCK_EX)
        os.write(result, KDF_LEASE_ACQUIRED)
        # flock belongs to the inherited shared open description. Closing this
        # copy preserves the parent's lease; explicit LOCK_UN would release it.
        return 0
    finally:
        os.close(lease)
        os.close(result)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["KDF_LEASE_ACQUIRED", "KDF_LEASE_WAITING", "main"]
