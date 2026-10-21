"""Enroll private KDF startup boundaries for repository benchmark observation."""

from collections.abc import Callable

from .. import _kdf_process
from .._kdf_worker_supervision import _SupervisedKdfWorker


def observe_kdf_startup(observe: Callable[[object, str, str], None]) -> None:
    """Expose timing registrations while keeping private custody imports with their owner."""
    observe(_SupervisedKdfWorker, "_start", "startup.kdf_prepare_and_launch")
    observe(_kdf_process, "worker_command", "startup.kdf_command")
    observe(_kdf_process, "_launch_worker_process", "startup.kdf_spawn")
