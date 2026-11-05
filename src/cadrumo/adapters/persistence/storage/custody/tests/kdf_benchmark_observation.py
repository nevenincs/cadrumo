"""Enroll private KDF startup boundaries for repository benchmark observation."""

from collections.abc import Callable

from .. import kdf_process
from ..kdf_worker_supervision import SupervisedKdfWorker


def observe_kdf_startup(observe: Callable[[object, str, str], None]) -> None:
    """Expose timing registrations while keeping private custody imports with their owner."""
    observe(SupervisedKdfWorker, "_start", "startup.kdf_prepare_and_launch")
    observe(kdf_process, "worker_command", "startup.kdf_command")
    observe(kdf_process, "launch_worker_process", "startup.kdf_spawn")
